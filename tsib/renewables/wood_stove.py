"""Energy-balanced residential wood-stove simulation helpers.

The MVP in this module is deliberately a system-layer model: it receives useful
space-heating demand from a building model, allocates a fuel-energy target to
that demand, and reports useful heat, fuel input, and unallocated energy. It
does not model combustion chemistry, indoor temperature feedback, or emissions.
The target-based event model adds a low-dimensional thermal store and discrete
fuel loads, while keeping the same post-processing boundary around the 5R1C
demand. The predictive event model is target-free: it derives finite log loads
from demand, outdoor temperature and a declared operating heuristic.
"""

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class WoodStoveResult:
    """Outputs from simulate_wood_stove."""

    heating_load_kw: pd.Series
    useful_heat_kw: pd.Series
    fuel_input_kw: pd.Series
    target_fuel_energy_kwh: float
    target_useful_energy_kwh: float
    assigned_useful_energy_kwh: float
    assigned_fuel_energy_kwh: float
    unallocated_useful_energy_kwh: float
    unallocated_fuel_energy_kwh: float
    unmet_heating_energy_kwh: float
    wood_mass_kg: float
    wood_volume_solid_m3: float
    wood_volume_stere: float
    efficiency: float
    dt_hours: float

    def as_dict(self):
        """Return scalar and hourly outputs in a serializable mapping."""
        return {
            "heating_load_kw": self.heating_load_kw,
            "useful_heat_kw": self.useful_heat_kw,
            "fuel_input_kw": self.fuel_input_kw,
            "target_fuel_energy_kwh": self.target_fuel_energy_kwh,
            "target_useful_energy_kwh": self.target_useful_energy_kwh,
            "assigned_useful_energy_kwh": self.assigned_useful_energy_kwh,
            "assigned_fuel_energy_kwh": self.assigned_fuel_energy_kwh,
            "unallocated_useful_energy_kwh": self.unallocated_useful_energy_kwh,
            "unallocated_fuel_energy_kwh": self.unallocated_fuel_energy_kwh,
            "unmet_heating_energy_kwh": self.unmet_heating_energy_kwh,
            "wood_mass_kg": self.wood_mass_kg,
            "wood_volume_solid_m3": self.wood_volume_solid_m3,
            "wood_volume_stere": self.wood_volume_stere,
            "efficiency": self.efficiency,
            "dt_hours": self.dt_hours,
        }


@dataclass(frozen=True)
class WoodStoveEventResult:
    """Outputs from :func:`simulate_wood_stove_events`.

    ``storage_kwh`` is the end-of-timestep useful thermal energy remaining in
    the stove store. ``combustion_heat_kw`` is heat produced by combustion
    after stove efficiency and before storage charge losses. ``useful_heat_kw``
    is the heat actually delivered to the 5R1C heating-load channel.
    """

    heating_load_kw: pd.Series
    combustion_heat_kw: pd.Series
    useful_heat_kw: pd.Series
    fuel_input_kw: pd.Series
    storage_kwh: pd.Series
    storage_loss_kwh: pd.Series
    storage_spill_kwh: pd.Series
    event_start: pd.Series
    event_fuel_input_kwh: pd.Series
    event_state: pd.Series
    target_fuel_energy_kwh: float
    target_useful_energy_kwh: float
    assigned_useful_energy_kwh: float
    assigned_fuel_energy_kwh: float
    unallocated_useful_energy_kwh: float
    unallocated_fuel_energy_kwh: float
    unmet_heating_energy_kwh: float
    stored_energy_end_kwh: float
    storage_loss_energy_kwh: float
    storage_spill_energy_kwh: float
    wood_mass_kg: float
    wood_volume_solid_m3: float
    wood_volume_stere: float
    efficiency: float
    dt_hours: float
    event_count: int

    def as_dict(self):
        """Return scalar and timestep outputs in a serializable mapping."""
        return {
            "heating_load_kw": self.heating_load_kw,
            "combustion_heat_kw": self.combustion_heat_kw,
            "useful_heat_kw": self.useful_heat_kw,
            "fuel_input_kw": self.fuel_input_kw,
            "storage_kwh": self.storage_kwh,
            "storage_loss_kwh": self.storage_loss_kwh,
            "storage_spill_kwh": self.storage_spill_kwh,
            "event_start": self.event_start,
            "event_fuel_input_kwh": self.event_fuel_input_kwh,
            "event_state": self.event_state,
            "target_fuel_energy_kwh": self.target_fuel_energy_kwh,
            "target_useful_energy_kwh": self.target_useful_energy_kwh,
            "assigned_useful_energy_kwh": self.assigned_useful_energy_kwh,
            "assigned_fuel_energy_kwh": self.assigned_fuel_energy_kwh,
            "unallocated_useful_energy_kwh": self.unallocated_useful_energy_kwh,
            "unallocated_fuel_energy_kwh": self.unallocated_fuel_energy_kwh,
            "unmet_heating_energy_kwh": self.unmet_heating_energy_kwh,
            "stored_energy_end_kwh": self.stored_energy_end_kwh,
            "storage_loss_energy_kwh": self.storage_loss_energy_kwh,
            "storage_spill_energy_kwh": self.storage_spill_energy_kwh,
            "wood_mass_kg": self.wood_mass_kg,
            "wood_volume_solid_m3": self.wood_volume_solid_m3,
            "wood_volume_stere": self.wood_volume_stere,
            "efficiency": self.efficiency,
            "dt_hours": self.dt_hours,
            "event_count": self.event_count,
        }


@dataclass(frozen=True)
class WoodStovePredictiveEventResult:
    """Outputs from the target-free, demand-driven event model.

    Unlike :class:`WoodStoveEventResult`, this result has no annual fuel
    target.  Fuel is generated by discrete log loads selected from the
    heating demand, outdoor-temperature trigger and operating schedule.
    """

    heating_load_kw: pd.Series
    outdoor_temperature_c: pd.Series
    heating_setpoint_c: pd.Series
    temperature_trigger_gap_c: pd.Series
    potential_useful_heat_kw: pd.Series
    useful_heat_kw: pd.Series
    fuel_input_kw: pd.Series
    event_start: pd.Series
    event_logs: pd.Series
    event_state: pd.Series
    fuel_energy_consumed_kwh: float
    potential_useful_energy_kwh: float
    assigned_useful_energy_kwh: float
    excess_useful_energy_kwh: float
    unmet_heating_energy_kwh: float
    wood_logs_burned: float
    wood_mass_kg: float
    wood_volume_stere: float
    wood_volume_solid_m3: float
    efficiency: float
    log_energy_kwh: float
    logs_per_stere: float
    event_count: int
    dt_hours: float
    trigger_delta_c: float
    start_load_threshold_kw: float
    operation_start_hour: int
    operation_end_hour: int

    def as_dict(self):
        """Return scalar and timestep outputs in a serializable mapping."""
        return {
            "heating_load_kw": self.heating_load_kw,
            "outdoor_temperature_c": self.outdoor_temperature_c,
            "heating_setpoint_c": self.heating_setpoint_c,
            "temperature_trigger_gap_c": self.temperature_trigger_gap_c,
            "potential_useful_heat_kw": self.potential_useful_heat_kw,
            "useful_heat_kw": self.useful_heat_kw,
            "fuel_input_kw": self.fuel_input_kw,
            "event_start": self.event_start,
            "event_logs": self.event_logs,
            "event_state": self.event_state,
            "fuel_energy_consumed_kwh": self.fuel_energy_consumed_kwh,
            "potential_useful_energy_kwh": self.potential_useful_energy_kwh,
            "assigned_useful_energy_kwh": self.assigned_useful_energy_kwh,
            "excess_useful_energy_kwh": self.excess_useful_energy_kwh,
            "unmet_heating_energy_kwh": self.unmet_heating_energy_kwh,
            "wood_logs_burned": self.wood_logs_burned,
            "wood_mass_kg": self.wood_mass_kg,
            "wood_volume_stere": self.wood_volume_stere,
            "wood_volume_solid_m3": self.wood_volume_solid_m3,
            "efficiency": self.efficiency,
            "log_energy_kwh": self.log_energy_kwh,
            "logs_per_stere": self.logs_per_stere,
            "event_count": self.event_count,
            "dt_hours": self.dt_hours,
            "trigger_delta_c": self.trigger_delta_c,
            "start_load_threshold_kw": self.start_load_threshold_kw,
            "operation_start_hour": self.operation_start_hour,
            "operation_end_hour": self.operation_end_hour,
        }


def _coerce_hourly(value, n, name, dtype=float):
    """Convert a scalar or sequence to a validated one-dimensional array."""
    if np.isscalar(value):
        array = np.full(n, value, dtype=dtype)
    else:
        array = np.asarray(
            value.to_numpy() if isinstance(value, pd.Series) else value,
            dtype=dtype,
        ).reshape(-1)
        if array.size != n:
            raise ValueError(f'"{name}" has length {array.size}, expected {n}.')
    return array


def _resolve_index_and_load(heating_load):
    if isinstance(heating_load, pd.Series):
        index = heating_load.index.copy()
        load = heating_load.to_numpy(dtype=float)
    else:
        load = np.asarray(heating_load, dtype=float).reshape(-1)
        index = pd.RangeIndex(load.size)
    if load.size == 0:
        raise ValueError('"heating_load" must contain at least one timestep.')
    if not np.all(np.isfinite(load)):
        raise ValueError('heating_load contains non-finite values.')
    if np.any(load < 0):
        raise ValueError('"heating_load must be non-negative.')
    return index, load


def _resolve_dt(index, dt_hours):
    if dt_hours is not None:
        dt = float(dt_hours)
        if not np.isfinite(dt) or dt <= 0:
            raise ValueError('"dt_hours" must be positive and finite.')
        return dt

    if isinstance(index, pd.DatetimeIndex) and len(index) > 1:
        differences = (
            index.to_series()
            .diff()
            .dropna()
            .dt.total_seconds()
            .to_numpy()
            / 3600.0
        )
        if not np.all(np.isfinite(differences)) or np.any(differences <= 0):
            raise ValueError('DatetimeIndex must be strictly increasing.')
        if not np.allclose(differences, differences[0]):
            raise ValueError(
                'DatetimeIndex must have a regular timestep; provide dt_hours '
                'for a custom schedule.'
            )
        return float(differences[0])

    return 1.0


def _allocate_useful_heat(load, capacity, weights, dt, target):
    """Allocate target useful energy under per-timestep power constraints."""
    useful = np.zeros_like(load, dtype=float)
    active = (capacity > 0) & (weights > 0)
    remaining = float(target)
    tolerance = max(1e-12, target * 1e-12)

    while remaining > tolerance and np.any(active):
        active_ix = np.flatnonzero(active)
        denominator = float(np.sum(weights[active_ix] * dt))
        if denominator <= 0:
            break

        proposed = remaining * weights[active_ix] / denominator
        capped = proposed >= capacity[active_ix] - tolerance

        if not np.any(capped):
            useful[active_ix] = proposed
            remaining = 0.0
            break

        capped_ix = active_ix[capped]
        useful[capped_ix] = capacity[capped_ix]
        remaining -= float(np.sum(useful[capped_ix] * dt))
        active[capped_ix] = False

    return useful, max(0.0, remaining)


def simulate_wood_stove_predictive_events(
    heating_load,
    outdoor_temperature_c,
    heating_setpoint_c,
    dt_hours=None,
    efficiency=0.50,
    pci_mj_per_kg=15.0,
    density_t_per_solid_m3=0.7,
    solid_m3_per_stere=0.64,
    log_energy_kwh=7.5,
    logs_per_stere=219.0,
    max_logs_per_event=4,
    startup_duration_hours=0.5,
    combustion_duration_hours=1.0,
    startup_energy_fraction=0.20,
    min_event_interval_hours=3.0,
    trigger_delta_c=8.0,
    start_load_threshold_kw=0.25,
    indoor_temperature_c=None,
    indoor_deficit_threshold_c=0.5,
    availability=None,
    operation_start_hour=8,
    operation_end_hour=23,
):
    """Predict wood consumption from demand and discrete log-burning events.

    This path deliberately does not accept an annual fuel target.  An event is
    started when the available heating demand is positive, the outdoor
    temperature trigger ``heating_setpoint_c - outdoor_temperature_c`` exceeds
    ``trigger_delta_c``, and the stove is available.  The number of logs is
    selected from the instantaneous demand and is limited to one through
    ``max_logs_per_event``.

    Each log contains ``log_energy_kwh`` of chemical energy.  The default event
    has a 30-minute startup phase and a one-hour combustion phase.  Twenty
    percent of the chemical energy is assigned to startup by default; this
    parameter is explicit because the supplied physical information defines
    the duration but not the phase energy split.  A package which produces
    more useful heat than the current demand reports the difference as
    ``excess_useful_energy_kwh``; it is not removed from fuel consumption.

    The model is a first predictive event layer over a precomputed 5R1C load.
    It does not yet feed the delivered stove heat back into the 5R1C indoor
    temperature state.  That feedback is the next coupling step.

    Parameters
    ----------
    heating_load : pandas.Series or array-like
        Useful space-heating demand in kW from 5R1C.
    outdoor_temperature_c, heating_setpoint_c : scalar or array-like
        Outdoor temperature and heating setpoint for each timestep.
    dt_hours : float, optional
        Timestep in hours; inferred from a regular DatetimeIndex when omitted.
    efficiency, pci_mj_per_kg, density_t_per_solid_m3, solid_m3_per_stere : float
        Fuel conversion parameters. ``logs_per_stere`` controls the reported
        volume directly from the discrete number of burned logs.
    log_energy_kwh : float
        Chemical energy in one log.
    logs_per_stere : float
        Number of logs represented by one stacked cubic metre.
    max_logs_per_event : int
        Maximum number of logs loaded at one event.
    startup_duration_hours, combustion_duration_hours : float
        Event phases. Both must be integer multiples of ``dt_hours``.
    startup_energy_fraction : float
        Fraction of event chemical energy consumed during startup.
    min_event_interval_hours : float
        Minimum interval between event starts.
    trigger_delta_c : float
        Minimum value of ``heating_setpoint_c - outdoor_temperature_c`` for a
        new event.
    start_load_threshold_kw : float
        Minimum heating demand used as an additional firing trigger.
    indoor_temperature_c : scalar or array-like, optional
        Optional indoor-temperature signal. If provided, an indoor deficit
        can activate the demand trigger, but the outdoor trigger remains
        mandatory.
    availability : scalar or array-like of bool, optional
        Explicit availability mask. When omitted and a DatetimeIndex is used,
        starts are allowed from ``operation_start_hour`` inclusive to
        ``operation_end_hour`` exclusive.
    operation_start_hour, operation_end_hour : int
        Default daily starting window when availability is not provided.

    Returns
    -------
    WoodStovePredictiveEventResult
        Predicted fuel use, event timing, useful heat and balance diagnostics.
    """
    index, load = _resolve_index_and_load(heating_load)
    n = load.size
    dt = _resolve_dt(index, dt_hours)

    def resolve_signal(value, name):
        if np.isscalar(value):
            array = np.full(n, value, dtype=float)
        else:
            array = np.asarray(
                value.to_numpy() if isinstance(value, pd.Series) else value,
                dtype=float,
            ).reshape(-1)
            if array.size != n:
                raise ValueError(f'"{name}" has length {array.size}, expected {n}.')
        if not np.all(np.isfinite(array)):
            raise ValueError(f'"{name}" must be finite.')
        return array

    outdoor = resolve_signal(outdoor_temperature_c, "outdoor_temperature_c")
    setpoint = resolve_signal(heating_setpoint_c, "heating_setpoint_c")
    indoor = (
        None
        if indoor_temperature_c is None
        else resolve_signal(indoor_temperature_c, "indoor_temperature_c")
    )

    efficiency = float(efficiency)
    if not np.isfinite(efficiency) or not 0 < efficiency <= 1:
        raise ValueError('"efficiency" must be in the interval (0, 1].')

    pci_mj_per_kg = float(pci_mj_per_kg)
    if not np.isfinite(pci_mj_per_kg) or pci_mj_per_kg <= 0:
        raise ValueError('"pci_mj_per_kg" must be positive and finite.')

    density_t_per_solid_m3 = float(density_t_per_solid_m3)
    if not np.isfinite(density_t_per_solid_m3) or density_t_per_solid_m3 <= 0:
        raise ValueError(
            '"density_t_per_solid_m3" must be positive and finite.'
        )

    solid_m3_per_stere = float(solid_m3_per_stere)
    if not np.isfinite(solid_m3_per_stere) or solid_m3_per_stere <= 0:
        raise ValueError('"solid_m3_per_stere" must be positive and finite.')

    log_energy_kwh = float(log_energy_kwh)
    if not np.isfinite(log_energy_kwh) or log_energy_kwh <= 0:
        raise ValueError('"log_energy_kwh" must be positive and finite.')

    logs_per_stere = float(logs_per_stere)
    if not np.isfinite(logs_per_stere) or logs_per_stere <= 0:
        raise ValueError('"logs_per_stere" must be positive and finite.')

    max_logs_per_event = int(max_logs_per_event)
    if max_logs_per_event < 1:
        raise ValueError('"max_logs_per_event" must be at least one.')

    startup_duration_hours = float(startup_duration_hours)
    combustion_duration_hours = float(combustion_duration_hours)
    if (
        not np.isfinite(startup_duration_hours)
        or startup_duration_hours <= 0
        or not np.isfinite(combustion_duration_hours)
        or combustion_duration_hours <= 0
    ):
        raise ValueError("event phase durations must be positive and finite.")
    startup_steps_float = startup_duration_hours / dt
    combustion_steps_float = combustion_duration_hours / dt
    startup_steps = int(round(startup_steps_float))
    combustion_steps = int(round(combustion_steps_float))
    if (
        startup_steps < 1
        or combustion_steps < 1
        or not np.isclose(startup_steps_float, startup_steps)
        or not np.isclose(combustion_steps_float, combustion_steps)
    ):
        raise ValueError(
            "event phase durations must be positive multiples of dt_hours."
        )

    startup_energy_fraction = float(startup_energy_fraction)
    if not np.isfinite(startup_energy_fraction) or not 0 <= startup_energy_fraction <= 1:
        raise ValueError('"startup_energy_fraction" must be in [0, 1].')

    min_event_interval_hours = float(min_event_interval_hours)
    if not np.isfinite(min_event_interval_hours) or min_event_interval_hours < 0:
        raise ValueError(
            '"min_event_interval_hours" must be non-negative and finite.'
        )
    min_event_steps = max(1, int(np.ceil(min_event_interval_hours / dt)))

    trigger_delta_c = float(trigger_delta_c)
    start_load_threshold_kw = float(start_load_threshold_kw)
    indoor_deficit_threshold_c = float(indoor_deficit_threshold_c)
    if not np.isfinite(trigger_delta_c) or trigger_delta_c < 0:
        raise ValueError('"trigger_delta_c" must be non-negative and finite.')
    if not np.isfinite(start_load_threshold_kw) or start_load_threshold_kw < 0:
        raise ValueError(
            '"start_load_threshold_kw" must be non-negative and finite.'
        )
    if (
        not np.isfinite(indoor_deficit_threshold_c)
        or indoor_deficit_threshold_c < 0
    ):
        raise ValueError(
            '"indoor_deficit_threshold_c" must be non-negative and finite.'
        )

    operation_start_hour = int(operation_start_hour)
    operation_end_hour = int(operation_end_hour)
    if not 0 <= operation_start_hour < operation_end_hour <= 24:
        raise ValueError(
            "operation hours must satisfy 0 <= start < end <= 24."
        )

    if availability is None:
        if isinstance(index, pd.DatetimeIndex):
            available = (
                (index.hour >= operation_start_hour)
                & (index.hour < operation_end_hour)
            )
        else:
            available = np.ones(n, dtype=bool)
    else:
        available = _coerce_hourly(availability, n, "availability", dtype=bool)

    event_steps = startup_steps + combustion_steps
    profile = np.concatenate(
        [
            np.full(
                startup_steps,
                startup_energy_fraction / startup_duration_hours,
                dtype=float,
            ),
            np.full(
                combustion_steps,
                (1.0 - startup_energy_fraction) / combustion_duration_hours,
                dtype=float,
            ),
        ]
    )
    if not np.isclose(float(np.sum(profile) * dt), 1.0):
        raise RuntimeError("The predictive event energy profile is not normalized.")

    temperature_gap = setpoint - outdoor
    indoor_deficit = (
        np.zeros(n, dtype=float)
        if indoor is None
        else np.maximum(setpoint - indoor, 0.0)
    )
    demand_trigger = (load >= start_load_threshold_kw) | (
        indoor_deficit >= indoor_deficit_threshold_c
    )
    trigger = (temperature_gap >= trigger_delta_c) & demand_trigger

    potential_useful = np.zeros(n, dtype=float)
    useful = np.zeros(n, dtype=float)
    fuel_input = np.zeros(n, dtype=float)
    event_start = np.zeros(n, dtype=bool)
    event_logs = np.zeros(n, dtype=float)
    event_state = np.full(n, "off", dtype=object)

    current_profile = None
    current_logs = 0
    current_profile_index = 0
    next_event_step = 0
    event_count = 0
    total_logs = 0.0

    for step in range(n):
        if (
            current_profile is None
            and step >= next_event_step
            and step + event_steps <= n
            and available[step]
            and trigger[step]
        ):
            required_useful_energy = max(
                load[step], start_load_threshold_kw
            ) * (startup_duration_hours + combustion_duration_hours)
            useful_per_log = log_energy_kwh * efficiency
            current_logs = int(
                np.clip(
                    np.ceil(required_useful_energy / useful_per_log),
                    1,
                    max_logs_per_event,
                )
            )
            current_profile = current_logs * log_energy_kwh * profile
            current_profile_index = 0
            event_start[step] = True
            event_logs[step] = current_logs
            event_count += 1
            total_logs += current_logs
            next_event_step = step + min_event_steps

        if current_profile is not None:
            fuel_input[step] = current_profile[current_profile_index]
            potential_useful[step] = fuel_input[step] * efficiency
            useful[step] = min(load[step], potential_useful[step])
            if current_profile_index < startup_steps:
                event_state[step] = "startup"
            else:
                event_state[step] = "combustion"
            current_profile_index += 1
            if current_profile_index >= current_profile.size:
                current_profile = None
                current_logs = 0

    fuel_energy = float(np.sum(fuel_input) * dt)
    potential_useful_energy = float(np.sum(potential_useful) * dt)
    assigned_useful = float(np.sum(useful) * dt)
    excess_useful = max(0.0, potential_useful_energy - assigned_useful)
    unmet_heating = float(np.sum(np.maximum(load - useful, 0.0)) * dt)
    mass_kg = fuel_energy * 3.6 / pci_mj_per_kg
    volume_stere = fuel_energy / log_energy_kwh / logs_per_stere
    solid_volume = volume_stere * solid_m3_per_stere

    return WoodStovePredictiveEventResult(
        heating_load_kw=pd.Series(load, index=index, name="heating_load_kw"),
        outdoor_temperature_c=pd.Series(
            outdoor, index=index, name="outdoor_temperature_c"
        ),
        heating_setpoint_c=pd.Series(
            setpoint, index=index, name="heating_setpoint_c"
        ),
        temperature_trigger_gap_c=pd.Series(
            temperature_gap, index=index, name="temperature_trigger_gap_c"
        ),
        potential_useful_heat_kw=pd.Series(
            potential_useful, index=index, name="potential_useful_heat_kw"
        ),
        useful_heat_kw=pd.Series(useful, index=index, name="useful_heat_kw"),
        fuel_input_kw=pd.Series(fuel_input, index=index, name="fuel_input_kw"),
        event_start=pd.Series(event_start, index=index, name="event_start"),
        event_logs=pd.Series(event_logs, index=index, name="event_logs"),
        event_state=pd.Series(event_state, index=index, name="event_state"),
        fuel_energy_consumed_kwh=fuel_energy,
        potential_useful_energy_kwh=potential_useful_energy,
        assigned_useful_energy_kwh=assigned_useful,
        excess_useful_energy_kwh=excess_useful,
        unmet_heating_energy_kwh=unmet_heating,
        wood_logs_burned=fuel_energy / log_energy_kwh,
        wood_mass_kg=mass_kg,
        wood_volume_stere=volume_stere,
        wood_volume_solid_m3=solid_volume,
        efficiency=efficiency,
        log_energy_kwh=log_energy_kwh,
        logs_per_stere=logs_per_stere,
        event_count=event_count,
        dt_hours=dt,
        trigger_delta_c=trigger_delta_c,
        start_load_threshold_kw=start_load_threshold_kw,
        operation_start_hour=operation_start_hour,
        operation_end_hour=operation_end_hour,
    )


def _heating_load_from_5r1c(source, heating_column):
    """Extract a 5R1C heating-load Series without changing the source."""
    if isinstance(source, pd.DataFrame):
        detailed_results = source
    elif hasattr(source, "thermalmodel"):
        detailed_results = getattr(source.thermalmodel, "detailedResults", None)
    else:
        detailed_results = getattr(source, "detailedResults", None)

    if not isinstance(detailed_results, pd.DataFrame):
        raise TypeError(
            "source must be a 5R1C model, a Building wrapper, or a "
            "DataFrame containing detailedResults."
        )
    if heating_column not in detailed_results:
        raise ValueError(
            f'5R1C results do not contain "{heating_column}". '
            "Run sim_demand_direct() or sim5R1C() before connecting the stove."
        )

    heating_load = detailed_results[heating_column]
    if not isinstance(heating_load, pd.Series):
        heating_load = pd.Series(heating_load, index=detailed_results.index)
    return heating_load


def simulate_wood_stove_predictive_events_from_5r1c(
    source,
    *,
    outdoor_temperature_c=None,
    heating_setpoint_c=None,
    dt_hours=None,
    heating_column="Heating Load",
    outdoor_column="T_e",
    heating_setpoint_column="Heating Setpoint",
    **stove_kwargs,
):
    """Run the predictive event model from completed 5R1C results.

    ``source`` is read-only.  When no explicit outdoor temperature or heating
    setpoint is supplied, the adapter reads ``T_e`` and ``Heating Setpoint``
    from ``detailedResults``.  The adapter requires these columns because the
    predictive event rule must be driven by an explicit temperature signal,
    rather than by an annual REDPE fuel target.
    """
    if isinstance(source, pd.DataFrame):
        detailed_results = source
    elif hasattr(source, "thermalmodel"):
        detailed_results = getattr(source.thermalmodel, "detailedResults", None)
    else:
        detailed_results = getattr(source, "detailedResults", None)

    if not isinstance(detailed_results, pd.DataFrame):
        raise TypeError(
            "source must be a 5R1C model, a Building wrapper, or a "
            "DataFrame containing detailedResults."
        )

    heating_load = _heating_load_from_5r1c(source, heating_column)
    if outdoor_temperature_c is None:
        if outdoor_column not in detailed_results:
            raise ValueError(
                f'5R1C results do not contain "{outdoor_column}"; provide '
                "outdoor_temperature_c explicitly."
            )
        outdoor_temperature_c = detailed_results[outdoor_column]
    if heating_setpoint_c is None:
        if heating_setpoint_column not in detailed_results:
            raise ValueError(
                f'5R1C results do not contain "{heating_setpoint_column}"; '
                "provide heating_setpoint_c explicitly."
            )
        heating_setpoint_c = detailed_results[heating_setpoint_column]

    return simulate_wood_stove_predictive_events(
        heating_load,
        outdoor_temperature_c=outdoor_temperature_c,
        heating_setpoint_c=heating_setpoint_c,
        dt_hours=dt_hours,
        **stove_kwargs,
    )


def simulate_wood_stove(
    heating_load,
    dt_hours=None,
    fuel_energy_target_kwh=None,
    efficiency=0.50,
    pci_mj_per_kg=15.0,
    density_t_per_solid_m3=0.7,
    solid_m3_per_stere=0.64,
    max_useful_power_kw=None,
    availability=None,
    event_profile=None,
):
    """Allocate wood-stove heat to a useful 5R1C heating-load series.

    Parameters
    ----------
    heating_load : pandas.Series or array-like
        Useful space-heating demand in kW. A Series index is preserved.
    dt_hours : float, optional
        Timestep in hours. If omitted, a regular DatetimeIndex is inferred;
        otherwise one hour is assumed.
    fuel_energy_target_kwh : float
        Annual or scenario fuel input target in kWh. This is chemical energy,
        before applying efficiency.
    efficiency : float
        Useful heat divided by fuel energy, in the interval (0, 1].
    pci_mj_per_kg : float
        Lower heating value of the wood in MJ/kg.
    density_t_per_solid_m3 : float
        Wood mass per solid cubic metre.
    solid_m3_per_stere : float
        Solid wood volume represented by one stacked cubic metre (stere).
    max_useful_power_kw : float, optional
        Maximum useful heat output of the stove.
    availability : scalar or array-like of bool, optional
        Timesteps during which the stove can operate.
    event_profile : array-like, optional
        Non-negative relative weights for distributing useful heat in time.
        It changes timing, not the target annual fuel energy.

    Returns
    -------
    WoodStoveResult
        Hourly useful heat and fuel input, plus annual/scenario balances.

    Notes
    -----
    This is a post-processing/system-layer model. It does not feed the stove
    heat back into indoor temperature or run combustion dynamics. That coupling
    is reserved for a later event/storage model.
    """
    index, load = _resolve_index_and_load(heating_load)
    n = load.size
    dt = _resolve_dt(index, dt_hours)

    if fuel_energy_target_kwh is None:
        raise ValueError('"fuel_energy_target_kwh" is required.')
    target_fuel = float(fuel_energy_target_kwh)
    if not np.isfinite(target_fuel) or target_fuel < 0:
        raise ValueError('"fuel_energy_target_kwh" must be finite and non-negative.')

    efficiency = float(efficiency)
    if not np.isfinite(efficiency) or not 0 < efficiency <= 1:
        raise ValueError('"efficiency" must be in the interval (0, 1].')

    pci_mj_per_kg = float(pci_mj_per_kg)
    if not np.isfinite(pci_mj_per_kg) or pci_mj_per_kg <= 0:
        raise ValueError('"pci_mj_per_kg" must be positive and finite.')

    density_t_per_solid_m3 = float(density_t_per_solid_m3)
    if not np.isfinite(density_t_per_solid_m3) or density_t_per_solid_m3 <= 0:
        raise ValueError('"density_t_per_solid_m3" must be positive and finite.')

    solid_m3_per_stere = float(solid_m3_per_stere)
    if not np.isfinite(solid_m3_per_stere) or solid_m3_per_stere <= 0:
        raise ValueError('"solid_m3_per_stere" must be positive and finite.')

    if max_useful_power_kw is None:
        capacity = load.copy()
    else:
        max_power = float(max_useful_power_kw)
        if not np.isfinite(max_power) or max_power < 0:
            raise ValueError(
                '"max_useful_power_kw" must be finite and non-negative.'
            )
        capacity = np.minimum(load, max_power)

    if availability is None:
        available = np.ones(n, dtype=bool)
    else:
        available = _coerce_hourly(availability, n, 'availability', dtype=bool)
    capacity = np.where(available, capacity, 0.0)

    if event_profile is None:
        weights = load.copy()
    else:
        weights = _coerce_hourly(event_profile, n, 'event_profile')
        if not np.all(np.isfinite(weights)) or np.any(weights < 0):
            raise ValueError('"event_profile" must be finite and non-negative.')
        weights = weights * load

    target_useful = target_fuel * efficiency
    if target_useful > 0 and not np.any((capacity > 0) & (weights > 0)):
        raise ValueError(
            'No positive, available heating-load timestep can receive the target.'
        )

    useful, unallocated_useful = _allocate_useful_heat(
        load, capacity, weights, dt, target_useful
    )
    fuel_input = useful / efficiency
    assigned_useful = float(np.sum(useful) * dt)
    assigned_fuel = float(np.sum(fuel_input) * dt)
    unmet_heating = float(np.sum(np.maximum(load - useful, 0.0)) * dt)
    unallocated_fuel = max(0.0, target_fuel - assigned_fuel)

    mass_kg = assigned_fuel * 3.6 / pci_mj_per_kg
    solid_volume = mass_kg / (density_t_per_solid_m3 * 1000.0)
    volume_stere = solid_volume / solid_m3_per_stere

    return WoodStoveResult(
        heating_load_kw=pd.Series(load, index=index, name='heating_load_kw'),
        useful_heat_kw=pd.Series(useful, index=index, name='useful_heat_kw'),
        fuel_input_kw=pd.Series(fuel_input, index=index, name='fuel_input_kw'),
        target_fuel_energy_kwh=target_fuel,
        target_useful_energy_kwh=target_useful,
        assigned_useful_energy_kwh=assigned_useful,
        assigned_fuel_energy_kwh=assigned_fuel,
        unallocated_useful_energy_kwh=unallocated_useful,
        unallocated_fuel_energy_kwh=unallocated_fuel,
        unmet_heating_energy_kwh=unmet_heating,
        wood_mass_kg=mass_kg,
        wood_volume_solid_m3=solid_volume,
        wood_volume_stere=volume_stere,
        efficiency=efficiency,
        dt_hours=dt,
    )


def simulate_wood_stove_from_5r1c(
    source,
    *,
    fuel_energy_target_kwh,
    dt_hours=None,
    heating_column="Heating Load",
    **stove_kwargs,
):
    """Connect a completed 5R1C simulation to the wood-stove model.

    Parameters
    ----------
    source : Building5R1C, Building, or pandas.DataFrame
        A completed 5R1C model, the high-level ``tsib.Building`` wrapper, or
        its ``detailedResults`` DataFrame. The source is read-only.
    fuel_energy_target_kwh : float
        Chemical energy target for the stove, before efficiency losses.
    dt_hours : float, optional
        Timestep in hours. If omitted, it is inferred from the result index
        when that index is a regular DatetimeIndex.
    heating_column : str, optional
        Column containing useful 5R1C heating demand. Defaults to
        ``"Heating Load"``.
    **stove_kwargs
        Additional keyword arguments accepted by :func:`simulate_wood_stove`,
        such as ``efficiency``, ``max_useful_power_kw``, ``availability`` and
        ``event_profile``.

    Returns
    -------
    WoodStoveResult
        The same energy-balanced result as :func:`simulate_wood_stove`.

    Notes
    -----
    This adapter does not run 5R1C automatically and does not mutate the
    model, its detailed results, or ``elecLoad``. Run the thermal simulation
    first, then pass its output to this function.
    """
    heating_load = _heating_load_from_5r1c(source, heating_column)
    return simulate_wood_stove(
        heating_load,
        dt_hours=dt_hours,
        fuel_energy_target_kwh=fuel_energy_target_kwh,
        **stove_kwargs,
    )


def simulate_wood_stove_events(
    heating_load,
    dt_hours=None,
    fuel_energy_target_kwh=None,
    efficiency=0.50,
    pci_mj_per_kg=15.0,
    density_t_per_solid_m3=0.7,
    solid_m3_per_stere=0.64,
    event_fuel_energy_kwh=20.0,
    event_duration_hours=2.0,
    event_profile=None,
    min_event_interval_hours=6.0,
    storage_capacity_kwh=20.0,
    storage_loss_rate_per_hour=0.0,
    charge_efficiency=1.0,
    release_efficiency=1.0,
    initial_storage_kwh=0.0,
    max_useful_power_kw=None,
    max_combustion_power_kw=None,
    availability=None,
    reorder_threshold_kwh=None,
):
    """Simulate discrete wood loads with a one-state thermal store.

    This is the second-stage system-layer model.  It does not modify a 5R1C
    model or feed heat back into indoor temperature.  At each event, a fixed
    chemical-energy load is burned over ``event_duration_hours`` according to
    ``event_profile``.  Combustion heat charges a finite store; the store then
    releases heat to the heating load subject to demand and
    ``max_useful_power_kw``.

    Events are started greedily at the first available positive-demand step
    after ``min_event_interval_hours`` when the store is at or below
    ``reorder_threshold_kwh``.  Availability prevents new events from
    starting; an event already burning is allowed to finish.  This explicit
    controller is intentionally simple and reproducible.  It is a reference
    event/storage layer, not a calibrated occupant-behaviour model.

    Parameters
    ----------
    heating_load : pandas.Series or array-like
        Useful space-heating demand in kW.
    dt_hours : float, optional
        Timestep in hours.  A regular ``DatetimeIndex`` is inferred when
        possible; otherwise one hour is assumed.
    fuel_energy_target_kwh : float
        Chemical-energy target over the simulated horizon.
    efficiency : float
        Combustion heat divided by chemical fuel energy.
    pci_mj_per_kg, density_t_per_solid_m3, solid_m3_per_stere : float
        Fuel conversion parameters, as in :func:`simulate_wood_stove`.
    event_fuel_energy_kwh : float
        Chemical energy loaded at each event.  The final event is shortened if
        the remaining target is smaller.
    event_duration_hours : float
        Duration represented by one event profile.
    event_profile : array-like, optional
        Non-negative relative combustion-power weights with one value per
        event timestep.  Its integral is normalized to one.  Defaults to a
        constant release profile.
    min_event_interval_hours : float
        Minimum time between event starts.
    storage_capacity_kwh : float
        Maximum useful thermal energy held by the store.
    storage_loss_rate_per_hour : float
        First-order storage-loss coefficient.  Losses use exponential decay.
    charge_efficiency, release_efficiency : float
        Efficiencies between combustion heat, stored energy, and delivered
        useful heat.
    initial_storage_kwh : float
        Store energy at the beginning of the first timestep.
    max_useful_power_kw : float, optional
        Maximum heat delivered from storage to the building.
    max_combustion_power_kw : float, optional
        Maximum combustion heat power.  The event profile must fit this limit.
    availability : scalar or array-like of bool, optional
        Availability for starting new events.
    reorder_threshold_kwh : float, optional
        Store level below which a new event may start.  Defaults to 25% of
        storage capacity.

    Returns
    -------
    WoodStoveEventResult
        Timestep profiles, event states, storage balance and fuel conversions.

    Notes
    -----
    The store state is useful thermal energy.  ``unmet_heating_energy_kwh``
    measures demand not delivered during the horizon, while energy remaining
    in the store at the end is reported separately.  The model deliberately
    keeps the stove heat in a separate channel and never changes ``elecLoad``.
    """
    index, load = _resolve_index_and_load(heating_load)
    n = load.size
    dt = _resolve_dt(index, dt_hours)

    if fuel_energy_target_kwh is None:
        raise ValueError('"fuel_energy_target_kwh" is required.')
    target_fuel = float(fuel_energy_target_kwh)
    if not np.isfinite(target_fuel) or target_fuel < 0:
        raise ValueError('"fuel_energy_target_kwh" must be finite and non-negative.')

    efficiency = float(efficiency)
    if not np.isfinite(efficiency) or not 0 < efficiency <= 1:
        raise ValueError('"efficiency" must be in the interval (0, 1].')

    pci_mj_per_kg = float(pci_mj_per_kg)
    if not np.isfinite(pci_mj_per_kg) or pci_mj_per_kg <= 0:
        raise ValueError('"pci_mj_per_kg" must be positive and finite.')

    density_t_per_solid_m3 = float(density_t_per_solid_m3)
    if not np.isfinite(density_t_per_solid_m3) or density_t_per_solid_m3 <= 0:
        raise ValueError(
            '"density_t_per_solid_m3" must be positive and finite.'
        )

    solid_m3_per_stere = float(solid_m3_per_stere)
    if not np.isfinite(solid_m3_per_stere) or solid_m3_per_stere <= 0:
        raise ValueError('"solid_m3_per_stere" must be positive and finite.')

    event_fuel_energy_kwh = float(event_fuel_energy_kwh)
    if not np.isfinite(event_fuel_energy_kwh) or event_fuel_energy_kwh <= 0:
        raise ValueError('"event_fuel_energy_kwh" must be positive and finite.')

    event_duration_hours = float(event_duration_hours)
    if not np.isfinite(event_duration_hours) or event_duration_hours <= 0:
        raise ValueError('"event_duration_hours" must be positive and finite.')
    event_steps_float = event_duration_hours / dt
    event_steps = int(round(event_steps_float))
    if event_steps < 1 or not np.isclose(event_steps_float, event_steps):
        raise ValueError(
            '"event_duration_hours" must be a positive multiple of the timestep.'
        )

    min_event_interval_hours = float(min_event_interval_hours)
    if not np.isfinite(min_event_interval_hours) or min_event_interval_hours < 0:
        raise ValueError('"min_event_interval_hours" must be non-negative and finite.')
    min_event_steps = max(1, int(np.ceil(min_event_interval_hours / dt)))

    storage_capacity_kwh = float(storage_capacity_kwh)
    if not np.isfinite(storage_capacity_kwh) or storage_capacity_kwh <= 0:
        raise ValueError('"storage_capacity_kwh" must be positive and finite.')

    storage_loss_rate_per_hour = float(storage_loss_rate_per_hour)
    if not np.isfinite(storage_loss_rate_per_hour) or storage_loss_rate_per_hour < 0:
        raise ValueError(
            '"storage_loss_rate_per_hour" must be non-negative and finite.'
        )

    charge_efficiency = float(charge_efficiency)
    if not np.isfinite(charge_efficiency) or not 0 < charge_efficiency <= 1:
        raise ValueError('"charge_efficiency" must be in the interval (0, 1].')

    release_efficiency = float(release_efficiency)
    if not np.isfinite(release_efficiency) or not 0 < release_efficiency <= 1:
        raise ValueError('"release_efficiency" must be in the interval (0, 1].')

    initial_storage_kwh = float(initial_storage_kwh)
    if (
        not np.isfinite(initial_storage_kwh)
        or initial_storage_kwh < 0
        or initial_storage_kwh > storage_capacity_kwh
    ):
        raise ValueError(
            '"initial_storage_kwh" must be between zero and storage capacity.'
        )

    if max_useful_power_kw is None:
        useful_power_limit = load.copy()
    else:
        max_useful_power_kw = float(max_useful_power_kw)
        if not np.isfinite(max_useful_power_kw) or max_useful_power_kw < 0:
            raise ValueError(
                '"max_useful_power_kw" must be finite and non-negative.'
            )
        useful_power_limit = np.minimum(load, max_useful_power_kw)

    if max_combustion_power_kw is not None:
        max_combustion_power_kw = float(max_combustion_power_kw)
        if not np.isfinite(max_combustion_power_kw) or max_combustion_power_kw < 0:
            raise ValueError(
                '"max_combustion_power_kw" must be finite and non-negative.'
            )

    if availability is None:
        available = np.ones(n, dtype=bool)
    else:
        available = _coerce_hourly(availability, n, "availability", dtype=bool)

    if event_profile is None:
        profile = np.ones(event_steps, dtype=float)
    else:
        profile = np.asarray(
            event_profile.to_numpy()
            if isinstance(event_profile, pd.Series)
            else event_profile,
            dtype=float,
        ).reshape(-1)
        if profile.size != event_steps:
            raise ValueError(
                '"event_profile" must have one value per event timestep '
                f"({event_steps})."
            )
        if not np.all(np.isfinite(profile)) or np.any(profile < 0):
            raise ValueError('"event_profile" must be finite and non-negative.')
    profile_integral = float(np.sum(profile) * dt)
    if profile_integral <= 0:
        raise ValueError('"event_profile" must contain positive energy.')
    profile = profile / profile_integral

    full_event_heat = event_fuel_energy_kwh * efficiency
    full_event_power = full_event_heat * profile
    if (
        max_combustion_power_kw is not None
        and np.max(full_event_power) > max_combustion_power_kw + 1e-12
    ):
        raise ValueError(
            "event profile exceeds max_combustion_power_kw; increase "
            "event_duration_hours or provide a lower-power profile."
        )

    if reorder_threshold_kwh is None:
        reorder_threshold_kwh = storage_capacity_kwh * 0.25
    else:
        reorder_threshold_kwh = float(reorder_threshold_kwh)
    if (
        not np.isfinite(reorder_threshold_kwh)
        or reorder_threshold_kwh < 0
        or reorder_threshold_kwh > storage_capacity_kwh
    ):
        raise ValueError(
            '"reorder_threshold_kwh" must be between zero and storage capacity.'
        )

    combustion_heat = np.zeros(n, dtype=float)
    fuel_input = np.zeros(n, dtype=float)
    useful_heat = np.zeros(n, dtype=float)
    storage = np.zeros(n, dtype=float)
    storage_loss = np.zeros(n, dtype=float)
    storage_spill = np.zeros(n, dtype=float)
    event_start = np.zeros(n, dtype=bool)
    event_fuel_input = np.zeros(n, dtype=float)
    event_state = np.full(n, "off", dtype=object)

    remaining_target = target_fuel
    current_profile = None
    current_profile_index = 0
    next_event_step = 0
    event_count = 0
    previous_storage = initial_storage_kwh
    tolerance = max(1e-12, target_fuel * 1e-12)

    for step in range(n):
        decayed_storage = previous_storage * np.exp(
            -storage_loss_rate_per_hour * dt
        )
        storage_loss[step] = previous_storage - decayed_storage

        if (
            current_profile is None
            and step >= next_event_step
            and available[step]
            and load[step] > 0
            and decayed_storage <= reorder_threshold_kwh + tolerance
            and remaining_target > tolerance
        ):
            load_fuel = min(event_fuel_energy_kwh, remaining_target)
            current_profile = load_fuel * efficiency * profile
            current_profile_index = 0
            event_start[step] = True
            event_fuel_input[step] = load_fuel
            event_count += 1
            remaining_target -= load_fuel
            next_event_step = step + min_event_steps

        if current_profile is not None:
            combustion_heat[step] = current_profile[current_profile_index]
            fuel_input[step] = combustion_heat[step] / efficiency
            current_profile_index += 1
            if current_profile_index >= current_profile.size:
                current_profile = None

        charged_storage = (
            decayed_storage
            + combustion_heat[step] * charge_efficiency * dt
        )
        storage_before_release = min(storage_capacity_kwh, charged_storage)
        storage_spill[step] = max(0.0, charged_storage - storage_capacity_kwh)

        release_capacity = storage_before_release * release_efficiency
        useful_energy = min(
            useful_power_limit[step] * dt,
            release_capacity,
        )
        useful_heat[step] = useful_energy / dt
        storage[step] = storage_before_release - useful_energy / release_efficiency
        previous_storage = storage[step]

        if combustion_heat[step] > tolerance:
            event_state[step] = "combustion"
        elif useful_heat[step] > tolerance:
            event_state[step] = "release"
        elif storage[step] > tolerance:
            event_state[step] = "storage"

    assigned_useful = float(np.sum(useful_heat) * dt)
    assigned_fuel = float(np.sum(fuel_input) * dt)
    combustion_energy = float(np.sum(combustion_heat) * dt)
    unmet_heating = float(np.sum(np.maximum(load - useful_heat, 0.0)) * dt)
    unallocated_fuel = max(0.0, target_fuel - assigned_fuel)
    unallocated_useful = max(0.0, target_fuel * efficiency - assigned_useful)
    storage_loss_energy = float(np.sum(storage_loss))
    storage_spill_energy = float(np.sum(storage_spill))

    mass_kg = assigned_fuel * 3.6 / pci_mj_per_kg
    solid_volume = mass_kg / (density_t_per_solid_m3 * 1000.0)
    volume_stere = solid_volume / solid_m3_per_stere

    return WoodStoveEventResult(
        heating_load_kw=pd.Series(load, index=index, name="heating_load_kw"),
        combustion_heat_kw=pd.Series(
            combustion_heat, index=index, name="combustion_heat_kw"
        ),
        useful_heat_kw=pd.Series(useful_heat, index=index, name="useful_heat_kw"),
        fuel_input_kw=pd.Series(fuel_input, index=index, name="fuel_input_kw"),
        storage_kwh=pd.Series(storage, index=index, name="storage_kwh"),
        storage_loss_kwh=pd.Series(
            storage_loss, index=index, name="storage_loss_kwh"
        ),
        storage_spill_kwh=pd.Series(
            storage_spill, index=index, name="storage_spill_kwh"
        ),
        event_start=pd.Series(event_start, index=index, name="event_start"),
        event_fuel_input_kwh=pd.Series(
            event_fuel_input, index=index, name="event_fuel_input_kwh"
        ),
        event_state=pd.Series(event_state, index=index, name="event_state"),
        target_fuel_energy_kwh=target_fuel,
        target_useful_energy_kwh=target_fuel * efficiency,
        assigned_useful_energy_kwh=assigned_useful,
        assigned_fuel_energy_kwh=assigned_fuel,
        unallocated_useful_energy_kwh=unallocated_useful,
        unallocated_fuel_energy_kwh=unallocated_fuel,
        unmet_heating_energy_kwh=unmet_heating,
        stored_energy_end_kwh=float(storage[-1]),
        storage_loss_energy_kwh=storage_loss_energy,
        storage_spill_energy_kwh=storage_spill_energy,
        wood_mass_kg=mass_kg,
        wood_volume_solid_m3=solid_volume,
        wood_volume_stere=volume_stere,
        efficiency=efficiency,
        dt_hours=dt,
        event_count=event_count,
    )


def simulate_wood_stove_events_from_5r1c(
    source,
    *,
    fuel_energy_target_kwh,
    dt_hours=None,
    heating_column="Heating Load",
    **stove_kwargs,
):
    """Connect a completed 5R1C result to the event/storage stove model."""
    heating_load = _heating_load_from_5r1c(source, heating_column)
    return simulate_wood_stove_events(
        heating_load,
        dt_hours=dt_hours,
        fuel_energy_target_kwh=fuel_energy_target_kwh,
        **stove_kwargs,
    )


@dataclass(frozen=True)
class WoodStoveEventCalibrationResult:
    """Result of numerical event-parameter calibration against the MVP."""

    reference_result: WoodStoveResult
    best_result: WoodStoveEventResult
    best_parameters: dict
    trials: pd.DataFrame


def calibrate_wood_stove_event_parameters(
    heating_load,
    *,
    fuel_energy_target_kwh,
    candidate_parameters,
    efficiency=0.50,
    pci_mj_per_kg=15.0,
    density_t_per_solid_m3=0.7,
    solid_m3_per_stere=0.64,
    score_weights=None,
):
    """Select event/storage parameters using the MVP as numerical reference.

    This helper is deliberately a *numerical calibration*: it has no physical
    observations and must not be interpreted as estimating real user
    behaviour.  It compares every candidate event model against
    :func:`simulate_wood_stove` for the same heating load and annual fuel
    target.  The default score favours matching annual useful heat and fuel
    and the hourly useful-heat profile, then penalizes unmet demand, storage
    spill and energy left in storage at the end of the horizon.

    Parameters
    ----------
    heating_load : pandas.Series or array-like
        Useful space-heating demand in kW.
    fuel_energy_target_kwh : float
        Common chemical-energy target passed to the MVP and every candidate.
    candidate_parameters : iterable of mappings
        Event/storage keyword dictionaries accepted by
        :func:`simulate_wood_stove_events`, for example
        ``event_fuel_energy_kwh`` or ``storage_capacity_kwh``.  Common fuel
        conversion parameters are supplied by the explicit function
        arguments and should not be repeated in a candidate.
    score_weights : mapping, optional
        Weights for ``useful``, ``fuel``, ``profile``, ``unmet``, ``spill`` and
        ``end_storage``.

    Returns
    -------
    WoodStoveEventCalibrationResult
        MVP reference, best dynamic result, selected parameters and a trial
        table. Invalid candidates remain in the table with ``valid=False``.
    """
    candidates = [dict(candidate) for candidate in candidate_parameters]
    if not candidates:
        raise ValueError('"candidate_parameters" must not be empty.')

    forbidden = {
        "heating_load",
        "dt_hours",
        "fuel_energy_target_kwh",
        "efficiency",
        "pci_mj_per_kg",
        "density_t_per_solid_m3",
        "solid_m3_per_stere",
    }
    for candidate in candidates:
        repeated = sorted(forbidden.intersection(candidate))
        if repeated:
            raise ValueError(
                "candidate parameters must not override common inputs: "
                + ", ".join(repeated)
            )

    reference = simulate_wood_stove(
        heating_load,
        fuel_energy_target_kwh=fuel_energy_target_kwh,
        efficiency=efficiency,
        pci_mj_per_kg=pci_mj_per_kg,
        density_t_per_solid_m3=density_t_per_solid_m3,
        solid_m3_per_stere=solid_m3_per_stere,
    )
    weights = {
        "useful": 1.0,
        "fuel": 0.5,
        "profile": 0.5,
        "unmet": 0.25,
        "spill": 0.25,
        "end_storage": 0.25,
    }
    if score_weights is not None:
        unknown = set(score_weights).difference(weights)
        if unknown:
            raise ValueError(
                "unknown score weights: " + ", ".join(sorted(unknown))
            )
        weights.update({key: float(value) for key, value in score_weights.items()})
    if any(not np.isfinite(value) or value < 0 for value in weights.values()):
        raise ValueError("score weights must be finite and non-negative.")

    useful_scale = max(reference.target_useful_energy_kwh, 1.0)
    fuel_scale = max(reference.target_fuel_energy_kwh, 1.0)
    trial_rows = []
    trial_results = []
    for trial_index, candidate in enumerate(candidates):
        row = {"trial": trial_index, **candidate}
        try:
            dynamic = simulate_wood_stove_events(
                heating_load,
                fuel_energy_target_kwh=fuel_energy_target_kwh,
                efficiency=efficiency,
                pci_mj_per_kg=pci_mj_per_kg,
                density_t_per_solid_m3=density_t_per_solid_m3,
                solid_m3_per_stere=solid_m3_per_stere,
                **candidate,
            )
            useful_error = abs(
                dynamic.assigned_useful_energy_kwh
                - reference.assigned_useful_energy_kwh
            )
            fuel_error = abs(
                dynamic.assigned_fuel_energy_kwh
                - reference.assigned_fuel_energy_kwh
            )
            unmet_error = abs(
                dynamic.unmet_heating_energy_kwh
                - reference.unmet_heating_energy_kwh
            )
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
                weights["useful"] * useful_error / useful_scale
                + weights["fuel"] * fuel_error / fuel_scale
                + weights["profile"] * profile_error / useful_scale
                + weights["unmet"] * unmet_error / useful_scale
                + weights["spill"]
                * dynamic.storage_spill_energy_kwh
                / useful_scale
                + weights["end_storage"]
                * dynamic.stored_energy_end_kwh
                / useful_scale
            )
            row.update(
                {
                    "valid": True,
                    "error": None,
                    "score": score,
                    "assigned_useful_energy_kwh": dynamic.assigned_useful_energy_kwh,
                    "assigned_fuel_energy_kwh": dynamic.assigned_fuel_energy_kwh,
                    "profile_error_kwh": profile_error,
                    "unmet_heating_energy_kwh": dynamic.unmet_heating_energy_kwh,
                    "storage_spill_energy_kwh": dynamic.storage_spill_energy_kwh,
                    "stored_energy_end_kwh": dynamic.stored_energy_end_kwh,
                    "event_count": dynamic.event_count,
                }
            )
            trial_results.append(dynamic)
        except (TypeError, ValueError, FloatingPointError) as error:
            row.update(
                {
                    "valid": False,
                    "error": str(error),
                    "score": np.inf,
                }
            )
            trial_results.append(None)
        trial_rows.append(row)

    trials = pd.DataFrame(trial_rows)
    valid = trials[trials["valid"]].sort_values(
        ["score", "event_count", "trial"], kind="stable"
    )
    if valid.empty:
        raise ValueError("No candidate event parameter set produced a valid result.")
    best_trial = int(valid.iloc[0]["trial"])
    return WoodStoveEventCalibrationResult(
        reference_result=reference,
        best_result=trial_results[best_trial],
        best_parameters=candidates[best_trial],
        trials=trials,
    )
