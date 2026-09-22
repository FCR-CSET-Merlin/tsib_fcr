# Consumo residencial de leña en Chile

## Estado y propósito

Esta rama prepara un modelo de **estimación de consumo de leña residencial**
para Chile. No debe reutilizar `simFireplace()` como si fuese un modelo
calibrado de combustión: esa función upstream sólo construye una señal horaria
estocástica a partir de temperatura y actividad.

El objetivo inicial es convertir una demanda térmica horaria ya calculada por
el modelo 5R1C en un rango trazable de:

- calor útil abastecido por leña;
- energía química de la leña;
- volumen anual en metros cúbicos estéreo (`m3 st`);
- masa anual de leña.

La calibración debe ser regional, explícita en sus supuestos y separada para
calefacción, cocina y ACS. La primera versión debe cubrir exclusivamente
**calefacción de espacios**; cocina y ACS se añadirán sólo con perfiles y
datos adecuados.

## Fuente de referencia

El insumo preparado se encuentra en MERLIN_RCP, rama
[`analysis-consumo-lena`](https://github.com/FCR-CSET-Merlin/MERLIN_RCP/tree/analysis-consumo-lena),
commit `c78c443e1739adbce8d6648f7c42a38496394c34`:

- `data/reference/lena_consumo_residencial_redpe_2020.csv`: consumo 2017 por
  región y por **vivienda consumidora**, con extremos inferior y superior.
- `data/reference/lena_artefactos_redpe_2020.csv`: parque de artefactos y una
  eficiencia ponderada de escenario.
- `data/reference/lena_penetracion_usos_casen_2017.csv`: penetración de leña
  por uso final, sin sumar usos porque un hogar puede declarar más de uno.
- `docs/guias/datos_lena_redpe_2020.md`: trazabilidad de RedPE 2020 y de las
  conversiones.

Los valores de consumo son energía de entrada de combustible; no son demanda
térmica útil ni promedios de todas las viviendas de una región.

La tabla regional REDPE incorporada en la librería es
`tsib/data/chile/lena_consumo_residencial_redpe_2020.csv`. Se puede consultar
mediante:

```python
redpe = tsib.get_chile_regional_wood_consumption(8, "mid")
redpe["consumption_m3st_per_consumer"]
redpe["energy_bruta_mwh_per_consumer"]
```

La tabla cubre las regiones con filas REDPE disponibles en la fuente 2017
(RM, O'Higgins, Maule, Biobío, Araucanía, Los Ríos, Los Lagos, Aysén y
Magallanes). Ñuble no tiene una fila independiente en esta fuente histórica;
la función falla explícitamente en vez de imputar un valor.

## Modelo propuesto

Para una vivienda que usa leña para calefacción:

```text
E_fuel,target [MWh/a]
    <- rango RedPE regional por vivienda consumidora

E_use,target [MWh/a]
    = E_fuel,target × eta_equipo

q_wood,useful(t) [kW]
    <- distribución de E_use,target sobre la demanda de calefacción 5R1C

q_wood,fuel(t) [kW]
    = q_wood,useful(t) / eta_equipo

V_wood [m3 st/a]
    = E_fuel,target / 1.867  # PCI = 15 MJ/kg

m_wood [t/a]
    = V_wood × 0.448
```

La asignación horaria se debe hacer sobre `Heating Load` del 5R1C y limitarse
por esa demanda. Así se evita que un perfil de encendidos cree calor útil donde
el edificio no lo requiere. Un primer perfil determinista y reproducible puede
normalizar los pasos con demanda positiva; una extensión posterior podrá usar
temperatura exterior, disponibilidad horaria y un modelo de ocupación.

### Cobertura y consistencia energética

Sea `Q_heat(t)` la demanda útil de calefacción y `E_use,target` la energía útil
anual objetivo. La implementación debe calcular:

```text
E_use,assigned = min(E_use,target, sum(Q_heat(t) × dt))
unallocated_use = E_use,target - E_use,assigned
```

`unallocated_use > 0` no se debe ocultar: puede indicar que el consumo regional
incluye cocina/ACS, que la demanda simulada es demasiado baja o que el hogar no
es comparable al promedio regional. El resultado debe reportar esa energía y
no forzarla en las horas de calefacción.

## Parámetros y escenarios

La API debería recibir, como mínimo:

```python
estimate_wood_consumption(
    heating_load,             # Series horaria, kW útiles
    region,                   # 6--16; mapeo explícito a nombres RedPE
    wood_heating_user=True,   # no inferir usuario individual desde penetración
    consumption_case="mid",   # "low", "mid", "high" o valor MWh/a explícito
    efficiency=None,          # si None: escenario regional documentado
    pci_mj_per_kg=15.0,
    solid_m3_per_stere=0.64,
    density_t_per_solid_m3=0.7,
)
```

La penetración CASEN se usará para expandir desde viviendas consumidoras al
stock regional o para generar escenarios poblacionales, nunca para reducir el
consumo de una vivienda ya clasificada como consumidora. Regiones sin valor
REDPE comparable deben requerir un valor explícito o devolver un resultado no
calibrado claramente marcado.

La eficiencia es un supuesto sensible. El escenario disponible pondera
aproximadamente 40 % para hechizo/chimenea, 50 % para cocina/salamandra/cámara
simple y 65 % para cámara doble/caldera. No representa eficiencias certificadas
por equipo ni una observación contemporánea homogénea.

## Relación con `simFireplace()`

`simFireplace()` puede inspirar una futura variante estocástica del *timing*,
pero no debe determinar el consumo anual chileno. Su parámetro `fullloadSteps`
no tiene relación con los rangos REDPE y su calibración no usa ni tipo de
artefacto, ni PCI, ni eficiencia, ni datos chilenos. La primera implementación
debe tener conservación energética y reproducibilidad como requisitos.

## Entregables incrementales

1. Incorporar la tabla REDPE normalizada con metadatos de fuente y un mapeo
   región administrativa (`1..16`) a región RedPE.
2. Implementar un estimador puro, sin depender de Pyomo ni de ocupación.
3. Añadir pruebas de conservación de energía, conversión de unidades,
   manejo de rango y límite por demanda útil.
4. Integrar opcionalmente en el flujo de `BuildingConfiguration` sólo después
   de validar resultados contra balances regionales; no alterar `elecLoad`.
5. Definir, con datos adicionales, perfiles de cocina/ACS y una posible
   estocasticidad de uso.
## MVP implementado

La rama incluye `tsib.simulate_wood_stove(...)` en `tsib/renewables/wood_stove.py`. El módulo recibe `Heating Load` útil, asigna un objetivo de energía de combustible respetando la demanda, la potencia máxima, la disponibilidad y un perfil temporal opcional, y devuelve calor útil, entrada de combustible, masa, volumen y energía no asignada.

El MVP es un modelo de capa de sistema posterior a 5R1C: no modifica `elecLoad`, no ejecuta combustión CFD y no retroalimenta todavía la temperatura interior. Esa dinámica queda reservada para la siguiente etapa, junto con eventos de encendido y almacenamiento térmico.

Las pruebas están en `test/test_wood_stove.py` y cubren conservación de energía, límite por demanda, disponibilidad, potencia máxima, perfil temporal, pasos de 30 minutos y validación de parámetros.

La segunda etapa dinámica está disponible en
`tsib.simulate_wood_stove_events(...)`. Añade cargas discretas de leña,
combustión distribuida por evento, almacenamiento térmico de un estado,
pérdidas, potencia de descarga y estados operativos. Su alcance y supuestos
están documentados en
[`PHASE6_EVENTS_STORAGE.md`](PHASE6_EVENTS_STORAGE.md), con un ejemplo en
[`examples/chile/wood_stove_events.py`](../../examples/chile/wood_stove_events.py).
La función `tsib.calibrate_wood_stove_event_parameters(...)` permite una
calibración numérica contra el MVP cuando no hay observaciones físicas; no debe
interpretarse como calibración del comportamiento real.

## Integración con 5R1C

La función `tsib.simulate_wood_stove_from_5r1c(...)` conecta una simulación
5R1C ya ejecutada con el módulo de estufa sin modificar el modelo de edificio
ni `elecLoad`:

```python
model = tsib.Building5R1C(cfg)
model.sim_demand_direct()

stove = tsib.simulate_wood_stove_from_5r1c(
    model,
    fuel_energy_target_kwh=target_fuel_kwh,
    efficiency=0.50,
)
```

El argumento `source` puede ser un objeto `Building5R1C`, el wrapper de alto
nivel `Building` o el `DataFrame` `detailedResults`. La simulación 5R1C debe
ejecutarse previamente mediante `sim_demand_direct()` o `sim5R1C()`; el
adaptador falla explícitamente si no existe la columna `Heating Load`.

El ejemplo reproducible
[`examples/chile/wood_stove_5r1c.py`](../../examples/chile/wood_stove_5r1c.py)
usa una vivienda chilena y meteorología sintética determinista. La selección
de una vivienda y un año meteorológico observacional queda reservada para la
Fase 5 de validación.

Para la validación con GeoNode se utiliza el script
[`examples/chile/validate_wood_stove_geonode.py`](../../examples/chile/validate_wood_stove_geonode.py).
Lee `merlin_rcp.edificios`, une el código SII con el CUT de la comuna y carga
el año local completo desde `meteorology_commune.era5_hourly_comunal`. Las
credenciales se entregan mediante `GEONODE_HOST`, `GEONODE_PORT`,
`GEONODE_DATABASE`, `GEONODE_USER` y `GEONODE_PASSWORD`, o mediante un archivo
local pasado con `--env-file`; nunca deben escribirse en el repositorio.

El script ejecuta tres sensibilidades de cobertura útil de calefacción (`low`,
`mid`, `high`) y tres escenarios REDPE (`redpe_low`, `redpe_mid`,
`redpe_high`). Los escenarios REDPE usan la energía bruta por vivienda
consumidora de la tabla incorporada y reportan por separado el calor útil
asignado, la demanda no satisfecha y la energía no asignada.

La primera corrida de dispersión regional está documentada en
[`REGIONAL_DISPERSION_WOOD_STOVE.md`](REGIONAL_DISPERSION_WOOD_STOVE.md). El
script [`examples/chile/analyze_wood_stove_regional_dispersion.py`](../../examples/chile/analyze_wood_stove_regional_dispersion.py)
selecciona por defecto 500 registros `edificio_id` con una cuota regional
proporcional al número de unidades habitacionales que declaran calefacción a
leña, usa ERA5 2024 y genera el resumen en
`outputs/chile_wood_stove_regional_dispersion/`. El informe también conserva la
proporción de unidades a leña respecto del stock regional elegible. La muestra
sigue siendo exploratoria: un `edificio_id` puede representar varias unidades
habitacionales y la base no equivale automáticamente a una muestra aleatoria
de viviendas individuales.

Las dependencias opcionales para ese script están en
`requirements-validation.txt`:

```bash
python -m pip install -r requirements-validation.txt
```

Para seleccionar los parámetros de eventos con el objetivo anual REDPE se
puede usar `examples/chile/calibrate_wood_stove_events.py --calibration-target
redpe_mid`. La opción `--total-samples` usa la misma cuota proporcional del
análisis regional; por defecto la calibración mantiene una muestra pequeña por
región para no multiplicar innecesariamente la grilla de 144 candidatos.

La calibración regional de cohorte, con un único conjunto de parámetros por
región y validación holdout, se ejecuta con
`examples/chile/calibrate_wood_stove_regional_cohort.py` y deja sus resultados
en `outputs/chile_wood_stove_regional_cohort_calibration/`. La corrida de 500
registros evalúa 144 candidatos por región sobre perfiles 5R1C agregados y
ponderados por `n_inmuebles`; nueve regiones se calibran contra `REDPE_mid` y
las siete restantes usan `MVP_coverage_mid` como fallback explícito. El
objetivo REDPE se compara directamente con el combustible asignado y se
reportan por separado el combustible no asignado y la demanda no satisfecha,
sin forzar que ambos balances coincidan.

También se ejecutó una sensibilidad de setpoint invernal a 22 °C y 24 °C para
Magallanes, Los Ríos, Los Lagos y Araucanía. El análisis está en
[`SETPOINT_SENSITIVITY_SOUTH.md`](SETPOINT_SENSITIVITY_SOUTH.md) y se puede
reproducir con
`examples/chile/analyze_wood_stove_setpoint_sensitivity.py`. La corrida usa
disponibilidad de la estufa entre las 08:00 y las 23:00.

Para inspeccionar un día horario se puede usar
`examples/chile/inspect_wood_stove_winter_day.py`. El ejemplo de Natales
selecciona el día invernal más frío y exporta temperatura ambiente, temperatura
interior, potencia de combustión, calor útil y masa de leña por hora en
`outputs/chile_wood_stove_winter_day_magallanes/`.
