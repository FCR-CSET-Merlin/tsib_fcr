# Dispersion regional de simulaciones de estufa a lena

## Configuracion

- Ano meteorologico: `2024`.
- Muestra: `10` registros `edificio_id` por region, semilla `2024`.
- Eficiencia de estufa: `0.50`.
- Muestreo: determinista y estratificado por comuna; un `edificio_id` puede representar varias unidades habitacionales.
- Escenario comparable: `coverage_mid`, 75% de cobertura util de calefaccion.
- Escenario complementario: `redpe_mid`, solo para regiones con fila REDPE 2020.

## Cobertura de la muestra

| Codigo region | Inmuebles seleccionados |
|---:|---:|
| 1 | 10 |
| 2 | 10 |
| 3 | 10 |
| 4 | 10 |
| 5 | 10 |
| 6 | 10 |
| 7 | 10 |
| 8 | 10 |
| 9 | 10 |
| 10 | 10 |
| 11 | 10 |
| 12 | 10 |
| 13 | 10 |
| 14 | 10 |
| 15 | 10 |
| 16 | 10 |

## Dispersion de demanda termica

Valores en kWh por registro `edificio_id`; P10 y P90 muestran la amplitud central de la muestra.

| Region | n | Demanda P10 | Mediana | Demanda P90 | CV mediana | Volumen leña P10-P90 (st) |
|---|---:|---:|---:|---:|---:|---:|
| Tarapaca | 10 | 1490.7 | 3494.8 | 8860.5 | 0.85 | 1.20-7.12 |
| Antofagasta | 10 | 760.5 | 6414.5 | 19718.7 | 1.56 | 0.61-15.85 |
| Atacama | 10 | 2421.5 | 5639.5 | 14451.3 | 0.97 | 1.95-11.61 |
| Coquimbo | 10 | 3725.3 | 6011.1 | 13274.5 | 1.05 | 2.99-10.67 |
| Valparaiso | 10 | 2464.6 | 3690.1 | 18657.9 | 1.87 | 1.98-14.99 |
| O'Higgins | 10 | 2008.9 | 5592.3 | 12103.7 | 0.89 | 1.61-9.73 |
| Maule | 10 | 3572.7 | 5452.0 | 12959.9 | 1.10 | 2.87-10.41 |
| Biobio | 10 | 3032.5 | 5965.4 | 16714.0 | 1.72 | 2.44-13.43 |
| Araucania | 10 | 2955.7 | 6532.1 | 9266.7 | 0.44 | 2.38-7.45 |
| Los Lagos | 10 | 3819.3 | 7606.7 | 12698.3 | 0.52 | 3.07-10.20 |
| Aysen | 10 | 6738.2 | 9426.4 | 13179.3 | 0.31 | 5.41-10.59 |
| Magallanes | 10 | 12175.8 | 17214.6 | 26647.9 | 0.59 | 9.78-21.41 |
| RM | 10 | 2731.5 | 4293.0 | 8380.2 | 0.60 | 2.19-6.73 |
| Los Rios | 10 | 3823.8 | 7454.2 | 14042.2 | 0.63 | 3.07-11.28 |
| Arica y Parinacota | 10 | 2634.5 | 6583.2 | 11064.0 | 1.12 | 2.12-8.89 |
| Nuble | 10 | 4054.8 | 7584.5 | 17284.6 | 1.04 | 3.26-13.89 |

## REDPE

`redpe_mid` se calculo para: O'Higgins, Maule, Biobio, Araucania, Los Lagos, Aysen, Magallanes, RM, Los Rios. Las regiones sin fila REDPE se mantienen en el escenario comparable de cobertura.

No se registraron errores de simulacion.
