# Calibración numérica de eventos y almacenamiento

Esta corrida no usa observaciones físicas. Selecciona parámetros que
reproducen, lo mejor posible, el balance anual del MVP para la misma
demanda 5R1C y el mismo objetivo de combustible.

## Configuración

- Año ERA5: `2024`.
- Registros: `por región=1`.
- Semilla de selección: `2024`.
- Candidatos por registro: `144`.
- Eficiencia: `0.50`.
- Objetivo de calibración: `redpe_mid`; las regiones sin fila REDPE_mid usan MVP coverage_mid.

## Resultado por registro

| Región | Demanda (kWh/a) | Score | Error perfil (kWh) | Eventos | Objetivo (m³ st) | Dinámico (m³ st) | Derrame (kWh) |
|---|---:|---:|---:|---:|---:|---:|---:|
| Tarapaca | 2769.9 | 0.2409 | 1000.97 | 520 | 2.23 | 2.23 | 0.00 |
| Antofagasta | 222.6 | 0.2235 | 74.60 | 42 | 0.18 | 0.18 | 0.00 |
| Atacama | 5957.5 | 0.2327 | 2079.30 | 1118 | 4.79 | 4.79 | 0.00 |
| Coquimbo | 6285.9 | 0.2142 | 2019.76 | 1179 | 5.05 | 5.05 | 0.00 |
| Valparaiso | 3427.6 | 0.2306 | 1185.53 | 643 | 2.75 | 2.75 | 0.00 |
| O'Higgins | 2407.5 | 0.0009 | 0.00 | 603 | 2.58 | 2.58 | 0.00 |
| Maule | 2842.6 | 0.0008 | 0.00 | 712 | 3.05 | 3.05 | 0.00 |
| Biobio | 5814.6 | 0.0006 | 0.00 | 1455 | 6.23 | 6.24 | 0.00 |
| Araucania | 7006.6 | 0.0004 | 0.00 | 1753 | 7.51 | 7.51 | 0.00 |
| Los Lagos | 10459.3 | 0.0002 | 0.00 | 1308 | 11.21 | 11.21 | 0.00 |
| Aysen | 3625.4 | 0.0001 | 0.00 | 907 | 3.88 | 3.89 | 0.00 |
| Magallanes | 17910.3 | 0.0003 | 0.00 | 2240 | 19.19 | 19.20 | 0.00 |
| RM | 1298.9 | 0.0015 | 0.00 | 163 | 1.39 | 1.40 | 0.00 |
| Los Rios | 7113.4 | 0.0004 | 0.00 | 890 | 7.62 | 7.63 | 0.00 |
| Arica y Parinacota | 819.5 | 0.2499 | 307.17 | 39 | 0.66 | 0.66 | 0.00 |
| Nuble | 29642.2 | 0.1789 | 7955.32 | 2779 | 23.82 | 23.82 | 0.00 |

## Transferencia a REDPE_mid

Los parámetros se calibraron contra REDPE_mid y se comparan con la transferencia REDPE.

| Región | REDPE (m³ st/a) | Dinámico (m³ st/a) | No satisfecho (kWh) | No asignado (kWh) |
|---|---:|---:|---:|---:|
| O'Higgins | 3.77 | 2.58 | 0.0 | 2216.0 |
| Maule | 5.35 | 3.05 | 0.0 | 4284.0 |
| Biobio | 7.14 | 6.24 | 0.0 | 1695.0 |
| Araucania | 11.05 | 7.51 | 0.0 | 6616.0 |
| Los Lagos | 16.10 | 11.21 | 0.0 | 9117.0 |
| Aysen | 24.86 | 3.89 | 0.0 | 39154.0 |
| Magallanes | 23.34 | 19.20 | 0.0 | 7740.0 |
| RM | 2.79 | 1.40 | 0.0 | 2617.0 |
| Los Rios | 14.16 | 7.63 | 0.0 | 12190.0 |

Score mediano: `0.0012`.
El score es una métrica de consistencia numérica, no un error físico observado.

## Archivos

- `calibration_summary.csv`: mejor candidato por registro y transferencia a REDPE_mid.
- `calibration_trials.csv`: todos los candidatos y sus métricas.
- `README.md`: esta descripción de la corrida.
