# Calibración regional de cohorte de estufa a leña

La calibración usa perfiles horarios 5R1C agregados por región y
ponderados por `n_inmuebles`. Los parámetros resultantes se evalúan
después en todos los registros de la cohorte.
El score compara explícitamente el combustible asignado con el
objetivo anual (`REDPE_mid` cuando existe), además del perfil útil,
la demanda no satisfecha y las pérdidas de almacenamiento. Por tanto,
un objetivo REDPE que no puede absorberse no se fuerza: queda reportado
como combustible no asignado.

## Configuración

- Año ERA5: `2024`.
- Registros seleccionados: `500`.
- Mínimo regional: `10`.
- Semilla: `2024`.
- Candidatos por región: `144`.
- Eficiencia: `0.50`.
- Objetivo: `redpe_mid`; fallback MVP donde REDPE no tiene fila.
- Ajuste: rangos impares de `regional_sample_rank`; validación: rangos pares.

## Validación regional

`simulado` es la media ponderada por `n_inmuebles` en toda la cohorte;
`holdout` usa sólo los registros reservados para validación.

| Región | Objetivo | n ajuste | n holdout | REDPE (m³ st) | Simulado (m³ st) | Holdout (m³ st) | Error holdout | No asignado (kWh) | No satisfecha (kWh) |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Tarapaca | MVP_coverage_mid | 5 | 5 | - | 2.87 | 2.67 | - | 1617.9 | 1592.4 |
| Antofagasta | MVP_coverage_mid | 5 | 5 | - | 3.45 | 3.58 | - | 3617.0 | 5742.4 |
| Atacama | MVP_coverage_mid | 5 | 5 | - | 4.95 | 4.02 | - | 3409.9 | 2799.0 |
| Coquimbo | MVP_coverage_mid | 8 | 7 | - | 4.67 | 4.61 | - | 2647.8 | 2083.1 |
| Valparaiso | MVP_coverage_mid | 19 | 18 | - | 4.25 | 4.35 | - | 1764.2 | 3361.6 |
| O'Higgins | REDPE_mid | 18 | 17 | 3.77 | 3.19 | 3.11 | -17.4% | 1076.8 | 2821.5 |
| Maule | REDPE_mid | 29 | 28 | 5.35 | 4.35 | 4.53 | -15.2% | 1862.0 | 3538.4 |
| Biobio | REDPE_mid | 44 | 44 | 7.14 | 5.65 | 5.59 | -21.7% | 2781.2 | 1397.7 |
| Araucania | REDPE_mid | 33 | 32 | 11.05 | 8.74 | 8.62 | -22.0% | 4327.9 | 881.2 |
| Los Lagos | REDPE_mid | 26 | 26 | 16.10 | 13.16 | 12.38 | -23.1% | 5471.2 | 882.6 |
| Aysen | REDPE_mid | 9 | 8 | 24.86 | 21.86 | 23.11 | -7.1% | 5604.7 | 1310.6 |
| Magallanes | REDPE_mid | 6 | 5 | 23.34 | 17.83 | 15.99 | -31.5% | 10289.8 | 2407.0 |
| RM | REDPE_mid | 10 | 10 | 2.79 | 2.71 | 2.78 | -0.6% | 167.8 | 6357.4 |
| Los Rios | REDPE_mid | 17 | 16 | 14.16 | 10.48 | 10.35 | -26.9% | 6865.0 | 1933.1 |
| Arica y Parinacota | MVP_coverage_mid | 5 | 5 | - | 5.24 | 5.60 | - | 3959.3 | 2712.3 |
| Nuble | MVP_coverage_mid | 15 | 15 | - | 4.67 | 4.83 | - | 1187.9 | 2171.4 |

## Parámetros compartidos por región

| Región | Energía/evento | Duración (h) | Intervalo (h) | Almacenamiento (kWh) | Pérdida/h | Score ajuste |
|---|---:|---:|---:|---:|---:|---:|
| Tarapaca | 8.0 | 2.0 | 4.0 | 8.0 | 0.000 | 0.3233 |
| Antofagasta | 8.0 | 2.0 | 4.0 | 8.0 | 0.000 | 0.2982 |
| Atacama | 8.0 | 2.0 | 1.0 | 8.0 | 0.000 | 0.2646 |
| Coquimbo | 8.0 | 2.0 | 1.0 | 8.0 | 0.000 | 0.2908 |
| Valparaiso | 8.0 | 2.0 | 1.0 | 8.0 | 0.000 | 0.2925 |
| O'Higgins | 8.0 | 2.0 | 4.0 | 8.0 | 0.000 | 0.4117 |
| Maule | 8.0 | 2.0 | 1.0 | 8.0 | 0.000 | 0.3646 |
| Biobio | 8.0 | 1.0 | 1.0 | 8.0 | 0.010 | 0.0124 |
| Araucania | 32.0 | 1.0 | 1.0 | 64.0 | 0.010 | 0.1186 |
| Los Lagos | 32.0 | 2.0 | 1.0 | 8.0 | 0.000 | 0.2903 |
| Aysen | 32.0 | 1.0 | 1.0 | 8.0 | 0.010 | 0.3392 |
| Magallanes | 16.0 | 2.0 | 1.0 | 16.0 | 0.000 | 0.0364 |
| RM | 8.0 | 2.0 | 4.0 | 8.0 | 0.000 | 0.5791 |
| Los Rios | 32.0 | 1.0 | 1.0 | 16.0 | 0.010 | 0.1020 |
| Arica y Parinacota | 8.0 | 2.0 | 4.0 | 16.0 | 0.000 | 0.3029 |
| Nuble | 8.0 | 2.0 | 1.0 | 8.0 | 0.000 | 0.2884 |

El resultado es una calibración numérica de consistencia. No
identifica todavía eficiencia real, conducta de los ocupantes ni
potencia física de una estufa observada.

## Archivos

- `cohort_calibration_summary.csv`: métricas regionales y parámetros.
- `cohort_calibration_trials.csv`: candidatos evaluados por región.
- `cohort_results.csv`: evaluación por edificio y conjunto ajuste/holdout.
- `README.md`: este informe.
