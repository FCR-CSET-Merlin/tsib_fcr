# Fase 6 — Eventos y almacenamiento de la estufa a leña

**Estado:** primera implementación de referencia completada; calibración y
retroalimentación térmica quedan pendientes.

## Alcance

La segunda etapa agrega una dinámica de baja dimensión sobre el contrato del
MVP:

```text
Heating Load(t) → eventos de carga → combustión → almacenamiento → calor útil(t)
```

El modelo sigue siendo una capa de sistema posterior a 5R1C. No modifica
`elecLoad`, no cambia `sim_demand_direct()` y no retroalimenta todavía la
temperatura interior. Esta separación permite comparar el balance anual del
MVP con una distribución temporal por eventos.

## Modelo implementado

La función pública es:

```python
result = tsib.simulate_wood_stove_events(
    heating_load,
    fuel_energy_target_kwh=24.0,
    efficiency=0.50,
    event_fuel_energy_kwh=4.0,
    event_duration_hours=2.0,
    min_event_interval_hours=6.0,
    storage_capacity_kwh=2.0,
)
```

También existe el adaptador
`tsib.simulate_wood_stove_events_from_5r1c(...)`, que consume la columna
`Heating Load` de un resultado 5R1C ya ejecutado.

Cada evento comienza en el primer paso con demanda positiva que cumple:

- disponibilidad para iniciar una carga;
- intervalo mínimo desde la carga anterior;
- almacenamiento por debajo del umbral de recarga;
- energía objetivo de combustible aún no utilizada.

La carga tiene una energía química fija (`event_fuel_energy_kwh`) y se
distribuye durante `event_duration_hours` mediante una curva relativa. La
última carga puede ser parcial. Un evento ya iniciado termina aunque la
disponibilidad cambie.

El estado de almacenamiento útil se actualiza como:

```text
S_decay[t] = S[t-1] × exp(-loss_rate × dt)
S_charge[t] = min(S_max, S_decay[t] + eta_charge × Q_comb[t] × dt)
E_release[t] = min(Q_load[t] × dt,
                   Q_release_max[t] × dt,
                   eta_release × S_charge[t])
S[t] = S_charge[t] - E_release[t] / eta_release
```

La energía que excede `S_max` se reporta como `storage_spill_kwh`; la energía
que permanece al final se reporta como `stored_energy_end_kwh`. La demanda no
satisfecha se calcula paso a paso, mientras que `unallocated_fuel_energy_kwh`
mantiene la diferencia entre el objetivo químico y el combustible realmente
quemado.

## Salidas adicionales

Además de las magnitudes del MVP, `WoodStoveEventResult` entrega:

- `combustion_heat_kw`;
- `storage_kwh` al final de cada paso;
- `storage_loss_kwh` y `storage_spill_kwh`;
- `event_start` y `event_fuel_input_kwh`;
- `event_state`, con `off`, `combustion`, `release` o `storage`;
- número de eventos y energía almacenada al final.

## Validación sintética

Las pruebas en `test/test_wood_stove.py` cubren:

1. liberación posterior a la combustión desde el almacenamiento;
2. derrame por capacidad insuficiente;
3. conservación del objetivo de combustible y demanda no satisfecha;
4. validación de duración, perfil y potencia de combustión;
5. adaptación desde un `DataFrame` 5R1C.

El ejemplo reproducible está en
[`examples/chile/wood_stove_events.py`](../../examples/chile/wood_stove_events.py).

## Calibración numérica sin datos físicos

Cuando no existen observaciones de encendido o temperatura interior, la
función `tsib.calibrate_wood_stove_event_parameters(...)` realiza una
calibración de consistencia. Usa el MVP como referencia para la misma serie
`Heating Load` y el mismo objetivo de combustible, y evalúa:

- diferencia de energía útil anual;
- diferencia de combustible asignado;
- diferencia absoluta del perfil horario útil;
- demanda no satisfecha;
- derrame del almacenamiento;
- energía remanente al final del horizonte.

El score resultante no es un error físico observado. Sólo permite seleccionar
parámetros dinámicos que no rompan el balance ni cambien arbitrariamente la
escala anual del MVP.

El script
[`examples/chile/calibrate_wood_stove_events.py`](../../examples/chile/calibrate_wood_stove_events.py)
ejecuta una grilla de 144 combinaciones sobre un registro representativo por
región, usando ERA5 2024. También transfiere el mejor conjunto de parámetros a
`REDPE_mid` en las regiones disponibles y reporta la demanda no satisfecha y
la energía no asignada. Los resultados se guardan en
`outputs/chile_wood_stove_event_calibration/`.

La corrida de referencia usó 16 registros, 144 candidatos por registro y
2.304 evaluaciones válidas. El mejor conjunto reproduce el combustible anual
del MVP en los 16 registros y no deja derrame ni combustible sin asignar para
el objetivo `coverage_mid`; sin embargo, el error horario mediano del perfil
útil fue 1.674,6 kWh. Esto confirma el balance anual, pero también muestra que
la regla de eventos todavía no reproduce la distribución temporal del MVP.

Al transferir esos parámetros al objetivo `REDPE_mid`, las nueve regiones con
datos presentan energía no asignada en la mayoría de los casos porque el
objetivo REDPE excede la energía que la regla de eventos consigue quemar en el
horizonte bajo sus intervalos y tamaños de carga. Esta diferencia es un
resultado de control y horizonte, no una estimación física del consumo.

## Límites de esta primera versión

- El controlador es una regla determinista de umbral, no un modelo de
  comportamiento observado.
- La estufa entrega calor a un único canal agregado; no se modelan zonas,
  radiación localizada ni estratificación.
- No hay retroalimentación sobre temperatura interior ni iteración con
  `Building5R1C`.
- La potencia de combustión debe ser compatible con la curva del evento; no
  se modela todavía modulación ni encendido parcial físico.
- Combustión detallada, emisiones y calidad del aire siguen fuera del alcance.

La siguiente tarea de esta fase es ampliar la muestra de validación y, si
aparecen datos de uso, reemplazar esta calibración de consistencia por una
calibración física. El acoplamiento térmico externo debe evaluarse sólo
después de esa comparación.
