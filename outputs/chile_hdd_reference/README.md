# Referencia regional de HDD ponderados por unidades a leña

Archivo: `hdd_regional_ponderado_lena_2024.csv`.

Los valores corresponden al año meteorológico 2024 y se calcularon usando la
temperatura horaria ERA5 de `meteorology_commune.era5_hourly_comunal`. La
temperatura media diaria se calculó en la zona horaria `America/Santiago`.

Para cada comuna se calculó:

```text
HDD_base = suma(max(base_temperature_c - temperatura_media_diaria, 0))
```

Luego se obtuvo el valor regional como media ponderada por `wood_units`, donde
`wood_units` es la suma de `n_inmuebles` de los registros elegibles que declaran
`tipo_comb_calef = lena`. Estos valores representan el stock regional de
viviendas a leña y no la muestra de 500 edificios simulados.

El archivo conserva simultáneamente HDD12 (`hdd12_c_day`) y HDD14
(`hdd14_c_day`) para facilitar su reutilización en análisis posteriores.
