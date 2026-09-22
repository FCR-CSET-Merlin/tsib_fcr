# Sensibilidad del setpoint de invierno en regiones del sur

La sensibilidad reutiliza la cohorte regional de calibración y mantiene
fijos los parámetros de eventos seleccionados por región. Sólo se
reemplaza el setpoint de calefacción de junio, julio y agosto; el resto
del año conserva el perfil mensual chileno por zona térmica. Durante
la sensibilidad, el setpoint de enfriamiento invernal se mantiene 2 °C
por encima del setpoint de calefacción. Los eventos sólo pueden iniciar
entre las 08:00 y 23:00;
si ya comenzaron, terminan según su duración configurada.

- Regiones: `Magallanes` (12), `Los Rios` (14), `Los Lagos` (10), `Araucania` (9).
- Año ERA5: `2024`.
- Eficiencia: `0.50`.

| Región | Escenario | Setpoint invierno | Demanda 5R1C (kWh) | REDPE (m³ st) | Leña simulada (m³ st) | Error REDPE | No asignado (kWh) | No satisfecha (kWh) |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| Magallanes | perfil_actual | - | 19046.8 | 23.345 | 12.52 | -46.4% | 20212.7 | 7369.0 |
| Magallanes | invierno_22C | 22.0 °C | 21234.0 | 23.345 | 13.40 | -42.6% | 18561.8 | 8730.7 |
| Magallanes | invierno_24C | 24.0 °C | 22115.4 | 23.345 | 13.70 | -41.3% | 18007.6 | 9335.0 |
| Los Rios | perfil_actual | - | 9161.6 | 14.160 | 8.16 | -42.4% | 11198.2 | 2930.7 |
| Los Rios | invierno_22C | 22.0 °C | 10405.6 | 14.160 | 8.85 | -37.5% | 9916.4 | 3604.6 |
| Los Rios | invierno_24C | 24.0 °C | 11094.2 | 14.160 | 9.23 | -34.8% | 9208.5 | 3978.9 |
| Los Lagos | perfil_actual | - | 7145.6 | 16.100 | 9.38 | -41.7% | 12535.5 | 2391.3 |
| Los Lagos | invierno_22C | 22.0 °C | 8285.5 | 16.100 | 10.47 | -35.0% | 10508.6 | 2858.6 |
| Los Lagos | invierno_24C | 24.0 °C | 8893.4 | 16.100 | 10.96 | -31.9% | 9592.9 | 3116.4 |
| Araucania | perfil_actual | - | 7216.4 | 11.055 | 8.44 | -23.6% | 4882.2 | 940.2 |
| Araucania | invierno_22C | 22.0 °C | 8384.4 | 11.055 | 9.14 | -17.4% | 3586.0 | 1392.6 |
| Araucania | invierno_24C | 24.0 °C | 9022.0 | 11.055 | 9.43 | -14.7% | 3034.1 | 1713.6 |

El perfil actual corresponde a la zona térmica de cada arquetipo;
la muestra usa las zonas térmicas propias de cada región. Este ejercicio modifica
sólo el setpoint de invierno y no constituye calibración física.

Archivos: `setpoint_sensitivity_results.csv` y
`setpoint_sensitivity_summary.csv`.
