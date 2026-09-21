# Dispersión regional de simulaciones de estufa a leña

**Estado:** corrida inicial de 10 registros por región completada; se agregó
una corrida proporcional de 500 registros.

## Objetivo

Evaluar la dispersión de la demanda de calefacción y del volumen de leña entre
registros residenciales que tienen `tipo_comb_calef='lena'` en GeoNode. La
corrida inicial seleccionó 10 registros `edificio_id` por cada una de las 16
regiones de Chile. La corrida ampliada selecciona 500 registros con una cuota
regional proporcional al número de unidades habitacionales con calefacción a
leña y ejecuta el camino ERA5 2024 → 5R1C → módulo de estufa.

La unidad de muestreo es el registro `edificio_id` de
`merlin_rcp.edificios`. Un registro puede representar varias unidades
habitacionales (`n_inmuebles`); por tanto, las 500 simulaciones son una muestra
de registros modelables y no 500 viviendas individuales independientes.

## Método reproducible

El análisis se ejecuta con:

```bash
PYTHONPATH=. python examples/chile/analyze_wood_stove_regional_dispersion.py \
  --env-file /ruta/local/geonode.env \
  --year 2024 \
  --total-samples 500 \
  --seed 2024 \
  --output-dir outputs/chile_wood_stove_regional_dispersion
```

La selección es determinista y estratificada por comuna: en cada región se
priorizan registros de comunas diferentes y luego se completa la muestra con
una segunda selección dentro de las comunas disponibles. La cuota regional se
calcula con el número de unidades (`n_inmuebles`) que declaran leña entre los
registros elegibles. Se conserva un mínimo de 10 registros por región para
que la dispersión regional siga siendo calculable y el resto de la cuota se
reparte proporcionalmente por unidades a leña. El informe registra además el
stock regional elegible y la proporción de unidades a leña sobre ese stock. Se
excluyen arquetipos no
reconocidos por el catálogo chileno, áreas no positivas y registros sin
coordenadas.

La asignación usa el número absoluto de unidades a leña, no sólo la fracción
regional. Esto es importante: para estimar el consumo de la población que usa
leña, una región grande con una fracción moderada puede aportar más viviendas
consumidoras que una región pequeña con una fracción alta. La fracción
`wood_share_regional` se conserva como indicador descriptivo de prevalencia.

La opción heredada `--samples-per-region 10` permite reproducir la corrida
exploratoria original con cuota fija.

Cada registro usa:

- la serie completa de `meteorology_commune.era5_hourly_comunal` para 2024;
- el `episcope_archetype`, área promedio y personas de GeoNode;
- el modelo directo 5R1C de tsib_fcr;
- eficiencia de estufa 0,50;
- `coverage_mid`: 75% de cobertura útil de la demanda de calefacción;
- `redpe_mid`: objetivo energético medio REDPE por vivienda consumidora, sólo
  en las nueve regiones con fila en la tabla REDPE 2020.

El escenario `coverage_mid` permite comparar las 16 regiones bajo una misma
regla. `redpe_mid` es una referencia observada regional y no sustituye una
calibración individual.

## Resultados de la corrida exploratoria inicial

Se completaron 160 simulaciones 5R1C, 10 por región, sin errores. Se generaron
250 filas porque las nueve regiones REDPE agregan una evaluación
`redpe_mid` adicional por registro.

| Región | Demanda P10 (kWh/a) | Mediana (kWh/a) | Demanda P90 (kWh/a) | CV | Leña mediana (m³ st/a) |
|---|---:|---:|---:|---:|---:|
| Tarapacá | 1.490,7 | 3.494,8 | 8.860,5 | 0,85 | 2,81 |
| Antofagasta | 760,5 | 6.414,5 | 19.718,7 | 1,56 | 5,15 |
| Atacama | 2.421,5 | 5.639,5 | 14.451,3 | 0,97 | 4,53 |
| Coquimbo | 3.725,3 | 6.011,1 | 13.274,5 | 1,05 | 4,83 |
| Valparaíso | 2.464,6 | 3.690,1 | 18.657,9 | 1,87 | 2,97 |
| O’Higgins | 2.008,9 | 5.592,3 | 12.103,7 | 0,89 | 4,49 |
| Maule | 3.572,7 | 5.452,0 | 12.959,9 | 1,10 | 4,38 |
| Biobío | 3.032,5 | 5.965,4 | 16.714,0 | 1,72 | 4,79 |
| Araucanía | 2.955,7 | 6.532,1 | 9.266,7 | 0,44 | 5,25 |
| Los Lagos | 3.819,3 | 7.606,7 | 12.698,3 | 0,52 | 6,11 |
| Aysén | 6.738,2 | 9.426,4 | 13.179,3 | 0,31 | 7,57 |
| Magallanes | 12.175,8 | 17.214,6 | 26.647,9 | 0,59 | 13,83 |
| RM | 2.731,5 | 4.293,0 | 8.380,2 | 0,60 | 3,45 |
| Los Ríos | 3.823,8 | 7.454,2 | 14.042,2 | 0,63 | 5,99 |
| Arica y Parinacota | 2.634,5 | 6.583,2 | 11.064,0 | 1,12 | 5,29 |
| Ñuble | 4.054,8 | 7.584,5 | 17.284,6 | 1,04 | 6,09 |

El escenario `coverage_mid` transforma la demanda en objetivo de combustible
con `fuel = demand × 0,75 / 0,50`; por eso la dispersión del volumen de leña
es proporcional a la dispersión de la demanda simulada.

La mayor dispersión relativa de esta muestra aparece en Valparaíso, Biobío y
Antofagasta. Las medianas más altas están en Magallanes, Aysén, Los Lagos,
Ñuble y Los Ríos. Son resultados exploratorios: no permiten todavía afirmar
que esas regiones tengan esa distribución poblacional de consumo.

## Corrida ampliada proporcional: 500 registros

La corrida ampliada completó 500 simulaciones sin errores. Se mantuvieron al
menos 10 registros por región y las 340 plazas restantes se asignaron según
las unidades que declaran calefacción a leña. Las cuotas fueron: Biobío 88,
Araucanía 65, Maule 57, Los Lagos 52, Valparaíso 37, O’Higgins 35, Los Ríos
33, Ñuble 30, RM 20, Aysén 17, Coquimbo 15, Magallanes 11, y 10 para
Tarapacá, Antofagasta, Atacama y Arica y Parinacota.

| Región | n | Demanda P10 | Mediana | Demanda P90 | CV | Leña mediana (m³ st/a) |
|---|---:|---:|---:|---:|---:|---:|
| Tarapacá | 10 | 1.490,7 | 3.494,8 | 8.860,5 | 0,85 | 2,81 |
| Antofagasta | 10 | 760,5 | 6.414,5 | 19.718,7 | 1,56 | 5,15 |
| Atacama | 10 | 2.421,5 | 5.639,5 | 14.451,3 | 0,97 | 4,53 |
| Coquimbo | 15 | 2.724,8 | 4.266,5 | 11.343,3 | 1,31 | 3,43 |
| Valparaíso | 37 | 2.368,9 | 5.325,5 | 18.522,6 | 1,14 | 4,28 |
| O’Higgins | 35 | 2.281,4 | 4.613,7 | 12.421,2 | 0,87 | 3,71 |
| Maule | 57 | 2.661,9 | 5.060,5 | 12.375,3 | 1,41 | 4,07 |
| Biobío | 88 | 3.232,0 | 5.113,7 | 10.745,6 | 0,88 | 4,11 |
| Araucanía | 65 | 3.779,7 | 6.173,8 | 12.563,4 | 0,67 | 4,96 |
| Los Lagos | 52 | 3.598,1 | 6.560,2 | 11.734,1 | 0,50 | 5,27 |
| Aysén | 17 | 6.556,9 | 9.408,9 | 13.269,2 | 0,38 | 7,56 |
| Magallanes | 11 | 12.433,1 | 17.910,3 | 24.569,2 | 0,54 | 14,39 |
| RM | 20 | 2.804,8 | 4.251,0 | 10.628,4 | 4,84 | 3,42 |
| Los Ríos | 33 | 3.854,9 | 7.012,0 | 17.581,4 | 1,06 | 5,63 |
| Arica y Parinacota | 10 | 2.634,5 | 6.583,2 | 11.064,0 | 1,12 | 5,29 |
| Ñuble | 30 | 3.297,5 | 4.958,5 | 10.337,3 | 1,06 | 3,98 |

El aumento de muestra mejora la estabilidad de los cuantiles en las regiones
del centro-sur, pero no convierte automáticamente el resultado en un
estimador insesgado: la selección sigue restringida a registros modelables,
se estratifica por comuna y puede representar varias unidades con un mismo
`edificio_id`. Para agregaciones poblacionales se debe usar el factor de
expansión y `n_inmuebles`, no el promedio simple de todos los registros.

## Comparación inicial con REDPE: muestra de 10 registros

La comparación se realizó contra la tabla REDPE 2020, que contiene consumos
anuales de 2017 en m³ estéreo por vivienda consumidora. El escenario simulado
`coverage_mid` no es una observación: representa 75% de cobertura útil con una
eficiencia de estufa de 0,50. Por ello, su volumen corresponde a la demanda de
combustible de la vivienda modelada, mientras que REDPE representa consumo
regional observado por vivienda consumidora.

| Región | REDPE bajo–alto (m³ st/a) | REDPE medio | Simulación mediana P10–P90 | Mediana / REDPE medio | Dentro del rango REDPE |
|---|---:|---:|---:|---:|---:|
| O’Higgins | 3,50–4,04 | 3,77 | 4,49 (1,61–9,73) | 1,19 | 1/10 |
| Maule | 3,50–7,19 | 5,35 | 4,38 (2,87–10,41) | 0,82 | 3/10 |
| Biobío | 5,50–8,79 | 7,14 | 4,79 (2,44–13,43) | 0,67 | 2/10 |
| Araucanía | 7,70–14,41 | 11,05 | 5,25 (2,38–7,45) | 0,47 | 1/10 |
| Los Lagos | 13,80–18,40 | 16,10 | 6,11 (3,07–10,20) | 0,38 | 0/10 |
| Aysén | 17,50–32,23 | 24,86 | 7,57 (5,41–10,59) | 0,30 | 0/10 |
| Magallanes | 18,16–28,53 | 23,34 | 13,83 (9,78–21,41) | 0,59 | 1/10 |
| RM | 2,59–3,00 | 2,79 | 3,45 (2,19–6,73) | 1,23 | 0/10 |
| Los Ríos | 14,10–14,22 | 14,16 | 5,99 (3,07–11,28) | 0,42 | 0/10 |

La mediana simulada supera REDPE en O’Higgins y la RM, es relativamente
próxima en Maule y Biobío, y queda bastante por debajo en Araucanía, Los
Lagos, Aysén, Magallanes y Los Ríos. Entre cero y tres de los diez registros
por región quedaron dentro del intervalo REDPE bajo–alto. No hay comparación
directa para Tarapacá, Antofagasta, Atacama, Coquimbo, Valparaíso, Arica y
Parinacota ni Ñuble porque la tabla REDPE incorporada no contiene esas filas.

El escenario adicional `redpe_mid` impone el objetivo medio REDPE y permite
observar el desbalance con la demanda 5R1C: el objetivo queda corto en parte
de las muestras de O’Higgins, Maule, Biobío y la RM, mientras que en Aysén,
Los Lagos y Los Ríos suele sobrar energía objetivo frente a la demanda
simulada. Esto no valida ni invalida por sí solo la tabla: muestra que ambas
fuentes representan unidades y poblaciones distintas.

### Comparación REDPE_mid en la muestra ampliada

En la corrida de 500 registros, el escenario `redpe_mid` se evaluó en las
nueve regiones con datos REDPE. La simulación corresponde al MVP directo con
el objetivo anual REDPE; todavía no es la calibración del controlador de
eventos y almacenamiento.

| Región | REDPE_mid (m³ st/a) | Simulación mediana P10–P90 (m³ st/a) | Mediana/REDPE | No asignado mediano (kWh) | No satisfecho mediano (kWh) |
|---|---:|---:|---:|---:|---:|
| O’Higgins | 3,77 | 3,77 (2,44–3,77) | 1,00 | 0 | 1.093,7 |
| Maule | 5,35 | 5,35 (2,85–5,35) | 1,00 | 0 | 70,5 |
| Biobío | 7,15 | 5,48 (3,46–7,14) | 0,77 | 3.107,6 | 0 |
| Araucanía | 11,06 | 6,61 (4,05–11,06) | 0,60 | 8.292,4 | 0 |
| Los Lagos | 16,10 | 7,03 (3,86–12,57) | 0,44 | 16.924,7 | 0 |
| Aysén | 24,87 | 10,08 (7,03–14,22) | 0,41 | 27.592,1 | 0 |
| Magallanes | 23,35 | 19,19 (13,32–23,35) | 0,82 | 7.759,3 | 0 |
| RM | 2,80 | 2,80 (2,77–2,80) | 1,00 | 0 | 1.638,5 |
| Los Ríos | 14,16 | 7,51 (4,13–14,16) | 0,53 | 12.406,0 | 0 |

La mayor discrepancia permanece en Aysén, Los Lagos y Los Ríos: el objetivo
REDPE supera la demanda térmica que puede absorber el modelo 5R1C de muchos
registros, por lo que aparece combustible no asignado. Esto justifica calibrar
la escala anual contra REDPE, pero manteniendo una penalización explícita por
energía no asignada y demanda no satisfecha.

## Archivos generados

Los resultados quedan en
`outputs/chile_wood_stove_regional_dispersion/`:

- `selected_buildings.csv`: los 500 registros seleccionados y sus atributos;
- `regional_sampling_allocation.csv`: stock regional, prevalencia de leña y
  cuota solicitada/seleccionada;
- `simulation_results.csv`: resultados por registro y escenario;
- `regional_summary.csv`: mínimos, P10, mediana, P90, máximos, desviación y
  coeficiente de variación por región, además de medias ponderadas por
  `n_inmuebles`;
- `simulation_errors.csv`: esquema de errores, vacío en esta ejecución;
- `README.md`: resumen de la corrida.

## Límites y siguiente uso

- `tipo_comb_calef` identifica un combustible principal asignado al registro,
  pero no observa potencia, eficiencia, encendidos ni consumo medido de la
  estufa.
- El arquetipo, las personas modeladas y el área promedio influyen fuertemente
  en la dispersión.
- Quinientos registros mejoran los cuantiles regionales, pero no reemplazan
  una muestra probabilística de viviendas consumidoras ni datos medidos de
  consumo.
- La comparación con REDPE debe hacerse en una cohorte de viviendas
  consumidoras y con una definición explícita de unidad (`edificio_id`,
  `n_inmuebles` o vivienda consumidora).

La Fase 6 ya inició con el modelo de eventos y almacenamiento documentado en
`PHASE6_EVENTS_STORAGE.md`. El siguiente paso es calibrar sus parámetros de
carga, duración, pérdidas y capacidad, y comparar su resultado temporal con el
MVP y REDPE antes de incorporar retroalimentación sobre la temperatura
interior.
