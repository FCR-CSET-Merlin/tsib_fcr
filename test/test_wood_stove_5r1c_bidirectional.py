"""Synthetic tests for the opt-in bidirectional 5R1C wood-stove coupling."""

import numpy as np
import pandas as pd
import pytest

import tsib

from test_chile import _build_cfg, _make_synthetic_tmy


def _model(n=96, temperature_mean=5.0, q_ig_kw=0.0):
    weather = _make_synthetic_tmy(T_mean=temperature_mean).iloc[:n]
    cfg = _build_cfg(
        "CL.SFH.preRT.mad.D",
        weather,
        60.0,
        {"U_Wall_1": 2.7, "U_Roof_1": 2.5, "U_Floor_1": 1.4, "U_Window_1": 5.8},
        weather_id="bidirectional_test",
        q_ig_kw=q_ig_kw,
    )
    return tsib.Building5R1C(cfg)


def test_controller_keeps_outdoor_trigger_mandatory_and_conserves_event_energy():
    controller = tsib.WoodStoveController(
        timestep_hours=0.5,
        trigger_delta_c=8.0,
        start_load_threshold_kw=0.25,
    )
    index = pd.date_range("2024-07-01 08:00", periods=5, freq="30min")

    warm_outside = tsib.StoveObservation(
        timestamp=index[0],
        t_ext_c=20.0,
        t_air_c=15.0,
        t_surface_c=15.0,
        t_mass_c=15.0,
        heating_setpoint_c=20.0,
        cooling_setpoint_c=26.0,
        free_float_heating_kw=0.0,
    )
    assert controller.step(warm_outside).event_start is False

    cold_outside = tsib.StoveObservation(
        timestamp=index[1],
        t_ext_c=5.0,
        t_air_c=15.0,
        t_surface_c=15.0,
        t_mass_c=15.0,
        heating_setpoint_c=20.0,
        cooling_setpoint_c=26.0,
        free_float_heating_kw=4.0,
    )
    commands = [controller.step(cold_outside)]
    commands.extend(
        controller.step(
            tsib.StoveObservation(
                timestamp=timestamp,
                t_ext_c=5.0,
                t_air_c=15.0,
                t_surface_c=15.0,
                t_mass_c=15.0,
                heating_setpoint_c=20.0,
                cooling_setpoint_c=26.0,
                free_float_heating_kw=4.0,
            )
        )
        for timestamp in index[2:4]
    )

    assert commands[0].event_start
    assert commands[0].logs_loaded == 2
    assert sum(command.fuel_energy_kwh for command in commands) == pytest.approx(15.0)
    assert sum(command.useful_energy_kwh for command in commands) == pytest.approx(7.5)


def test_bidirectional_without_stove_and_with_auxiliary_matches_direct_path():
    direct_model = _model(n=72, temperature_mean=6.0, q_ig_kw=0.3)
    direct_model.sim_demand_direct(heating_setpoint=20.0, cooling_setpoint=26.0)
    direct = direct_model.detailedResults.copy(deep=True)

    coupled_model = _model(n=72, temperature_mean=6.0, q_ig_kw=0.3)
    result = tsib.simulate_wood_stove_5r1c_bidirectional(
        coupled_model,
        heating_setpoint=20.0,
        cooling_setpoint=26.0,
        heating_mode="wood_plus_auxiliary",
        availability=False,
        timestep_minutes=60,
    )

    np.testing.assert_allclose(result.detailed_results["T_air"], direct["T_air"])
    np.testing.assert_allclose(result.detailed_results["T_s"], direct["T_s"])
    np.testing.assert_allclose(result.detailed_results["T_m"], direct["T_m"])
    np.testing.assert_allclose(
        result.detailed_results["auxiliary_heating_kw"], direct["Heating Load"]
    )
    np.testing.assert_allclose(
        result.detailed_results["cooling_kw"], direct["Cooling Load"]
    )
    np.testing.assert_allclose(
        result.detailed_results["Electricity Load"], direct["Electricity Load"]
    )
    assert result.fuel_energy_consumed_kwh == pytest.approx(0.0)


def test_wood_heat_changes_zone_state_and_preserves_electricity_load():
    base_model = _model(n=96, temperature_mean=2.0, q_ig_kw=0.0)
    base = tsib.simulate_wood_stove_5r1c_bidirectional(
        base_model,
        heating_setpoint=20.0,
        cooling_setpoint=26.0,
        heating_mode="wood_only",
        availability=False,
        timestep_minutes=60,
    )

    stove_model = _model(n=96, temperature_mean=2.0, q_ig_kw=0.0)
    stove = tsib.simulate_wood_stove_5r1c_bidirectional(
        stove_model,
        heating_setpoint=20.0,
        cooling_setpoint=26.0,
        heating_mode="wood_only",
        timestep_minutes=60,
        spinup_passes=1,
    )

    assert stove.event_count > 0
    assert stove.fuel_energy_consumed_kwh == pytest.approx(
        stove.wood_logs_burned * 7.5
    )
    assert stove.wood_useful_energy_kwh == pytest.approx(
        stove.fuel_energy_consumed_kwh * stove.efficiency
    )
    event_steps = stove.detailed_results["event_state"] != "off"
    assert (
        stove.detailed_results.loc[event_steps, "T_air"]
        > base.detailed_results.loc[event_steps, "T_air"]
    ).any()
    np.testing.assert_allclose(
        stove.detailed_results["Electricity Load"],
        base.detailed_results["Electricity Load"],
    )
