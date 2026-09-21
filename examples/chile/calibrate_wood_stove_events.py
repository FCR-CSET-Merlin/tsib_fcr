# -*- coding: utf-8 -*-
"""Numerically calibrate event/storage parameters without physical data.

The reference is the existing annual MVP for the same 5R1C heating-load
series and fuel target.  This is a consistency calibration, not an empirical
calibration of occupant behaviour or stove physics.
"""

from __future__ import annotations

import argparse
import itertools
from pathlib import Path

import numpy as np
import pandas as pd
import tsib

from examples.chile.analyze_wood_stove_regional_dispersion import (
    REGION_NAMES,
    _load_sampled_buildings,
)
from examples.chile.validate_wood_stove_geonode import (
    DEFAULT_EFFICIENCY,
    DEFAULT_YEAR,
    _build_model,
    _create_engine,
    _load_env_file,
    _load_era5_weather,
)


def _parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--year", type=int, default=DEFAULT_YEAR)
    sampling_group = parser.add_mutually_exclusive_group()
    sampling_group.add_argument(
        "--total-samples",
        type=int,
        default=None,
        help="Total de registros con cuota proporcional a unidades a lena.",
    )
    sampling_group.add_argument(
        "--samples-per-region",
        type=int,
        default=None,
        help="Cantidad fija de registros por region (default: 1).",
    )
    parser.add_argument("--seed", type=int, default=2024)
    parser.add_argument("--efficiency", type=float, default=DEFAULT_EFFICIENCY)
    parser.add_argument(
        "--calibration-target",
        choices=("mvp", "redpe_mid"),
        default="mvp",
        help="Objetivo anual usado para seleccionar parametros (default: mvp).",
    )
    parser.add_argument("--env-file", type=Path, default=None)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    if args.total_samples is None and args.samples_per_region is None:
        args.samples_per_region = 1
    sample_count = (
        args.total_samples
        if args.total_samples is not None
        else args.samples_per_region
    )
    if sample_count <= 0:
        parser.error("el numero de muestras debe ser mayor que cero.")
    if args.total_samples is not None and args.total_samples < 160:
        parser.error("--total-samples debe permitir al menos 10 registros por region.")
    if args.samples_per_region is not None and args.samples_per_region <= 0:
        parser.error("--samples-per-region debe ser mayor que cero.")
    if not 0 < args.efficiency <= 1:
        parser.error("--efficiency debe estar en (0, 1].")
    return args


def _candidate_parameters():
    """Return a compact grid covering event and store time scales."""
    candidates = []
    for event_fuel, duration, interval, capacity, loss_rate in itertools.product(
        (8.0, 16.0, 32.0),
        (1.0, 2.0),
        (1.0, 2.0, 4.0),
        (8.0, 16.0, 32.0, 64.0),
        (0.0, 0.01),
    ):
        candidates.append(
            {
                "event_fuel_energy_kwh": event_fuel,
                "event_duration_hours": duration,
                "min_event_interval_hours": interval,
                "storage_capacity_kwh": capacity,
                "storage_loss_rate_per_hour": loss_rate,
            }
        )
    return candidates


def _calibration_rows(
    building, weather, year, efficiency, candidates, calibration_target
):
    model, archetype, persons, area_m2 = _build_model(building, weather)
    demand_kwh = float(model.detailedResults["Heating Load"].sum())

    redpe_mid = np.nan
    redpe_target_fuel = np.nan
    redpe_dynamic = None
    try:
        redpe = tsib.get_chile_regional_wood_consumption(
            int(building["codigo_region"]), "mid"
        )
        redpe_mid = redpe["consumption_m3st_per_consumer"]
        redpe_target_fuel = redpe["energy_bruta_mwh_per_consumer"] * 1000.0
    except ValueError:
        pass

    mvp_target_fuel = demand_kwh * 0.75 / efficiency
    if calibration_target == "redpe_mid" and np.isfinite(redpe_target_fuel):
        target_fuel = redpe_target_fuel
        target_source = "REDPE_mid"
    else:
        target_fuel = mvp_target_fuel
        target_source = "MVP_coverage_mid"
    calibration = tsib.calibrate_wood_stove_event_parameters(
        model.detailedResults["Heating Load"],
        fuel_energy_target_kwh=target_fuel,
        candidate_parameters=candidates,
        efficiency=efficiency,
    )
    trials = calibration.trials.copy()
    trials.insert(0, "edificio_id", int(building["edificio_id"]))
    trials.insert(1, "codigo_region", int(building["codigo_region"]))
    trials.insert(
        2,
        "region",
        REGION_NAMES.get(int(building["codigo_region"]), "unknown"),
    )
    trials.insert(3, "heating_demand_kwh", demand_kwh)
    trials.insert(4, "calibration_target_source", target_source)
    trials.insert(5, "calibration_target_fuel_energy_kwh", target_fuel)
    trials.insert(6, "mvp_target_fuel_energy_kwh", mvp_target_fuel)
    trials.insert(7, "mvp_assigned_useful_energy_kwh", calibration.reference_result.assigned_useful_energy_kwh)
    trials.insert(8, "mvp_unmet_heating_energy_kwh", calibration.reference_result.unmet_heating_energy_kwh)
    trials["is_best"] = trials["trial"] == int(
        trials.loc[trials["score"].idxmin(), "trial"]
    )
    best_trial = trials.loc[trials["is_best"]].iloc[0]

    if np.isfinite(redpe_target_fuel):
        redpe_dynamic = tsib.simulate_wood_stove_events(
            model.detailedResults["Heating Load"],
            fuel_energy_target_kwh=redpe_target_fuel,
            efficiency=efficiency,
            **calibration.best_parameters,
        )

    best = calibration.best_result
    summary = {
        "edificio_id": int(building["edificio_id"]),
        "codigo_region": int(building["codigo_region"]),
        "region": REGION_NAMES.get(int(building["codigo_region"]), "unknown"),
        "codigo_comuna": int(building["codigo_comuna"]),
        "nombre_comuna": building["nombre_comuna"],
        "tmy_commune_id": int(building["tmy_commune_id"]),
        "episcope_archetype": building["episcope_archetype"],
        "building_year": archetype["building_year"],
        "building_type": archetype["building_type"],
        "material": archetype["material"],
        "thermal_zone": archetype["thermal_zone"],
        "model_persons": persons,
        "model_area_m2": area_m2,
        "heating_demand_kwh": demand_kwh,
        "calibration_target_source": target_source,
        "calibration_target_fuel_energy_kwh": target_fuel,
        "mvp_target_fuel_energy_kwh": mvp_target_fuel,
        "calibration_target_wood_volume_stere": calibration.reference_result.wood_volume_stere,
        "mvp_wood_volume_stere": (
            calibration.reference_result.wood_volume_stere
            if target_source == "MVP_coverage_mid"
            else np.nan
        ),
        "redpe_mid_m3st_per_consumer": redpe_mid,
        "redpe_mid_target_fuel_energy_kwh": redpe_target_fuel,
        "candidate_count": len(candidates),
        "valid_candidate_count": int(trials["valid"].sum()),
        "best_score": float(trials.loc[trials["is_best"], "score"].iloc[0]),
        "best_profile_error_kwh": float(best_trial["profile_error_kwh"]),
        "best_event_fuel_energy_kwh": calibration.best_parameters["event_fuel_energy_kwh"],
        "best_event_duration_hours": calibration.best_parameters["event_duration_hours"],
        "best_min_event_interval_hours": calibration.best_parameters["min_event_interval_hours"],
        "best_storage_capacity_kwh": calibration.best_parameters["storage_capacity_kwh"],
        "best_storage_loss_rate_per_hour": calibration.best_parameters["storage_loss_rate_per_hour"],
        "dynamic_assigned_fuel_energy_kwh": best.assigned_fuel_energy_kwh,
        "dynamic_assigned_useful_energy_kwh": best.assigned_useful_energy_kwh,
        "dynamic_unmet_heating_energy_kwh": best.unmet_heating_energy_kwh,
        "dynamic_unallocated_fuel_energy_kwh": best.unallocated_fuel_energy_kwh,
        "dynamic_storage_spill_energy_kwh": best.storage_spill_energy_kwh,
        "dynamic_stored_energy_end_kwh": best.stored_energy_end_kwh,
        "dynamic_event_count": best.event_count,
        "dynamic_wood_volume_stere": best.wood_volume_stere,
        "redpe_dynamic_assigned_fuel_energy_kwh": (
            redpe_dynamic.assigned_fuel_energy_kwh
            if redpe_dynamic is not None
            else np.nan
        ),
        "redpe_dynamic_assigned_useful_energy_kwh": (
            redpe_dynamic.assigned_useful_energy_kwh
            if redpe_dynamic is not None
            else np.nan
        ),
        "redpe_dynamic_unmet_heating_energy_kwh": (
            redpe_dynamic.unmet_heating_energy_kwh
            if redpe_dynamic is not None
            else np.nan
        ),
        "redpe_dynamic_unallocated_fuel_energy_kwh": (
            redpe_dynamic.unallocated_fuel_energy_kwh
            if redpe_dynamic is not None
            else np.nan
        ),
        "redpe_dynamic_wood_volume_stere": (
            redpe_dynamic.wood_volume_stere
            if redpe_dynamic is not None
            else np.nan
        ),
    }
    return trials, summary


def _write_report(output_dir, args, summaries, trial_count):
    summary = pd.DataFrame(summaries).sort_values("codigo_region")
    best_score = summary["best_score"]
    lines = [
        "# Calibración numérica de eventos y almacenamiento",
        "",
        "Esta corrida no usa observaciones físicas. Selecciona parámetros que",
        "reproducen, lo mejor posible, el balance anual del MVP para la misma",
        "demanda 5R1C y el mismo objetivo de combustible.",
        "",
        "## Configuración",
        "",
        f"- Año ERA5: `{args.year}`.",
        f"- Registros: `{'total=' + str(args.total_samples) if args.total_samples is not None else 'por región=' + str(args.samples_per_region)}`.",
        f"- Semilla de selección: `{args.seed}`.",
        f"- Candidatos por registro: `{trial_count}`.",
        f"- Eficiencia: `{args.efficiency:.2f}`.",
        f"- Objetivo de calibración: `{args.calibration_target}`; las regiones sin fila REDPE_mid usan MVP coverage_mid.",
        "",
        "## Resultado por registro",
        "",
        "| Región | Demanda (kWh/a) | Score | Error perfil (kWh) | Eventos | Objetivo (m³ st) | Dinámico (m³ st) | Derrame (kWh) |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in summary.itertuples(index=False):
        lines.append(
            f"| {row.region} | {row.heating_demand_kwh:.1f} | {row.best_score:.4f} | "
            f"{row.best_profile_error_kwh:.2f} | "
            f"{row.dynamic_event_count} | {row.calibration_target_wood_volume_stere:.2f} | "
            f"{row.dynamic_wood_volume_stere:.2f} | "
            f"{row.dynamic_storage_spill_energy_kwh:.2f} |"
        )
    redpe_summary = summary.dropna(subset=["redpe_mid_m3st_per_consumer"])
    if not redpe_summary.empty:
        lines.extend(
            [
                "",
                "## Transferencia a REDPE_mid",
                "",
                (
                    "Los parámetros se calibraron contra REDPE_mid y se comparan "
                    "con la transferencia REDPE."
                    if args.calibration_target == "redpe_mid"
                    else "Los parámetros se calibraron contra el MVP y luego se aplicaron al objetivo REDPE."
                ),
                "",
                "| Región | REDPE (m³ st/a) | Dinámico (m³ st/a) | No satisfecho (kWh) | No asignado (kWh) |",
                "|---|---:|---:|---:|---:|",
            ]
        )
        for row in redpe_summary.itertuples(index=False):
            lines.append(
                f"| {row.region} | {row.redpe_mid_m3st_per_consumer:.2f} | "
                f"{row.redpe_dynamic_wood_volume_stere:.2f} | "
                f"{row.redpe_dynamic_unmet_heating_energy_kwh:.1f} | "
                f"{row.redpe_dynamic_unallocated_fuel_energy_kwh:.1f} |"
            )
    lines.extend(
        [
            "",
            f"Score mediano: `{best_score.median():.4f}`.",
            "El score es una métrica de consistencia numérica, no un error físico observado.",
            "",
            "## Archivos",
            "",
        "- `calibration_summary.csv`: mejor candidato por registro y transferencia a REDPE_mid.",
            "- `calibration_trials.csv`: todos los candidatos y sus métricas.",
            "- `README.md`: esta descripción de la corrida.",
        ]
    )
    (output_dir / "README.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    args = _parse_args()
    _load_env_file(args.env_file)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    engine = _create_engine()
    if args.total_samples is not None:
        buildings = _load_sampled_buildings(
            engine,
            args.total_samples,
            args.seed,
        )
    else:
        buildings = _load_sampled_buildings(
            engine,
            args.samples_per_region,
            args.seed,
            samples_per_region=args.samples_per_region,
        )
    candidates = _candidate_parameters()
    weather_cache = {}
    all_trials = []
    summaries = []

    for position, building in enumerate(buildings.to_dict("records"), start=1):
        commune_id = int(building["tmy_commune_id"])
        if commune_id not in weather_cache:
            weather_cache[commune_id] = _load_era5_weather(
                engine, commune_id, args.year
            )
        trials, summary = _calibration_rows(
            building,
            weather_cache[commune_id],
            args.year,
            args.efficiency,
            candidates,
            args.calibration_target,
        )
        all_trials.append(trials)
        summaries.append(summary)
        print(
            f"[{position}/{len(buildings)}] region={building['codigo_region']} "
            f"edificio_id={building['edificio_id']} best_score={summary['best_score']:.4f}"
        )

    summary = pd.DataFrame(summaries).sort_values("codigo_region")
    trials = pd.concat(all_trials, ignore_index=True)
    summary.to_csv(args.output_dir / "calibration_summary.csv", index=False)
    trials.to_csv(args.output_dir / "calibration_trials.csv", index=False)
    _write_report(args.output_dir, args, summaries, len(candidates))
    print(summary.to_string(index=False, float_format=lambda value: f"{value:.3f}"))
    print(f"Resultados: {args.output_dir}")


if __name__ == "__main__":
    main()
