# Validación inicial 5R1C + estufa a leña con GeoNode

**Estado:** validación de pipeline y comparación inicial con el rango REDPE completadas; calibración de cohorte pendiente.

## 1. Objetivo

Comprobar que una vivienda chilena de la base GeoNode puede conectarse a un
año completo de meteorología ERA5/ERA5-Land, ejecutar el camino directo 5R1C y
entregar su demanda útil al modelo de estufa a leña. Esta ejecución valida la
trazabilidad de datos, el contrato temporal y la conservación energética del
acoplamiento; no pretende calibrar todavía el consumo real de leña.

## 2. Caso reproducible

El caso se ejecutó con:

| Campo | Valor |
|---|---|
| Base de viviendas | `merlin_rcp.edificios` |
| `edificio_id` | `1690556` |
| Tipo | Casa / `SFH` |
| Comuna | Concepción |
| CUT meteorológico | `8101` |
| Región | 8 |
| Combustible de calefacción | `lena` |
| Arquetipo | `CL.SFH.preRT.lad.E` |
| Área modelada | 66,0 m² por vivienda |
| Personas modeladas | 3 |
| Meteorología | `meteorology_commune.era5_hourly_comunal` |
| Año local | 2024 |
| Cobertura | 8.784 horas, de `2024-01-01 00:00` a `2024-12-31 23:00` hora local |
| Eficiencia de estufa | 0,50 |
| Tabla REDPE | `tsib/data/chile/lena_consumo_residencial_redpe_2020.csv` |

La vivienda se seleccionó como caso representativo de una cohorte de casas de
Concepción con `tipo_comb_calef='lena'`, arquetipo válido, área entre 45 y
100 m² y personas positivas. Su área y población están próximas a las
medianas de esa cohorte. El ID debe conservarse como referencia de la captura
de la base; para una nueva versión de GeoNode se debe volver a ejecutar la
consulta de selección.

Comando utilizado:

```bash
PYTHONPATH=. python examples/chile/validate_wood_stove_geonode.py \
  --env-file /ruta/local/geonode.env \
  --edificio-id 1690556 \
  --year 2024 \
  --output /tmp/wood_stove_validation_1690556.csv
```

Las credenciales no forman parte del comando documentado ni del repositorio;
`geonode.env` debe permanecer fuera de Git.

## 3. Controles ejecutados

El validador comprueba:

- existencia de la vivienda y unión `codigo_comuna` → CUT;
- cobertura horaria completa, ordenada y sin duplicados para el año local;
- presencia y finitud de `ghi`, `dni`, `dhi`, `tdry` y `t_mains`;
- irradiancia no negativa;
- arquetipo chileno válido para `CL_episcope.csv`;
- conservación entre objetivo de combustible, eficiencia y calor útil asignado;
- energía no asignada y demanda no satisfecha reportadas explícitamente.

El intervalo se consulta en UTC y se convierte a `America/Santiago` antes de
construir el `DataFrame` que recibe `BuildingConfiguration`. Esto conserva la
semántica del año civil local y sus 8.784 horas en 2024.

## 4. Resultados

La demanda térmica útil anual del 5R1C fue:

```text
Heating Load = 7.776,506 kWh/a
```

Se evaluaron tres sensibilidades. La cobertura es una fracción de la demanda
útil anual, no un rango observado de consumo de leña:

| Escenario | Cobertura útil | Energía de combustible objetivo | Calor útil asignado | Demanda no satisfecha | Leña |
|---|---:|---:|---:|---:|---:|
| `low` | 50% | 7.776,506 kWh | 3.888,253 kWh | 3.888,253 kWh | 4,166 m³ st |
| `mid` | 75% | 11.664,759 kWh | 5.832,380 kWh | 1.944,127 kWh | 6,249 m³ st |
| `high` | 100% | 15.553,012 kWh | 7.776,506 kWh | 0,000 kWh | 8,332 m³ st |

También se aplicó el rango REDPE de Biobío para una vivienda consumidora. La
tabla fuente entrega energía bruta redondeada; por eso el volumen calculado a
partir de la energía puede diferir marginalmente del volumen tabulado:

| Escenario | REDPE objetivo | Combustible objetivo | Calor útil asignado | No asignado | Demanda no satisfecha | Leña asignada |
|---|---:|---:|---:|---:|---:|---:|
| `redpe_low` | 5,500 m³ st | 10.270 kWh | 5.135 kWh | 0 kWh | 2.641,506 kWh | 5,502 m³ st |
| `redpe_mid` | 7,145 m³ st | 13.335 kWh | 6.667,5 kWh | 0 kWh | 1.109,006 kWh | 7,144 m³ st |
| `redpe_high` | 8,790 m³ st | 16.400 kWh | 7.776,506 kWh | 846,988 kWh | 0 kWh | 8,332 m³ st |

En los tres casos la energía de combustible asignada coincide con el objetivo
y el calor útil es `eficiencia × combustible`. Como la potencia no se limitó y
el objetivo fue construido desde la demanda, no aparece energía no asignada.

## 5. Interpretación y límites

Esta validación confirma el pipeline:

```text
GeoNode vivienda → CUT → ERA5/ERA5-Land → 5R1C → estufa → balance de leña
```

No confirma que la vivienda consuma exactamente los valores REDPE. El rango
REDPE es regional y por vivienda consumidora, mientras que la simulación es
individual y utiliza supuestos de arquetipo, `Q_ig`, personas y setpoints. El
resultado sí muestra cuándo el objetivo regional puede ser absorbido por la
demanda 5R1C y cuándo debe reportarse como energía no asignada.

La ejecución tampoco utiliza una medición de temperatura interior, factura,
encendido real ni perfil individual de ocupación.

La comparación regional completa queda pendiente. La tabla ya está integrada,
pero se debe ejecutar una cohorte de viviendas consumidoras y comparar sus
distribuciones con el rango REDPE; no basta con un único edificio.

## 6. Siguiente paso de validación

1. Ejecutar una cohorte estratificada por región, zona térmica, arquetipo y
   tipo de combustible, no sólo una vivienda.
2. Comparar consumo de leña en m³ estéreo por vivienda consumidora, calor útil
   asignado y demanda no satisfecha.
3. Repetir la sensibilidad para eficiencia, PCI y paso temporal.
4. Sólo después fijar la especificación de eventos de encendido y
   almacenamiento térmico de la Fase 6.
