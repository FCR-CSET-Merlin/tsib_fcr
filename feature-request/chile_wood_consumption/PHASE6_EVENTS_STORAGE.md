# Fase 6 — Eventos y almacenamiento de la estufa a leña

**Estado:** primera implementación de referencia y calibración numérica
regional completadas; calibración física y retroalimentación térmica quedan
pendientes.

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

El mismo script admite ahora `--calibration-target redpe_mid`. En ese modo,
cuando existe una fila REDPE para la región, el objetivo anual usado para
seleccionar los parámetros es directamente la energía bruta `REDPE_mid`; en
las regiones sin fila se usa explícitamente `MVP_coverage_mid`. Por ejemplo,
para una cohorte regional exploratoria:

```bash
PYTHONPATH=. python examples/chile/calibrate_wood_stove_events.py \
  --env-file /ruta/local/geonode.env \
  --year 2024 \
  --samples-per-region 10 \
  --calibration-target redpe_mid \
  --output-dir outputs/chile_wood_stove_redpe_calibration
```

Esta opción calibra la escala anual REDPE y la dinámica de eventos bajo la
misma demanda 5R1C, pero sigue sin identificar físicamente el comportamiento
de los ocupantes. La muestra de 500 registros del análisis de dispersión no se
usa automáticamente para explorar las 144 combinaciones por registro, porque
eso multiplica innecesariamente el costo; debe reservarse para evaluar los
parámetros seleccionados o para una estrategia regional agregada.

La corrida de control con un registro por región se guardó en
`outputs/chile_wood_stove_redpe_calibration/`. En las nueve regiones REDPE,
el objetivo usado por la calibración fue exactamente la energía `REDPE_mid`;
en las siete regiones restantes quedó registrado el fallback
`MVP_coverage_mid`. Esto confirma la ruta numérica de calibración, pero no
constituye validación física.

Para evitar sobreajustar cada vivienda, la calibración de cohorte usa
`examples/chile/calibrate_wood_stove_regional_cohort.py`. Construye un perfil
horario regional ponderado por `n_inmuebles`, ajusta un único conjunto de
parámetros por región y evalúa esos parámetros en todos los registros. Los
rangos impares de `regional_sample_rank` forman el ajuste y los rangos pares
el holdout. La corrida de 500 registros se guarda en
`outputs/chile_wood_stove_regional_cohort_calibration/`.

En esta corrida se evaluaron 144 candidatos por cada una de las 16 regiones
(2.304 evaluaciones). Nueve regiones usaron `REDPE_mid` y siete usaron
`MVP_coverage_mid` por ausencia de una fila REDPE aplicable. Para las regiones
REDPE, el error relativo ponderado del holdout quedó entre `-0,6%` (RM) y
`-31,5%` (Magallanes). La subestimación no se oculta con un ajuste forzado:
la función penaliza explícitamente la diferencia entre combustible asignado y
energía REDPE objetivo, pero conserva y reporta el combustible no asignado y
la demanda no satisfecha cuando la combinación de demanda 5R1C, potencia y
regla de eventos no puede absorber todo el objetivo anual. El detalle por
región, inmueble y candidato se encuentra en el CSV de resultados y en el
README de la salida.

Como sensibilidad adicional, se evaluaron setpoints invernales constantes de
22 °C y 24 °C en Magallanes, Los Ríos, Los Lagos y Araucanía, manteniendo
fijos los parámetros de eventos calibrados. El setpoint de enfriamiento se
mantiene 2 °C por encima del de calefacción durante esos meses. La demanda
aumentó y la brecha contra `REDPE_mid` se redujo en las cuatro regiones, pero
también aumentó la demanda no satisfecha. El análisis está documentado en
`SETPOINT_SENSITIVITY_SOUTH.md` y sus CSV quedan en
`outputs/chile_wood_stove_setpoint_sensitivity_south/`. En la nueva corrida,
los eventos sólo pueden iniciar entre las 08:00 y las 23:00; un evento ya
iniciado puede terminar según su duración configurada.

También se agregó
`examples/chile/inspect_wood_stove_winter_day.py`, que simula el año completo
de un inmueble representativo de Magallanes y extrae el día invernal más frío.
La salida contiene `T_amb`, `T_air`, temperaturas internas 5R1C, potencia de
combustión, calor útil, estado de almacenamiento y masa horaria de leña. El
caso de Natales (`edificio_id=2577343`) queda en
`outputs/chile_wood_stove_winter_day_magallanes/`.

Para explorar la hipótesis de pobreza energética se agregó
`examples/chile/run_wood_stove_construction_doe.py`. El DOE varía
multiplicadores de U de muros, U de ventanas e infiltración, manteniendo el
horario 08:00–23:00, y valida la configuración seleccionada en la cohorte.
El screening ampliado usa niveles `1×`, `1,5×`, `2×`, `2,5×` y `3×` en un
factorial `5³` por región y setpoint. En la validación de cohorte, las mejores
brechas alcanzan aproximadamente `-10,3%` en Magallanes, `-10,8%` en Los
Ríos, `-12,8%` en Los Lagos y `-6,6%` en Araucanía. En Magallanes esa mejora
requiere los tres multiplicadores en `3×` y produce más de 30 MWh/año de
demanda no satisfecha; por tanto, no debe interpretarse como una configuración
física validada. Los resultados están en
`outputs/chile_wood_stove_construction_doe_south_expanded/`.

La corrida de referencia del script base usó 16 registros, uno por región,
144 candidatos por registro y 2.304 evaluaciones válidas. El mejor conjunto
reproduce el combustible anual del MVP en esos registros y no deja derrame ni
combustible sin asignar para el objetivo `coverage_mid`; sin embargo, el error
horario mediano del perfil útil fue 1.674,6 kWh. Esto confirma el balance anual,
pero también muestra que la regla de eventos todavía no reproduce la
distribución temporal del MVP.

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
