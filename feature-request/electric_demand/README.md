# Consumo eléctrico residencial regional, 2024

La tabla atribuye el consumo BNE de electricidad residencial a las viviendas que
declaran conexión a red pública (`p9_fuente_elect = 1`) y a las personas que
residen o fueron censadas en dichas viviendas.

Unidades: consumo BNE en teracalorías (Tcal); conversión de referencia:
1 Tcal = 1.162222 GWh = 1,162,222.22 kWh. Los indicadores son anuales.

| region | nombre_region | consumo_electrico_residencial_tcal | consumo_electrico_residencial_gwh | viviendas_conectadas_red_publica | personas_residentes_p11a | personas_censadas_cant_per | kwh_por_vivienda_conectada | kwh_por_persona_p11a | kwh_por_persona_cant_per |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | Tarapacá | 217.66 | 252.97 | 111,029.00 | 353,185.00 | 348,534.00 | 2,278.45 | 716.26 | 725.82 |
| 2 | Antofagasta | 400.60 | 465.59 | 195,881.00 | 620,050.00 | 610,613.00 | 2,376.89 | 750.89 | 762.49 |
| 3 | Atacama | 177.49 | 206.28 | 94,227.00 | 284,875.00 | 282,329.00 | 2,189.16 | 724.10 | 730.63 |
| 4 | Coquimbo | 498.29 | 579.12 | 274,291.00 | 806,323.00 | 800,331.00 | 2,111.34 | 718.23 | 723.60 |
| 5 | Valparaíso | 1,483.66 | 1,724.35 | 675,418.00 | 1,868,098.00 | 1,855,194.00 | 2,553.01 | 923.05 | 929.47 |
| 6 | Libertador General Bernardo O'Higgins | 735.92 | 855.30 | 338,196.00 | 975,188.00 | 969,855.00 | 2,529.01 | 877.06 | 881.88 |
| 7 | Maule | 862.22 | 1,002.10 | 395,661.00 | 1,112,096.00 | 1,106,287.00 | 2,532.71 | 901.09 | 905.82 |
| 8 | Biobío | 1,116.23 | 1,297.31 | 561,680.00 | 1,596,666.00 | 1,588,502.00 | 2,309.69 | 812.51 | 816.69 |
| 9 | La Araucanía | 689.41 | 801.25 | 359,921.00 | 986,815.00 | 980,840.00 | 2,226.18 | 811.96 | 816.90 |
| 10 | Los Lagos | 727.22 | 845.19 | 322,473.00 | 875,807.00 | 870,564.00 | 2,620.98 | 965.05 | 970.86 |
| 11 | Aysén | 86.91 | 101.00 | 38,186.00 | 97,263.00 | 96,719.00 | 2,645.03 | 1,038.45 | 1,044.29 |
| 12 | Magallanes y de la Antártica Chilena | 127.38 | 148.04 | 60,580.00 | 161,688.00 | 160,648.00 | 2,443.71 | 915.59 | 921.52 |
| 13 | Metropolitana de Santiago | 6,039.35 | 7,019.07 | 2,487,750.00 | 7,380,622.00 | 7,312,825.00 | 2,821.45 | 951.01 | 959.83 |
| 14 | Los Ríos | 321.26 | 373.37 | 143,895.00 | 391,129.00 | 388,975.00 | 2,594.75 | 954.60 | 959.88 |
| 15 | Arica y Parinacota | 148.50 | 172.59 | 71,896.00 | 230,445.00 | 227,533.00 | 2,400.54 | 748.94 | 758.52 |
| 16 | Ñuble | 397.33 | 461.79 | 185,063.00 | 506,391.00 | 504,002.00 | 2,495.29 | 911.91 | 916.24 |

## Fuentes y criterios

- `shared/bne/ConsumosRegionales_BNE2024.xlsx`, hoja `data`, fila
  `ELECTRICIDAD` / `CPR` / `RESIDENCIAL`. La planilla indica valores en Tcal.
- `shared/census2024/viv_hog_per_censo2024/viviendas_censo2024.parquet`.
  Se consideraron solo registros con `p9_fuente_elect = 1`.
- `personas_residentes_p11a` es la suma de `p11a_num_personas` y
  `personas_censadas_cant_per` la suma de `cant_per`, ambas dentro de las
  viviendas conectadas a la red pública.

## Integración en tsib-fcr

La librería usa `kwh_por_persona_p11a` cuando `BuildingConfiguration` recibe
`country="CL"` y `region`. El script de cálculo también actualiza la copia de
runtime en `tsib/data/chile/consumo_electrico_residencial_regional_2024.csv`.
El valor regional se multiplica por `n_persons` y `n_apartments`; la forma
horaria existente no cambia.

Esta cifra representa electricidad residencial total observada y puede incluir
calefacción, refrigeración y ACS eléctricos. En el flujo previsto, esos usos se
simulan por separado y luego se reconcilian con el balance energético; no deben
sumarse directamente a esta línea base sin ese ajuste posterior.
