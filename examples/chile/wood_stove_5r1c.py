# -*- coding: utf-8 -*-
"""Reproducible Phase 4 example: 5R1C demand connected to a wood stove.

The example uses a deterministic synthetic weather series so it does not
depend on a downloaded weather resource. Replace ``_synthetic_tmy`` with a
validated Chilean TMY before using the result for calibration or reporting.

Run from the repository root::

    PYTHONPATH=. python examples/chile/wood_stove_5r1c.py
"""

import numpy as np
import pandas as pd

import tsib


ARCHETYPE_ID = "CL.SFH.preRT.mad.G"
A_REF = 60.0
EFFICIENCY = 0.50
WOOD_USEFUL_SHARE = 0.70


def _synthetic_tmy(n=14 * 24):
    """Build a deterministic two-week hourly weather fixture."""
    index = pd.date_range("2010-07-01", periods=n, freq="h")
    step = np.arange(n)
    temperature = 6.0 + 7.0 * np.sin(2 * np.pi * (step - 8) / (24 * 7))
    daylight = np.clip(np.sin(np.pi * (step % 24 - 6) / 12), 0, None)
    return pd.DataFrame(
        {
            "T": temperature,
            "DHI": 200.0 * daylight,
            "DNI": 400.0 * daylight,
            "GHI": 500.0 * daylight,
        },
        index=index,
    )


def _building_configuration(weather):
    """Create a self-contained Chilean configuration for the example."""
    cfg_obj = tsib.BuildingConfiguration(
        {
            "ID": ARCHETYPE_ID,
            "country": "CL",
            "a_ref": A_REF,
            "weatherData": weather,
            "weatherID": "wood_stove_phase4_synthetic",
            "refurbishment": False,
            "autoProfiles": False,
            "U_Wall_1": 2.7,
            "U_Roof_1": 2.5,
            "U_Floor_1": 1.4,
            "U_Window_1": 5.8,
        },
        ignore_profiles=True,
    )
    cfg = cfg_obj.getBdgCfg(includeSupply=True)
    zeros = pd.Series(np.zeros(len(weather)), index=weather.index)
    cfg.update(
        {
            "Q_ig": np.full(len(weather), 0.3),
            "occ_nothome": zeros,
            "occ_sleeping": zeros,
            "elecLoad": zeros,
            "hotWaterLoad": zeros,
        }
    )
    return cfg


def main():
    weather = _synthetic_tmy()
    model = tsib.Building5R1C(_building_configuration(weather))
    model.sim_demand_direct(
        heating_setpoint=20.0,
        cooling_setpoint=26.0,
    )

    heating_demand_kwh = float(model.detailedResults["Heating Load"].sum())
    target_fuel_kwh = heating_demand_kwh * WOOD_USEFUL_SHARE / EFFICIENCY
    stove = tsib.simulate_wood_stove_from_5r1c(
        model,
        fuel_energy_target_kwh=target_fuel_kwh,
        efficiency=EFFICIENCY,
    )

    print(f"Archetype:                 {ARCHETYPE_ID}")
    print(f"5R1C heating demand:       {heating_demand_kwh:10.2f} kWh")
    print(f"Stove useful heat:         {stove.assigned_useful_energy_kwh:10.2f} kWh")
    print(f"Stove fuel input:          {stove.assigned_fuel_energy_kwh:10.2f} kWh")
    print(f"Wood mass:                 {stove.wood_mass_kg:10.2f} kg")
    print(f"Wood volume:               {stove.wood_volume_stere:10.2f} m3 st")
    print(f"Unmet heating demand:      {stove.unmet_heating_energy_kwh:10.2f} kWh")
    print(f"Unallocated fuel target:   {stove.unallocated_fuel_energy_kwh:10.2f} kWh")


if __name__ == "__main__":
    main()
