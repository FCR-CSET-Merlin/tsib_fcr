# Tabla regional REDPE de consumo residencial de leña

## Fuente y archivo incorporado

La tabla incorporada en la librería es:

[`tsib/data/chile/lena_consumo_residencial_redpe_2020.csv`](../../tsib/data/chile/lena_consumo_residencial_redpe_2020.csv)

Proviene de la tabla 3 del informe RedPE (2020),
*Caracterización del mercado de la leña en Chile y sus barreras para la
transición energética*. La copia de respaldo y la transcripción original se
encuentran en la rama `analysis-consumo-lena` de MERLIN_RCP, commit
`142f32124ee28063e04fabcbb00d44a18fc0de62`.

Los valores corresponden al año 2017 y combinan penetración regional CASEN
2017, viviendas Censo 2017 y rangos de consumo reportados por RedPE. El valor
por vivienda es el promedio de **viviendas consumidoras de leña**, no de todas
las viviendas de la región.

## Contenido

La tabla contiene:

- región y año de referencia;
- penetración de leña y viviendas Censo 2017;
- consumo total inferior y superior en m³ estéreo/año;
- consumo inferior y superior por vivienda consumidora;
- masa equivalente inferior y superior;
- energía bruta inferior y superior con PCI de 15 MJ/kg;
- fuente del límite superior.

Las regiones disponibles son RM, O'Higgins, Maule, Biobío, Araucanía, Los
Ríos, Los Lagos, Aysén y Magallanes. La fuente histórica no tiene una fila
independiente para Ñuble; la API genera un error explícito en ese caso y no
imputa un valor desde Biobío u otra región.

## Conversión energética

La fuente usa estos supuestos transparentes:

```text
masa [t/año] = volumen [m³ st/año] × 0,64 [m³ sólido/m³ st]
               × 0,7 [t/m³ sólido]

energía bruta [MWh/año] = masa [t/año] × 15 [MJ/kg] / 3,6
```

Por lo tanto, la energía de la tabla es energía química de entrada, antes de
aplicar la eficiencia de la estufa. No es demanda térmica útil ni energía
entregada al edificio.

## API

```python
import tsib

redpe = tsib.get_chile_regional_wood_consumption(8, "mid")
print(redpe["region"])  # Biobio
print(redpe["consumption_m3st_per_consumer"])
print(redpe["energy_bruta_mwh_per_consumer"])
```

`consumption_case` acepta `low`, `mid` y `high`. `mid` es el punto medio
aritmético del límite inferior y superior. La función conserva los metadatos
de la fila y añade el valor seleccionado, el PCI y el caso solicitado.

## Uso en la validación

`examples/chile/validate_wood_stove_geonode.py` usa la energía bruta regional
como objetivo químico de combustible y la compara con la demanda útil 5R1C.
Reporta por separado:

- calor útil que la demanda puede absorber;
- demanda térmica no satisfecha;
- energía de combustible no asignada cuando el objetivo excede la demanda;
- masa y volumen de leña asignados.

Esta comparación no debe interpretarse como calibración individual. Es una
prueba de consistencia entre un rango regional de consumo y una vivienda
simulada; la calibración requiere una cohorte y una regla explícita de
expansión desde vivienda consumidora a población regional.
