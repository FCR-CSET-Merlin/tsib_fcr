# DOE de calidad constructiva y consumo residencial de leña

El DOE varía multiplicadores relativos de U de muros, U de ventanas y
renovaciones por infiltración. Los niveles `1,0`, `1,5` y `2,0` son
escenarios exploratorios de deterioro constructivo; no son mediciones
de cada vivienda.

- Regiones: `Magallanes, Los Rios, Los Lagos, Araucania`.
- Setpoints: `22 °C, 24 °C`.
- Disponibilidad: `08:00–23:00`.
- Eficiencia de estufa: `0.50`.
- Selección: error relativo de volumen REDPE y penalización secundaria por demanda no satisfecha.

## Inmuebles representativos

| Región | Edificio | Comuna | Demanda anual de referencia (kWh) |
|---|---:|---|---:|
| Magallanes | 2577343 | Natales | 17910.3 |
| Los Rios | 2334311 | Corral | 7012.0 |
| Los Lagos | 2413153 | Puerto Octay | 6582.8 |
| Araucania | 2073021 | Victoria | 6173.8 |

## Configuración seleccionada en el DOE

| Región | Setpoint | U muros | U ventanas | Infiltración | Error representante | Score |
|---|---:|---:|---:|---:|---:|---:|
| Araucania | 22 °C | 1.5× | 1.0× | 2.0× | 0.0% | 0.0083 |
| Araucania | 24 °C | 1.0× | 1.0× | 2.0× | 0.0% | 0.0060 |
| Los Lagos | 22 °C | 2.0× | 2.0× | 2.0× | -0.0% | 0.0367 |
| Los Lagos | 24 °C | 1.0× | 2.0× | 2.0× | -0.3% | 0.0356 |
| Magallanes | 22 °C | 2.0× | 2.0× | 2.0× | -13.7% | 0.2042 |
| Magallanes | 24 °C | 2.0× | 2.0× | 2.0× | -13.7% | 0.2094 |
| Los Rios | 22 °C | 2.0× | 2.0× | 2.0× | -4.5% | 0.0858 |
| Los Rios | 24 °C | 2.0× | 2.0× | 2.0× | -0.0% | 0.0443 |

## Validación en la cohorte

| Región | Setpoint | Demanda media ponderada (kWh) | REDPE (m³ st) | Simulado (m³ st) | Error | No asignado (kWh) | No satisfecha (kWh) |
|---|---:|---:|---:|---:|---:|---:|---:|
| Araucania | 22 °C | 11902.9 | 11.055 | 10.32 | -6.6% | 1371.1 | 3634.2 |
| Araucania | 24 °C | 11650.3 | 11.055 | 10.24 | -7.4% | 1531.6 | 3476.2 |
| Los Lagos | 22 °C | 16134.4 | 16.100 | 14.71 | -8.6% | 2582.6 | 7632.5 |
| Los Lagos | 24 °C | 15015.6 | 16.100 | 14.47 | -10.1% | 3029.2 | 6722.8 |
| Magallanes | 22 °C | 37217.5 | 23.345 | 18.46 | -20.9% | 9113.5 | 19989.0 |
| Magallanes | 24 °C | 38590.5 | 23.345 | 18.53 | -20.6% | 8986.9 | 21298.7 |
| Los Rios | 22 °C | 19155.9 | 14.160 | 12.31 | -13.1% | 3453.7 | 9324.3 |
| Los Rios | 24 °C | 20211.7 | 14.160 | 12.70 | -10.3% | 2725.6 | 10028.2 |

La configuración seleccionada es una solución de screening numérico.
No debe interpretarse como diagnóstico físico individual sin datos de
temperatura interior, infiltración o consumo medido.

Archivos: `doe_trials.csv`, `doe_selected_configurations.csv`,
`doe_validation_results.csv` y `doe_validation_summary.csv`.
