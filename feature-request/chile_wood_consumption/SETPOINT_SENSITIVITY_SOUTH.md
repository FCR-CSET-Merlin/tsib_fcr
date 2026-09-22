# Sensibilidad del setpoint de invierno en el sur de Chile

## Objetivo

Evaluar si un setpoint de calefacción invernal de 22–24 °C reduce la
discrepancia observada entre el modelo 5R1C + estufa a eventos y `REDPE_mid`.
Se reutilizó la misma cohorte de la calibración regional y se evaluaron
Magallanes, Los Ríos, Los Lagos y Araucanía.

El escenario `perfil_actual` conserva el perfil mensual chileno asociado al
arquetipo de cada inmueble. Los escenarios `invierno_22C` e `invierno_24C`
reemplazan únicamente el setpoint de junio, julio y agosto. Los parámetros de
eventos calibrados por región se mantienen fijos para aislar el efecto del
setpoint sobre la demanda 5R1C. Durante esos meses, el setpoint de enfriamiento
se mantiene 2 °C por encima del setpoint de calefacción para conservar una
banda de confort válida. Los eventos de la estufa sólo pueden iniciar entre
las 08:00 y las 23:00; los eventos ya iniciados terminan según su duración.

## Resultados

| Región | Demanda actual (kWh) | Demanda a 22 °C | Demanda a 24 °C | Error REDPE actual | Error a 22 °C | Error a 24 °C |
|---|---:|---:|---:|---:|---:|---:|
| Magallanes | 19.046,8 | 21.234,0 | 22.115,4 | -23,6% | -17,7% | -15,7% |
| Los Ríos | 9.161,6 | 10.405,6 | 11.094,2 | -26,0% | -20,2% | -17,2% |
| Los Lagos | 7.145,6 | 8.285,5 | 8.893,4 | -18,2% | -12,9% | -10,7% |
| Araucanía | 7.216,4 | 8.384,4 | 9.022,0 | -21,0% | -14,8% | -12,0% |

El aumento del setpoint mejora el ajuste en las cuatro regiones. A 24 °C, la
leña simulada alcanza `13,70 m³ st` en Magallanes, `9,23` en Los Ríos,
`10,96` en Los Lagos y `9,43` en Araucanía. Sin embargo, todavía queda por
debajo de `REDPE_mid` en todos los casos.

La restricción horaria reduce fuertemente la leña asignada respecto de la
simulación sin horario: el controlador ya no puede iniciar eventos durante la
noche y la madrugada. Por ello, la demanda no satisfecha y el combustible no
asignado aumentan, aunque el setpoint de 22–24 °C sigue reduciendo la brecha
relativa dentro de cada región.

El efecto no es gratuito en el balance horario: al pasar de la configuración
actual a 24 °C, disminuye el combustible no asignado, pero aumenta la demanda
no satisfecha. Esto muestra que un setpoint mayor acerca la demanda térmica al
consumo REDPE, pero no garantiza que el controlador de eventos pueda entregar
todo el calor requerido.

## Interpretación

La sensibilidad respalda la observación de que el setpoint de 17 °C usado en
la zona térmica `I` puede estar subestimando la demanda efectiva de hogares con
calefacción a leña. No obstante, no permite concluir todavía que 22 °C o 24 °C
sea el valor real regional: ambos son escenarios de sensibilidad y no una
calibración física.

La discrepancia residual puede provenir de una combinación de:

- horas reales de operación y comportamiento de los ocupantes;
- demanda de calefacción no capturada por el arquetipo o el año meteorológico;
- diferencias entre consumo químico REDPE y calor útil de calefacción;
- potencia, almacenamiento y regla de encendido de la estufa.

Para la siguiente iteración conviene calibrar conjuntamente el setpoint
invernal y los parámetros de eventos, o introducir un perfil de ocupación y
temperatura interior observada. No se recomienda cambiar el valor base global
sin esa validación.

## Reproducción

```bash
PYTHONPATH=. python examples/chile/analyze_wood_stove_setpoint_sensitivity.py \
  --env-file /ruta/local/geonode.env \
  --region-code 12 14 10 9 \
  --year 2024 \
  --winter-setpoints 22 24 \
  --operation-start-hour 8 \
  --operation-end-hour 23 \
  --output-dir outputs/chile_wood_stove_setpoint_sensitivity_south
```

Los resultados por inmueble y el resumen numérico están en
`outputs/chile_wood_stove_setpoint_sensitivity_south/`.

La sensibilidad de setpoint debe interpretarse junto con el DOE de calidad
constructiva, porque una vivienda con mayor U e infiltración puede cerrar la
brecha anual a costa de incrementar la demanda no satisfecha. Ese DOE está en
`outputs/chile_wood_stove_construction_doe_south_expanded/`.
