import numpy as np
import pandas as pd
import pytest

import tsib


def test_wood_stove_conserves_fuel_and_useful_energy():
    load = pd.Series([1.0, 2.0, 0.0, 1.0])
    result = tsib.simulate_wood_stove(
        load,
        fuel_energy_target_kwh=4.0,
        efficiency=0.5,
        pci_mj_per_kg=15.0,
    )

    assert result.useful_heat_kw.sum() == pytest.approx(2.0)
    assert result.fuel_input_kw.sum() == pytest.approx(4.0)
    assert result.target_useful_energy_kwh == pytest.approx(2.0)
    assert result.assigned_useful_energy_kwh == pytest.approx(2.0)
    assert result.unallocated_useful_energy_kwh == pytest.approx(0.0)
    assert result.unmet_heating_energy_kwh == pytest.approx(2.0)
    assert result.wood_mass_kg == pytest.approx(0.96)
    assert result.useful_heat_kw.index.equals(load.index)


def test_wood_stove_reports_unallocated_target_when_demand_is_too_small():
    result = tsib.simulate_wood_stove(
        pd.Series([0.0, 2.0, 0.0]),
        fuel_energy_target_kwh=10.0,
        efficiency=0.5,
    )

    assert result.assigned_useful_energy_kwh == pytest.approx(2.0)
    assert result.assigned_fuel_energy_kwh == pytest.approx(4.0)
    assert result.unallocated_useful_energy_kwh == pytest.approx(3.0)
    assert result.unallocated_fuel_energy_kwh == pytest.approx(6.0)
    assert result.unmet_heating_energy_kwh == pytest.approx(0.0)


def test_wood_stove_respects_power_availability_and_event_profile():
    result = tsib.simulate_wood_stove(
        pd.Series([2.0, 2.0, 2.0]),
        fuel_energy_target_kwh=2.0,
        efficiency=0.5,
        max_useful_power_kw=0.75,
        availability=[True, False, True],
        event_profile=[0.0, 1.0, 1.0],
    )

    assert result.useful_heat_kw.iloc[0] == pytest.approx(0.0)
    assert result.useful_heat_kw.iloc[1] == pytest.approx(0.0)
    assert result.useful_heat_kw.iloc[2] == pytest.approx(0.75)
    assert result.assigned_useful_energy_kwh == pytest.approx(0.75)
    assert result.unallocated_useful_energy_kwh == pytest.approx(0.25)


def test_wood_stove_conserves_energy_for_half_hour_steps():
    index = pd.date_range("2024-01-01", periods=2, freq="30min")
    result = tsib.simulate_wood_stove(
        pd.Series([2.0, 2.0], index=index),
        fuel_energy_target_kwh=1.0,
        efficiency=0.5,
    )

    assert result.dt_hours == pytest.approx(0.5)
    assert result.assigned_useful_energy_kwh == pytest.approx(0.5)
    assert result.useful_heat_kw.sum() * result.dt_hours == pytest.approx(0.5)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"fuel_energy_target_kwh": -1.0},
        {"fuel_energy_target_kwh": 1.0, "efficiency": 0.0},
        {"fuel_energy_target_kwh": 1.0, "pci_mj_per_kg": 0.0},
    ],
)
def test_wood_stove_rejects_invalid_energy_parameters(kwargs):
    with pytest.raises(ValueError):
        tsib.simulate_wood_stove([1.0], **kwargs)


def test_wood_stove_rejects_negative_heating_load():
    with pytest.raises(ValueError, match="heating_load"):
        tsib.simulate_wood_stove(np.array([-0.1]), fuel_energy_target_kwh=1.0)
