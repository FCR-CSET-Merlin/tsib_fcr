"""Opt-in bidirectional coupling between a 5R1C zone and a wood stove.

The legacy wood-stove functions remain post-processing models.  This module
contains the first causal coupling layer: the stove observes the current 5R1C
state, emits a discrete event profile, and the useful heat is then inserted
explicitly into the air, surface and (optionally) mass nodes.

The implementation deliberately uses the numerical context prepared by
``Building5R1C._prepare_direct_5r1c``.  In particular, the historical
``Q_st`` gains are preserved and stove heat is added through separate source
channels, so the old ``Heating Load`` column is never reinterpreted.
"""

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class FiveR1CState:
    """State passed between coupled 5R1C steps."""

    t_mass_c: float
    t_surface_c: float
    t_air_c: float


@dataclass(frozen=True)
class StoveObservation:
    """Causal observation available to the stove controller at one step."""

    timestamp: object
    t_ext_c: float
    t_air_c: float
    t_surface_c: float
    t_mass_c: float
    heating_setpoint_c: float
    cooling_setpoint_c: float
    free_float_heating_kw: float
    available: bool = True


@dataclass(frozen=True)
class StoveCommand:
    """Heat and event command produced for one timestep."""

    fuel_input_kw: float
    useful_heat_kw: float
    fuel_energy_kwh: float
    useful_energy_kwh: float
    event_start: bool
    logs_loaded: int
    event_state: str
    excess_useful_energy_kwh: float


@dataclass
class WoodStoveControllerState:
    """Mutable event state retained by :class:`WoodStoveController`."""

    active_profile: np.ndarray | None = None
    profile_index: int = 0
    next_allowed_step: int = 0
    step_index: int = 0
    event_count: int = 0
    logs_burned: float = 0.0


class WoodStoveController:
    """Incremental, target-free event controller for a wood stove.

    The controller does not know annual consumption.  A load is selected from
    the current free-float demand and the indoor deficit, then emitted through
    a fixed startup/combustion profile.  The profile conserves the declared
    chemical energy even when the building subsequently overheats.
    """

    def __init__(
        self,
        *,
        timestep_hours,
        efficiency=0.50,
        log_energy_kwh=7.5,
        max_logs_per_event=4,
        startup_duration_hours=0.5,
        combustion_duration_hours=1.0,
        startup_energy_fraction=0.20,
        min_event_interval_hours=3.0,
        trigger_delta_c=8.0,
        indoor_deficit_threshold_c=0.5,
        start_load_threshold_kw=0.25,
        operation_start_hour=8,
        operation_end_hour=23,
    ):
        self.dt_hours = _positive_float(timestep_hours, "timestep_hours")
        self.efficiency = _bounded_float(efficiency, "efficiency", 0.0, 1.0)
        self.log_energy_kwh = _positive_float(log_energy_kwh, "log_energy_kwh")
        self.max_logs_per_event = int(max_logs_per_event)
        if self.max_logs_per_event < 1:
            raise ValueError('"max_logs_per_event" must be at least one.')

        self.startup_duration_hours = _positive_float(
            startup_duration_hours, "startup_duration_hours"
        )
        self.combustion_duration_hours = _positive_float(
            combustion_duration_hours, "combustion_duration_hours"
        )
        self.startup_energy_fraction = _bounded_float(
            startup_energy_fraction, "startup_energy_fraction", 0.0, 1.0
        )
        self.min_event_interval_hours = _nonnegative_float(
            min_event_interval_hours, "min_event_interval_hours"
        )
        self.trigger_delta_c = _nonnegative_float(trigger_delta_c, "trigger_delta_c")
        self.indoor_deficit_threshold_c = _nonnegative_float(
            indoor_deficit_threshold_c, "indoor_deficit_threshold_c"
        )
        self.start_load_threshold_kw = _nonnegative_float(
            start_load_threshold_kw, "start_load_threshold_kw"
        )
        self.operation_start_hour = int(operation_start_hour)
        self.operation_end_hour = int(operation_end_hour)
        if not 0 <= self.operation_start_hour < self.operation_end_hour <= 24:
            raise ValueError("operation hours must satisfy 0 <= start < end <= 24.")

        # A non-30-minute model is supported as a declared coarse approximation:
        # each phase is rounded up, but the phase energy remains exact.  At the
        # intended 30-minute resolution these are exactly 1 and 2 steps.
        self.startup_steps = max(
            1, int(np.ceil(self.startup_duration_hours / self.dt_hours - 1e-12))
        )
        self.combustion_steps = max(
            1, int(np.ceil(self.combustion_duration_hours / self.dt_hours - 1e-12))
        )
        self.min_event_steps = max(
            1, int(np.ceil(self.min_event_interval_hours / self.dt_hours - 1e-12))
        )
        self._state = WoodStoveControllerState()

    @property
    def state(self):
        """Return the controller's current event state object."""

        return self._state

    def reset(self):
        """Reset event memory before a new spin-up year or independent run."""

        self._state = WoodStoveControllerState()

    def _operation_window_open(self, timestamp):
        hour = getattr(timestamp, "hour", None)
        if hour is None:
            return True
        return self.operation_start_hour <= hour < self.operation_end_hour

    def _start_event_if_needed(self, observation):
        state = self._state
        if state.active_profile is not None:
            return False, 0
        if state.step_index < state.next_allowed_step:
            return False, 0
        if not observation.available or not self._operation_window_open(observation.timestamp):
            return False, 0

        outdoor_trigger = (
            observation.heating_setpoint_c - observation.t_ext_c
            >= self.trigger_delta_c
        )
        indoor_deficit = max(
            observation.heating_setpoint_c - observation.t_air_c, 0.0
        )
        indoor_trigger = (
            indoor_deficit >= self.indoor_deficit_threshold_c
            or observation.free_float_heating_kw >= self.start_load_threshold_kw
        )
        if not outdoor_trigger or not indoor_trigger:
            return False, 0

        horizon_hours = self.startup_duration_hours + self.combustion_duration_hours
        required_useful_energy = max(
            observation.free_float_heating_kw,
            self.start_load_threshold_kw,
        ) * horizon_hours
        useful_per_log = self.log_energy_kwh * self.efficiency
        logs = int(
            np.clip(
                np.ceil(required_useful_energy / useful_per_log),
                1,
                self.max_logs_per_event,
            )
        )
        profile = _event_profile(
            logs * self.log_energy_kwh,
            self.startup_steps,
            self.combustion_steps,
            self.startup_energy_fraction,
            self.dt_hours,
            self.startup_duration_hours,
            self.combustion_duration_hours,
        )
        state.active_profile = profile
        state.profile_index = 0
        state.next_allowed_step = state.step_index + self.min_event_steps
        state.event_count += 1
        state.logs_burned += logs
        return True, logs

    def step(self, observation):
        """Make one causal event decision and return the current heat command."""

        if not isinstance(observation, StoveObservation):
            raise TypeError("observation must be a StoveObservation instance.")
        started, logs = self._start_event_if_needed(observation)
        state = self._state

        fuel_input_kw = 0.0
        useful_heat_kw = 0.0
        event_state = "off"
        if state.active_profile is not None:
            fuel_input_kw = float(state.active_profile[state.profile_index])
            useful_heat_kw = fuel_input_kw * self.efficiency
            event_state = (
                "startup"
                if state.profile_index < self.startup_steps
                else "combustion"
            )
            state.profile_index += 1
            if state.profile_index >= state.active_profile.size:
                state.active_profile = None
                state.profile_index = 0

        state.step_index += 1
        fuel_energy_kwh = fuel_input_kw * self.dt_hours
        useful_energy_kwh = useful_heat_kw * self.dt_hours
        reference_demand = max(observation.free_float_heating_kw, 0.0)
        excess = max(0.0, useful_energy_kwh - reference_demand * self.dt_hours)
        return StoveCommand(
            fuel_input_kw=fuel_input_kw,
            useful_heat_kw=useful_heat_kw,
            fuel_energy_kwh=fuel_energy_kwh,
            useful_energy_kwh=useful_energy_kwh,
            event_start=started,
            logs_loaded=logs,
            event_state=event_state,
            excess_useful_energy_kwh=excess,
        )


@dataclass(frozen=True)
class _StepPreview:
    t_surface_free_c: float
    t_air_free_c: float
    free_float_heating_kw: float


@dataclass(frozen=True)
class _StepAdvance:
    state_at_step: FiveR1CState
    next_state: FiveR1CState
    auxiliary_heating_kw: float
    cooling_kw: float
    unmet_heating_kw: float
    overheating_c: float


@dataclass(frozen=True)
class BidirectionalWoodStoveResult:
    """Hourly or sub-hourly result of the coupled simulation."""

    detailed_results: pd.DataFrame
    heating_mode: str
    efficiency: float
    log_energy_kwh: float
    logs_per_stere: float
    event_count: int
    wood_logs_burned: float
    fuel_energy_consumed_kwh: float
    wood_useful_energy_kwh: float
    auxiliary_heating_energy_kwh: float
    unmet_heating_energy_kwh: float
    overheating_degree_hours: float
    wood_mass_kg: float
    wood_volume_solid_m3: float
    wood_volume_stere: float
    air_fraction: float
    surface_fraction: float
    mass_fraction: float
    dt_hours: float
    scenario_parameters: dict

    @property
    def results(self):
        """Alias for the tabular output."""

        return self.detailed_results

    def as_dict(self):
        """Return tabular and scalar outputs in a serializable mapping."""

        return {
            "detailed_results": self.detailed_results,
            "heating_mode": self.heating_mode,
            "efficiency": self.efficiency,
            "log_energy_kwh": self.log_energy_kwh,
            "logs_per_stere": self.logs_per_stere,
            "event_count": self.event_count,
            "wood_logs_burned": self.wood_logs_burned,
            "fuel_energy_consumed_kwh": self.fuel_energy_consumed_kwh,
            "wood_useful_energy_kwh": self.wood_useful_energy_kwh,
            "auxiliary_heating_energy_kwh": self.auxiliary_heating_energy_kwh,
            "unmet_heating_energy_kwh": self.unmet_heating_energy_kwh,
            "overheating_degree_hours": self.overheating_degree_hours,
            "wood_mass_kg": self.wood_mass_kg,
            "wood_volume_solid_m3": self.wood_volume_solid_m3,
            "wood_volume_stere": self.wood_volume_stere,
            "air_fraction": self.air_fraction,
            "surface_fraction": self.surface_fraction,
            "mass_fraction": self.mass_fraction,
            "dt_hours": self.dt_hours,
            "scenario_parameters": self.scenario_parameters,
        }


def _positive_float(value, name):
    value = float(value)
    if not np.isfinite(value) or value <= 0:
        raise ValueError(f'"{name}" must be positive and finite.')
    return value


def _nonnegative_float(value, name):
    value = float(value)
    if not np.isfinite(value) or value < 0:
        raise ValueError(f'"{name}" must be non-negative and finite.')
    return value


def _bounded_float(value, name, lower, upper):
    value = float(value)
    if not np.isfinite(value) or not lower < value <= upper:
        raise ValueError(f'"{name}" must be in the interval ({lower}, {upper}].')
    return value


def _event_profile(
    event_fuel_kwh,
    startup_steps,
    combustion_steps,
    startup_energy_fraction,
    dt_hours,
    startup_duration_hours,
    combustion_duration_hours,
):
    startup_energy = event_fuel_kwh * startup_energy_fraction
    combustion_energy = event_fuel_kwh * (1.0 - startup_energy_fraction)
    # The effective represented duration is step-count * dt.  This keeps
    # energy exact when a coarse input timestep cannot represent 30 minutes.
    startup_power = startup_energy / (startup_steps * dt_hours)
    combustion_power = combustion_energy / (combustion_steps * dt_hours)
    profile = np.concatenate(
        [
            np.full(startup_steps, startup_power, dtype=float),
            np.full(combustion_steps, combustion_power, dtype=float),
        ]
    )
    if not np.isclose(float(profile.sum() * dt_hours), event_fuel_kwh):
        raise RuntimeError("The wood-stove event profile is not energy normalized.")
    return profile


def _resolve_mask(value, n, name, default=True):
    if value is None:
        return np.full(n, default, dtype=bool)
    if np.isscalar(value):
        return np.full(n, bool(value), dtype=bool)
    array = np.asarray(
        value.to_numpy() if isinstance(value, (pd.Series, pd.DataFrame)) else value,
        dtype=bool,
    ).reshape(-1)
    if array.size != n:
        raise ValueError(f'"{name}" has length {array.size}, expected {n}.')
    return array


def _preview_5r1c_step(data, state, index):
    """Preview free-float temperature and ideal heat demand without stove heat."""

    return _solve_preview(data, state, index, 0.0, 0.0, 0.0)


def _solve_preview(data, state, index, source_air_kw, source_surface_kw, source_mass_kw):
    te = float(data["T_e"][index])
    tm = float(state.t_mass_c)
    dte = tm - te
    q_surface = float(data["Q_st"][index]) + source_surface_kw
    q_air = float(data["Q_st"][index]) + source_air_kw
    h_ms = data["H_ms"]
    h_is = data["H_is"]
    h_win = data["H_win"]
    h_vent = data["H_vent"]
    t_surface_free = (
        h_ms * tm + q_surface + q_air - (h_win + h_vent) * dte
    ) / h_ms
    t_air_free = t_surface_free + (q_air - h_vent * dte) / h_is

    t_lb = float(data["T_lb_arr"][index])
    t_surface_at_setpoint = (
        q_surface + h_ms * tm - h_win * dte + h_is * t_lb
    ) / (h_ms + h_is)
    required = max(
        0.0,
        h_vent * dte
        + h_is * (t_lb - t_surface_at_setpoint)
        - q_air,
    )
    if t_air_free >= t_lb:
        required = 0.0
    return _StepPreview(t_surface_free, t_air_free, required)


def _advance_5r1c_step(
    data,
    state,
    index,
    *,
    source_air_kw=0.0,
    source_surface_kw=0.0,
    source_mass_kw=0.0,
    auxiliary_enabled=False,
    cooling_enabled=False,
):
    """Advance one 5R1C step with explicit node sources."""

    preview = _solve_preview(
        data, state, index, source_air_kw, source_surface_kw, source_mass_kw
    )
    te = float(data["T_e"][index])
    tm = float(state.t_mass_c)
    dte = tm - te
    q_surface = float(data["Q_st"][index]) + source_surface_kw
    q_air = float(data["Q_st"][index]) + source_air_kw
    q_mass = float(data["Q_m"][index]) + source_mass_kw
    h_ms = data["H_ms"]
    h_is = data["H_is"]
    h_win = data["H_win"]
    h_vent = data["H_vent"]
    t_lb = float(data["T_lb_arr"][index])
    t_ub = float(data["T_ub_arr"][index])

    auxiliary_kw = 0.0
    cooling_kw = 0.0
    if preview.t_air_free_c < t_lb and auxiliary_enabled and data["heat_avail"][index]:
        t_surface = (
            q_surface + h_ms * tm - h_win * dte + h_is * t_lb
        ) / (h_ms + h_is)
        t_air = t_lb
        auxiliary_kw = max(
            0.0,
            h_vent * dte + h_is * (t_lb - t_surface) - q_air,
        )
    elif preview.t_air_free_c > t_ub and cooling_enabled and data["cool_avail"][index]:
        t_surface = (
            q_surface + h_ms * tm - h_win * dte + h_is * t_ub
        ) / (h_ms + h_is)
        t_air = t_ub
        cooling_kw = max(
            0.0,
            q_air - (h_vent * dte + h_is * (t_ub - t_surface)),
        )
    else:
        t_surface = preview.t_surface_free_c
        t_air = preview.t_air_free_c

    state_at_step = FiveR1CState(tm, t_surface, t_air)
    next_mass = tm + (
        q_mass
        - h_ms * (tm - t_surface)
        - (data["H_em"] + data["H_door"]) * dte
    ) * data["dt"] / data["C_m"]
    next_state = FiveR1CState(next_mass, t_surface, t_air)
    unmet = 0.0 if auxiliary_kw > 0.0 else preview.free_float_heating_kw
    # In a wood-only run, preview.free_float_heating_kw includes the residual
    # demand after stove source because preview was computed with that source.
    if preview.t_air_free_c >= t_lb:
        unmet = 0.0
    overheating = max(0.0, t_air - t_ub)
    return _StepAdvance(
        state_at_step=state_at_step,
        next_state=next_state,
        auxiliary_heating_kw=auxiliary_kw,
        cooling_kw=cooling_kw,
        unmet_heating_kw=unmet,
        overheating_c=overheating,
    )


def simulate_wood_stove_5r1c_bidirectional(
    model,
    *,
    heating_setpoint=None,
    cooling_setpoint=None,
    heating_mode="wood_only",
    efficiency=0.50,
    log_energy_kwh=7.5,
    logs_per_stere=219.0,
    pci_mj_per_kg=15.0,
    density_t_per_solid_m3=0.7,
    solid_m3_per_stere=0.64,
    max_logs_per_event=4,
    startup_duration_hours=0.5,
    combustion_duration_hours=1.0,
    startup_energy_fraction=0.20,
    trigger_delta_c=8.0,
    indoor_deficit_threshold_c=0.5,
    start_load_threshold_kw=0.25,
    min_event_interval_hours=3.0,
    operation_start_hour=8,
    operation_end_hour=23,
    air_fraction=0.70,
    surface_fraction=0.30,
    mass_fraction=0.00,
    timestep_minutes=None,
    availability=None,
    auxiliary_available=None,
    cooling_available=None,
    spinup_passes=5,
):
    """Run the opt-in causal wood-stove/5R1C coupling.

    ``model`` must be a ``Building5R1C`` instance (or wrapper exposing one as
    ``thermalmodel``).  The model's native timestep is used unless
    ``timestep_minutes`` is given; this first implementation does not silently
    resample hourly weather to 30 minutes.  Use a 30-minute model input for
    the physically intended startup resolution.
    """
    thermal_model = getattr(model, "thermalmodel", model)
    if isinstance(thermal_model, dict):
        # Keep configuration-equivalent input opt-in without importing the
        # thermal class at module import time.
        from .model5R1C import Building5R1C

        thermal_model = Building5R1C(thermal_model)
    prepare = getattr(thermal_model, "_prepare_direct_5r1c", None)
    if prepare is None:
        raise TypeError(
            "model must be a Building5R1C or a wrapper exposing thermalmodel."
        )
    if heating_mode not in {"wood_only", "wood_plus_auxiliary"}:
        raise ValueError(
            '"heating_mode" must be "wood_only" or "wood_plus_auxiliary".'
        )
    if not isinstance(spinup_passes, (int, np.integer)) or spinup_passes < 1:
        raise ValueError('"spinup_passes" must be a positive integer.')

    air_fraction = _nonnegative_float(air_fraction, "air_fraction")
    surface_fraction = _nonnegative_float(surface_fraction, "surface_fraction")
    mass_fraction = _nonnegative_float(mass_fraction, "mass_fraction")
    if not np.isclose(air_fraction + surface_fraction + mass_fraction, 1.0):
        raise ValueError("air_fraction + surface_fraction + mass_fraction must equal 1.")
    logs_per_stere = _positive_float(logs_per_stere, "logs_per_stere")
    pci_mj_per_kg = _positive_float(pci_mj_per_kg, "pci_mj_per_kg")
    density_t_per_solid_m3 = _positive_float(
        density_t_per_solid_m3, "density_t_per_solid_m3"
    )
    solid_m3_per_stere = _positive_float(solid_m3_per_stere, "solid_m3_per_stere")

    # Auxiliary heat is deliberately a separate mode/channel.  In wood-only
    # mode it is disabled even if the building's historical HVAC availability
    # would otherwise be true.
    n = len(thermal_model.times)
    auxiliary_enabled = _resolve_mask(
        auxiliary_available,
        n,
        "auxiliary_available",
        default=heating_mode == "wood_plus_auxiliary",
    )
    cooling_enabled = _resolve_mask(
        cooling_available,
        n,
        "cooling_available",
        default=heating_mode == "wood_plus_auxiliary",
    )
    data = prepare(
        heating_setpoint=heating_setpoint,
        cooling_setpoint=cooling_setpoint,
        heating_available=auxiliary_enabled,
        cooling_available=cooling_enabled,
    )
    dt = float(data["dt"])
    if timestep_minutes is not None:
        requested_dt = _positive_float(timestep_minutes, "timestep_minutes") / 60.0
        if not np.isclose(requested_dt, dt):
            raise ValueError(
                "timestep_minutes must match the Building5R1C native timestep; "
                "remeshing is not implicit in this first implementation."
            )

    stove_available = _resolve_mask(availability, n, "availability", default=True)
    controller_kwargs = {
        "timestep_hours": dt,
        "efficiency": efficiency,
        "log_energy_kwh": log_energy_kwh,
        "max_logs_per_event": max_logs_per_event,
        "startup_duration_hours": startup_duration_hours,
        "combustion_duration_hours": combustion_duration_hours,
        "startup_energy_fraction": startup_energy_fraction,
        "min_event_interval_hours": min_event_interval_hours,
        "trigger_delta_c": trigger_delta_c,
        "indoor_deficit_threshold_c": indoor_deficit_threshold_c,
        "start_load_threshold_kw": start_load_threshold_kw,
        "operation_start_hour": operation_start_hour,
        "operation_end_hour": operation_end_hour,
    }

    index = thermal_model.times.copy()
    final = None
    state = FiveR1CState(
        float(np.mean(data["T_lb_arr"])),
        float(np.mean(data["T_lb_arr"])),
        float(np.mean(data["T_lb_arr"])),
    )
    for _pass in range(int(spinup_passes)):
        pass_initial_mass = state.t_mass_c
        controller = WoodStoveController(**controller_kwargs)
        output = _run_coupled_pass(
            data,
            index,
            state,
            controller,
            stove_available,
            air_fraction,
            surface_fraction,
            mass_fraction,
            auxiliary_enabled,
            cooling_enabled,
        )
        final = output
        state = output["final_state"]
        if abs(state.t_mass_c - pass_initial_mass) < 0.01:
            break

    return _build_result(
        final,
        index,
        heating_mode=heating_mode,
        efficiency=float(efficiency),
        log_energy_kwh=float(log_energy_kwh),
        logs_per_stere=logs_per_stere,
        pci_mj_per_kg=pci_mj_per_kg,
        density_t_per_solid_m3=density_t_per_solid_m3,
        solid_m3_per_stere=solid_m3_per_stere,
        air_fraction=air_fraction,
        surface_fraction=surface_fraction,
        mass_fraction=mass_fraction,
        dt=dt,
        scenario_parameters={
            "efficiency": float(efficiency),
            "log_energy_kwh": float(log_energy_kwh),
            "logs_per_stere": logs_per_stere,
            "pci_mj_per_kg": pci_mj_per_kg,
            "density_t_per_solid_m3": density_t_per_solid_m3,
            "solid_m3_per_stere": solid_m3_per_stere,
            "startup_duration_hours": float(startup_duration_hours),
            "combustion_duration_hours": float(combustion_duration_hours),
            "startup_energy_fraction": float(startup_energy_fraction),
            "max_logs_per_event": int(max_logs_per_event),
            "trigger_delta_c": float(trigger_delta_c),
            "indoor_deficit_threshold_c": float(indoor_deficit_threshold_c),
            "start_load_threshold_kw": float(start_load_threshold_kw),
            "min_event_interval_hours": float(min_event_interval_hours),
            "operation_start_hour": int(operation_start_hour),
            "operation_end_hour": int(operation_end_hour),
        },
    )


def _run_coupled_pass(
    data,
    index,
    initial_state,
    controller,
    stove_available,
    air_fraction,
    surface_fraction,
    mass_fraction,
    auxiliary_enabled,
    cooling_enabled,
):
    n = data["N"]
    state = initial_state
    t_air = np.zeros(n)
    t_surface = np.zeros(n)
    t_mass = np.zeros(n)
    free_demand = np.zeros(n)
    fuel_input = np.zeros(n)
    useful_heat = np.zeros(n)
    auxiliary = np.zeros(n)
    cooling = np.zeros(n)
    unmet = np.zeros(n)
    overheating = np.zeros(n)
    event_start = np.zeros(n, dtype=bool)
    event_logs = np.zeros(n, dtype=int)
    event_state = np.full(n, "off", dtype=object)
    event_fuel = np.zeros(n)
    event_useful = np.zeros(n)

    for i in range(n):
        preview = _preview_5r1c_step(data, state, i)
        free_demand[i] = preview.free_float_heating_kw
        timestamp = index[i]
        observation = StoveObservation(
            timestamp=timestamp,
            t_ext_c=float(data["T_e"][i]),
            t_air_c=float(state.t_air_c),
            t_surface_c=float(state.t_surface_c),
            t_mass_c=float(state.t_mass_c),
            heating_setpoint_c=float(data["T_lb_arr"][i]),
            cooling_setpoint_c=float(data["T_ub_arr"][i]),
            free_float_heating_kw=preview.free_float_heating_kw,
            available=bool(stove_available[i])
            and i + controller.startup_steps + controller.combustion_steps <= n,
        )
        command = controller.step(observation)
        source_air = command.useful_heat_kw * air_fraction
        source_surface = command.useful_heat_kw * surface_fraction
        source_mass = command.useful_heat_kw * mass_fraction
        advanced = _advance_5r1c_step(
            data,
            state,
            i,
            source_air_kw=source_air,
            source_surface_kw=source_surface,
            source_mass_kw=source_mass,
            auxiliary_enabled=bool(auxiliary_enabled[i]),
            cooling_enabled=bool(cooling_enabled[i]),
        )
        state = advanced.next_state
        t_air[i] = advanced.state_at_step.t_air_c
        t_surface[i] = advanced.state_at_step.t_surface_c
        t_mass[i] = advanced.state_at_step.t_mass_c
        fuel_input[i] = command.fuel_input_kw
        useful_heat[i] = command.useful_heat_kw
        auxiliary[i] = advanced.auxiliary_heating_kw
        cooling[i] = advanced.cooling_kw
        unmet[i] = advanced.unmet_heating_kw
        overheating[i] = advanced.overheating_c
        event_start[i] = command.event_start
        event_logs[i] = command.logs_loaded
        event_state[i] = command.event_state
        event_fuel[i] = command.fuel_energy_kwh if command.event_start else 0.0
        event_useful[i] = command.useful_energy_kwh

    return {
        "final_state": state,
        "T_air": t_air,
        "T_s": t_surface,
        "T_m": t_mass,
        "free_float_heating_demand_kw": free_demand,
        "Q_wood_fuel_kw": fuel_input,
        "Q_wood_useful_kw": useful_heat,
        "auxiliary_heating_kw": auxiliary,
        "cooling_kw": cooling,
        "unmet_heating_kw": unmet,
        "overheating_c": overheating,
        "event_start": event_start,
        "event_logs": event_logs,
        "event_state": event_state,
        "event_fuel_input_kwh": event_fuel,
        "wood_useful_energy_kwh": float(np.sum(useful_heat) * data["dt"]),
        "fuel_energy_consumed_kwh": float(np.sum(fuel_input) * data["dt"]),
        "auxiliary_heating_energy_kwh": float(np.sum(auxiliary) * data["dt"]),
        "unmet_heating_energy_kwh": float(np.sum(unmet) * data["dt"]),
        "overheating_degree_hours": float(np.sum(overheating) * data["dt"]),
        "event_count": controller.state.event_count,
        "wood_logs_burned": controller.state.logs_burned,
        "T_e": np.asarray(data["T_e"], dtype=float),
        "Heating Setpoint": np.asarray(data["T_lb_arr"], dtype=float),
        "Cooling Setpoint": np.asarray(data["T_ub_arr"], dtype=float),
        "Electricity Load": np.asarray(data["elec"], dtype=float),
    }


def _build_result(
    output,
    index,
    *,
    heating_mode,
    efficiency,
    log_energy_kwh,
    logs_per_stere,
    pci_mj_per_kg,
    density_t_per_solid_m3,
    solid_m3_per_stere,
    air_fraction,
    surface_fraction,
    mass_fraction,
    dt,
    scenario_parameters,
):
    fuel_energy = output["fuel_energy_consumed_kwh"]
    mass_kg = fuel_energy * 3.6 / pci_mj_per_kg
    volume_stere = output["wood_logs_burned"] / logs_per_stere
    volume_solid = volume_stere * solid_m3_per_stere
    frame = pd.DataFrame(
        {
            "T_air": output["T_air"],
            "T_s": output["T_s"],
            "T_m": output["T_m"],
            "T_e": output["T_e"],
            "free_float_heating_demand_kw": output[
                "free_float_heating_demand_kw"
            ],
            "Q_wood_fuel_kw": output["Q_wood_fuel_kw"],
            "Q_wood_useful_kw": output["Q_wood_useful_kw"],
            "auxiliary_heating_kw": output["auxiliary_heating_kw"],
            "cooling_kw": output["cooling_kw"],
            "unmet_heating_kw": output["unmet_heating_kw"],
            "overheating_c": output["overheating_c"],
            "event_start": output["event_start"],
            "event_logs": output["event_logs"],
            "event_state": output["event_state"],
            "event_fuel_input_kwh": output["event_fuel_input_kwh"],
        },
        index=index,
    )
    # Add the base-building signals after constructing the frame so a missing
    # value can never silently masquerade as a wood-stove quantity.
    if "T_e" in output:
        frame["T_e"] = output["T_e"]
    if "Heating Setpoint" in output:
        frame["Heating Setpoint"] = output["Heating Setpoint"]
    if "Cooling Setpoint" in output:
        frame["Cooling Setpoint"] = output["Cooling Setpoint"]
    if "Electricity Load" in output:
        frame["Electricity Load"] = output["Electricity Load"]
    return BidirectionalWoodStoveResult(
        detailed_results=frame,
        heating_mode=heating_mode,
        efficiency=efficiency,
        log_energy_kwh=log_energy_kwh,
        logs_per_stere=logs_per_stere,
        event_count=output["event_count"],
        wood_logs_burned=output["wood_logs_burned"],
        fuel_energy_consumed_kwh=fuel_energy,
        wood_useful_energy_kwh=output["wood_useful_energy_kwh"],
        auxiliary_heating_energy_kwh=output["auxiliary_heating_energy_kwh"],
        unmet_heating_energy_kwh=output["unmet_heating_energy_kwh"],
        overheating_degree_hours=output["overheating_degree_hours"],
        wood_mass_kg=mass_kg,
        wood_volume_solid_m3=volume_solid,
        wood_volume_stere=volume_stere,
        air_fraction=air_fraction,
        surface_fraction=surface_fraction,
        mass_fraction=mass_fraction,
        dt_hours=dt,
        scenario_parameters=scenario_parameters,
    )


__all__ = [
    "BidirectionalWoodStoveResult",
    "FiveR1CState",
    "StoveCommand",
    "StoveObservation",
    "WoodStoveController",
    "WoodStoveControllerState",
    "simulate_wood_stove_5r1c_bidirectional",
]
