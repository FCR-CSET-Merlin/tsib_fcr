"""Energy-balanced residential wood-stove simulation helpers.

The MVP in this module is deliberately a system-layer model: it receives useful
space-heating demand from a building model, allocates a fuel-energy target to
that demand, and reports useful heat, fuel input, and unallocated energy. It
does not model combustion chemistry, indoor temperature feedback, or emissions.
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
        differences = np.diff(index.asi8) / 3.6e12
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
