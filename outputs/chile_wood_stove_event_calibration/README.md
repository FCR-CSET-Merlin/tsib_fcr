# Calibración numérica de eventos y almacenamiento

Esta corrida no usa observaciones físicas. Selecciona parámetros que
reproducen, lo mejor posible, el balance anual del MVP para la misma
demanda 5R1C y el mismo objetivo de combustible.

## Configuración

- Año ERA5: `2024`.
- Registros por región: `1`.
- Semilla de selección: `2024`.
- Candidatos por registro: `144`.
- Eficiencia: `0.50`.
- Objetivo MVP: 75% de cobertura útil con eficiencia 0,50.

## Resultado por registro

| Región | Demanda MVP (kWh/a) | Score | Error perfil (kWh) | Eventos | MVP (m³ st) | Dinámico (m³ st) | Derrame (kWh) |
|---|---:|---:|---:|---:|---:|---:|---:|
| Tarapaca | 2769.9 | 0.2409 | 1000.97 | 520 | 2.23 | 2.23 | 0.00 |
| Antofagasta | 222.6 | 0.2235 | 74.60 | 42 | 0.18 | 0.18 | 0.00 |
| Atacama | 5957.5 | 0.2327 | 2079.30 | 1118 | 4.79 | 4.79 | 0.00 |
| Coquimbo | 6285.9 | 0.2142 | 2019.76 | 1179 | 5.05 | 5.05 | 0.00 |
| Valparaiso | 3427.6 | 0.2306 | 1185.53 | 643 | 2.75 | 2.75 | 0.00 |
| O'Higgins | 2407.5 | 0.2423 | 875.18 | 452 | 1.93 | 1.93 | 0.00 |
| Maule | 2842.6 | 0.2417 | 1030.64 | 533 | 2.28 | 2.28 | 0.00 |
| Biobio | 5814.6 | 0.2283 | 1990.86 | 1091 | 4.67 | 4.67 | 0.00 |
| Araucania | 7006.6 | 0.2301 | 2418.29 | 1314 | 5.63 | 5.63 | 0.00 |
| Los Lagos | 10459.3 | 0.2423 | 3801.10 | 1962 | 8.40 | 8.40 | 0.00 |
| Aysen | 3625.4 | 0.2498 | 1358.30 | 680 | 2.91 | 2.91 | 0.00 |
| Magallanes | 17910.3 | 0.1424 | 3825.55 | 3359 | 14.39 | 14.39 | 0.00 |
| RM | 1298.9 | 0.2498 | 486.74 | 61 | 1.04 | 1.04 | 0.00 |
| Los Rios | 7113.4 | 0.2284 | 2437.13 | 1334 | 5.72 | 5.72 | 0.00 |
| Arica y Parinacota | 819.5 | 0.2499 | 307.17 | 39 | 0.66 | 0.66 | 0.00 |
| Nuble | 29642.2 | 0.1789 | 7955.32 | 2779 | 23.82 | 23.82 | 0.00 |

## Transferencia a REDPE_mid

Los parámetros se calibraron contra el MVP y luego se aplicaron al objetivo REDPE.

| Región | REDPE (m³ st/a) | Dinámico (m³ st/a) | No satisfecho (kWh) | No asignado (kWh) |
|---|---:|---:|---:|---:|
| O'Higgins | 3.77 | 2.45 | 122.5 | 2464.0 |
| Maule | 5.35 | 2.87 | 168.6 | 4628.0 |
| Biobio | 7.14 | 4.89 | 1256.5 | 4215.0 |
| Araucania | 11.05 | 5.90 | 1505.8 | 9632.0 |
| Los Lagos | 16.10 | 11.11 | 90.6 | 9301.0 |
| Aysen | 24.86 | 3.89 | 0.7 | 39154.0 |
| Magallanes | 23.34 | 16.35 | 2651.5 | 13056.0 |
| RM | 2.79 | 1.41 | 0.0 | 2601.0 |
| Los Rios | 14.16 | 5.87 | 1639.4 | 15478.0 |

Score mediano: `0.2316`.
El score es una métrica de consistencia numérica, no un error físico observado.

## Archivos

- `calibration_summary.csv`: mejor candidato por registro y transferencia a REDPE_mid.
- `calibration_trials.csv`: todos los candidatos y sus métricas.
- `README.md`: esta descripción de la corrida.
