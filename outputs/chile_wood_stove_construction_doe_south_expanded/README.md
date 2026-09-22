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
| Araucania | 22 °C | 1.0× | 1.0× | 2.5× | 0.0% | 0.0071 |
| Araucania | 24 °C | 1.0× | 1.0× | 2.0× | 0.0% | 0.0060 |
| Los Lagos | 22 °C | 1.5× | 2.5× | 1.0× | -0.0% | 0.0352 |
| Los Lagos | 24 °C | 1.0× | 2.5× | 1.0× | -0.0% | 0.0349 |
| Magallanes | 22 °C | 3.0× | 3.0× | 3.0× | -2.2% | 0.1323 |
| Magallanes | 24 °C | 3.0× | 3.0× | 3.0× | -2.2% | 0.1391 |
| Los Rios | 22 °C | 1.0× | 3.0× | 1.5× | -0.0% | 0.0439 |
| Los Rios | 24 °C | 1.0× | 3.0× | 1.0× | -0.0% | 0.0435 |

## Validación en la cohorte

| Región | Setpoint | Demanda media ponderada (kWh) | REDPE (m³ st) | Simulado (m³ st) | Error | No asignado (kWh) | No satisfecha (kWh) |
|---|---:|---:|---:|---:|---:|---:|---:|
| Araucania | 22 °C | 12160.5 | 11.055 | 10.32 | -6.6% | 1373.5 | 3891.4 |
| Araucania | 24 °C | 11650.3 | 11.055 | 10.24 | -7.4% | 1531.6 | 3476.2 |
| Los Lagos | 22 °C | 13396.0 | 16.100 | 14.03 | -12.8% | 3852.2 | 5629.4 |
| Los Lagos | 24 °C | 13126.2 | 16.100 | 13.99 | -13.1% | 3922.2 | 5358.6 |
| Magallanes | 22 °C | 51418.0 | 23.345 | 20.92 | -10.4% | 4525.8 | 31894.6 |
| Magallanes | 24 °C | 53228.3 | 23.345 | 20.93 | -10.3% | 4511.3 | 33697.6 |
| Los Rios | 22 °C | 18737.4 | 14.160 | 12.62 | -10.8% | 2865.3 | 8662.1 |
| Los Rios | 24 °C | 18121.3 | 14.160 | 12.62 | -10.9% | 2879.0 | 8056.6 |

La configuración seleccionada es una solución de screening numérico.
No debe interpretarse como diagnóstico físico individual sin datos de
temperatura interior, infiltración o consumo medido.

Archivos: `doe_trials.csv`, `doe_selected_configurations.csv`,
`doe_validation_results.csv` y `doe_validation_summary.csv`.
