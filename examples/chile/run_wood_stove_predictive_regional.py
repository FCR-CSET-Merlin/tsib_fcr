# -*- coding: utf-8 -*-
"""Run the target-free predictive wood-stove event model by region.

One deterministic wood-heating dwelling is selected per Chilean region from
the existing regional sample.  The direct 5R1C demand, outdoor temperature and
heating setpoint are converted to a 30-minute signal and passed to
``simulate_wood_stove_predictive_events``.  REDPE is loaded only after the
simulation to calculate a validation error; it is never used as a simulation
input.

Example::

    PYTHONPATH=. python examples/chile/run_wood_stove_predictive_regional.py \
        --env-file /home/pca/merlin/geonode_connection/.env \
        --sample-file outputs/chile_wood_stove_regional_dispersion_hdd12/selected_buildings.csv \
        --output-dir outputs/chile_wood_stove_predictive_regional
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
import tsib

from examples.chile.analyze_wood_stove_regional_dispersion import REGION_NAMES
from examples.chile.validate_wood_stove_geonode import (
    DEFAULT_EFFICIENCY,
    DEFAULT_YEAR,
    _build_model,
    _create_engine,
    _load_env_file,
    _load_era5_weather,
)


DEFAULT_SAMPLE_FILE = Path(
    "outputs/chile_wood_stove_regional_dispersion_hdd12/selected_buildings.csv"
)


def _parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--year", type=int, default=DEFAULT_YEAR)
    parser.add_argument("--efficiency", type=float, default=DEFAULT_EFFICIENCY)
    parser.add_argument("--sample-file", type=Path, default=DEFAULT_SAMPLE_FILE)
    parser.add_argument("--env-file", type=Path, default=None)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--trigger-delta-c", type=float, default=8.0)
    parser.add_argument("--start-load-threshold-kw", type=float, default=0.25)
    parser.add_argument("--log-energy-kwh", type=float, default=7.5)
    parser.add_argument("--logs-per-stere", type=float, default=219.0)
    parser.add_argument("--max-logs-per-event", type=int, default=4)
    parser.add_argument("--min-event-interval-hours", type=float, default=3.0)
    parser.add_argument("--startup-energy-fraction", type=float, default=0.20)
    parser.add_argument("--operation-start-hour", type=int, default=8)
    parser.add_argument("--operation-end-hour", type=int, default=23)
    args = parser.parse_args()
    if not 0 < args.efficiency <= 1:
        parser.error("--efficiency debe estar en (0, 1].")
    if args.trigger_delta_c < 0:
        parser.error("--trigger-delta-c debe ser no negativo.")
    if args.start_load_threshold_kw < 0:
        parser.error("--start-load-threshold-kw debe ser no negativo.")
    if args.log_energy_kwh <= 0 or args.logs_per_stere <= 0:
        parser.error("La energia del leno y los lenos por stere deben ser positivos.")
    if args.max_logs_per_event < 1:
        parser.error("--max-logs-per-event debe ser al menos uno.")
    if not 0 <= args.operation_start_hour < args.operation_end_hour <= 24:
        parser.error("El horario debe cumplir 0 <= inicio < fin <= 24.")
    return args


def _select_one_per_region(sample_file):
    buildings = pd.read_csv(sample_file)
    required = {
        "edificio_id",
        "codigo_region",
        "tmy_commune_id",
        "nombre_comuna",
        "episcope_archetype",
        "longitud",
        "latitud",
    }
    missing = required.difference(buildings.columns)
    if missing:
        raise ValueError(
            "El archivo de muestra no contiene: " + ", ".join(sorted(missing))
        )
    sort_columns = [column for column in ["codigo_region", "regional_sample_rank"] if column in buildings]
    sort_columns.append("edificio_id")
    selected = (
        buildings.sort_values(sort_columns)
        .drop_duplicates("codigo_region", keep="first")
        .sort_values("codigo_region")
        .reset_index(drop=True)
    )
    missing_regions = sorted(set(REGION_NAMES).difference(selected.codigo_region))
    if missing_regions:
        raise ValueError(f"Faltan regiones en la muestra: {missing_regions}.")
    return selected


def _resample_half_hour(series):
    values = pd.Series(series.to_numpy(dtype=float), index=series.index)
    return values.resample("30min").ffill()


def _redpe_mid(region_code):
    try:
        redpe = tsib.get_chile_regional_wood_consumption(region_code, "mid")
    except (KeyError, ValueError):
        return np.nan, np.nan
    return (
        float(redpe["consumption_m3st_per_consumer"]),
        float(redpe["energy_bruta_mwh_per_consumer"]) * 1000.0,
    )


def _simulate_building(building, weather, args):
    model, archetype, persons, area_m2 = _build_model(building, weather)
    detailed = model.detailedResults
    heating_load = _resample_half_hour(detailed["Heating Load"])
    outdoor = _resample_half_hour(weather["T"])
    setpoint = _resample_half_hour(detailed["Heating Setpoint"])
    result = tsib.simulate_wood_stove_predictive_events(
        heating_load,
        outdoor_temperature_c=outdoor,
        heating_setpoint_c=setpoint,
        efficiency=args.efficiency,
        log_energy_kwh=args.log_energy_kwh,
        logs_per_stere=args.logs_per_stere,
        max_logs_per_event=args.max_logs_per_event,
        startup_energy_fraction=args.startup_energy_fraction,
        min_event_interval_hours=args.min_event_interval_hours,
        trigger_delta_c=args.trigger_delta_c,
        start_load_threshold_kw=args.start_load_threshold_kw,
        operation_start_hour=args.operation_start_hour,
        operation_end_hour=args.operation_end_hour,
    )
    region_code = int(building["codigo_region"])
    redpe_m3, redpe_energy = _redpe_mid(region_code)
    summary = {
        "edificio_id": int(building["edificio_id"]),
        "codigo_region": region_code,
        "region": REGION_NAMES[region_code],
        "nombre_comuna": building["nombre_comuna"],
        "episcope_archetype": building["episcope_archetype"],
        "thermal_zone": archetype["thermal_zone"],
        "model_persons": persons,
        "model_area_m2": area_m2,
        "heating_demand_kwh": float(heating_load.sum() * result.dt_hours),
        "event_count": result.event_count,
        "wood_logs_burned": result.wood_logs_burned,
        "fuel_energy_consumed_kwh": result.fuel_energy_consumed_kwh,
        "wood_mass_kg": result.wood_mass_kg,
        "wood_volume_stere": result.wood_volume_stere,
        "assigned_useful_energy_kwh": result.assigned_useful_energy_kwh,
        "potential_useful_energy_kwh": result.potential_useful_energy_kwh,
        "excess_useful_energy_kwh": result.excess_useful_energy_kwh,
        "unmet_heating_energy_kwh": result.unmet_heating_energy_kwh,
        "trigger_hours": int(
            np.sum(result.temperature_trigger_gap_c >= args.trigger_delta_c)
        ),
        "redpe_mid_m3st_per_consumer": redpe_m3,
        "redpe_mid_energy_kwh": redpe_energy,
        "relative_error_to_redpe_mid": (
            np.nan
            if not np.isfinite(redpe_m3) or redpe_m3 <= 0
            else result.wood_volume_stere / redpe_m3 - 1.0
        ),
    }
    hourly = pd.DataFrame(
        {
            "edificio_id": int(building["edificio_id"]),
            "codigo_region": region_code,
            "region": REGION_NAMES[region_code],
            "timestamp_local": result.heating_load_kw.index,
            "t_ext_c": result.outdoor_temperature_c.to_numpy(),
            "heating_setpoint_c": result.heating_setpoint_c.to_numpy(),
            "temperature_trigger_gap_c": result.temperature_trigger_gap_c.to_numpy(),
            "heating_load_kw": result.heating_load_kw.to_numpy(),
            "potential_useful_heat_kw": result.potential_useful_heat_kw.to_numpy(),
            "useful_heat_kw": result.useful_heat_kw.to_numpy(),
            "excess_useful_heat_kw": (
                result.potential_useful_heat_kw - result.useful_heat_kw
            ).to_numpy(),
            "fuel_input_kw": result.fuel_input_kw.to_numpy(),
            "event_start": result.event_start.to_numpy(),
            "event_logs": result.event_logs.to_numpy(),
            "event_state": result.event_state.to_numpy(),
        }
    )
    return summary, hourly


def _write_report(output_dir, args, summary):
    lines = [
        "# Modelo predictivo de eventos de estufa a lena",
        "",
        "La corrida no recibe un objetivo anual REDPE. El consumo se genera a "
        "partir de la demanda 5R1C, el disparador de temperatura exterior y "
        "eventos discretos de lenos.",
        "",
        "## Parametros",
        "",
        f"- Año ERA5: `{args.year}`.",
        f"- Eficiencia: `{args.efficiency:.2f}`.",
        f"- Disparador: `T_setpoint - T_ext >= {args.trigger_delta_c:.1f} C`.",
        f"- Umbral de demanda para iniciar: `{args.start_load_threshold_kw:.2f} kW`.",
        f"- Energia por leno: `{args.log_energy_kwh:.1f} kWh`.",
        f"- Lenos por stere: `{args.logs_per_stere:.0f}`.",
        f"- Carga maxima: `{args.max_logs_per_event}` lenos por evento.",
        "- Evento: 30 min de arranque + 1 h de combustion.",
        f"- Fraccion de energia durante arranque: `{args.startup_energy_fraction:.2f}`.",
        f"- Inicio de eventos: `{args.operation_start_hour:02d}:00–{args.operation_end_hour:02d}:00`.",
        "- REDPE_mid se consulta sólo despues de simular, como validacion.",
        "",
        "## Resultado por inmueble y validacion",
        "",
        "| Region | Inmueble | Eventos | Lenos | Leña (m3 st/a) | REDPE_mid | Error relativo | Exceso util (kWh) | No satisfecha (kWh) |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in summary.itertuples(index=False):
        redpe = "-" if pd.isna(row.redpe_mid_m3st_per_consumer) else f"{row.redpe_mid_m3st_per_consumer:.2f}"
        error = "-" if pd.isna(row.relative_error_to_redpe_mid) else f"{row.relative_error_to_redpe_mid:.1%}"
        lines.append(
            f"| {row.region} | {row.edificio_id} | {row.event_count} | "
            f"{row.wood_logs_burned:.1f} | {row.wood_volume_stere:.3f} | "
            f"{redpe} | {error} | {row.excess_useful_energy_kwh:.1f} | "
            f"{row.unmet_heating_energy_kwh:.1f} |"
        )
    lines.extend(
        [
            "",
            "El error relativo se calcula como `consumo_predicho / REDPE_mid - 1` "
            "y no participa en la simulacion.",
            "",
        "Los resultados horarios completos estan en `predictive_hourly_profiles.csv.gz`.",
        ]
    )
    (output_dir / "README.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    args = _parse_args()
    _load_env_file(args.env_file)
    selected = _select_one_per_region(args.sample_file)
    engine = _create_engine()
    summaries = []
    hourly_frames = []
    for row in selected.to_dict("records"):
        print(
            f"region={REGION_NAMES[int(row['codigo_region'])]} "
            f"edificio_id={int(row['edificio_id'])}"
        )
        weather = _load_era5_weather(engine, row["tmy_commune_id"], args.year)
        result_summary, hourly = _simulate_building(row, weather, args)
        summaries.append(result_summary)
        hourly_frames.append(hourly)

    args.output_dir.mkdir(parents=True, exist_ok=True)
    summary = pd.DataFrame(summaries).sort_values("codigo_region")
    hourly = pd.concat(hourly_frames, ignore_index=True)
    summary.to_csv(args.output_dir / "predictive_regional_summary.csv", index=False)
    hourly.to_csv(
        args.output_dir / "predictive_hourly_profiles.csv.gz",
        index=False,
        compression="gzip",
    )
    _write_report(args.output_dir, args, summary)
    print(summary.to_string(index=False))
    print(f"saved: {args.output_dir}")


if __name__ == "__main__":
    main()
