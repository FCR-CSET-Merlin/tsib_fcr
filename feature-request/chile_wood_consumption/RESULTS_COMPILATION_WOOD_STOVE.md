# Compilación de resultados de la simulación de leña

## Objetivo y criterio de comparación

Este documento reúne los resultados regionales obtenidos durante el desarrollo
del módulo de estufa a leña. Las cifras de consumo están expresadas como
metros cúbicos estéreo por año (`m³ st/a`) y corresponden a la **mediana no
ponderada por registro `edificio_id`** dentro de cada región.

La muestra principal contiene 500 registros y es la misma en el MVP, el modelo
por eventos y la corrida HDD12. Se verificó que los 500 `edificio_id` son
idénticos entre esas corridas. La sensibilidad de setpoint usa el subconjunto
de las cuatro regiones del sur analizadas.

La secuencia debe leerse como una progresión de modelos y sensibilidades, no
como una única corrida acumulativa:

```text
5R1C sin estufa → MVP simple → eventos y almacenamiento → banda 08:00–23:00
                                      └─ sensibilidad HDD12 separada
                                                  └─ setpoint 22/24 °C
```

Para mantener comparable el objetivo anual:

- en las nueve regiones con información REDPE se usa `REDPE_mid`;
- en las siete regiones restantes se usa `MVP_coverage_mid`, equivalente a
  75% de cobertura útil de calefacción y eficiencia 0,50.

## Qué significa “sin simulación de leña”

Antes del módulo de leña, el modelo sólo entregaba la demanda útil de
calefacción 5R1C (`Heating Load`). Por ello, el valor original no es un
consumo de leña: se reporta en `kWh/a`. Convertirlo directamente a `m³ st/a`
requiere asumir cobertura de la demanda, eficiencia, PCI y disponibilidad del
combustible.

## Medianas regionales: línea base, MVP, eventos y HDD12

| Región | 5R1C sin estufa (kWh/a) | MVP simple (m³ st/a) | Eventos sin banda (m³ st/a) | Banda 08–23 (m³ st/a) | HDD12 MVP (m³ st/a) |
|---|---:|---:|---:|---:|---:|
| Tarapacá | 3.494,8 | 2,81 | 3,40 | — | 2,81 |
| Antofagasta | 6.414,5 | 5,15 | 4,35 | — | 5,15 |
| Atacama | 5.639,5 | 4,53 | 5,47 | — | 4,53 |
| Coquimbo | 4.266,5 | 3,43 | 4,56 | — | 3,43 |
| Valparaíso | 5.325,5 | 4,28 | 5,20 | — | 4,28 |
| O’Higgins | 4.613,7 | 3,77 | 3,50 | — | 3,77 |
| Maule | 5.060,5 | 5,35 | 5,33 | — | 5,35 |
| Biobío | 5.113,7 | 5,48 | 5,73 | — | 5,48 |
| Araucanía | 6.173,8 | 6,61 | 8,74 | 8,37 | 7,41 |
| Los Lagos | 6.560,2 | 7,03 | 14,45 | 9,47 | 8,65 |
| Aysén | 9.408,9 | 10,08 | 24,86 | — | 13,96 |
| Magallanes | 17.910,3 | 19,19 | 19,17 | 12,57 | 23,35 |
| RM | 4.251,0 | 2,80 | 2,80 | — | 2,80 |
| Los Ríos | 7.012,0 | 7,51 | 10,54 | 7,58 | 8,72 |
| Arica y Parinacota | 6.583,2 | 5,29 | 6,37 | — | 5,29 |
| Ñuble | 4.958,5 | 3,98 | 5,20 | — | 3,98 |

La columna de banda horaria sólo existe para Araucanía, Los Ríos, Los Lagos y
Magallanes, que fueron las regiones seleccionadas para la sensibilidad de
operación realista de la estufa.

## Comparación transversal contra REDPE_mid

La siguiente tabla concentra las medianas regionales disponibles junto al
objetivo `REDPE_mid`. Todas las columnas de consumo están en `m³ st/a`. El
objetivo REDPE representa consumo de combustible por vivienda consumidora; las
columnas simuladas representan el combustible asignado por el modelo bajo
cada configuración.

| Región | REDPE_mid | MVP simple | Eventos sin banda | Banda 08–23 | 22 °C | 24 °C | HDD12 MVP |
|---|---:|---:|---:|---:|---:|---:|---:|
| O’Higgins | 3,77 | 3,77 | 3,50 | — | — | — | 3,77 |
| Maule | 5,35 | 5,35 | 5,33 | — | — | — | 5,35 |
| Biobío | 7,15 | 5,48 | 5,73 | — | — | — | 5,48 |
| Araucanía | 11,06 | 6,61 | 8,74 | 8,37 | 9,29 | 9,74 | 7,41 |
| Los Lagos | 16,10 | 7,03 | 14,45 | 9,47 | 10,48 | 10,93 | 8,65 |
| Aysén | 24,87 | 10,08 | 24,86 | — | — | — | 13,96 |
| Magallanes | 23,35 | 19,19 | 19,17 | 12,57 | 13,70 | 14,04 | 23,35 |
| RM | 2,80 | 2,80 | 2,80 | — | — | — | 2,80 |
| Los Ríos | 14,16 | 7,51 | 10,54 | 7,58 | 8,21 | 8,76 | 8,72 |

La cercanía de Aysén en la columna de eventos sin banda y de Magallanes en la
columna HDD12 no significa que esas configuraciones sean equivalentes: cada
una modifica un componente distinto del modelo. En particular, HDD12 se
aplicó al MVP simple y todavía no se combinó con eventos, banda horaria ni
setpoint.

## Efecto de la banda horaria y del setpoint

La corrida de eventos sin banda permite iniciar cargas cuando la demanda lo
requiere durante todo el día. La banda horaria permite iniciar eventos sólo
entre las 08:00 y las 23:00; un evento iniciado puede terminar después según
su duración. Los setpoints de 22 °C y 24 °C se aplican en junio, julio y
agosto, manteniendo el cooling setpoint 2 °C por encima.

| Región | Eventos sin banda | Banda 08–23 | Cambio banda | Setpoint 22 °C | Cambio vs banda | Setpoint 24 °C | Cambio 24 vs 22 |
|---|---:|---:|---:|---:|---:|---:|---:|
| Araucanía | 8,74 | 8,37 | -4,3% | 9,29 | +11,1% | 9,74 | +4,8% |
| Los Ríos | 10,54 | 7,58 | -28,1% | 8,21 | +8,4% | 8,76 | +6,7% |
| Los Lagos | 14,45 | 9,47 | -34,5% | 10,48 | +10,7% | 10,93 | +4,3% |
| Magallanes | 19,17 | 12,57 | -34,4% | 13,70 | +8,9% | 14,04 | +2,5% |

La banda horaria reduce el consumo simulado porque impide iniciar eventos en
las horas nocturnas, cuando existe demanda térmica. El efecto es más fuerte en
Los Lagos y Magallanes. Subir el setpoint recupera parte del consumo al
aumentar la demanda invernal, pero no compensa completamente la reducción
causada por la disponibilidad horaria.

## Efecto del ajuste HDD12

El ajuste HDD12 se aplicó al MVP simple, no al modelo de eventos con banda y
setpoint. Se calcularon grados-día con temperatura base de 12 °C usando todo
el stock elegible que declara leña, ponderado por `n_inmuebles`, y se
modificaron U de muros, U de ventanas e infiltración en las regiones sur y
austral.

| Región | MVP simple | HDD12 MVP | Cambio HDD12 |
|---|---:|---:|---:|
| Araucanía | 6,61 | 7,41 | +12,0% |
| Los Ríos | 7,51 | 8,72 | +16,0% |
| Los Lagos | 7,03 | 8,65 | +23,1% |
| Aysén | 10,08 | 13,96 | +38,4% |
| Magallanes | 19,19 | 23,35 | +21,7% |

El aumento es coherente con la severidad climática introducida: Aysén recibe
el mayor incremento relativo por su razón HDD12/Araucanía, mientras Magallanes
alcanza un valor mediano cercano a `REDPE_mid`. La sensibilidad no constituye
una calibración física y todavía no combina simultáneamente HDD, eventos,
banda horaria y setpoint.

## Primera corrida del predictor sin objetivo anual

Como prueba del nuevo modo predictivo, se simuló un inmueble por región con
7,5 kWh por leño, 219 leños por m³ estéreo, máximo de cuatro leños por evento,
umbral térmico de 8 °C y operación de 08:00 a 23:00. Estos valores son
consumos predichos por eventos y no medianas regionales; `REDPE_mid` aparece
únicamente como validación posterior.

| Región | Leña predicha (m³ st/a) | REDPE_mid | Error relativo | Eventos |
|---|---:|---:|---:|---:|
| Tarapacá | 0,790 | — | — | 173 |
| Antofagasta | 0,078 | — | — | 16 |
| Atacama | 4,616 | — | — | 1.011 |
| Coquimbo | 2,183 | — | — | 440 |
| Valparaíso | 1,717 | — | — | 371 |
| O’Higgins | 2,037 | 3,77 | -46,0% | 446 |
| Maule | 2,237 | 5,35 | -58,1% | 490 |
| Biobío | 3,041 | 7,15 | -57,4% | 657 |
| Araucanía | 4,384 | 11,06 | -60,3% | 959 |
| Los Lagos | 6,489 | 16,10 | -59,7% | 1.412 |
| Aysén | 3,105 | 24,87 | -87,5% | 680 |
| Magallanes | 9,717 | 23,35 | -58,4% | 1.761 |
| RM | 1,233 | 2,80 | -55,9% | 270 |
| Los Ríos | 4,557 | 14,16 | -67,8% | 988 |
| Arica y Parinacota | 0,215 | — | — | 47 |
| Ñuble | 8,959 | — | — | 675 |

La primera corrida conserva el orden climático esperado entre Antofagasta y
RM para los inmuebles seleccionados, pero subestima REDPE en todas las
regiones con referencia disponible. Esto no se corrige inyectando REDPE como
objetivo: se debe revisar la potencia efectiva, frecuencia de recarga,
setpoint, respuesta térmica del edificio y retroalimentación de la temperatura
interior. El detalle horario está en
`outputs/chile_wood_stove_predictive_regional/`.

## Interpretación principal

1. El 5R1C base cuantifica la demanda térmica, pero no determina por sí solo
   el consumo de leña.
2. El MVP simple transforma un objetivo anual en combustible asignado de forma
   directa y sirve como referencia energética estable.
3. El modelo por eventos redistribuye temporalmente la misma escala anual y,
   con la calibración regional de cohorte, aumenta la mediana en varias
   regiones australes.
4. La banda 08:00–23:00 tiene un efecto importante: reduce el consumo
   asignado en torno a 28–34% en Los Ríos, Los Lagos y Magallanes.
5. Elevar el setpoint a 22–24 °C aumenta el consumo entre aproximadamente 8 y
   11% respecto de la banda con 22 °C, y entre 2,5 y 6,7% adicionales al pasar
   de 22 °C a 24 °C.
6. HDD12 mejora la representación de pérdidas regionales omitidas en el MVP,
   pero deja abierta la brecha entre demanda 5R1C y consumo REDPE en Aysén,
   Los Lagos, Los Ríos y Araucanía.

## Fuentes reproducibles

- Línea base y MVP: `outputs/chile_wood_stove_regional_dispersion/`.
- Eventos regionales: `outputs/chile_wood_stove_regional_cohort_calibration/`.
- Banda horaria y setpoints: `outputs/chile_wood_stove_setpoint_sensitivity_south/`.
- HDD12: `outputs/chile_wood_stove_regional_dispersion_hdd12/`.
- Descripción de la muestra y comparación REDPE: [`REGIONAL_DISPERSION_WOOD_STOVE.md`](REGIONAL_DISPERSION_WOOD_STOVE.md).
