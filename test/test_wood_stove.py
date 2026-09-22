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


def test_wood_stove_adapter_consumes_5r1c_results_without_mutation():
    index = pd.date_range("2024-07-01", periods=3, freq="h")
    detailed_results = pd.DataFrame(
        {
            "Heating Load": [1.0, 2.0, 0.0],
            "Electricity Load": [0.5, 0.5, 0.5],
        },
        index=index,
    )
    original = detailed_results.copy(deep=True)

    result = tsib.simulate_wood_stove_from_5r1c(
        detailed_results,
        fuel_energy_target_kwh=1.5,
        efficiency=0.5,
    )

    assert result.heating_load_kw.index.equals(index)
    assert result.assigned_useful_energy_kwh == pytest.approx(0.75)
    pd.testing.assert_frame_equal(detailed_results, original)


def test_wood_stove_adapter_accepts_thermal_model_like_source():
    class Fake5R1C:
        detailedResults = pd.DataFrame(
            {"Heating Load": [2.0, 2.0]},
            index=pd.date_range("2024-07-01", periods=2, freq="h"),
        )

    class FakeBuilding:
        thermalmodel = Fake5R1C()

    result = tsib.simulate_wood_stove_from_5r1c(
        FakeBuilding(),
        fuel_energy_target_kwh=1.0,
        efficiency=0.5,
    )

    assert result.assigned_useful_energy_kwh == pytest.approx(0.5)


def test_wood_stove_adapter_requires_completed_5r1c_results():
    empty_results = pd.DataFrame(index=pd.date_range("2024-07-01", periods=2, freq="h"))

    with pytest.raises(ValueError, match="sim_demand_direct"):
        tsib.simulate_wood_stove_from_5r1c(
            empty_results,
            fuel_energy_target_kwh=1.0,
        )


def test_event_stove_releases_heat_from_storage_after_combustion():
    load = pd.Series([2.0, 0.0, 1.0, 0.0])
    result = tsib.simulate_wood_stove_events(
        load,
        fuel_energy_target_kwh=2.0,
        efficiency=0.5,
        event_fuel_energy_kwh=2.0,
        event_duration_hours=2.0,
        min_event_interval_hours=4.0,
        storage_capacity_kwh=2.0,
    )

    assert result.event_count == 1
    assert result.event_start.iloc[0]
    assert result.event_state.iloc[0] == "combustion"
    assert result.event_state.iloc[1] == "combustion"
    assert result.event_state.iloc[2] == "release"
    assert result.assigned_fuel_energy_kwh == pytest.approx(2.0)
    assert result.assigned_useful_energy_kwh == pytest.approx(1.0)
    assert result.unmet_heating_energy_kwh == pytest.approx(2.0)
    assert result.stored_energy_end_kwh == pytest.approx(0.0)
    assert result.useful_heat_kw.iloc[2] == pytest.approx(0.5)


def test_event_stove_reports_storage_spill_and_unallocated_useful_energy():
    result = tsib.simulate_wood_stove_events(
        pd.Series([1.0, 0.0]),
        fuel_energy_target_kwh=2.0,
        efficiency=0.5,
        event_fuel_energy_kwh=2.0,
        event_duration_hours=2.0,
        storage_capacity_kwh=0.25,
    )

    assert result.event_count == 1
    assert result.assigned_fuel_energy_kwh == pytest.approx(2.0)
    assert result.assigned_useful_energy_kwh == pytest.approx(0.25)
    assert result.storage_spill_energy_kwh == pytest.approx(0.5)
    assert result.unallocated_useful_energy_kwh == pytest.approx(0.75)
    assert result.unmet_heating_energy_kwh == pytest.approx(0.75)


def test_event_stove_validates_event_shape_and_power():
    with pytest.raises(ValueError, match="event_profile"):
        tsib.simulate_wood_stove_events(
            [1.0, 1.0],
            fuel_energy_target_kwh=1.0,
            event_duration_hours=2.0,
            event_profile=[1.0],
        )

    with pytest.raises(ValueError, match="max_combustion_power_kw"):
        tsib.simulate_wood_stove_events(
            [1.0, 1.0],
            fuel_energy_target_kwh=2.0,
            event_fuel_energy_kwh=2.0,
            event_duration_hours=2.0,
            max_combustion_power_kw=0.1,
        )


def test_event_stove_adapter_consumes_5r1c_results():
    detailed_results = pd.DataFrame(
        {"Heating Load": [1.0, 0.0, 1.0]},
        index=pd.date_range("2024-07-01", periods=3, freq="h"),
    )
    result = tsib.simulate_wood_stove_events_from_5r1c(
        detailed_results,
        fuel_energy_target_kwh=1.0,
        event_fuel_energy_kwh=1.0,
        event_duration_hours=1.0,
        storage_capacity_kwh=1.0,
    )

    assert result.event_count == 1
    assert result.heating_load_kw.index.equals(detailed_results.index)


def test_event_parameter_calibration_uses_mvp_as_numerical_reference():
    load = pd.Series([1.0, 0.0, 1.0, 0.0])
    calibration = tsib.calibrate_wood_stove_event_parameters(
        load,
        fuel_energy_target_kwh=1.0,
        candidate_parameters=[
            {
                "event_fuel_energy_kwh": 1.0,
                "event_duration_hours": 1.0,
                "min_event_interval_hours": 1.0,
                "storage_capacity_kwh": 1.0,
            },
            {
                "event_fuel_energy_kwh": 2.0,
                "event_duration_hours": 2.0,
                "min_event_interval_hours": 4.0,
                "storage_capacity_kwh": 0.25,
            },
        ],
    )

    assert len(calibration.trials) == 2
    assert calibration.trials["valid"].all()
    assert calibration.best_parameters["event_fuel_energy_kwh"] == 2.0
    best_trial = calibration.trials.loc[calibration.trials["score"].idxmin()]
    assert best_trial["profile_error_kwh"] == pytest.approx(0.0)
    assert calibration.best_result.assigned_useful_energy_kwh == pytest.approx(
        calibration.reference_result.assigned_useful_energy_kwh
    )


def test_predictive_events_do_not_require_an_annual_fuel_target():
    index = pd.date_range("2024-07-01 08:00", periods=8, freq="30min")
    load = pd.Series([4.0] * 8, index=index)
    outdoor = pd.Series([20.0, 20.0, 5.0, 5.0, 5.0, 5.0, 20.0, 20.0], index=index)
    setpoint = pd.Series(20.0, index=index)

    result = tsib.simulate_wood_stove_predictive_events(
        load,
        outdoor_temperature_c=outdoor,
        heating_setpoint_c=setpoint,
        dt_hours=0.5,
        efficiency=0.50,
        log_energy_kwh=7.5,
        logs_per_stere=219.0,
        trigger_delta_c=8.0,
        start_load_threshold_kw=0.25,
        startup_duration_hours=0.5,
        combustion_duration_hours=1.0,
    )

    assert result.event_count == 1
    assert not result.event_start.iloc[0]
    assert not result.event_start.iloc[1]
    assert result.event_start.iloc[2]
    assert result.wood_logs_burned == pytest.approx(2.0)
    assert result.fuel_energy_consumed_kwh == pytest.approx(15.0)
    assert result.wood_volume_stere == pytest.approx(2.0 / 219.0)
    assert result.excess_useful_energy_kwh > 0
    assert result.unmet_heating_energy_kwh > 0


def test_predictive_events_require_the_outdoor_temperature_trigger():
    index = pd.date_range("2024-07-01 08:00", periods=6, freq="30min")
    result = tsib.simulate_wood_stove_predictive_events(
        pd.Series(4.0, index=index),
        outdoor_temperature_c=pd.Series(20.0, index=index),
        heating_setpoint_c=pd.Series(20.0, index=index),
        dt_hours=0.5,
        trigger_delta_c=8.0,
    )

    assert result.event_count == 0
    assert result.fuel_energy_consumed_kwh == pytest.approx(0.0)
    assert result.wood_volume_stere == pytest.approx(0.0)


def test_predictive_5r1c_adapter_reads_temperature_columns_without_mutation():
    index = pd.date_range("2024-07-01 08:00", periods=6, freq="30min")
    detailed_results = pd.DataFrame(
        {
            "Heating Load": [4.0] * 6,
            "T_e": [5.0] * 6,
            "Heating Setpoint": [20.0] * 6,
        },
        index=index,
    )
    original = detailed_results.copy(deep=True)

    result = tsib.simulate_wood_stove_predictive_events_from_5r1c(
        detailed_results,
        dt_hours=0.5,
        trigger_delta_c=8.0,
    )

    assert result.event_count == 1
    assert result.outdoor_temperature_c.index.equals(index)
    pd.testing.assert_frame_equal(detailed_results, original)
