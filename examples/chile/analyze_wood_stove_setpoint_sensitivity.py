# -*- coding: utf-8 -*-
"""Evaluate winter heating-setpoint sensitivity for Chilean cohorts.

The default cases target Magallanes, Los Ríos, Los Lagos and Araucanía. The
script keeps the existing Chilean monthly profile outside June-August and
replaces the winter heating setpoint with each requested constant value. The
calibrated regional event parameters are held fixed so the result isolates the
effect of the 5R1C heating setpoint.
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


DEFAULT_REGIONS = [12, 14, 10, 9]
DEFAULT_SAMPLE_FILE = Path(
    "outputs/chile_wood_stove_regional_cohort_calibration/selected_buildings.csv"
)
DEFAULT_CALIBRATION_SUMMARY = Path(
    "outputs/chile_wood_stove_regional_cohort_calibration/cohort_calibration_summary.csv"
)


def _parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--region-code",
        type=int,
        nargs="+",
        default=DEFAULT_REGIONS,
        help="Regiones a evaluar (default: 12 14 10 9).",
    )
    parser.add_argument("--year", type=int, default=DEFAULT_YEAR)
    parser.add_argument("--efficiency", type=float, default=DEFAULT_EFFICIENCY)
    parser.add_argument(
        "--winter-setpoints",
        type=float,
        nargs="+",
        default=[22.0, 24.0],
        help="Constant June-August heating setpoints to evaluate [degC].",
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
    if not args.winter_setpoints:
        parser.error("--winter-setpoints debe contener al menos un valor.")
    if not 0 < args.efficiency <= 1:
        parser.error("--efficiency debe estar en (0, 1].")
    if not args.region_code:
        parser.error("--region-code debe contener al menos una región.")
    return args


def _load_buildings(sample_file, region_code):
    buildings = pd.read_csv(sample_file)
    buildings = buildings[buildings["codigo_region"] == region_code].copy()
    if buildings.empty:
        raise ValueError(
            f"No hay inmuebles de la región {region_code} en {sample_file}."
        )
    buildings = buildings.sort_values("regional_sample_rank")
    return buildings


def _safe_weight(building):
    value = pd.to_numeric(building.get("n_inmuebles", 1), errors="coerce")
    return max(float(value) if pd.notna(value) else 1.0, 1.0)


def _weighted_mean(values, weights):
    values = np.asarray(values, dtype=float)
    weights = np.asarray(weights, dtype=float)
    return float(np.average(values, weights=weights))


def _scenario_label(winter_setpoint):
    if winter_setpoint is None:
        return "perfil_actual"
    return f"invierno_{winter_setpoint:g}C"


def _run_scenario(
    buildings,
    weather_cache,
    year,
    efficiency,
    winter_setpoint,
    target_fuel,
    target_volume,
    event_parameters,
):
    rows = []
    for building in buildings.to_dict("records"):
        commune_id = int(building["tmy_commune_id"])
        if commune_id not in weather_cache:
            weather_cache[commune_id] = None
        weather = weather_cache[commune_id]
        model, archetype, persons, area_m2 = _build_model(
            building, weather, winter_heating_setpoint=winter_setpoint
        )
        heating_load = model.detailedResults["Heating Load"]
        result = tsib.simulate_wood_stove_events(
            heating_load,
            fuel_energy_target_kwh=target_fuel,
            efficiency=efficiency,
            **event_parameters,
        )
        rows.append(
            {
                "edificio_id": int(building["edificio_id"]),
                "codigo_region": int(building["codigo_region"]),
                "region": REGION_NAMES[int(building["codigo_region"])],
                "codigo_comuna": int(building["codigo_comuna"]),
                "nombre_comuna": building["nombre_comuna"],
                "regional_sample_rank": int(building["regional_sample_rank"]),
                "n_inmuebles": int(_safe_weight(building)),
                "winter_setpoint_c": (
                    np.nan if winter_setpoint is None else float(winter_setpoint)
                ),
                "setpoint_scenario": _scenario_label(winter_setpoint),
                "thermal_zone": archetype["thermal_zone"],
                "model_persons": persons,
                "model_area_m2": area_m2,
                "heating_demand_kwh": float(heating_load.sum()),
                "target_fuel_energy_kwh": target_fuel,
                "redpe_target_wood_volume_stere": target_volume,
                "assigned_fuel_energy_kwh": result.assigned_fuel_energy_kwh,
                "assigned_useful_energy_kwh": result.assigned_useful_energy_kwh,
                "wood_volume_stere": result.wood_volume_stere,
                "unallocated_fuel_energy_kwh": result.unallocated_fuel_energy_kwh,
                "unmet_heating_energy_kwh": result.unmet_heating_energy_kwh,
                "storage_spill_energy_kwh": result.storage_spill_energy_kwh,
                "event_count": result.event_count,
                **event_parameters,
            }
        )
    return pd.DataFrame(rows)


def _load_event_parameters(summary_file, region_code):
    summary = pd.read_csv(summary_file)
    row = summary.loc[summary["codigo_region"] == region_code]
    if row.empty:
        raise ValueError(
            f"No hay parámetros calibrados para la región {region_code} en "
            f"{summary_file}."
        )
    row = row.iloc[0]
    return {
        "event_fuel_energy_kwh": float(row["best_event_fuel_energy_kwh"]),
        "event_duration_hours": float(row["best_event_duration_hours"]),
        "min_event_interval_hours": float(row["best_min_event_interval_hours"]),
        "storage_capacity_kwh": float(row["best_storage_capacity_kwh"]),
        "storage_loss_rate_per_hour": float(
            row["best_storage_loss_rate_per_hour"]
        ),
    }


def _summarize(results):
    rows = []
    for (region_code, scenario), group in results.groupby(
        ["codigo_region", "setpoint_scenario"], sort=False
    ):
        weights = group["n_inmuebles"].to_numpy(dtype=float)
        target_volume = float(group["redpe_target_wood_volume_stere"].iloc[0])
        simulated_volume = _weighted_mean(group["wood_volume_stere"], weights)
        rows.append(
            {
                "setpoint_scenario": scenario,
                "codigo_region": int(region_code),
                "region": group["region"].iloc[0],
                "winter_setpoint_c": group["winter_setpoint_c"].iloc[0],
                "n_simulations": len(group),
                "n_inmuebles": int(group["n_inmuebles"].sum()),
                "heating_demand_kwh_weighted_mean": _weighted_mean(
                    group["heating_demand_kwh"], weights
                ),
                "redpe_mid_m3st_per_consumer": target_volume,
                "simulated_wood_volume_stere_weighted_mean": simulated_volume,
                "relative_volume_error": (simulated_volume - target_volume) / target_volume,
                "assigned_fuel_energy_kwh_weighted_mean": _weighted_mean(
                    group["assigned_fuel_energy_kwh"], weights
                ),
                "unallocated_fuel_energy_kwh_weighted_mean": _weighted_mean(
                    group["unallocated_fuel_energy_kwh"], weights
                ),
                "unmet_heating_energy_kwh_weighted_mean": _weighted_mean(
                    group["unmet_heating_energy_kwh"], weights
                ),
                "event_count_weighted_mean": _weighted_mean(
                    group["event_count"], weights
                ),
            }
        )
    return pd.DataFrame(rows)


def _write_report(output_dir, args, summary):
    lines = [
        "# Sensibilidad del setpoint de invierno en regiones del sur",
        "",
        "La sensibilidad reutiliza la cohorte regional de calibración y mantiene",
        "fijos los parámetros de eventos seleccionados por región. Sólo se",
        "reemplaza el setpoint de calefacción de junio, julio y agosto; el resto",
        "del año conserva el perfil mensual chileno por zona térmica. Durante",
        "la sensibilidad, el setpoint de enfriamiento invernal se mantiene 2 °C",
        "por encima del setpoint de calefacción.",
        "",
        "- Regiones: "
        + ", ".join(
            f"`{REGION_NAMES[region_code]}` ({region_code})"
            for region_code in args.region_code
        )
        + ".",
        f"- Año ERA5: `{args.year}`.",
        f"- Eficiencia: `{args.efficiency:.2f}`.",
        "",
        "| Región | Escenario | Setpoint invierno | Demanda 5R1C (kWh) | REDPE (m³ st) | Leña simulada (m³ st) | Error REDPE | No asignado (kWh) | No satisfecha (kWh) |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in summary.itertuples(index=False):
        lines.append(
            f"| {row.region} | {row.setpoint_scenario} | "
            f"{('-' if pd.isna(row.winter_setpoint_c) else f'{row.winter_setpoint_c:.1f} °C')} | "
            f"{row.heating_demand_kwh_weighted_mean:.1f} | "
            f"{row.redpe_mid_m3st_per_consumer:.3f} | "
            f"{row.simulated_wood_volume_stere_weighted_mean:.2f} | "
            f"{row.relative_volume_error:.1%} | "
            f"{row.unallocated_fuel_energy_kwh_weighted_mean:.1f} | "
            f"{row.unmet_heating_energy_kwh_weighted_mean:.1f} |"
        )
    lines.extend(
        [
            "",
            "El perfil actual corresponde a la zona térmica de cada arquetipo;",
            "la muestra usa las zonas térmicas propias de cada región. Este ejercicio modifica",
            "sólo el setpoint de invierno y no constituye calibración física.",
            "",
            "Archivos: `setpoint_sensitivity_results.csv` y",
            "`setpoint_sensitivity_summary.csv`.",
        ]
    )
    (output_dir / "README.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    args = _parse_args()
    _load_env_file(args.env_file)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    buildings = pd.read_csv(args.sample_file)
    buildings = buildings[buildings["codigo_region"].isin(args.region_code)].copy()
    if buildings.empty:
        raise ValueError(
            f"No hay inmuebles de las regiones {args.region_code} en {args.sample_file}."
        )
    engine = _create_engine()
    weather_cache = {}
    for commune_id in buildings["tmy_commune_id"].astype(int).unique():
        weather_cache[commune_id] = _load_era5_weather(engine, commune_id, args.year)

    scenarios = [None, *args.winter_setpoints]
    result_frames = []
    for region_code in args.region_code:
        region_buildings = buildings[buildings["codigo_region"] == region_code]
        if region_buildings.empty:
            raise ValueError(
                f"No hay inmuebles de la región {region_code} en {args.sample_file}."
            )
        redpe = tsib.get_chile_regional_wood_consumption(region_code, "mid")
        target_fuel = float(redpe["energy_bruta_mwh_per_consumer"]) * 1000.0
        target_volume = float(redpe["consumption_m3st_per_consumer"])
        event_parameters = _load_event_parameters(
            args.calibration_summary_file, region_code
        )
        for winter_setpoint in scenarios:
            print(
                f"Región {region_code} ({REGION_NAMES[region_code]}): "
                f"escenario {_scenario_label(winter_setpoint)}"
            )
            result_frames.append(
                _run_scenario(
                    region_buildings,
                    weather_cache,
                    args.year,
                    args.efficiency,
                    winter_setpoint,
                    target_fuel,
                    target_volume,
                    event_parameters,
                )
            )
    results = pd.concat(result_frames, ignore_index=True)
    summary = _summarize(results)
    results.to_csv(args.output_dir / "setpoint_sensitivity_results.csv", index=False)
    summary.to_csv(args.output_dir / "setpoint_sensitivity_summary.csv", index=False)
    _write_report(args.output_dir, args, summary)
    print(summary.to_string(index=False, float_format=lambda value: f"{value:.3f}"))


if __name__ == "__main__":
    main()
