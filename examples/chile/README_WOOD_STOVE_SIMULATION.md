# Simulación de calefacción a leña en Chile

Esta guía describe cómo ejecutar el módulo bidireccional de estufa a leña
acoplado al modelo térmico 5R1C de `tsib-fcr`. La estufa observa el estado
térmico del edificio, genera eventos discretos de carga y entrega el calor
útil a los nodos de aire, superficie y masa del edificio.

El módulo no usa un objetivo anual REDPE para decidir cuánta leña consumir.
REDPE se utiliza sólo como referencia posterior para comparar resultados.

## Instalación

Para reproducir el motor publicado:

```bash
python -m pip install \
  "tsib-fcr @ git+https://github.com/FCR-CSET-Merlin/tsib_fcr.git@6af57d61bd001162743a9ff9b26df27c3868bdb1"
```

En desarrollo local, la alternativa editable es:

```bash
python -m pip install -e /ruta/a/tsib_fcr
```

La simulación directa 5R1C no requiere solver. Los ejemplos GeoNode y
regionales requieren además `pandas`, `SQLAlchemy`, `psycopg2`, `Pyomo`,
`matplotlib` y las dependencias indicadas en
[`requirements-validation.txt`](../../requirements-validation.txt).

## Configurar un edificio con estufa a leña

La tecnología se selecciona en `BuildingConfiguration` mediante
`existingHeatSupply="wood_stove"`. Los parámetros de la estufa se pasan en
`woodStoveParameters`:

```python
import numpy as np
import pandas as pd
import tsib

# tmy debe tener DatetimeIndex y una resolución compatible con timestep_minutes.
# Para la resolución recomendada, debe ser de 30 minutos.
tmy = pd.DataFrame(
    {
        "T": np.full(17520, 8.0),
        "DHI": np.zeros(17520),
        "DNI": np.zeros(17520),
        "GHI": np.zeros(17520),
    },
    index=pd.date_range("2024-01-01", periods=17520, freq="30min"),
)

configurator = tsib.BuildingConfiguration(
    {
        "ID": "CL.SFH.preRT.mad.D",
        "country": "CL",
        "a_ref": 70.0,
        "weatherData": tmy,
        "weatherID": "mi_comuna",
        "refurbishment": False,
        "autoProfiles": False,
        "existingHeatSupply": "wood_stove",
        "woodStoveParameters": {
            "heating_mode": "wood_only",
            "efficiency": 0.50,
            "timestep_minutes": 30,
            "min_event_interval_hours": 1.0,
            "heating_setpoint_offset_c": 0.0,
            "trigger_delta_c": 10.0,
            "spinup_passes": 1,
        },
    },
    ignore_profiles=True,
)
cfg = configurator.getBdgCfg(includeSupply=True)
cfg.update(
    {
        "Q_ig": np.zeros(len(tmy)),
        "occ_nothome": pd.Series(0.0, index=tmy.index),
        "occ_sleeping": pd.Series(0.0, index=tmy.index),
        "elecLoad": pd.Series(0.0, index=tmy.index),
        "hotWaterLoad": pd.Series(0.0, index=tmy.index),
    }
)

building = tsib.Building(configurator=configurator)
heat_profiles = building.getHeatLoad()
wood_result = building.wood_stove_result
```

`wood_result.detailed_results` contiene, entre otras, estas señales:

- `T_e`: temperatura exterior;
- `T_air`: temperatura interior;
- `Heating Setpoint`: setpoint aplicado;
- `Q_wood_useful_kw`: potencia útil de la estufa;
- `event_start`, `event_state` y `event_logs`: eventos de carga;
- `H_vent`: conductancia de ventilación/infiltración efectiva.

Los agregados principales son `wood_logs_burned`, `wood_volume_stere`,
`fuel_energy_consumed_kwh`, `wood_useful_energy_kwh`, `event_count` y
`unmet_heating_energy_kwh`. La conversión usada en los análisis de Chile es:

```text
220 leños = 1 m³ estéreo
```

También se puede llamar directamente al acoplamiento, sin el wrapper
`Building`, usando un `Building5R1C` ya construido:

```python
model = tsib.Building5R1C(cfg)
result = tsib.simulate_wood_stove_5r1c_bidirectional(
    model,
    heating_mode="wood_only",
    efficiency=0.50,
    timestep_minutes=30,
    min_event_interval_hours=1.0,
    heating_setpoint_offset_c=0.0,
    trigger_delta_c=10.0,
    spinup_passes=1,
)
```

En `wood_only` no se activa calefacción auxiliar. Si un offset alto hace que
el setpoint de calefacción supere el límite mensual de enfriamiento, el motor
eleva automáticamente ese límite inactivo; no se activa enfriamiento ni se
modifica el setpoint de calefacción solicitado.

## Simulación individual con datos GeoNode

El ejemplo
[`validate_wood_stove_geonode.py`](validate_wood_stove_geonode.py) carga una
vivienda y su año meteorológico desde GeoNode/PostgreSQL:

```bash
PYTHONPATH=. python examples/chile/validate_wood_stove_geonode.py \
  --env-file /ruta/a/geonode_connection/.env \
  --edificio-id 1690556 \
  --year 2024 \
  --output /tmp/wood_stove_validation.csv
```

El archivo `.env` debe contener `GEONODE_HOST`, `GEONODE_PORT`,
`GEONODE_DATABASE`, `GEONODE_USER` y `GEONODE_PASSWORD`. Nunca se debe
cometer ese archivo.

## Corrida regional de 500 viviendas

La corrida reproducible usa la muestra regional almacenada en:

```text
outputs/chile_wood_stove_regional_dispersion_hdd12/selected_buildings.csv
```

La muestra contiene `edificio_id`, región, comuna, arquetipo, superficie,
stock de viviendas y comuna meteorológica. El script agrupa edificios por
comuna meteorológica y usa un pool de procesos; `--workers 10` ejecuta diez
procesos en paralelo.

Ejemplo de la configuración actualmente calibrada:

```bash
PYTHONPATH=. python \
  examples/chile/analyze_wood_stove_bidirectional_regional_dispersion.py \
  --env-file /ruta/a/geonode_connection/.env \
  --sample-file outputs/chile_wood_stove_regional_dispersion_hdd12/selected_buildings.csv \
  --year 2024 \
  --efficiency 0.50 \
  --logs-per-stere 220 \
  --timestep-minutes 30 \
  --min-event-interval-hours 1 \
  --setpoint-offset-c 0 \
  --trigger-delta-c 10 \
  --weather-exposure \
  --hdd-envelope \
  --hdd-file outputs/chile_hdd_reference/hdd_regional_ponderado_lena_2024.csv \
  --hdd-base-c 14 \
  --hdd-factor-min 0.70 \
  --hdd-factor-max 1.75 \
  --hardcoded-regional-offsets \
  --workers 10 \
  --output-dir outputs/chile_wood_stove_regional_run
```

`--hardcoded-regional-offsets` aplica la tabla experimental vigente:

| Región | Offset |
|---|---:|
| RM | −1 °C |
| Biobío | +2 °C |
| Araucanía | +3 °C |
| Los Ríos | +3 °C |
| Los Lagos | +4 °C |
| Aysén | +5 °C |

Las demás regiones usan el offset global de `--setpoint-offset-c`.

## HDD regional y exposición meteorológica

El archivo aislado de referencia es:

```text
outputs/chile_hdd_reference/hdd_regional_ponderado_lena_2024.csv
```

Incluye HDD12 y HDD14 por región, ponderados por el número de inmuebles que
declaran calefacción a leña. Con `--hdd-envelope`, el script calcula factores
regionales para `U_Wall_*`, `U_Window` y `n_air_infiltration`:

```text
factor = clip((HDD14_region / HDD14_reference) ** beta, 0.70, 1.75)
```

Los exponentes actuales son `beta_wall=0.25`, `beta_window=0.15` y
`beta_infiltration=0.35`. Se pueden modificar con los argumentos
`--hdd-beta-wall`, `--hdd-beta-window` y `--hdd-beta-infiltration`.

Con `--weather-exposure`, el viento (`wspd`) y un proxy de humedad construido
con `rh` y `tdew` modifican temporalmente sólo la infiltración. La vista
`meteorology_commune.era5_hourly_comunal` debe entregar `tdry`, `tdew`, `rh`,
`wspd` y `wdir`; no hay precipitación directa en esta fuente.

## Archivos de salida

Cada corrida escribe:

```text
simulation_results.csv                 # una fila por vivienda
simulation_errors.csv                  # sólo si hay fallos
regional_consumption_comparison.csv   # tabla regional vs REDPE
regional_consumption_comparison.md    # tabla legible
regional_consumption_vs_redpe.png     # gráfico regional ordenado geográficamente
regional_hdd_weighted_by_wood_units.csv
redpe_reference_ranges.csv
run_summary.json
```

Para reutilizar resultados sin repetir las 500 simulaciones:

```bash
PYTHONPATH=. python \
  examples/chile/analyze_wood_stove_bidirectional_regional_dispersion.py \
  --env-file /ruta/a/geonode_connection/.env \
  --output-dir outputs/chile_wood_stove_regional_run \
  --sample-file outputs/chile_wood_stove_regional_dispersion_hdd12/selected_buildings.csv \
  --hdd-envelope \
  --hdd-file outputs/chile_hdd_reference/hdd_regional_ponderado_lena_2024.csv \
  --hardcoded-regional-offsets \
  --reuse-results
```

## Verificación

Las pruebas del acoplamiento bidireccional se ejecutan con:

```bash
PYTHONPATH=. pytest -q test/test_wood_stove_5r1c_bidirectional.py
```

El resultado esperado actual es `5 passed`. Las simulaciones regionales deben
terminar con `successful_simulations=500` y `failed_simulations=0` en
`run_summary.json`.

Para el razonamiento y las iteraciones de calibración, consultar
[`PLAN_BIDIRECTIONAL_5R1C_WOOD_STOVE.md`](../../feature-request/chile_wood_consumption/PLAN_BIDIRECTIONAL_5R1C_WOOD_STOVE.md).
