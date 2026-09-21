# -*- coding: utf-8 -*-
"""Deterministic example of discrete wood loads and thermal storage."""

from __future__ import annotations

import numpy as np
import pandas as pd
import tsib


def main():
    index = pd.date_range("2024-07-01", periods=48, freq="h")
    outside_shape = np.tile([0.0, 0.0, 0.2, 0.6, 1.0, 0.8, 0.3, 0.1], 6)
    heating_load = pd.Series(1.5 * outside_shape, index=index, name="Heating Load")

    result = tsib.simulate_wood_stove_events(
        heating_load,
        fuel_energy_target_kwh=24.0,
        efficiency=0.50,
        event_fuel_energy_kwh=4.0,
        event_duration_hours=2.0,
        min_event_interval_hours=6.0,
        storage_capacity_kwh=2.0,
        storage_loss_rate_per_hour=0.01,
        charge_efficiency=0.95,
        release_efficiency=0.95,
        max_useful_power_kw=0.75,
        availability=(heating_load.to_numpy() > 0),
    )

    event_table = pd.DataFrame(
        {
            "event_start": result.event_start,
            "event_fuel_input_kwh": result.event_fuel_input_kwh,
            "event_state": result.event_state,
            "combustion_heat_kw": result.combustion_heat_kw,
            "useful_heat_kw": result.useful_heat_kw,
            "storage_kwh": result.storage_kwh,
        }
    )
    print(event_table[event_table["event_start"]].to_string())
    print(
        {
            "event_count": result.event_count,
            "assigned_fuel_energy_kwh": result.assigned_fuel_energy_kwh,
            "assigned_useful_energy_kwh": result.assigned_useful_energy_kwh,
            "unmet_heating_energy_kwh": result.unmet_heating_energy_kwh,
            "stored_energy_end_kwh": result.stored_energy_end_kwh,
            "wood_volume_stere": result.wood_volume_stere,
        }
    )

    assert np.isclose(
        result.assigned_fuel_energy_kwh + result.unallocated_fuel_energy_kwh,
        result.target_fuel_energy_kwh,
    )


if __name__ == "__main__":
    main()
