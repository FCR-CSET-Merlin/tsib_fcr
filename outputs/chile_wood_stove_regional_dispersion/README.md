# Dispersion regional de simulaciones de estufa a lena

## Configuracion

- Ano meteorologico: `2024`.
- Muestra solicitada: `500` registros `edificio_id`, semilla `2024`.
- Eficiencia de estufa: `0.50`.
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
| Araucania | 65 | 3779.7 | 6173.8 | 12563.4 | 0.67 | 3.04-10.10 |
| Los Lagos | 52 | 3598.1 | 6560.2 | 11734.1 | 0.50 | 2.89-9.43 |
| Aysen | 17 | 6556.9 | 9408.9 | 13269.2 | 0.38 | 5.27-10.66 |
| Magallanes | 11 | 12433.1 | 17910.3 | 24569.2 | 0.54 | 9.99-19.74 |
| RM | 20 | 2804.8 | 4251.0 | 10628.4 | 4.84 | 2.25-8.54 |
| Los Rios | 33 | 3854.9 | 7012.0 | 17581.4 | 1.06 | 3.10-14.13 |
| Arica y Parinacota | 10 | 2634.5 | 6583.2 | 11064.0 | 1.12 | 2.12-8.89 |
| Nuble | 30 | 3297.5 | 4958.5 | 10337.3 | 1.06 | 2.65-8.31 |

## REDPE

`redpe_mid` se calculo para: O'Higgins, Maule, Biobio, Araucania, Los Lagos, Aysen, Magallanes, RM, Los Rios. Las regiones sin fila REDPE se mantienen en el escenario comparable de cobertura.

No se registraron errores de simulacion.
