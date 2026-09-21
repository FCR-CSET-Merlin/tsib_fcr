# -*- coding: utf-8 -*-
"""Calibrate shared wood-stove event parameters by regional cohort.

The script builds a weighted regional heating-load profile from the selected
GeoNode cohort, calibrates one event/storage parameter set per region, and
evaluates those parameters on every sampled building. The regional calibration
uses an odd/even deterministic split of ``regional_sample_rank`` so the
remaining records act as a small holdout validation set.

This is a numerical REDPE calibration, not a physical calibration of stove
operation or occupant behaviour.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd
import tsib

from examples.chile.analyze_wood_stove_regional_dispersion import (
    REGION_NAMES,
    _load_sampled_buildings,
)
from examples.chile.calibrate_wood_stove_events import _candidate_parameters
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
    parser.add_argument("--total-samples", type=int, default=500)
    parser.add_argument("--minimum-samples-per-region", type=int, default=10)
    parser.add_argument("--seed", type=int, default=2024)
    parser.add_argument("--efficiency", type=float, default=DEFAULT_EFFICIENCY)
    parser.add_argument(
        "--calibration-target",
        choices=("redpe_mid", "mvp"),
        default="redpe_mid",
        help="Annual target used per region (default: redpe_mid).",
    )
    parser.add_argument("--env-file", type=Path, default=None)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    if args.total_samples <= 0:
        parser.error("--total-samples debe ser mayor que cero.")
    if args.minimum_samples_per_region <= 0:
        parser.error("--minimum-samples-per-region debe ser mayor que cero.")
    if not 0 < args.efficiency <= 1:
        parser.error("--efficiency debe estar en (0, 1].")
    return args


def _safe_unit_weight(building):
    value = building.get("n_inmuebles", 1)
    if pd.isna(value):
        return 1.0
    return max(float(value), 1.0)


def _weighted_mean(values, weights):
    numeric = pd.to_numeric(pd.Series(values), errors="coerce").to_numpy(float)
    weights = np.asarray(weights, dtype=float)
    valid = np.isfinite(numeric) & np.isfinite(weights) & (weights > 0)
    if not np.any(valid):
        return np.nan
    return float(np.average(numeric[valid], weights=weights[valid]))


def _load_cohort_records(engine, buildings, year):
    """Run 5R1C once per sampled building and retain its hourly load."""
    weather_cache = {}
    records = []
    buildings = buildings.sort_values(["codigo_region", "regional_sample_rank"])
    for position, building in enumerate(buildings.to_dict("records"), start=1):
        commune_id = int(building["tmy_commune_id"])
        if commune_id not in weather_cache:
            weather_cache[commune_id] = _load_era5_weather(
                engine, commune_id, year
            )
        model, archetype, persons, area_m2 = _build_model(
            building, weather_cache[commune_id]
        )
        heating_load = model.detailedResults["Heating Load"].copy()
        building["building_year"] = archetype["building_year"]
        building["building_type"] = archetype["building_type"]
        building["material"] = archetype["material"]
        building["thermal_zone"] = archetype["thermal_zone"]
        building["model_persons"] = persons
        building["model_area_m2"] = area_m2
        building["heating_demand_kwh"] = float(heating_load.sum())
        building["cohort_weight"] = _safe_unit_weight(building)
        # Alternating ranks gives every region a deterministic fit/holdout set.
        building["calibration_set"] = (
            int(building["regional_sample_rank"]) % 2 == 1
        )
        records.append({"building": building, "heating_load": heating_load})
        if position == 1 or position % 25 == 0 or position == len(buildings):
            print(f"[{position}/{len(buildings)}] 5R1C completado")
    return records


def _aggregate_heating_load(records):
    """Build a per-dwelling weighted regional load profile."""
    if not records:
        raise ValueError("The calibration cohort is empty.")
    index = records[0]["heating_load"].index
    matrix = []
    weights = []
    for record in records:
        load = record["heating_load"]
        if not load.index.equals(index):
            raise ValueError("All cohort heating-load indexes must be identical.")
        matrix.append(load.to_numpy(dtype=float))
        weights.append(float(record["building"]["cohort_weight"]))
    return pd.Series(
        np.average(np.vstack(matrix), axis=0, weights=np.asarray(weights)),
        index=index,
        name="Heating Load",
    )


def _regional_target(region_code, average_demand_kwh, efficiency, target_case):
    redpe_mid = np.nan
    redpe_target_fuel = np.nan
    try:
        redpe = tsib.get_chile_regional_wood_consumption(region_code, "mid")
        redpe_mid = float(redpe["consumption_m3st_per_consumer"])
        redpe_target_fuel = float(redpe["energy_bruta_mwh_per_consumer"]) * 1000.0
    except ValueError:
        pass

    mvp_target = float(average_demand_kwh) * 0.75 / efficiency
    if target_case == "redpe_mid" and np.isfinite(redpe_target_fuel):
        return {
            "target_source": "REDPE_mid",
            "target_fuel_energy_kwh": redpe_target_fuel,
            "target_wood_volume_stere": redpe_mid,
            "redpe_mid_m3st_per_consumer": redpe_mid,
            "redpe_mid_target_fuel_energy_kwh": redpe_target_fuel,
            "mvp_target_fuel_energy_kwh": mvp_target,
        }
    return {
        "target_source": "MVP_coverage_mid",
        "target_fuel_energy_kwh": mvp_target,
        "target_wood_volume_stere": np.nan,
        "redpe_mid_m3st_per_consumer": redpe_mid,
        "redpe_mid_target_fuel_energy_kwh": redpe_target_fuel,
        "mvp_target_fuel_energy_kwh": mvp_target,
    }


def _calibrate_regional_profile(heating_load, target_fuel, candidates, efficiency):
    """Select parameters against the explicit annual fuel target.

    ``tsib.calibrate_wood_stove_event_parameters`` compares the event model
    with the fuel that the scalar MVP can assign. For REDPE this can be lower
    than the observed target when the 5R1C demand is insufficient. The cohort
    calibration therefore keeps the MVP useful-heat profile as a secondary
    reference but compares assigned fuel directly with ``target_fuel``.
    """
    reference = tsib.simulate_wood_stove(
        heating_load,
        fuel_energy_target_kwh=target_fuel,
        efficiency=efficiency,
    )
    useful_scale = max(reference.target_useful_energy_kwh, 1.0)
    fuel_scale = max(float(target_fuel), 1.0)
    trial_rows = []
    trial_results = []
    for trial_index, candidate in enumerate(candidates):
        row = {"trial": trial_index, **candidate}
        try:
            dynamic = tsib.simulate_wood_stove_events(
                heating_load,
                fuel_energy_target_kwh=target_fuel,
                efficiency=efficiency,
                **candidate,
            )
            useful_error = abs(
                dynamic.assigned_useful_energy_kwh
                - reference.assigned_useful_energy_kwh
            )
            fuel_error = abs(dynamic.assigned_fuel_energy_kwh - target_fuel)
            profile_error = float(
                np.sum(
                    np.abs(
                        dynamic.useful_heat_kw.to_numpy()
                        - reference.useful_heat_kw.to_numpy()
                    )
                )
                * dynamic.dt_hours
            )
            score = (
                useful_error / useful_scale
                + 2.0 * fuel_error / fuel_scale
                + 0.5 * profile_error / useful_scale
                + 0.25 * dynamic.unmet_heating_energy_kwh / useful_scale
                + 0.5 * dynamic.storage_spill_energy_kwh / useful_scale
                + 0.25 * dynamic.stored_energy_end_kwh / useful_scale
            )
            row.update(
                {
                    "valid": True,
                    "error": None,
                    "score": score,
                    "assigned_useful_energy_kwh": dynamic.assigned_useful_energy_kwh,
                    "assigned_fuel_energy_kwh": dynamic.assigned_fuel_energy_kwh,
                    "fuel_error_kwh": fuel_error,
                    "profile_error_kwh": profile_error,
                    "unmet_heating_energy_kwh": dynamic.unmet_heating_energy_kwh,
                    "unallocated_fuel_energy_kwh": dynamic.unallocated_fuel_energy_kwh,
                    "storage_spill_energy_kwh": dynamic.storage_spill_energy_kwh,
                    "stored_energy_end_kwh": dynamic.stored_energy_end_kwh,
                    "event_count": dynamic.event_count,
                }
            )
            trial_results.append(dynamic)
        except (TypeError, ValueError, FloatingPointError) as error:
            row.update({"valid": False, "error": str(error), "score": np.inf})
            trial_results.append(None)
        trial_rows.append(row)

    trials = pd.DataFrame(trial_rows)
    valid = trials[trials["valid"]].sort_values(
        ["score", "event_count", "trial"], kind="stable"
    )
    if valid.empty:
        raise RuntimeError("No valid regional calibration candidate.")
    best_trial = int(valid.iloc[0]["trial"])
    best_parameters = dict(candidates[best_trial])
    return SimpleNamespace(
        reference_result=reference,
        best_result=trial_results[best_trial],
        best_parameters=best_parameters,
        trials=trials,
    )


def _calibrate_regions(records, candidates, efficiency, target_case):
    calibrations = {}
    trial_frames = []
    for region_code in sorted(
        {int(record["building"]["codigo_region"]) for record in records}
    ):
        region_records = [
            record
            for record in records
            if int(record["building"]["codigo_region"]) == region_code
        ]
        fit_records = [
            record for record in region_records if record["building"]["calibration_set"]
        ]
        aggregate_load = _aggregate_heating_load(fit_records)
        average_demand = float(aggregate_load.sum())
        target = _regional_target(
            region_code, average_demand, efficiency, target_case
        )
        calibration = _calibrate_regional_profile(
            aggregate_load,
            target["target_fuel_energy_kwh"],
            candidates,
            efficiency=efficiency,
        )
        trials = calibration.trials.copy()
        trials.insert(0, "codigo_region", region_code)
        trials.insert(1, "region", REGION_NAMES.get(region_code, "unknown"))
        trials.insert(2, "fit_records", len(fit_records))
        trials.insert(3, "holdout_records", len(region_records) - len(fit_records))
        trials.insert(4, "target_source", target["target_source"])
        trials.insert(5, "target_fuel_energy_kwh", target["target_fuel_energy_kwh"])
        trials.insert(6, "target_wood_volume_stere", target["target_wood_volume_stere"])
        trial_frames.append(trials)
        calibrations[region_code] = {
            "calibration": calibration,
            "target": target,
            "fit_records": len(fit_records),
            "holdout_records": len(region_records) - len(fit_records),
            "average_demand_kwh": average_demand,
        }
        print(
            f"region={region_code} "
            f"fit={len(fit_records)} holdout={len(region_records) - len(fit_records)} "
            f"target={target['target_source']} score={calibration.trials['score'].min():.4f}"
        )
    return calibrations, pd.concat(trial_frames, ignore_index=True)


def _evaluate_cohort(records, calibrations, efficiency):
    rows = []
    for record in records:
        building = record["building"]
        region_code = int(building["codigo_region"])
        selected = calibrations[region_code]
        target = selected["target"]
        result = tsib.simulate_wood_stove_events(
            record["heating_load"],
            fuel_energy_target_kwh=target["target_fuel_energy_kwh"],
            efficiency=efficiency,
            **selected["calibration"].best_parameters,
        )
        row = {
            "edificio_id": int(building["edificio_id"]),
            "codigo_region": region_code,
            "region": REGION_NAMES.get(region_code, "unknown"),
            "codigo_comuna": int(building["codigo_comuna"]),
            "nombre_comuna": building["nombre_comuna"],
            "regional_sample_rank": int(building["regional_sample_rank"]),
            "calibration_set": bool(building["calibration_set"]),
            "n_inmuebles": int(_safe_unit_weight(building)),
            "cohort_weight": float(building["cohort_weight"]),
            "heating_demand_kwh": float(building["heating_demand_kwh"]),
            "target_source": target["target_source"],
            "redpe_mid_m3st_per_consumer": target["redpe_mid_m3st_per_consumer"],
            "redpe_mid_target_fuel_energy_kwh": target[
                "redpe_mid_target_fuel_energy_kwh"
            ],
            "mvp_target_fuel_energy_kwh": target["mvp_target_fuel_energy_kwh"],
            "target_fuel_energy_kwh": target["target_fuel_energy_kwh"],
            "target_wood_volume_stere": target["target_wood_volume_stere"],
            "assigned_fuel_energy_kwh": result.assigned_fuel_energy_kwh,
            "assigned_useful_energy_kwh": result.assigned_useful_energy_kwh,
            "unallocated_fuel_energy_kwh": result.unallocated_fuel_energy_kwh,
            "unmet_heating_energy_kwh": result.unmet_heating_energy_kwh,
            "storage_spill_energy_kwh": result.storage_spill_energy_kwh,
            "stored_energy_end_kwh": result.stored_energy_end_kwh,
            "event_count": result.event_count,
            "wood_volume_stere": result.wood_volume_stere,
            **selected["calibration"].best_parameters,
        }
        rows.append(row)
    return pd.DataFrame(rows)


def _summary_table(results, calibrations):
    rows = []
    for region_code, group in results.groupby("codigo_region", sort=True):
        selected = calibrations[int(region_code)]
        target = selected["target"]
        weights = group["cohort_weight"].to_numpy(dtype=float)
        holdout = group[~group["calibration_set"]]
        holdout_weights = holdout["cohort_weight"].to_numpy(dtype=float)
        target_volume = target["target_wood_volume_stere"]
        weighted_volume = _weighted_mean(group["wood_volume_stere"], weights)
        weighted_holdout_volume = _weighted_mean(
            holdout["wood_volume_stere"], holdout_weights
        )
        row = {
            "codigo_region": int(region_code),
            "region": REGION_NAMES.get(int(region_code), "unknown"),
            "target_source": target["target_source"],
            "n_simulations": len(group),
            "n_calibration": int(group["calibration_set"].sum()),
            "n_holdout": int((~group["calibration_set"]).sum()),
            "n_inmuebles_sampled": int(group["n_inmuebles"].sum()),
            "heating_demand_kwh_weighted_mean": _weighted_mean(
                group["heating_demand_kwh"], weights
            ),
            "redpe_mid_m3st_per_consumer": target[
                "redpe_mid_m3st_per_consumer"
            ],
            "target_fuel_energy_kwh": target["target_fuel_energy_kwh"],
            "target_wood_volume_stere": target_volume,
            "simulated_wood_volume_stere_weighted_mean": weighted_volume,
            "simulated_wood_volume_stere_median": float(
                group["wood_volume_stere"].median()
            ),
            "simulated_wood_volume_stere_p10": float(
                group["wood_volume_stere"].quantile(0.10)
            ),
            "simulated_wood_volume_stere_p90": float(
                group["wood_volume_stere"].quantile(0.90)
            ),
            "holdout_wood_volume_stere_weighted_mean": weighted_holdout_volume,
            "relative_volume_error": (
                (weighted_volume - target_volume) / target_volume
                if np.isfinite(target_volume) and target_volume > 0
                else np.nan
            ),
            "holdout_relative_volume_error": (
                (weighted_holdout_volume - target_volume) / target_volume
                if np.isfinite(target_volume) and target_volume > 0
                else np.nan
            ),
            "assigned_fuel_energy_kwh_weighted_mean": _weighted_mean(
                group["assigned_fuel_energy_kwh"], weights
            ),
            "unallocated_fuel_energy_kwh_weighted_mean": _weighted_mean(
                group["unallocated_fuel_energy_kwh"], weights
            ),
            "unmet_heating_energy_kwh_weighted_mean": _weighted_mean(
                group["unmet_heating_energy_kwh"], weights
            ),
            "storage_spill_energy_kwh_weighted_mean": _weighted_mean(
                group["storage_spill_energy_kwh"], weights
            ),
            "best_score": float(selected["calibration"].trials["score"].min()),
            "best_profile_error_kwh": float(
                selected["calibration"].trials.loc[
                    selected["calibration"].trials["score"].idxmin(),
                    "profile_error_kwh",
                ]
            ),
            "best_event_fuel_energy_kwh": selected["calibration"].best_parameters[
                "event_fuel_energy_kwh"
            ],
            "best_event_duration_hours": selected["calibration"].best_parameters[
                "event_duration_hours"
            ],
            "best_min_event_interval_hours": selected["calibration"].best_parameters[
                "min_event_interval_hours"
            ],
            "best_storage_capacity_kwh": selected["calibration"].best_parameters[
                "storage_capacity_kwh"
            ],
            "best_storage_loss_rate_per_hour": selected["calibration"].best_parameters[
                "storage_loss_rate_per_hour"
            ],
        }
        rows.append(row)
    return pd.DataFrame(rows)


def _write_report(output_dir, args, summary, records, trial_count):
    def _format_optional(value, format_spec):
        if not np.isfinite(value):
            return "-"
        return format(value, format_spec)

    lines = [
        "# Calibración regional de cohorte de estufa a leña",
        "",
        "La calibración usa perfiles horarios 5R1C agregados por región y",
        "ponderados por `n_inmuebles`. Los parámetros resultantes se evalúan",
        "después en todos los registros de la cohorte.",
        "El score compara explícitamente el combustible asignado con el",
        "objetivo anual (`REDPE_mid` cuando existe), además del perfil útil,",
        "la demanda no satisfecha y las pérdidas de almacenamiento. Por tanto,",
        "un objetivo REDPE que no puede absorberse no se fuerza: queda reportado",
        "como combustible no asignado.",
        "",
        "## Configuración",
        "",
        f"- Año ERA5: `{args.year}`.",
        f"- Registros seleccionados: `{len(records)}`.",
        f"- Mínimo regional: `{args.minimum_samples_per_region}`.",
        f"- Semilla: `{args.seed}`.",
        f"- Candidatos por región: `{trial_count}`.",
        f"- Eficiencia: `{args.efficiency:.2f}`.",
        f"- Objetivo: `{args.calibration_target}`; fallback MVP donde REDPE no tiene fila.",
        "- Ajuste: rangos impares de `regional_sample_rank`; validación: rangos pares.",
        "",
        "## Validación regional",
        "",
        "`simulado` es la media ponderada por `n_inmuebles` en toda la cohorte;",
        "`holdout` usa sólo los registros reservados para validación.",
        "",
        "| Región | Objetivo | n ajuste | n holdout | REDPE (m³ st) | Simulado (m³ st) | Holdout (m³ st) | Error holdout | No asignado (kWh) | No satisfecha (kWh) |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in summary.itertuples(index=False):
        lines.append(
            f"| {row.region} | {row.target_source} | {row.n_calibration} | "
            f"{row.n_holdout} | "
            f"{_format_optional(row.redpe_mid_m3st_per_consumer, '.2f')} | "
            f"{row.simulated_wood_volume_stere_weighted_mean:.2f} | "
            f"{row.holdout_wood_volume_stere_weighted_mean:.2f} | "
            f"{_format_optional(row.holdout_relative_volume_error, '.1%')} | "
            f"{row.unallocated_fuel_energy_kwh_weighted_mean:.1f} | "
            f"{row.unmet_heating_energy_kwh_weighted_mean:.1f} |"
        )
    lines.extend(
        [
            "",
            "## Parámetros compartidos por región",
            "",
            "| Región | Energía/evento | Duración (h) | Intervalo (h) | Almacenamiento (kWh) | Pérdida/h | Score ajuste |",
            "|---|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for row in summary.itertuples(index=False):
        lines.append(
            f"| {row.region} | {row.best_event_fuel_energy_kwh:.1f} | "
            f"{row.best_event_duration_hours:.1f} | "
            f"{row.best_min_event_interval_hours:.1f} | "
            f"{row.best_storage_capacity_kwh:.1f} | "
            f"{row.best_storage_loss_rate_per_hour:.3f} | {row.best_score:.4f} |"
        )
    lines.extend(
        [
            "",
            "El resultado es una calibración numérica de consistencia. No",
            "identifica todavía eficiencia real, conducta de los ocupantes ni",
            "potencia física de una estufa observada.",
            "",
            "## Archivos",
            "",
            "- `cohort_calibration_summary.csv`: métricas regionales y parámetros.",
            "- `cohort_calibration_trials.csv`: candidatos evaluados por región.",
            "- `cohort_results.csv`: evaluación por edificio y conjunto ajuste/holdout.",
            "- `README.md`: este informe.",
        ]
    )
    (output_dir / "README.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    args = _parse_args()
    _load_env_file(args.env_file)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    engine = _create_engine()
    buildings = _load_sampled_buildings(
        engine,
        args.total_samples,
        args.seed,
        minimum_samples_per_region=args.minimum_samples_per_region,
    )
    buildings.to_csv(args.output_dir / "selected_buildings.csv", index=False)
    records = _load_cohort_records(engine, buildings, args.year)
    candidates = _candidate_parameters()
    calibrations, trials = _calibrate_regions(
        records, candidates, args.efficiency, args.calibration_target
    )
    results = _evaluate_cohort(records, calibrations, args.efficiency)
    summary = _summary_table(results, calibrations).sort_values("codigo_region")
    summary.to_csv(args.output_dir / "cohort_calibration_summary.csv", index=False)
    trials.to_csv(args.output_dir / "cohort_calibration_trials.csv", index=False)
    results.to_csv(args.output_dir / "cohort_results.csv", index=False)
    _write_report(args.output_dir, args, summary, records, len(candidates))
    print(summary.to_string(index=False, float_format=lambda value: f"{value:.3f}"))
    print(f"Resultados: {args.output_dir}")


if __name__ == "__main__":
    main()
