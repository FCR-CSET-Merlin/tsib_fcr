# Dispersion regional de simulaciones de estufa a lena

## Configuracion

- Ano meteorologico: `2024`.
- Muestra solicitada: `500` registros `edificio_id`, semilla `2024`.
- Eficiencia de estufa: `0.50`.
- Severidad climatica: HDD base `12.0 C`, aplicada a Araucania, Los Rios, Los Lagos, Aysen y Magallanes; los exponentes amortiguan la doble contabilizacion con la temperatura que ya usa 5R1C.
- Muestreo determinista y estratificado por comuna; cuota proporcional a unidades con calefaccion a lena, con piso de `10` por region. La prevalencia se reporta como unidades a lena sobre el stock regional elegible.
- Un `edificio_id` puede representar varias unidades habitacionales; por eso se conserva `n_inmuebles` y el factor de expansion regional.
- Escenario comparable: `coverage_mid`, 75% de cobertura util de calefaccion.
- Escenario complementario: `redpe_mid`, solo para regiones con fila REDPE 2020.

## Cobertura de la muestra

| Codigo | Region | Stock regional | Inmuebles a lena | Participacion lena | Muestra |
|---:|---|---:|---:|---:|---:|
| 1 | Tarapaca | 89793 | 166 | 0.185% | 10 |
| 2 | Antofagasta | 175972 | 970 | 0.551% | 10 |
| 3 | Atacama | 93940 | 1342 | 1.429% | 10 |
| 4 | Coquimbo | 274131 | 14348 | 5.234% | 15 |
| 5 | Valparaiso | 645498 | 79282 | 12.282% | 37 |
| 6 | O'Higgins | 276334 | 71629 | 25.921% | 35 |
| 7 | Maule | 350269 | 135357 | 38.644% | 57 |
| 8 | Biobio | 484775 | 224598 | 46.330% | 88 |
| 9 | Araucania | 283027 | 160179 | 56.595% | 65 |
| 10 | Los Lagos | 190634 | 120683 | 63.306% | 52 |
| 11 | Aysen | 27888 | 20143 | 72.228% | 17 |
| 12 | Magallanes | 50171 | 1384 | 2.759% | 11 |
| 13 | RM | 2378702 | 28987 | 1.219% | 20 |
| 14 | Los Rios | 97794 | 67772 | 69.301% | 33 |
| 15 | Arica y Parinacota | 64076 | 122 | 0.190% | 10 |
| 16 | Nuble | 126745 | 58288 | 45.988% | 30 |

## Dispersion de demanda termica

Valores en kWh por registro `edificio_id`; P10 y P90 muestran la amplitud central de la muestra.

| Region | n | Demanda P10 | Mediana | Demanda P90 | CV mediana | Volumen leña P10-P90 (st) |
|---|---:|---:|---:|---:|---:|---:|
| Tarapaca | 10 | 1490.7 | 3494.8 | 8860.5 | 0.85 | 1.20-7.12 |
| Antofagasta | 10 | 760.5 | 6414.5 | 19718.7 | 1.56 | 0.61-15.85 |
| Atacama | 10 | 2421.5 | 5639.5 | 14451.3 | 0.97 | 1.95-11.61 |
| Coquimbo | 15 | 2724.8 | 4266.5 | 11343.3 | 1.31 | 2.19-9.12 |
| Valparaiso | 37 | 2368.9 | 5325.5 | 18522.6 | 1.14 | 1.90-14.88 |
| O'Higgins | 35 | 2281.4 | 4613.7 | 12421.2 | 0.87 | 1.83-9.98 |
| Maule | 57 | 2661.9 | 5060.5 | 12375.3 | 1.41 | 2.14-9.94 |
| Biobio | 88 | 3232.0 | 5113.7 | 10745.6 | 0.88 | 2.60-8.63 |
| Araucania | 65 | 4257.9 | 6911.8 | 14039.4 | 0.66 | 3.42-11.28 |
| Los Lagos | 52 | 4693.4 | 8074.0 | 13780.6 | 0.48 | 3.77-11.07 |
| Aysen | 17 | 9415.2 | 13026.7 | 18336.9 | 0.38 | 7.57-14.73 |
| Magallanes | 11 | 17810.3 | 25193.7 | 35853.1 | 0.56 | 14.31-28.81 |
| RM | 20 | 2804.8 | 4251.0 | 10628.4 | 4.84 | 2.25-8.54 |
| Los Rios | 33 | 4562.7 | 8134.0 | 19880.7 | 1.01 | 3.67-15.98 |
| Arica y Parinacota | 10 | 2634.5 | 6583.2 | 11064.0 | 1.12 | 2.12-8.89 |
| Nuble | 30 | 3297.5 | 4958.5 | 10337.3 | 1.06 | 2.65-8.31 |

## REDPE

`redpe_mid` se calculo para: O'Higgins, Maule, Biobio, Araucania, Los Lagos, Aysen, Magallanes, RM, Los Rios. Las regiones sin fila REDPE se mantienen en el escenario comparable de cobertura.

### Comparacion ponderada contra REDPE_mid

El valor simulado es la media ponderada por `n_inmuebles` de los registros seleccionados.

| Region | REDPE_mid (m3 st/a) | Simulado (m3 st/a) | Ratio | Error relativo |
|---|---:|---:|---:|---:|
| O'Higgins | 3.770 | 3.378 | 0.896 | -10.4% |
| Maule | 5.345 | 4.358 | 0.815 | -18.5% |
| Biobio | 7.145 | 5.464 | 0.765 | -23.5% |
| Araucania | 11.055 | 7.669 | 0.694 | -30.6% |
| Los Lagos | 16.100 | 9.166 | 0.569 | -43.1% |
| Aysen | 24.865 | 14.181 | 0.570 | -43.0% |
| Magallanes | 23.345 | 21.876 | 0.937 | -6.3% |
| RM | 2.795 | 2.725 | 0.975 | -2.5% |
| Los Rios | 14.160 | 9.150 | 0.646 | -35.4% |

### Factores de severidad climatica

HDD calculados con temperatura media diaria y ponderacion por el stock elegible regional.

| Region | HDD base 12 C | HDD regional | HDD/ref. | U muros | U ventanas | Infiltracion |
|---|---:|---:|---:|---:|---:|---:|
| Araucania | 12.0 | 1015.3 | 1.000 | 1.100 | 1.080 | 1.200 |
| Los Rios | 12.0 | 1106.6 | 1.090 | 1.119 | 1.099 | 1.237 |
| Los Lagos | 12.0 | 1303.3 | 1.284 | 1.156 | 1.135 | 1.310 |
| Aysen | 12.0 | 3079.6 | 3.033 | 1.373 | 1.348 | 1.769 |
| Magallanes | 12.0 | 3212.1 | 3.164 | 1.385 | 1.360 | 1.796 |

No se registraron errores de simulacion.
