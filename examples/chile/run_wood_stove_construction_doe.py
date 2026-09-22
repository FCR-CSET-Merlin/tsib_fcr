# -*- coding: utf-8 -*-
"""Run a construction-quality DOE against regional REDPE wood consumption.

The screening varies wall U-values, window U-value and infiltration while
keeping the climate, occupancy, wood-stove parameters, efficiency and daytime
availability fixed. A full factorial is run on one representative dwelling
per region; the best configuration is then evaluated on the complete sampled
regional cohort.
"""

from __future__ import annotations

import argparse
from itertools import product
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
DEFAULT_SETPOINTS = [22.0, 24.0]
DEFAULT_LEVELS = [1.0, 1.5, 2.0]
DEFAULT_SAMPLE_FILE = Path(
    "outputs/chile_wood_stove_regional_cohort_calibration/selected_buildings.csv"
)
DEFAULT_COHORT_RESULTS = Path(
    "outputs/chile_wood_stove_regional_cohort_calibration/cohort_results.csv"
)
DEFAULT_CALIBRATION_SUMMARY = Path(
    "outputs/chile_wood_stove_regional_cohort_calibration/cohort_calibration_summary.csv"
)


def _parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--region-code", type=int, nargs="+", default=DEFAULT_REGIONS)
    parser.add_argument("--year", type=int, default=DEFAULT_YEAR)
    parser.add_argument("--efficiency", type=float, default=DEFAULT_EFFICIENCY)
    parser.add_argument(
        "--winter-setpoints",
        type=float,
        nargs="+",
        default=DEFAULT_SETPOINTS,
    )
    parser.add_argument("--wall-levels", type=float, nargs="+", default=DEFAULT_LEVELS)
    parser.add_argument(
        "--window-levels", type=float, nargs="+", default=DEFAULT_LEVELS
    )
    parser.add_argument(
        "--infiltration-levels",
        type=float,
        nargs="+",
        default=DEFAULT_LEVELS,
    )
    parser.add_argument("--operation-start-hour", type=int, default=8)
    parser.add_argument("--operation-end-hour", type=int, default=23)
    parser.add_argument("--sample-file", type=Path, default=DEFAULT_SAMPLE_FILE)
    parser.add_argument(
        "--cohort-results-file", type=Path, default=DEFAULT_COHORT_RESULTS
    )
    parser.add_argument(
        "--calibration-summary-file",
        type=Path,
        default=DEFAULT_CALIBRATION_SUMMARY,
    )
    parser.add_argument("--env-file", type=Path, default=None)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    if not args.region_code or not args.winter_setpoints:
        parser.error("Debe indicar al menos una región y un setpoint.")
    if not 0 < args.efficiency <= 1:
        parser.error("--efficiency debe estar en (0, 1].")
    if not 0 <= args.operation_start_hour < args.operation_end_hour <= 24:
        parser.error("El horario debe cumplir 0 <= inicio < fin <= 24.")
    levels = args.wall_levels + args.window_levels + args.infiltration_levels
    if any(not np.isfinite(value) or value <= 0 for value in levels):
        parser.error("Todos los multiplicadores DOE deben ser positivos y finitos.")
    return args


def _load_event_parameters(summary_file, region_code):
    summary = pd.read_csv(summary_file)
    rows = summary[summary["codigo_region"] == region_code]
    if rows.empty:
        raise ValueError(f"No hay calibración para la región {region_code}.")
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


def _load_buildings(sample_file, regions):
    buildings = pd.read_csv(sample_file)
    buildings = buildings[buildings["codigo_region"].isin(regions)].copy()
    if buildings.empty:
        raise ValueError(f"No hay edificios para las regiones {regions}.")
    return buildings


def _select_representatives(buildings, cohort_results, regions):
    results = pd.read_csv(cohort_results)
    representatives = {}
    for region_code in regions:
        region_results = results[results["codigo_region"] == region_code].copy()
        region_buildings = buildings[buildings["codigo_region"] == region_code]
        if region_results.empty or region_buildings.empty:
            raise ValueError(f"No hay cohorte suficiente para región {region_code}.")
        median_demand = region_results["heating_demand_kwh"].median()
        selected_id = int(
            region_results.iloc[
                (region_results["heating_demand_kwh"] - median_demand)
                .abs()
                .argmin()
            ]["edificio_id"]
        )
        row = region_buildings[region_buildings["edificio_id"] == selected_id]
        if row.empty:
            raise ValueError(f"No se encontró representante {selected_id}.")
        representatives[region_code] = row.iloc[0].to_dict()
    return representatives


def _availability(index, start_hour, end_hour):
    return (index.hour >= start_hour) & (index.hour < end_hour)


def _safe_weight(value):
    value = pd.to_numeric(value, errors="coerce")
    return max(float(value) if pd.notna(value) else 1.0, 1.0)


def _weighted_mean(values, weights):
    return float(np.average(np.asarray(values, dtype=float), weights=weights))


def _simulate(
    building,
    weather,
    region_code,
    redpe,
    parameters,
    efficiency,
    setpoint,
    factors,
    operation_start_hour,
    operation_end_hour,
):
    model, archetype, persons, area_m2 = _build_model(
        building,
        weather,
        winter_heating_setpoint=setpoint,
        envelope_factors=factors,
    )
    heating_load = model.detailedResults["Heating Load"]
    target_fuel = float(redpe["energy_bruta_mwh_per_consumer"]) * 1000.0
    result = tsib.simulate_wood_stove_events(
        heating_load,
        fuel_energy_target_kwh=target_fuel,
        efficiency=efficiency,
        availability=_availability(
            heating_load.index, operation_start_hour, operation_end_hour
        ),
        **parameters,
    )
    target_volume = float(redpe["consumption_m3st_per_consumer"])
    simulated_volume = result.wood_volume_stere
    relative_error = (simulated_volume - target_volume) / target_volume
    useful_target = max(target_fuel * efficiency, 1.0)
    selection_score = abs(relative_error) + 0.10 * (
        result.unmet_heating_energy_kwh / useful_target
    )
    return {
        "codigo_region": region_code,
        "region": REGION_NAMES[region_code],
        "edificio_id": int(building["edificio_id"]),
        "nombre_comuna": building["nombre_comuna"],
        "setpoint_c": float(setpoint),
        "wall_u_multiplier": factors["wall_u_multiplier"],
        "window_u_multiplier": factors["window_u_multiplier"],
        "infiltration_multiplier": factors["infiltration_multiplier"],
        "heating_demand_kwh": float(heating_load.sum()),
        "redpe_mid_m3st_per_consumer": target_volume,
        "simulated_wood_volume_stere": simulated_volume,
        "relative_volume_error": relative_error,
        "assigned_fuel_energy_kwh": result.assigned_fuel_energy_kwh,
        "unallocated_fuel_energy_kwh": result.unallocated_fuel_energy_kwh,
        "unmet_heating_energy_kwh": result.unmet_heating_energy_kwh,
        "storage_spill_energy_kwh": result.storage_spill_energy_kwh,
        "wood_mass_kg": result.wood_mass_kg,
        "event_count": result.event_count,
        "selection_score": selection_score,
        "u_wall_1": float(model.cfg.get("U_Wall_1", np.nan)),
        "u_window": float(model.cfg.get("U_Window", np.nan)),
        "n_air_infiltration": float(
            model.cfg.get("n_air_infiltration", np.nan)
        ),
        "thermal_zone": archetype["thermal_zone"],
        "model_persons": persons,
        "model_area_m2": area_m2,
    }


def _run_doe(args, buildings, representatives, weather_cache):
    rows = []
    combinations = list(
        product(
            args.wall_levels,
            args.window_levels,
            args.infiltration_levels,
        )
    )
    total = len(args.region_code) * len(args.winter_setpoints) * len(combinations)
    completed = 0
    for region_code in args.region_code:
        parameters, redpe = _load_event_parameters(
            args.calibration_summary_file, region_code
        )
        for setpoint in args.winter_setpoints:
            for wall, window, infiltration in combinations:
                factors = {
                    "wall_u_multiplier": wall,
                    "window_u_multiplier": window,
                    "infiltration_multiplier": infiltration,
                }
                rows.append(
                    _simulate(
                        representatives[region_code],
                        weather_cache[
                            int(representatives[region_code]["tmy_commune_id"])
                        ],
                        region_code,
                        redpe,
                        parameters,
                        args.efficiency,
                        setpoint,
                        factors,
                        args.operation_start_hour,
                        args.operation_end_hour,
                    )
                )
                completed += 1
                if completed == 1 or completed % 20 == 0 or completed == total:
                    print(f"DOE {completed}/{total}")
    return pd.DataFrame(rows)


def _select_configurations(trials):
    selected = (
        trials.sort_values(
            ["codigo_region", "setpoint_c", "selection_score", "unmet_heating_energy_kwh"],
            kind="stable",
        )
        .groupby(["codigo_region", "setpoint_c"], as_index=False)
        .head(1)
        .reset_index(drop=True)
    )
    return selected


def _validate_cohort(
    args, buildings, selected, weather_cache
):
    rows = []
    for selected_row in selected.to_dict("records"):
        region_code = int(selected_row["codigo_region"])
        setpoint = float(selected_row["setpoint_c"])
        region_buildings = buildings[buildings["codigo_region"] == region_code]
        parameters, redpe = _load_event_parameters(
            args.calibration_summary_file, region_code
        )
        factors = {
            "wall_u_multiplier": float(selected_row["wall_u_multiplier"]),
            "window_u_multiplier": float(selected_row["window_u_multiplier"]),
            "infiltration_multiplier": float(
                selected_row["infiltration_multiplier"]
            ),
        }
        target_fuel = float(redpe["energy_bruta_mwh_per_consumer"]) * 1000.0
        target_volume = float(redpe["consumption_m3st_per_consumer"])
        for building in region_buildings.to_dict("records"):
            weather = weather_cache[int(building["tmy_commune_id"])]
            model, _, _, _ = _build_model(
                building,
                weather,
                winter_heating_setpoint=setpoint,
                envelope_factors=factors,
            )
            heating_load = model.detailedResults["Heating Load"]
            result = tsib.simulate_wood_stove_events(
                heating_load,
                fuel_energy_target_kwh=target_fuel,
                efficiency=args.efficiency,
                availability=_availability(
                    heating_load.index,
                    args.operation_start_hour,
                    args.operation_end_hour,
                ),
                **parameters,
            )
            rows.append(
                {
                    "edificio_id": int(building["edificio_id"]),
                    "codigo_region": region_code,
                    "region": REGION_NAMES[region_code],
                    "nombre_comuna": building["nombre_comuna"],
                    "setpoint_c": setpoint,
                    "n_inmuebles": _safe_weight(building["n_inmuebles"]),
                    "heating_demand_kwh": float(heating_load.sum()),
                    "target_wood_volume_stere": target_volume,
                    "simulated_wood_volume_stere": result.wood_volume_stere,
                    "relative_volume_error": (
                        result.wood_volume_stere - target_volume
                    )
                    / target_volume,
                    "assigned_fuel_energy_kwh": result.assigned_fuel_energy_kwh,
                    "unallocated_fuel_energy_kwh": result.unallocated_fuel_energy_kwh,
                    "unmet_heating_energy_kwh": result.unmet_heating_energy_kwh,
                    "wood_mass_kg": result.wood_mass_kg,
                    **factors,
                }
            )
        print(f"Validación región={region_code} setpoint={setpoint:.0f} °C")
    return pd.DataFrame(rows)


def _summarize_validation(results):
    rows = []
    for (region_code, setpoint), group in results.groupby(
        ["codigo_region", "setpoint_c"], sort=True
    ):
        weights = group["n_inmuebles"].to_numpy(float)
        target_volume = float(group["target_wood_volume_stere"].iloc[0])
        simulated_volume = _weighted_mean(
            group["simulated_wood_volume_stere"], weights
        )
        first = group.iloc[0]
        rows.append(
            {
                "codigo_region": int(region_code),
                "region": first["region"],
                "setpoint_c": float(setpoint),
                "n_simulations": len(group),
                "n_inmuebles": int(group["n_inmuebles"].sum()),
                "heating_demand_kwh_weighted_mean": _weighted_mean(
                    group["heating_demand_kwh"], weights
                ),
                "target_wood_volume_stere": target_volume,
                "simulated_wood_volume_stere_weighted_mean": simulated_volume,
                "relative_volume_error": (simulated_volume - target_volume)
                / target_volume,
                "unallocated_fuel_energy_kwh_weighted_mean": _weighted_mean(
                    group["unallocated_fuel_energy_kwh"], weights
                ),
                "unmet_heating_energy_kwh_weighted_mean": _weighted_mean(
                    group["unmet_heating_energy_kwh"], weights
                ),
                "wall_u_multiplier": first["wall_u_multiplier"],
                "window_u_multiplier": first["window_u_multiplier"],
                "infiltration_multiplier": first["infiltration_multiplier"],
            }
        )
    return pd.DataFrame(rows)


def _write_report(output_dir, args, representatives, selected, validation_summary):
    lines = [
        "# DOE de calidad constructiva y consumo residencial de leña",
        "",
        "El DOE varía multiplicadores relativos de U de muros, U de ventanas y",
        "renovaciones por infiltración. Los niveles `1,0`, `1,5` y `2,0` son",
        "escenarios exploratorios de deterioro constructivo; no son mediciones",
        "de cada vivienda.",
        "",
        f"- Regiones: `{', '.join(REGION_NAMES[r] for r in args.region_code)}`.",
        f"- Setpoints: `{', '.join(f'{value:g} °C' for value in args.winter_setpoints)}`.",
        f"- Disponibilidad: `{args.operation_start_hour:02d}:00–{args.operation_end_hour:02d}:00`.",
        f"- Eficiencia de estufa: `{args.efficiency:.2f}`.",
        "- Selección: error relativo de volumen REDPE y penalización secundaria por demanda no satisfecha.",
        "",
        "## Inmuebles representativos",
        "",
        "| Región | Edificio | Comuna | Demanda anual de referencia (kWh) |",
        "|---|---:|---|---:|",
    ]
    cohort_results = pd.read_csv(args.cohort_results_file)
    for region_code in args.region_code:
        building = representatives[region_code]
        demand = cohort_results[
            cohort_results["edificio_id"] == int(building["edificio_id"])
        ]["heating_demand_kwh"].iloc[0]
        lines.append(
            f"| {REGION_NAMES[region_code]} | {building['edificio_id']} | "
            f"{building['nombre_comuna']} | {demand:.1f} |"
        )
    lines.extend(
        [
            "",
            "## Configuración seleccionada en el DOE",
            "",
            "| Región | Setpoint | U muros | U ventanas | Infiltración | Error representante | Score |",
            "|---|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for row in selected.itertuples(index=False):
        lines.append(
            f"| {row.region} | {row.setpoint_c:.0f} °C | "
            f"{row.wall_u_multiplier:.1f}× | {row.window_u_multiplier:.1f}× | "
            f"{row.infiltration_multiplier:.1f}× | "
            f"{row.relative_volume_error:.1%} | {row.selection_score:.4f} |"
        )
    lines.extend(
        [
            "",
            "## Validación en la cohorte",
            "",
            "| Región | Setpoint | Demanda media ponderada (kWh) | REDPE (m³ st) | Simulado (m³ st) | Error | No asignado (kWh) | No satisfecha (kWh) |",
            "|---|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for row in validation_summary.itertuples(index=False):
        lines.append(
            f"| {row.region} | {row.setpoint_c:.0f} °C | "
            f"{row.heating_demand_kwh_weighted_mean:.1f} | "
            f"{row.target_wood_volume_stere:.3f} | "
            f"{row.simulated_wood_volume_stere_weighted_mean:.2f} | "
            f"{row.relative_volume_error:.1%} | "
            f"{row.unallocated_fuel_energy_kwh_weighted_mean:.1f} | "
            f"{row.unmet_heating_energy_kwh_weighted_mean:.1f} |"
        )
    lines.extend(
        [
            "",
            "La configuración seleccionada es una solución de screening numérico.",
            "No debe interpretarse como diagnóstico físico individual sin datos de",
            "temperatura interior, infiltración o consumo medido.",
            "",
            "Archivos: `doe_trials.csv`, `doe_selected_configurations.csv`,",
            "`doe_validation_results.csv` y `doe_validation_summary.csv`.",
        ]
    )
    (output_dir / "README.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    args = _parse_args()
    _load_env_file(args.env_file)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    buildings = _load_buildings(args.sample_file, args.region_code)
    representatives = _select_representatives(
        buildings, args.cohort_results_file, args.region_code
    )
    engine = _create_engine()
    weather_cache = {}
    needed_buildings = pd.concat(
        [
            buildings,
            pd.DataFrame(representatives.values()),
        ],
        ignore_index=True,
    ).drop_duplicates("edificio_id")
    for commune_id in needed_buildings["tmy_commune_id"].astype(int).unique():
        weather_cache[commune_id] = _load_era5_weather(engine, commune_id, args.year)

    trials = _run_doe(args, buildings, representatives, weather_cache)
    selected = _select_configurations(trials)
    validation = _validate_cohort(args, buildings, selected, weather_cache)
    validation_summary = _summarize_validation(validation)
    trials.to_csv(args.output_dir / "doe_trials.csv", index=False)
    selected.to_csv(args.output_dir / "doe_selected_configurations.csv", index=False)
    validation.to_csv(args.output_dir / "doe_validation_results.csv", index=False)
    validation_summary.to_csv(
        args.output_dir / "doe_validation_summary.csv", index=False
    )
    _write_report(
        args.output_dir,
        args,
        representatives,
        selected,
        validation_summary,
    )
    print("\nConfiguraciones seleccionadas:")
    print(selected.to_string(index=False, float_format=lambda value: f"{value:.3f}"))
    print("\nValidación:")
    print(
        validation_summary.to_string(
            index=False, float_format=lambda value: f"{value:.3f}"
        )
    )
    print(f"Resultados: {args.output_dir}")


if __name__ == "__main__":
    main()
