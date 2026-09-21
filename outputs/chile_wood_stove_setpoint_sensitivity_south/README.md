# Sensibilidad del setpoint de invierno en regiones del sur

La sensibilidad reutiliza la cohorte regional de calibración y mantiene
fijos los parámetros de eventos seleccionados por región. Sólo se
reemplaza el setpoint de calefacción de junio, julio y agosto; el resto
del año conserva el perfil mensual chileno por zona térmica. Durante
la sensibilidad, el setpoint de enfriamiento invernal se mantiene 2 °C
por encima del setpoint de calefacción.

- Regiones: `Magallanes` (12), `Los Rios` (14), `Los Lagos` (10), `Araucania` (9).
- Año ERA5: `2024`.
- Eficiencia: `0.50`.

| Región | Escenario | Setpoint invierno | Demanda 5R1C (kWh) | REDPE (m³ st) | Leña simulada (m³ st) | Error REDPE | No asignado (kWh) | No satisfecha (kWh) |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| Magallanes | perfil_actual | - | 19046.8 | 23.345 | 17.83 | -23.6% | 10289.8 | 2407.0 |
| Magallanes | invierno_22C | 22.0 °C | 21234.0 | 23.345 | 19.22 | -17.7% | 7695.6 | 3296.3 |
| Magallanes | invierno_24C | 24.0 °C | 22115.4 | 23.345 | 19.67 | -15.7% | 6854.9 | 3758.8 |
| Los Rios | perfil_actual | - | 9161.6 | 14.160 | 10.48 | -26.0% | 6865.0 | 1933.1 |
| Los Rios | invierno_22C | 22.0 °C | 10405.6 | 14.160 | 11.29 | -20.2% | 5350.4 | 2471.2 |
| Los Rios | invierno_24C | 24.0 °C | 11094.2 | 14.160 | 11.72 | -17.2% | 4555.3 | 2784.9 |
| Los Lagos | perfil_actual | - | 7145.6 | 16.100 | 13.16 | -18.2% | 5471.2 | 882.6 |
| Los Lagos | invierno_22C | 22.0 °C | 8285.5 | 16.100 | 14.03 | -12.9% | 3861.5 | 1341.1 |
| Los Lagos | invierno_24C | 24.0 °C | 8893.4 | 16.100 | 14.37 | -10.7% | 3216.3 | 1606.8 |
| Araucania | perfil_actual | - | 7216.4 | 11.055 | 8.74 | -21.0% | 4327.9 | 881.2 |
| Araucania | invierno_22C | 22.0 °C | 8384.4 | 11.055 | 9.42 | -14.8% | 3056.7 | 1325.0 |
| Araucania | invierno_24C | 24.0 °C | 9022.0 | 11.055 | 9.73 | -12.0% | 2477.3 | 1620.5 |

El perfil actual corresponde a la zona térmica de cada arquetipo;
la muestra usa las zonas térmicas propias de cada región. Este ejercicio modifica
sólo el setpoint de invierno y no constituye calibración física.

Archivos: `setpoint_sensitivity_results.csv` y
`setpoint_sensitivity_summary.csv`.
