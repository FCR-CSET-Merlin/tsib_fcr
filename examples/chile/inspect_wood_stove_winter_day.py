# -*- coding: utf-8 -*-
"""Export an hourly winter day for a representative Chilean wood-stove home.

The annual 5R1C and event-stove simulations are run first. A single winter
day is then extracted so the annual REDPE fuel target is not incorrectly
concentrated into a 24-hour simulation horizon.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
import tsib
import matplotlib.pyplot as plt

from examples.chile.analyze_wood_stove_regional_dispersion import REGION_NAMES
from examples.chile.validate_wood_stove_geonode import (
    DEFAULT_EFFICIENCY,
    DEFAULT_YEAR,
    _build_model,
    _create_engine,
    _load_env_file,
    _load_era5_weather,
)


DEFAULT_BUILDING_ID = 2577343
DEFAULT_REGION_CODE = 12
DEFAULT_SAMPLE_FILE = Path(
    "outputs/chile_wood_stove_regional_cohort_calibration/selected_buildings.csv"
)
DEFAULT_CALIBRATION_SUMMARY = Path(
    "outputs/chile_wood_stove_regional_cohort_calibration/cohort_calibration_summary.csv"
)


def _parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--building-id", type=int, default=DEFAULT_BUILDING_ID)
    parser.add_argument("--region-code", type=int, default=DEFAULT_REGION_CODE)
    parser.add_argument("--year", type=int, default=DEFAULT_YEAR)
    parser.add_argument("--efficiency", type=float, default=DEFAULT_EFFICIENCY)
    parser.add_argument("--operation-start-hour", type=int, default=8)
    parser.add_argument("--operation-end-hour", type=int, default=23)
    parser.add_argument(
        "--date",
        default=None,
        help="Local date YYYY-MM-DD; by default selects the coldest winter day.",
    )
    parser.add_argument("--sample-file", type=Path, default=DEFAULT_SAMPLE_FILE)
    parser.add_argument(
        "--calibration-summary-file",
        type=Path,
        default=DEFAULT_CALIBRATION_SUMMARY,
    )
    parser.add_argument("--env-file", type=Path, default=None)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    if not 0 < args.efficiency <= 1:
        parser.error("--efficiency debe estar en (0, 1].")
    if not 0 <= args.operation_start_hour < args.operation_end_hour <= 24:
        parser.error("El horario debe cumplir 0 <= inicio < fin <= 24.")
    return args


def _load_building(sample_file, building_id, region_code):
    buildings = pd.read_csv(sample_file)
    rows = buildings[
        (buildings["edificio_id"] == building_id)
        & (buildings["codigo_region"] == region_code)
    ]
    if rows.empty:
        raise ValueError(
            f"No se encontró edificio_id={building_id} en la región "
            f"{region_code} dentro de {sample_file}."
        )
    return rows.iloc[0].to_dict()


def _load_event_parameters(summary_file, region_code):
    summary = pd.read_csv(summary_file)
    rows = summary[summary["codigo_region"] == region_code]
    if rows.empty:
        raise ValueError(
            f"No hay parámetros calibrados para la región {region_code} en "
            f"{summary_file}."
        )
    row = rows.iloc[0]
    parameters = {
        "event_fuel_energy_kwh": float(row["best_event_fuel_energy_kwh"]),
        "event_duration_hours": float(row["best_event_duration_hours"]),
        "min_event_interval_hours": float(row["best_min_event_interval_hours"]),
        "storage_capacity_kwh": float(row["best_storage_capacity_kwh"]),
        "storage_loss_rate_per_hour": float(
            row["best_storage_loss_rate_per_hour"]
        ),
    }
    redpe = tsib.get_chile_regional_wood_consumption(region_code, "mid")
    return parameters, redpe


def _select_day(weather, requested_date):
    if requested_date is not None:
        selected = pd.Timestamp(requested_date).date()
        if selected.year != weather.index[0].year:
            raise ValueError("--date debe pertenecer al año simulado.")
        return selected
    winter = weather.index.month.isin((6, 7, 8))
    daily_mean = weather.loc[winter, "T"].resample("D").mean().dropna()
    return daily_mean.idxmin().date()


def _day_mask(index, selected_date):
    return pd.Series(index.date == selected_date, index=index)


def _simulate_scenario(
    building,
    weather,
    target_fuel,
    efficiency,
    parameters,
    setpoint,
    operation_start_hour,
    operation_end_hour,
):
    model, archetype, persons, area_m2 = _build_model(
        building,
        weather,
        winter_heating_setpoint=setpoint,
    )
    heating_load = model.detailedResults["Heating Load"]
    stove = tsib.simulate_wood_stove_events(
        heating_load,
        fuel_energy_target_kwh=target_fuel,
        efficiency=efficiency,
        availability=(
            (heating_load.index.hour >= operation_start_hour)
            & (heating_load.index.hour < operation_end_hour)
        ),
        **parameters,
    )
    return model, stove, archetype, persons, area_m2


def _daily_frame(
    model,
    stove,
    weather,
    selected_date,
    scenario,
    region_code,
    operation_start_hour,
    operation_end_hour,
):
    mask = _day_mask(model.detailedResults.index, selected_date)
    index = model.detailedResults.index[mask.to_numpy()]
    dt_hours = stove.dt_hours
    fuel_input_kw = stove.fuel_input_kw.loc[index]
    frame = pd.DataFrame(
        {
            "timestamp_local": index,
            "codigo_region": region_code,
            "region": REGION_NAMES[region_code],
            "scenario": scenario,
            "t_amb_c": weather.loc[index, "T"].to_numpy(dtype=float),
            "t_air_c": model.detailedResults.loc[index, "T_air"].to_numpy(
                dtype=float
            ),
            "t_surface_c": model.detailedResults.loc[index, "T_s"].to_numpy(
                dtype=float
            ),
            "t_mass_c": model.detailedResults.loc[index, "T_m"].to_numpy(
                dtype=float
            ),
            "heating_setpoint_c": model.detailedResults.loc[
                index, "Heating Setpoint"
            ].to_numpy(dtype=float),
            "heating_load_kw": stove.heating_load_kw.loc[index].to_numpy(
                dtype=float
            ),
            "stove_combustion_power_kw": stove.combustion_heat_kw.loc[index].to_numpy(
                dtype=float
            ),
            "stove_useful_power_kw": stove.useful_heat_kw.loc[index].to_numpy(
                dtype=float
            ),
            "stove_fuel_power_kw": fuel_input_kw.to_numpy(dtype=float),
            "wood_consumed_kg": fuel_input_kw.to_numpy(dtype=float)
            * dt_hours
            * 3.6
            / 15.0,
            "storage_kwh": stove.storage_kwh.loc[index].to_numpy(dtype=float),
            "event_start": stove.event_start.loc[index].to_numpy(dtype=bool),
            "event_fuel_input_kwh": stove.event_fuel_input_kwh.loc[index].to_numpy(
                dtype=float
            ),
            "event_state": stove.event_state.loc[index].to_numpy(),
            "stove_available": (
                (index.hour >= operation_start_hour)
                & (index.hour < operation_end_hour)
            ),
        }
    )
    return frame


def _summary_row(frame, stove, building_id, selected_date):
    return {
        "edificio_id": building_id,
        "date": selected_date.isoformat(),
        "scenario": frame["scenario"].iloc[0],
        "n_hours": len(frame),
        "t_amb_mean_c": frame["t_amb_c"].mean(),
        "t_amb_min_c": frame["t_amb_c"].min(),
        "t_air_mean_c": frame["t_air_c"].mean(),
        "t_air_min_c": frame["t_air_c"].min(),
        "t_air_max_c": frame["t_air_c"].max(),
        "heating_demand_day_kwh": frame["heating_load_kw"].sum() * stove.dt_hours,
        "stove_combustion_energy_day_kwh": frame[
            "stove_combustion_power_kw"
        ].sum()
        * stove.dt_hours,
        "stove_useful_energy_day_kwh": frame["stove_useful_power_kw"].sum()
        * stove.dt_hours,
        "wood_consumed_day_kg": frame["wood_consumed_kg"].sum(),
        "event_count_day": int(frame["event_start"].sum()),
        "annual_wood_consumed_kg": stove.wood_mass_kg,
        "annual_unmet_heating_energy_kwh": stove.unmet_heating_energy_kwh,
        "annual_unallocated_fuel_energy_kwh": stove.unallocated_fuel_energy_kwh,
    }


def _write_report(
    output_dir,
    building,
    archetype,
    selected_date,
    summary,
    parameters,
    operation_start_hour,
    operation_end_hour,
):
    lines = [
        "# Perfil diario de estufa a leña en invierno",
        "",
        f"- Inmueble: `{building['edificio_id']}`.",
        f"- Comuna: `{building['nombre_comuna']}`; región: `{REGION_NAMES[int(building['codigo_region'])]}`.",
        f"- Arquetipo: `{building['episcope_archetype']}`; zona térmica: `{archetype['thermal_zone']}`.",
        f"- Día seleccionado: `{selected_date.isoformat()}`; criterio: día invernal con menor temperatura media diaria.",
        "- El año completo se simuló antes de extraer el día para conservar el objetivo anual REDPE y el estado de almacenamiento.",
        f"- Disponibilidad para iniciar eventos: `{operation_start_hour:02d}:00–{operation_end_hour:02d}:00`.",
        "",
        "## Parámetros de la estufa",
        "",
    ]
    for key, value in parameters.items():
        lines.append(f"- `{key}`: `{value}`.")
    lines.extend(
        [
            "",
            "## Resumen diario",
            "",
            "| Escenario | T. ambiente media (°C) | T. aire min–max (°C) | Demanda (kWh) | Combustión (kWh) | Calor útil (kWh) | Leña (kg) | Eventos |",
            "|---|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for row in summary.itertuples(index=False):
        lines.append(
            f"| {row.scenario} | {row.t_amb_mean_c:.1f} | "
            f"{row.t_air_min_c:.1f}–{row.t_air_max_c:.1f} | "
            f"{row.heating_demand_day_kwh:.1f} | "
            f"{row.stove_combustion_energy_day_kwh:.1f} | "
            f"{row.stove_useful_energy_day_kwh:.1f} | "
            f"{row.wood_consumed_day_kg:.2f} | {row.event_count_day} |"
        )
    lines.extend(
        [
            "",
            "`stove_combustion_power_kw` es la potencia térmica producida por la",
            "combustión después de la eficiencia; `stove_useful_power_kw` es la",
            "potencia efectivamente entregada a la demanda 5R1C; y",
            "`wood_consumed_kg` es la masa química consumida en cada hora usando",
            "PCI = 15 MJ/kg.",
            "",
            "Los perfiles horarios completos están en",
            "`winter_day_hourly_profile.csv`.",
        ]
    )
    (output_dir / "README.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_plot(output_dir, hourly):
    scenarios = list(hourly["scenario"].drop_duplicates())
    colors = {
        "perfil_actual": "#4c78a8",
        "invierno_22C": "#f58518",
        "invierno_24C": "#e45756",
    }
    figure, axes = plt.subplots(3, 1, figsize=(13, 10), sharex=True)
    for scenario in scenarios:
        group = hourly[hourly["scenario"] == scenario]
        color = colors.get(scenario)
        axes[0].plot(
            group["timestamp_local"],
            group["t_amb_c"],
            color=color,
            linestyle="--",
            label=f"T amb — {scenario}",
        )
        axes[0].plot(
            group["timestamp_local"],
            group["t_air_c"],
            color=color,
            label=f"T air — {scenario}",
        )
        axes[1].plot(
            group["timestamp_local"],
            group["stove_combustion_power_kw"],
            color=color,
            linestyle="--",
            label=f"Combustión — {scenario}",
        )
        axes[1].plot(
            group["timestamp_local"],
            group["stove_useful_power_kw"],
            color=color,
            label=f"Útil — {scenario}",
        )
        axes[2].bar(
            group["timestamp_local"],
            group["wood_consumed_kg"],
            width=0.025,
            alpha=0.25,
            color=color,
            label=f"Leña — {scenario}",
        )
    axes[0].set_ylabel("Temperatura (°C)")
    axes[1].set_ylabel("Potencia (kW)")
    axes[2].set_ylabel("Leña (kg/h)")
    axes[2].set_xlabel("Hora local")
    axes[0].set_title("Perfil diario de estufa a leña — Natales, Magallanes")
    for axis in axes:
        axis.grid(alpha=0.25)
        axis.legend(ncol=2, fontsize=8)
    figure.tight_layout()
    figure.savefig(output_dir / "winter_day_profile.png", dpi=160)
    plt.close(figure)


def main():
    args = _parse_args()
    _load_env_file(args.env_file)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    building = _load_building(args.sample_file, args.building_id, args.region_code)
    parameters, redpe = _load_event_parameters(
        args.calibration_summary_file, args.region_code
    )
    engine = _create_engine()
    weather = _load_era5_weather(engine, int(building["tmy_commune_id"]), args.year)
    selected_date = _select_day(weather, args.date)
    target_fuel = float(redpe["energy_bruta_mwh_per_consumer"]) * 1000.0
    scenarios = [("perfil_actual", None), ("invierno_22C", 22.0), ("invierno_24C", 24.0)]
    frames = []
    summary_rows = []
    archetype = None
    for scenario, setpoint in scenarios:
        print(f"Ejecutando {scenario} para {selected_date}")
        model, stove, archetype, persons, area_m2 = _simulate_scenario(
            building,
            weather,
            target_fuel,
            args.efficiency,
            parameters,
            setpoint,
            args.operation_start_hour,
            args.operation_end_hour,
        )
        frame = _daily_frame(
            model,
            stove,
            weather,
            selected_date,
            scenario,
            args.region_code,
            args.operation_start_hour,
            args.operation_end_hour,
        )
        frame["edificio_id"] = int(building["edificio_id"])
        frame["episcope_archetype"] = building["episcope_archetype"]
        frame["model_persons"] = persons
        frame["model_area_m2"] = area_m2
        frames.append(frame)
        summary_rows.append(
            _summary_row(frame, stove, int(building["edificio_id"]), selected_date)
        )
    hourly = pd.concat(frames, ignore_index=True)
    summary = pd.DataFrame(summary_rows)
    hourly.to_csv(args.output_dir / "winter_day_hourly_profile.csv", index=False)
    summary.to_csv(args.output_dir / "winter_day_summary.csv", index=False)
    _write_report(
        args.output_dir,
        building,
        archetype,
        selected_date,
        summary,
        parameters,
        args.operation_start_hour,
        args.operation_end_hour,
    )
    _write_plot(args.output_dir, hourly)
    print(summary.to_string(index=False, float_format=lambda value: f"{value:.3f}"))
    print(f"Resultados: {args.output_dir}")


if __name__ == "__main__":
    main()
