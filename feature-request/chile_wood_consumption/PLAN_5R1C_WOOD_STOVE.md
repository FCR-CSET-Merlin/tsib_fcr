# Plan — Estado del arte y módulo 5R1C para estufa a leña

**Estado:** Fases 0–5 ejecutadas; Fase 6 iniciada con eventos y almacenamiento térmico de baja dimensión; queda pendiente calibrar parámetros, evaluar retroalimentación térmica y preparar el PR.
**Rama:** `feature/chile-wood-stove-simulation`
**Objetivo:** identificar enfoques publicados y diseñar una primera implementación de calefacción con estufa a leña compatible con `tsib-fcr`, sin duplicar energía ni alterar `elecLoad`.

## 1. Preguntas que debe responder el estado del arte

1. ¿Cómo se representa una estufa a leña acoplada a un modelo 5R1C?
2. ¿Se modela como una fuente ideal de calor, un equipo de conversión combustible → calor útil, un modelo dinámico de habitación o una combinación?
3. ¿Cómo se representan encendido, apagado, carga parcial, inercia térmica, almacenamiento y disponibilidad de leña?
4. ¿Qué control se utiliza: temperatura interior, demanda térmica, ocupación, temperatura exterior, reglas horarias, optimización o comportamiento estocástico?
5. ¿Cómo se separan combustible, calor útil entregado al edificio, pérdidas del equipo y emisiones?
6. ¿Qué resolución temporal, parámetros y datos de calibración se requieren?
7. ¿Qué enfoques son reproducibles y suficientemente simples para integrarse primero en `tsib`?
8. ¿Qué validaciones se reportan y qué límites tienen los modelos?

## 2. Familias de enfoques a comparar

La investigación clasificará cada referencia en una o más familias:

### A. Fuente ideal limitada por demanda

La estufa satisface una fracción de `Heating Load` con una eficiencia fija o regional. Es el enfoque base para un MVP transparente.

### B. Conversor de energía final

Se parte de energía o masa de leña y se calcula:

```text
combustible → energía química → calor útil → calor entregado al edificio
```

Debe explicitar PCI, eficiencia, pérdidas, unidades, masa, volumen y energía no asignada.

### C. Equipo con estados y dinámica

La estufa tiene estados como apagada, encendido, operación nominal, carga parcial y enfriamiento. Puede incluir potencia mínima/máxima, tiempos de arranque, inercia y calor residual.

### D. Perfil de uso o eventos de encendido

La demanda se distribuye mediante reglas horarias, temperatura exterior, ocupación o eventos estocásticos. Se evaluará si el perfil determina sólo el *timing* o también el consumo anual.

### E. Control y despacho de sistemas híbridos

La estufa compite o coopera con resistencia eléctrica, bomba de calor, gas u otra fuente. Se compararán reglas heurísticas con optimización LP/MILP y se verificará si requieren Pyomo.

### F. Modelo detallado del artefacto o co-simulación

Incluye combustión, transferencia de calor, emisiones, habitación multizona o CFD. Se considerará como referencia o futura extensión, no como objetivo inicial de integración.

### G. Modelo de emisiones y calidad del aire

Se separan consumo de leña, calor útil, contaminantes y ventilación. Se documentará qué variables son necesarias para Chile y cuáles quedan fuera del MVP.

## 3. Estrategia de búsqueda

Se buscarán fuentes primarias y documentación técnica en:

- artículos revisados por pares y tesis con modelo reproducible;
- ISO/EN y documentación técnica de modelos de edificios;
- documentación oficial de EnergyPlus, Modelica, TRNSYS, IDA ICE u otros motores;
- repositorios de código y modelos abiertos;
- documentación de datos chilenos sobre leña, artefactos, eficiencia y emisiones.

Consultas iniciales:

- `5R1C wood stove heating model`
- `ISO 13790 biomass stove room heater`
- `5R1C solid fuel heating appliance`
- `building simulation wood stove stochastic operation`
- `residential wood heating dispatch model`
- `biomass stove heat emission efficiency dynamic model`
- `EnergyPlus wood stove room air heater`
- `Modelica wood stove building heating`
- `Chile residential wood heating simulation efficiency emissions`

Cada afirmación técnica deberá quedar asociada a una fuente, preferentemente primaria. Se separarán claramente resultados publicados, decisiones de diseño e inferencias propias.

## 4. Matriz de evidencia

El estado del arte incluirá una tabla con al menos estas columnas:

| Campo | Contenido |
| --- | --- |
| Referencia | Autor, año, título, DOI/URL |
| Motor o implementación | 5R1C, EnergyPlus, Modelica, TRNSYS, código propio, etc. |
| Escala | Zona única, vivienda, edificio multizona, distrito |
| Paso temporal | Minutos, hora, día |
| Representación de estufa | Ideal, conversor, estados, dinámica, co-simulación |
| Entrada principal | Demanda, temperatura, ocupación, eventos, energía de combustible |
| Control | Regla, termostato, optimización, estocástico |
| Parámetros | Eficiencia, potencia, inercia, almacenamiento, PCI |
| Salidas | Calor útil, combustible, temperatura, emisiones, unmet load |
| Validación | Datos, métrica, alcance y limitaciones |
| Compatibilidad con tsib | Directa, adaptable, compleja o no recomendable |
| Decisión | Adoptar, adaptar, reservar o descartar |

## 5. Auditoría del repositorio antes del diseño

Se revisarán, como mínimo:

- `tsib/thermal/model5R1C.py`: significado y unidades de `Heating Load`, paso temporal y ruta `sim_demand_direct()`.
- `tsib/buildingconfig.py`: construcción de perfiles y puntos de integración.
- `tsib/profiles.py`: utilidades de series horarias, normalización y energía anual.
- `tsib/renewables/fireplace.py`: diferencias entre `simFireplace()` y un modelo calibrado de estufa.
- `test/test_chile.py`: convenciones de fixtures y validaciones existentes.
- `feature-request/chile_wood_consumption/README.md`: datos REDPE, escenarios y conversiones ya definidos.

La auditoría debe producir un diagrama simple de flujo:

```text
BuildingConfiguration / 5R1C
    → Heating Load útil [kW]
    → módulo de estufa
    → calor útil asignado + consumo de leña + energía no asignada
    → resultados trazables y opcionalmente perfiles para una simulación posterior
```

## 6. Criterios para seleccionar el enfoque

El primer enfoque seleccionado deberá:

- conservar energía en cada paso y en el año;
- distinguir demanda útil, calor útil entregado y energía de combustible;
- limitar la entrega por la demanda térmica disponible;
- reportar explícitamente energía no asignada y demanda no satisfecha;
- ser determinista y reproducible con los mismos inputs;
- funcionar sin Pyomo ni `tsorb` en el camino directo;
- no alterar `elecLoad` ni introducir doble conteo eléctrico;
- aceptar eficiencia, PCI, potencia y escenarios como parámetros explícitos;
- permitir una extensión posterior a control estocástico, híbrido y emisiones;
- tener pruebas unitarias independientes del solver.

## 7. Candidato de arquitectura compatible con tsib

La primera implementación se evaluará como un módulo puro, separado del solver:

```python
result = simulate_wood_stove(
    heating_load,
    dt_hours,
    fuel_energy_target=None,
    consumption_case="mid",
    efficiency=None,
    pci_mj_per_kg=15.0,
    solid_m3_per_stere=0.64,
    density_t_per_solid_m3=0.7,
    control=None,
)
```

La firma es preliminar y sólo se fijará después de la investigación. El resultado candidato debe incluir:

- `useful_heat_kw`;
- `fuel_input_kw` o `fuel_input_kwh`;
- `fuel_mass_kg`;
- `fuel_volume_m3_stere`;
- `assigned_useful_energy_kwh`;
- `unallocated_useful_energy_kwh`;
- `unmet_heating_energy_kwh`;
- supuestos y parámetros efectivos.

La integración inicial recomendada es posterior al cálculo 5R1C: recibe una serie de demanda útil y devuelve un balance de estufa. Una integración que modifique directamente las restricciones de `sim5R1C()` se evaluará sólo si una referencia demuestra que el control acoplado es indispensable.

## 8. Fases de ejecución

### Fase 0 — Línea base reproducible

- Ejecutar la auditoría del repositorio.
- Confirmar unidades, índice temporal y significado de `Heating Load`.
- Definir un caso sintético mínimo para pruebas.

**Salida:** nota de línea base y fixture horario.

### Fase 1 — Estado del arte

- Buscar y seleccionar referencias.
- Completar la matriz de evidencia.
- Clasificar los enfoques A–G.
- Identificar parámetros, ecuaciones, validaciones y limitaciones.

**Salida:** `STATE_OF_ART_5R1C_WOOD_HEATING.md`.

### Fase 2 — Decisión de modelo

- Comparar enfoques con los criterios de selección.
- Elegir MVP y extensiones posteriores.
- Fijar convenciones de unidades y nombres.
- Definir cómo evitar doble conteo con calefacción eléctrica y otros usos.

**Salida:** especificación técnica revisable.

### Fase 3 — Núcleo puro

- Implementar el balance de energía y conversiones.
- Separar escenario anual de distribución horaria.
- Validar potencia, eficiencia, PCI, masa y volumen.
- Mantener errores explícitos para regiones o supuestos no disponibles.

**Salida:** módulo de simulación y tests unitarios.

### Fase 4 — Adaptador tsib

- Añadir una función de alto nivel que consuma la salida 5R1C.
- No modificar `elecLoad`.
- Documentar el punto de integración y el contrato de series.
- Añadir un ejemplo reproducible para una vivienda chilena.

**Salida:** integración opcional y documentación de API. Implementada mediante
`simulate_wood_stove_from_5r1c(...)` y
`examples/chile/wood_stove_5r1c.py`, usando un caso sintético determinista.

### Fase 5 — Validación

- Tests de conservación de energía.
- Tests de límite por demanda.
- Tests de escenarios bajo/medio/alto.
- Comparación con datos REDPE por vivienda consumidora.
- Sensibilidad de eficiencia, PCI y resolución temporal.
- Revisión de energía no asignada y demanda no satisfecha.

**Salida:** informe corto de validación y límites.

**Avance:** disponible
`examples/chile/validate_wood_stove_geonode.py`, que usa una vivienda
marcada con calefacción a leña, su `episcope_archetype`, el CUT asociado y un
año local completo de `meteorology_commune.era5_hourly_comunal`. La primera
ejecución separa sensibilidades de cobertura útil de una calibración REDPE;
La tabla regional de consumo por vivienda consumidora ya está incorporada en
`tsib/data/chile/lena_consumo_residencial_redpe_2020.csv` y se consulta con
`tsib.get_chile_regional_wood_consumption(...)`.

El resultado de la primera ejecución está documentado en
`VALIDATION_5R1C_WOOD_STOVE.md`. La conexión y el año ERA5 ya fueron
verificados; el validador ahora ejecuta las sensibilidades de cobertura y los
escenarios REDPE por separado para no confundir demanda útil simulada con
consumo regional observado.

Se agregó además `examples/chile/analyze_wood_stove_regional_dispersion.py`,
que ejecuta 10 registros `edificio_id` por región usando una muestra
determinista y estratificada por comuna. La corrida 2024 completó 160
simulaciones, sin errores, y dejó el resumen en
`outputs/chile_wood_stove_regional_dispersion/`. Esta evidencia se considera
exploratoria; aún falta definir la unidad de calibración REDPE y ampliar la
muestra si se necesitan cuantiles regionales robustos.

### Fase 6 — Segunda etapa: eventos y almacenamiento

Esta fase se ejecutará después de validar el adaptador y el balance del MVP.
Su alcance queda limitado a una dinámica de baja dimensión, compatible con
el flujo 5R1C:

- definir estados de operación: apagada, encendido, combustión y enfriamiento;
- representar eventos de carga de leña y perfiles de liberación de calor;
- añadir un estado térmico de almacenamiento o calor residual de la estufa;
- limitar el calor entregado por potencia, disponibilidad y demanda;
- documentar si el acoplamiento será iteración externa o entrada térmica
  explícita al 5R1C;
- comparar la versión por eventos con el MVP mediante pruebas de conservación
  de energía y sensibilidad temporal.

**Salida:** módulo dinámico de eventos y almacenamiento, con pruebas y un
caso sintético de referencia. La combustión CFD, emisiones y calidad del aire
quedan fuera de esta etapa.

**Avance:** implementado en `tsib.renewables.wood_stove` mediante
`simulate_wood_stove_events(...)` y
`simulate_wood_stove_events_from_5r1c(...)`. La primera versión usa cargas de
energía química fija, una curva de combustión, almacenamiento de un estado,
pérdidas exponenciales, potencia de descarga y un controlador determinista de
umbral. No modifica `Building5R1C` ni `elecLoad`; sus supuestos y pruebas están
en `PHASE6_EVENTS_STORAGE.md`.

### Fase 7 — Entrega

- Actualizar README y CHANGELOG.
- Revisar compatibilidad de empaquetado.
- Ejecutar tests disponibles.
- Crear commit y PR separado para la estufa a leña.

## 9. Entregables previstos

1. Este plan.
2. Estado del arte con fuentes y matriz comparativa.
3. Especificación del modelo elegido.
4. Módulo Python puro.
5. Tests unitarios y fixture sintético.
6. Ejemplo de integración con 5R1C.
7. Documentación de supuestos y límites.
8. PR revisable separado de la calibración eléctrica ya fusionada.

## 10. Riesgos y decisiones abiertas

- El consumo REDPE es energía de entrada y no equivale automáticamente a demanda útil de calefacción.
- La demanda 5R1C puede ser menor que el consumo regional asignado a un hogar; la diferencia debe reportarse, no forzarse.
- Una eficiencia única puede ocultar diferencias entre hechizo, salamandra, cámara simple y cámara doble.
- La estufa puede entregar calor radiante y convectivo con distinta interacción con el modelo 5R1C.
- Encendidos reales, recarga de combustible y operación nocturna pueden requerir un modelo de eventos.
- La ventilación, emisiones y calidad de aire no se incluirán en el MVP salvo que sean necesarias para la pregunta de validación.
- Debe decidirse si el modelo representa una vivienda consumidora individual o una expansión regional de viviendas.
- El nombre final de la API y el punto exacto de integración se fijarán después de la Fase 1 y la auditoría de la Fase 0.

## 11. Puertas de revisión

No se implementará un modelo dinámico complejo antes de:

1. completar la matriz de evidencia;
2. resolver el balance entre demanda útil y combustible;
3. fijar la unidad de tiempo y el contrato de series;
4. demostrar un caso sintético con conservación energética;
5. documentar qué variables quedan fuera del MVP.
