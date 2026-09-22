# Plan de acoplamiento bidireccional 5R1C + estufa a leña

**Estado:** listo para implementación en una conversación nueva  
**Rama de referencia:** `feature/chile-wood-stove-simulation`  
**Fecha:** 2026-09-22  
**Alcance:** transformar el predictor de eventos sin objetivo anual en una
fuente térmica que interactúe con el estado dinámico de `Building5R1C`.

## 1. Decisión de diseño

El siguiente modelo no debe recibir `REDPE_mid` ni otro objetivo anual para
decidir cuánta leña quemar. La simulación debe producir el consumo a partir de:

```text
estado 5R1C + meteorología + setpoints + heurística de uso
    → decisión de encendido y número de leños
    → potencia de combustión y calor útil
    → actualización de T_air, T_s y T_m
    → nuevo estado que condiciona el siguiente evento
```

“Bidireccional” significa, específicamente:

1. la estufa observa `T_air`, `T_s`, `T_m`, `T_ext`, setpoints y la demanda
   libre de la vivienda;
2. el calor útil de la estufa entra al balance térmico de los nodos 5R1C;
3. la temperatura resultante cambia la demanda, el sobrecalentamiento y la
   decisión del siguiente evento;
4. `REDPE_mid` queda reservado para comparación y validación posterior, nunca
   como entrada de control.

El modelo actual `simulate_wood_stove_predictive_events(...)` es una buena base
para la lógica de eventos, pero aún es un postproceso: recibe una serie
precalculada de `Heating Load` y no modifica las temperaturas interiores. El
objetivo de este plan es cerrar ese lazo sin romper las APIs existentes.

## 2. Qué existe hoy y qué falta

### 2.1. Núcleo 5R1C existente

`Building5R1C.sim_demand_direct()` ya extrae y utiliza:

- `H_em`: conductancia opaca de la envolvente;
- `H_win`, `H_vent` y `H_door`;
- `H_ms` y `H_is`;
- `C_m`;
- temperatura exterior, ganancias internas y ganancias solares;
- estados `T_m`, `T_s` y `T_air`;
- disponibilidad horaria de calefacción y refrigeración.

El camino actual calcula una calefacción ideal: cuando el aire libre queda
bajo el setpoint, fija `T_air` al límite y registra la potencia requerida como
`Heating Load`. Esta ruta debe permanecer intacta para compatibilidad y
regresión.

### 2.2. Predictor de eventos existente

`simulate_wood_stove_predictive_events(...)` ya representa:

- eventos de 1 a 4 leños;
- 7,5 kWh químicos por leño;
- 219 leños por m³ estéreo;
- arranque de 30 minutos y combustión de una hora;
- eficiencia combustible → calor útil;
- ventana de inicio 08:00–23:00;
- intervalo mínimo entre eventos;
- disparador basado en `T_setpoint - T_ext` y demanda.

Sus limitaciones para el acoplamiento son:

- el evento se calcula usando una demanda congelada;
- no observa el `T_air` producido por eventos anteriores;
- el exceso útil no calienta la vivienda;
- no existe una potencia de estufa conectada a los nodos 5R1C;
- la salida `Heating Load` no distingue demanda libre, calor de leña,
  calefacción auxiliar y demanda no satisfecha.

## 3. Arquitectura recomendada

### 3.1. Mantener el camino existente

No se debe reemplazar ni cambiar silenciosamente el comportamiento de:

- `sim_demand_direct()`;
- `simulate_wood_stove()`;
- `simulate_wood_stove_events()`;
- `simulate_wood_stove_predictive_events()`.

La integración nueva debe ser una API separada y opt-in. Se recomienda un
módulo nuevo, por ejemplo:

```text
tsib/thermal/wood_stove_5r1c.py
```

Esto evita que la lógica de control de la estufa quede embebida en el modelo
térmico y reduce el riesgo de importaciones circulares.

### 3.2. Refactor interno antes del acoplamiento

Extraer de `sim_demand_direct()` funciones privadas y testeables, sin cambiar
su resultado:

```text
_extract_5r1c_parameters(model)
_resolve_5r1c_profiles(model, setpoints, availability)
_preview_5r1c_step(state, inputs, source_heat=0)
_advance_5r1c_step(state, inputs, source_heat, auxiliary_heat=0)
```

El `preview` debe calcular el aire libre y la potencia ideal necesaria para
alcanzar el setpoint. El `advance` debe actualizar el estado térmico con la
fuente de calor seleccionada. La ruta antigua puede reutilizar estas funciones
después de demostrar que sus resultados se mantienen dentro de la tolerancia
de regresión.

### 3.3. Controlador de estufa con estado explícito

Crear un controlador incremental, no una función que procese todo el año de
una vez. La interfaz conceptual es:

```python
observation = StoveObservation(
    timestamp=...,
    t_ext_c=...,
    t_air_c=...,
    t_surface_c=...,
    t_mass_c=...,
    heating_setpoint_c=...,
    cooling_setpoint_c=...,
    free_float_heating_kw=...,
    available=True,
)

command = controller.step(observation)
```

El comando debe devolver, como mínimo:

- `fuel_input_kw` y `useful_heat_kw` del paso;
- `event_start`;
- número de leños cargados;
- estado (`off`, `startup`, `combustion`);
- energía química acumulada y diagnóstico de exceso.

El controlador conserva entre pasos el evento activo, fase, tiempo desde el
último inicio e intervalo mínimo. Si un evento comienza antes de las 23:00,
puede terminar después de esa hora; la ventana limita los inicios, no corta la
combustión ya iniciada.

## 4. Regla física-operativa inicial

La primera versión debe utilizar una regla transparente y sin REDPE:

```text
outdoor_trigger = T_setpoint - T_ext >= trigger_delta_c
indoor_trigger  = T_setpoint - T_air >= indoor_deficit_threshold_c
                  o free_float_heating_kw >= start_load_threshold_kw
start_event     = outdoor_trigger
                  y indoor_trigger
                  y disponibilidad horaria
                  y no existe evento activo
                  y se cumple el intervalo mínimo
```

El disparador exterior es obligatorio. Así se preserva la heurística indicada:
una vivienda fría no enciende la estufa si afuera hace calor.

### 4.1. Tamaño del evento

Para cada inicio, calcular una necesidad de energía de corto horizonte, no un
objetivo anual. Inicialmente se utilizará el horizonte de arranque más
combustión:

```text
E_necesaria = max(free_float_heating_kw, potencia_deficitaria_interior)
              × (0,5 h + 1,0 h)

n_leños = ceil(E_necesaria / (7,5 kWh × eficiencia))
n_leños = clip(n_leños, 1, 4)
```

La fórmula será un parámetro de estrategia para poder probar después un
horizonte de 3 horas o una predicción basada en la inercia térmica. No se debe
aumentar `n_leños` para alcanzar una mediana REDPE.

### 4.2. Perfil del leño

Cada leño aporta 7,5 kWh de energía química. El perfil inicial será:

- 30 minutos de arranque;
- 1 hora de combustión;
- 20% de la energía química durante el arranque y 80% durante la combustión,
  como supuesto explícito pendiente de medición;
- `Q_useful = efficiency × Q_fuel`.

La eficiencia, la fracción de arranque y la potencia máxima serán parámetros
de escenario. La energía no se recorta para coincidir con la demanda: si el
paquete calienta la vivienda por encima del setpoint, se reporta
`overheating_degree_hours` y no se borra combustible consumido.

## 5. Cómo entra la estufa al 5R1C

La fuente no debe agregarse de forma opaca a `Heating Load` ni a `elecLoad`.
Se deben conservar tres canales observables:

```text
Q_wood_fuel_kw       energía química de leña
Q_wood_useful_kw     calor útil después de eficiencia
Q_auxiliary_kw       calefacción ideal restante, si se habilita
```

La fuente útil debe distribuirse explícitamente entre los nodos interiores:

```text
Q_wood_useful = Q_wood_air + Q_wood_surface + Q_wood_mass
f_air + f_surface + f_mass = 1
```

Configuración inicial recomendada:

- `f_air = 0,70` para convección al aire;
- `f_surface = 0,30` para radiación a superficies;
- `f_mass = 0,00` en la primera implementación, porque la masa recibe calor
  indirectamente a través de la superficie.

La distribución debe ser configurable para análisis de sensibilidad. No se
debe insertar el total directamente en `Q_st` sin declarar qué nodo recibe la
energía, porque el modelo actual usa `Q_st` en más de una ecuación y eso puede
crear doble conteo.

El paso acoplado debe respetar los balances conceptuales:

```text
masa:
  C_m dT_m/dt = Q_m + H_ms(T_s - T_m)
                - H_em(T_m - T_ext) - H_door(T_m - T_ext)

superficie:
  H_ms(T_s - T_m) + H_is(T_s - T_air)
  + pérdidas por ventanas = Q_surface + ganancias superficiales

aire:
  H_vent(T_air - T_ext) + H_is(T_air - T_s)
  = Q_air + Q_auxiliary - ganancias de aire
```

Las expresiones exactas deben derivarse de las ecuaciones ya implementadas y
verificarse contra la formulación 5R1C existente. El objetivo es reutilizar
las conductancias y el estado del repositorio, no introducir una segunda
definición incompatible de `H_ms`, `H_is` o `C_m`.

### 5.1. Calefacción auxiliar y modos de simulación

La API nueva debe distinguir dos modos:

1. `heating_mode="wood_only"`: la estufa es la única fuente; el aire queda
   libre, se reporta demanda no satisfecha y se permite sobrecalentamiento.
2. `heating_mode="wood_plus_auxiliary"`: si después de aplicar la estufa el
   aire queda bajo el setpoint, se agrega sólo la potencia auxiliar necesaria
   y se reporta separadamente.

En ambos casos el resultado debe incluir:

- `free_float_heating_demand_kw`;
- `wood_useful_heat_kw`;
- `auxiliary_heating_kw`;
- `unmet_heating_kw`;
- `T_air`, `T_s`, `T_m`;
- `overheating_c` u horas-grado de sobrecalentamiento;
- combustible, masa, volumen y eventos.

El `Heating Load` de una corrida antigua no debe reinterpretarse. En la nueva
salida se usarán nombres explícitos para evitar confundir demanda ideal con
calor efectivamente entregado.

## 6. Algoritmo de simulación acoplada

Para cada paso temporal `i`:

1. leer meteorología, ganancias, setpoints y estado térmico anterior;
2. ejecutar `preview` sin estufa para obtener `T_air_free` y
   `free_float_heating_demand_kw`;
3. entregar esos valores, junto con el estado real anterior, al controlador;
4. obtener el paquete de leños y `Q_wood_useful` del paso;
5. distribuir la fuente entre aire y superficie;
6. resolver el balance 5R1C con la fuente y, opcionalmente, calefacción
   auxiliar;
7. actualizar `T_m`, `T_s`, `T_air` y el estado del evento;
8. guardar todas las magnitudes sin reemplazar la historia del paso anterior.

El modelo debe hacer una única decisión causal por paso. No se debe mirar la
temperatura futura para cambiar un evento ya iniciado. Si más adelante se
implementa una predicción de corto horizonte, debe quedar como estrategia
opcional y compararse contra la regla causal.

## 7. Resolución temporal y condiciones iniciales

La duración de arranque de 30 minutos exige una resolución de 30 minutos para
la primera versión acoplada. El plan de datos es:

- temperatura exterior: interpolación lineal;
- irradiancia: remuestreo consistente con potencia media del intervalo;
- ganancias internas y perfiles de uso: valor constante por subintervalo,
  conservando su energía;
- `elecLoad`: conservar energía y no sumar calor de leña al consumo eléctrico.

No se debe duplicar una fila horaria sin revisar la conservación energética.
La utilidad de remuestreo debe tener tests específicos.

Para la masa térmica y el controlador de eventos se recomienda una condición
periódica por *spin-up*:

1. inicializar `T_m` cerca del setpoint y la estufa apagada;
2. repetir el año meteorológico hasta que la diferencia entre el estado final
   y el inicial sea menor que una tolerancia, o hasta `max_spinup_years`;
3. reportar sólo el último año convergido;
4. reiniciar eventos al comenzar cada año de spin-up y registrar esa decisión.

La convergencia debe revisar tanto `T_m` como la energía anual de leña y el
número de eventos. El método actual de cinco pasadas de `sim_demand_direct()`
no es suficiente por sí solo para una secuencia de eventos con memoria.

## 8. API propuesta

El nombre final puede cambiar durante la implementación, pero el contrato
debe ser equivalente a:

```python
result = tsib.simulate_wood_stove_5r1c_bidirectional(
    model,
    heating_setpoint=20.0,
    cooling_setpoint=22.0,
    heating_mode="wood_only",
    efficiency=0.50,
    log_energy_kwh=7.5,
    logs_per_stere=219.0,
    max_logs_per_event=4,
    startup_duration_hours=0.5,
    combustion_duration_hours=1.0,
    startup_energy_fraction=0.20,
    trigger_delta_c=8.0,
    indoor_deficit_threshold_c=0.5,
    min_event_interval_hours=3.0,
    operation_start_hour=8,
    operation_end_hour=23,
    air_fraction=0.70,
    surface_fraction=0.30,
    timestep_minutes=30,
)
```

La función debe aceptar un `Building5R1C` o una configuración equivalente,
pero no un `Heating Load` ya calculado como única entrada: para el modo
bidireccional necesita acceder a los parámetros, perfiles y estado térmico.

## 9. Plan de implementación para el próximo agente

### Paso 0 — Preparación

- Leer este plan, `STATE_OF_ART_5R1C_WOOD_HEATING.md` y
  `PHASE6_EVENTS_STORAGE.md`.
- Revisar `sim_demand_direct()` y ejecutar el caso sintético existente.
- Crear una prueba de regresión del resultado actual antes de refactorizar.

### Paso 1 — Kernel térmico reutilizable

- Extraer parámetros, perfiles y un paso 5R1C.
- Agregar entradas explícitas `source_air_kw`, `source_surface_kw` y,
  si corresponde, `source_mass_kw`.
- Mantener el resultado de la ruta antigua dentro de una tolerancia definida.

### Paso 2 — Controlador incremental

- Crear dataclasses o estructuras equivalentes para observación, comando y
  estado de evento.
- Reutilizar la validación de parámetros del predictor actual.
- Implementar la regla exterior + interior + horario.
- Escribir tests sin depender del modelo térmico.

### Paso 3 — Adaptador bidireccional

- Implementar la secuencia `preview → controller.step → advance`.
- Añadir modo `wood_only` y modo `wood_plus_auxiliary`.
- Crear el resultado tabular con temperaturas, potencias, eventos y balances.
- Exportar la API desde `tsib/__init__.py` sólo cuando exista un smoke test.

### Paso 4 — Resolución de 30 minutos y spin-up

- Implementar el remuestreo de weather/profiles.
- Verificar que la energía de irradiancia, ganancias y electricidad no cambia
  por el remuestreo salvo la tolerancia documentada.
- Añadir convergencia anual y un diagnóstico de estado inicial/final.

### Paso 5 — Validación sintética

Validar antes de consultar GeoNode o REDPE:

1. sin estufa y con auxiliar ideal, el resultado coincide con la ruta directa;
2. con estufa apagada, no se altera `T_air`, `T_s` ni `T_m`;
3. una casa con `T_ext=20 °C` no enciende aunque el aire interior esté frío;
4. una casa con `T_ext=5 °C`, `T_air=15 °C` y setpoint de 22 °C sí puede
   encender;
5. un leño consume exactamente 7,5 kWh químicos antes de eficiencia;
6. el perfil dura 0,5 h + 1 h y no se inicia una segunda carga durante el
   intervalo mínimo;
7. el calor útil aumenta `T_air`, `T_s` o `T_m` frente al caso sin estufa;
8. la energía de leña no desaparece cuando existe sobrecalentamiento;
9. `elecLoad` queda idéntico al caso base;
10. los balances de combustible, calor útil, auxiliar y demanda no presentan
    doble conteo.

### Paso 6 — Primera corrida regional

- Ejecutar un inmueble por región con ERA5, incluyendo Magallanes.
- Inspeccionar un día de invierno con `T_ext`, `T_air`, `T_s`, `T_m`, potencia
  de leña, estado del evento, leños y masa.
- Comparar contra la corrida unidireccional sólo como diagnóstico metodológico.
- No ajustar todavía los parámetros para coincidir con REDPE.

### Paso 7 — Cohorte y validación externa

Sólo después de aprobar los tests y la corrida regional:

- ejecutar la cohorte de 500 inmuebles a leña;
- calcular medianas regionales y dispersión;
- comparar únicamente contra el subconjunto REDPE de viviendas consumidoras de
  leña;
- reportar sesgo, MAE, RMSE, razón simulación/REDPE, percentiles, eventos,
  horas de sobrecalentamiento y demanda no satisfecha;
- usar REDPE como validación externa, no como entrada ni objetivo de eventos.

## 10. Criterios de aceptación

La primera versión acoplada estará lista para revisión cuando:

- la API nueva sea opt-in y no rompa las APIs anteriores;
- el predictor no acepte ni use un objetivo anual REDPE;
- una corrida de 30 minutos conserve energía y unidades;
- el calor de leña modifique efectivamente `T_air`, `T_s` y `T_m`;
- la decisión de un evento use el estado térmico generado por eventos previos;
- el resultado separe combustible, calor útil, auxiliar y demanda no satisfecha;
- exista un caso sintético reproducible y un inmueble por región;
- los supuestos de eficiencia, reparto aire/superficie y energía de arranque
  estén expuestos en la salida;
- la documentación declare que viento y lluvia no son pérdidas adicionales
  directas en este primer acoplamiento. Si se incorporan, será mediante una
  hipótesis explícita sobre infiltración/`H_vent`, no mediante un factor oculto.

## 11. Riesgos y decisiones que deben mantenerse visibles

- La potencia y eficiencia de una estufa real dependen de humedad, especie,
  tiro, carga y operación; 7,5 kWh/leño y 50% son supuestos iniciales.
- El reparto 70/30 aire-superficie es una hipótesis de modelación y debe tener
  sensibilidad, no presentarse como medición.
- Una estufa de radiación local no se representa completamente con una zona
  única 5R1C.
- El remuestreo a 30 minutos puede dar una falsa precisión si los datos ERA5
  son horarios; la limitación debe quedar documentada.
- El consumo alto de REDPE puede incluir usos o comportamientos que el modelo
  no reproduce. La comparación no autoriza a inyectar energía objetivo.
- Magallanes debe poder simularse para APE, pero el predominio regional del gas
  natural debe quedar como contexto de interpretación y no como una corrección
  silenciosa del modelo de leña.

## 12. Referencias técnicas de diseño

- [ISO 13790:2008 / ISO, Energy performance of buildings](https://www.iso.org/cms/%20render/live/en/sites/isoorg/contents/data/standard/04/19/41974.html): marco de necesidades de calefacción, ganancias y sistemas.
- [Buildings.ThermalZones.ISO13790.Zone5R1C](https://simulationresearch.lbl.gov/modelica/releases/v10.1.0/help/Buildings_ThermalZones_ISO13790_Zone5R1C.html): implementación de referencia de una zona 5R1C con nodos de aire, superficie, masa y puertos de calor separados para aire y superficie.
- [Buildings ReducedOrder RC User Guide](https://build.openmodelica.org/Documentation/Buildings.ThermalZones.ReducedOrder.RC.UsersGuide.html): referencia para modelos RC reducidos y conexión de fuentes térmicas.
- [`STATE_OF_ART_5R1C_WOOD_HEATING.md`](STATE_OF_ART_5R1C_WOOD_HEATING.md): estado del arte y decisiones previas del repositorio.
- [`PHASE6_EVENTS_STORAGE.md`](PHASE6_EVENTS_STORAGE.md): contrato actual de eventos, almacenamiento y predictor sin objetivo anual.

## 13. Resultado esperado de la siguiente conversación

La siguiente conversación debe comenzar implementando el Paso 0 y el Paso 1,
no ejecutando todavía una nueva calibración REDPE. El primer entregable de
código debe ser un kernel 5R1C con fuente térmica explícita y pruebas de
regresión; el controlador de eventos se conecta después de demostrar que el
kernel conserva el comportamiento anterior.

## 14. Mensaje para el próximo agente

Vienes a continuar un trabajo ya avanzado. No partas desde cero ni reemplaces
el predictor existente. Lee primero este plan, el estado del arte y
`PHASE6_EVENTS_STORAGE.md`; después inspecciona `sim_demand_direct()` en
`tsib/thermal/model5R1C.py` y `simulate_wood_stove_predictive_events()` en
`tsib/renewables/wood_stove.py`.

Tu primer objetivo no es obtener una mediana cercana a REDPE. Es demostrar que
una fuente térmica explícita puede entrar al balance 5R1C sin romper la ruta
actual. Implementa primero el kernel reutilizable y sus pruebas de regresión.
Sólo cuando el caso sin estufa reproduzca el resultado existente debes conectar
el controlador de eventos.

Mantén estas reglas durante toda la implementación:

- no uses `REDPE_mid` como entrada, objetivo anual ni mecanismo para decidir
  cuántos leños quemar;
- no mezcles calor de leña con `elecLoad` ni ocultes la fuente dentro de
  `Heating Load`;
- separa siempre combustible, calor útil de leña, calefacción auxiliar,
  demanda no satisfecha y sobrecalentamiento;
- conserva las APIs y resultados históricos del modelo unidireccional;
- documenta cualquier supuesto nuevo, especialmente eficiencia, reparto
  aire/superficie y fracción de energía del arranque;
- no ejecutes todavía las 500 viviendas ni una calibración regional antes de
  pasar las pruebas sintéticas y la corrida de un inmueble por región.

El siguiente entregable concreto debe ser un commit pequeño que contenga el
kernel 5R1C con fuente térmica explícita, tests de conservación de energía y
una prueba que verifique que, con la fuente apagada, el resultado coincide con
`sim_demand_direct()`. Después continúa con el controlador incremental
`preview → decide → advance` y registra los cambios en este plan.

## 15. Avance de implementación — 2026-09-22

Se implementó el primer entregable del Paso 1 y una primera conexión opt-in:

- `Building5R1C._prepare_direct_5r1c()` concentra la extracción de
  conductancias, perfiles, ganancias y setpoints que usa la ruta directa.
- `tsib/thermal/wood_stove_5r1c.py` contiene el kernel de paso 5R1C con
  fuentes explícitas en aire, superficie y masa, además de
  `preview → controller.step → advance`.
- `WoodStoveController` conserva el evento activo, fases, intervalo mínimo y
  número de leños sin recibir un objetivo anual.
- `simulate_wood_stove_5r1c_bidirectional()` expone los modos `wood_only` y
  `wood_plus_auxiliary`, y separa combustible, calor útil, auxiliar, demanda
  no satisfecha, sobrecalentamiento y electricidad.
- La API nueva se exporta desde `tsib`; las APIs históricas no se reemplazan.
- Se añadieron pruebas sintéticas para disparador exterior, conservación de
  energía de eventos, regresión contra `sim_demand_direct()`, efecto térmico
  de la estufa y conservación de `Electricity Load`.

La prueba específica del acoplamiento pasa completa (`22 passed`). La suite
completa también ejecutó los tests nuevos y existentes relevantes; los fallos
restantes provienen de compatibilidad preexistente con `pandas` reciente
(`freq="H"`) y de dos APIs históricas ausentes (`simHouseholdsParallel` y
`simSingleHousehold`), no de este acoplamiento.

Quedan para los siguientes pasos el remuestreo explícito a 30 minutos, el
spin-up anual con convergencia de eventos, la corrida regional y la validación
externa. Esta implementación no usa `REDPE_mid`.

La selección desde el flujo de `Building` quedó integrada mediante
`existingHeatSupply="wood_stove"`. Los parámetros opcionales del escenario se
pueden pasar en `woodStoveParameters`; `Building.getHeatLoad()` activa entonces
la API bidireccional y conserva `Heating Load` como demanda ideal libre,
reportando el calor de leña y la calefacción auxiliar en columnas separadas.
