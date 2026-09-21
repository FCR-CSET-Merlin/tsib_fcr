"""Energy-balanced residential wood-stove simulation helpers.

The MVP in this module is deliberately a system-layer model: it receives useful
space-heating demand from a building model, allocates a fuel-energy target to
that demand, and reports useful heat, fuel input, and unallocated energy. It
does not model combustion chemistry, indoor temperature feedback, or emissions.
The event model adds a low-dimensional thermal store and discrete fuel loads,
while keeping the same post-processing boundary around the 5R1C demand.
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
