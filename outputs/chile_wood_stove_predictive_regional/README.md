# Modelo predictivo de eventos de estufa a lena

La corrida no recibe un objetivo anual REDPE. El consumo se genera a partir de la demanda 5R1C, el disparador de temperatura exterior y eventos discretos de lenos.

## Parametros

- Año ERA5: `2024`.
- Eficiencia: `0.50`.
- Disparador: `T_setpoint - T_ext >= 8.0 C`.
- Umbral de demanda para iniciar: `0.25 kW`.
- Energia por leno: `7.5 kWh`.
- Lenos por stere: `219`.
- Carga maxima: `4` lenos por evento.
- Evento: 30 min de arranque + 1 h de combustion.
- Fraccion de energia durante arranque: `0.20`.
- Inicio de eventos: `08:00–23:00`.
- REDPE_mid se consulta sólo despues de simular, como validacion.

## Resultado por inmueble y validacion

| Region | Inmueble | Eventos | Lenos | Leña (m3 st/a) | REDPE_mid | Error relativo | Exceso util (kWh) | No satisfecha (kWh) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Tarapaca | 99748 | 173 | 173.0 | 0.790 | - | - | 426.8 | 2548.0 |
| Antofagasta | 111131 | 16 | 17.0 | 0.078 | - | - | 43.0 | 201.8 |
| Atacama | 307529 | 1011 | 1011.0 | 4.616 | - | - | 2585.6 | 4751.6 |
| Coquimbo | 529140 | 440 | 478.0 | 2.183 | - | - | 914.3 | 5407.7 |
| Valparaiso | 861373 | 371 | 376.0 | 1.717 | - | - | 803.7 | 2821.3 |
| O'Higgins | 1202172 | 446 | 446.0 | 2.037 | 3.77 | -46.0% | 1192.3 | 1927.4 |
| Maule | 1440031 | 490 | 490.0 | 2.237 | 5.35 | -58.1% | 1270.8 | 2275.9 |
| Biobio | 1902270 | 657 | 666.0 | 3.041 | 7.14 | -57.4% | 1456.3 | 4773.3 |
| Araucania | 2205143 | 959 | 960.0 | 4.384 | 11.05 | -60.3% | 2139.0 | 5545.6 |
| Los Lagos | 2542125 | 1412 | 1421.0 | 6.489 | 16.10 | -59.7% | 2648.0 | 7777.9 |
| Aysen | 2551775 | 680 | 680.0 | 3.105 | 24.86 | -87.5% | 1902.4 | 2977.8 |
| Magallanes | 2577343 | 1761 | 2128.0 | 9.717 | 23.34 | -58.4% | 3155.5 | 13085.4 |
| RM | 3136144 | 270 | 270.0 | 1.233 | 2.79 | -55.9% | 807.1 | 1093.5 |
| Los Rios | 2355533 | 988 | 998.0 | 4.557 | 14.16 | -67.8% | 2157.6 | 5528.3 |
| Arica y Parinacota | 45480 | 47 | 47.0 | 0.215 | - | - | 154.5 | 797.7 |
| Nuble | 1643605 | 675 | 1962.0 | 8.959 | - | - | 1758.0 | 24042.8 |

El error relativo se calcula como `consumo_predicho / REDPE_mid - 1` y no participa en la simulacion.

Los resultados horarios completos estan en `predictive_hourly_profiles.csv.gz`.
