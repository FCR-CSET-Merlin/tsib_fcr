# Dispersión regional de simulaciones de estufa a leña

**Estado:** primera corrida exploratoria completada.

## Objetivo

Evaluar la dispersión de la demanda de calefacción y del volumen de leña entre
registros residenciales que tienen `tipo_comb_calef='lena'` en GeoNode. Se
seleccionaron 10 registros `edificio_id` por cada una de las 16 regiones de
Chile y se ejecutó el camino ERA5 2024 → 5R1C → módulo de estufa.

La unidad de muestreo es el registro `edificio_id` de
`merlin_rcp.edificios`. Un registro puede representar varias unidades
habitacionales (`n_inmuebles`); por tanto, esta primera corrida no debe
interpretarse como una muestra de 10 viviendas individuales por región.

## Método reproducible

El análisis se ejecuta con:

```bash
PYTHONPATH=. python examples/chile/analyze_wood_stove_regional_dispersion.py \
  --env-file /ruta/local/geonode.env \
  --year 2024 \
  --samples-per-region 10 \
  --seed 2024 \
  --output-dir outputs/chile_wood_stove_regional_dispersion
```

La selección es determinista y estratificada por comuna: en cada región se
priorizan registros de comunas diferentes y luego se completa la muestra con
una segunda selección dentro de las comunas disponibles. Se excluyen
arquetipos no reconocidos por el catálogo chileno, áreas no positivas y
registros sin coordenadas.

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

## Resultados

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

## Archivos generados

Los resultados quedan en
`outputs/chile_wood_stove_regional_dispersion/`:

- `selected_buildings.csv`: los 160 registros seleccionados y sus atributos;
- `simulation_results.csv`: resultados por registro y escenario;
- `regional_summary.csv`: mínimos, P10, mediana, P90, máximos, desviación y
  coeficiente de variación por región;
- `simulation_errors.csv`: esquema de errores, vacío en esta ejecución;
- `README.md`: resumen de la corrida.

## Límites y siguiente uso

- `tipo_comb_calef` identifica un combustible principal asignado al registro,
  pero no observa potencia, eficiencia, encendidos ni consumo medido de la
  estufa.
- El arquetipo, las personas modeladas y el área promedio influyen fuertemente
  en la dispersión.
- Diez registros por región sirven para inspección inicial, no para estimar
  cuantiles regionales definitivos.
- La comparación con REDPE debe hacerse en una cohorte de viviendas
  consumidoras y con una definición explícita de unidad (`edificio_id`,
  `n_inmuebles` o vivienda consumidora).

El siguiente paso recomendado es ampliar la muestra o aplicar un diseño
estratificado por región, comuna, arquetipo y área, antes de calibrar la
dinámica de eventos y almacenamiento de la Fase 6.
