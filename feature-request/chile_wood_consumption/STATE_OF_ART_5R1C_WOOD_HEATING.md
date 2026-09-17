# Estado del arte — simulación 5R1C con estufa a leña

**Fecha de revisión:** 2026-09-17
**Rama:** `feature/chile-wood-stove-simulation`
**Alcance:** calefacción residencial con leña, conectada a un modelo de zona 5R1C y compatible con la API de `tsib-fcr`.

## Resumen ejecutivo

La literatura no converge en una única forma de representar una estufa a leña junto a un modelo 5R1C. Los enfoques se agrupan en capas:

1. **Modelo de edificio:** el 5R1C calcula la demanda sensible o la temperatura de la zona.
2. **Modelo de equipo:** la estufa convierte combustible en calor útil, normalmente con eficiencia y potencia limitada.
3. **Modelo de operación:** decide cuándo encender, cuánto combustible cargar y cómo distribuir el calor.
4. **Modelo de detalle opcional:** representa almacenamiento térmico, radiación/convección, combustión, emisiones o CFD.

La conclusión para `tsib-fcr` es separar explícitamente esas capas. El primer módulo debe ser un modelo de equipo/operación con balance energético, no un modelo de combustión CFD. Debe poder recibir `Heating Load` desde 5R1C, entregar calor útil limitado por la demanda, calcular energía de combustible y reportar energía no asignada. Una segunda etapa puede acoplar eventos de encendido y almacenamiento térmico al estado de la zona.

## 1. Qué representa el 5R1C

[ISO 52016-1](https://www.iso.org/standard/65696.html) define procedimientos horarios o mensuales para necesidades de calefacción y refrigeración, temperatura interior y cargas sensibles. También distingue entre el cálculo de cargas/necesidades básicas y la interacción con sistemas técnicos específicos. Esto respalda una arquitectura en la que el 5R1C calcula la demanda de la zona y la estufa se modela como una capa de sistema.

El modelo 5R1C representa una zona mediante tres nodos principales —aire interior, superficie y masa térmica— conectados por cinco conductancias/resistencias y una capacitancia térmica. Las referencias de validación y comparación con modelos detallados destacan su bajo coste computacional, pero también sus límites para describir distribuciones espaciales y transitorios rápidos:

- [Pizzuti, Roberto y Arcuri (2016), comparación 5R1C–TRNSYS](https://www.sciencedirect.com/science/article/pii/S1876610216312346).
- [Oliveira Panão et al. (2016), validación de un modelo RC lumped](https://www.sciencedirect.com/science/article/pii/S0378778816302109).
- [Michalak (2019), modelo 4R1C/5R1C con ventilación variable](https://www.sciencedirect.com/science/article/pii/S037877881930787X).

**Implicación:** `Heating Load` debe interpretarse como demanda útil requerida por la zona para mantener el setpoint bajo las hipótesis del modelo. No es automáticamente consumo de leña ni energía química de combustible.

## 2. Enfoques encontrados para la estufa

### 2.1. Fuente ideal o fuente limitada por demanda

La estufa se modela como una fuente que satisface toda o una fracción de la demanda de calefacción, con potencia máxima y eficiencia fija. Es equivalente a un sistema ideal con límites operativos.

**Ventajas**

- Muy barato y robusto para simulaciones anuales.
- Fácil de calibrar con un consumo regional.
- Compatible con una salida horaria de 5R1C.
- Permite separar calor útil de energía final.

**Limitaciones**

- No representa sobrecalentamiento causado por una carga de leña demasiado grande.
- No representa el retardo entre encendido y emisión.
- La eficiencia fija puede ocultar operación a carga parcial y calidad de combustible.
- Si se aplica después de 5R1C, no retroalimenta la temperatura interior.

La documentación oficial de [EnergyPlus sobre `ZoneHVAC:IdealLoadsAirSystem`](https://energyplus.net/assets/nrel_custom/pdfs/pdfs_v24.2.0/EngineeringReference.pdf) ilustra esta capa: un equipo ideal satisface la carga de la zona hasta los límites especificados. Es una referencia conceptual útil, no una representación específica de una estufa.

### 2.2. Conversor de combustible a calor útil

El equipo se representa con una ecuación de conversión:

```text
E_fuel(t) = m_wood(t) × PCI
Q_useful(t) = E_fuel(t) × eta(t)
```

Puede añadirse una potencia mínima/máxima y una fracción de pérdidas. Este enfoque es el más apropiado para el primer módulo de `tsib-fcr`, porque permite conservar energía y utilizar los escenarios REDPE ya documentados.

La biblioteca [Modelica Buildings — datos de combustibles](https://simulationresearch.lbl.gov/modelica/releases/v5.0.0/help/Buildings_Fluid_Data_Fuels.html) separa propiedades del combustible como poder calorífico inferior, densidad y emisiones de CO₂. Su registro de madera secada al aire usa valores de referencia de 14.6 MJ/kg y 700 kg/m³; esos números deben tratarse como referencia de modelado, no como sustituto automático de los supuestos chilenos de la rama.

### 2.3. Perfil de potencia o eventos de carga

La estufa se representa como una sucesión de eventos de encendido, recarga y enfriamiento. Cada evento produce un pulso o curva de liberación de calor.

[Saastamoinen et al. (2005)](https://doi.org/10.1016/j.applthermaleng.2005.02.009) proponen tres maneras de representar la entrada de calor de una carga de leña: ajustar una distribución estadística a mediciones, usar una distribución basada en la física aproximada de la combustión o usar una función analítica simple para simulaciones rápidas. La contribución importante para este proyecto es que el perfil de combustión y la respuesta térmica de la estufa pueden separarse.

**Aplicación en `tsib`:**

```text
evento de carga
    → energía liberada por combustión
    → almacenamiento térmico de la estufa
    → calor convectivo + radiante emitido a la zona
```

### 2.4. Estufa con almacenamiento térmico

En estufas de masa, la combustión ocurre en pulsos relativamente concentrados, pero la habitación recibe calor durante un intervalo más largo. El almacenamiento puede representarse con uno o varios estados térmicos de baja dimensión.

[Georges y Skreiberg (2016)](https://doi.org/10.1080/19401493.2016.1188988) desarrollan un procedimiento simplificado para simular el ambiente térmico de edificios calentados por estufas, con validación experimental de la interacción entre estufa y edificio. Reportan que la estratificación térmica de la habitación es una fuente importante de error y que un modelo simple puede ser útil para estudiar confort global.

[Georges et al. (2012), integración de estufas en casas pasivas](https://www.sciencedirect.com/science/article/abs/pii/S0378778812006834), muestran el problema de dimensionamiento excesivo y distribución de calor: una sola fuente en la sala puede producir sobrecalentamiento local aunque otras habitaciones permanezcan frías.

[Marigo et al. (2022), análisis dinámico de estufa de leña y pellet en una vivienda](https://sfera.unife.it/retrieve/e309ade4-ed9d-3969-e053-3a05fe0a2c94/2022_Energy%20analysis%20of%20a%20wood%20or%20pellet%20stove%20in%20a%20single-family%20house.pdf), modelan la estufa como una fuente de alta temperatura localizada en la sala y destacan que la distribución entre zonas y la ventilación son determinantes.

**Aplicación en `tsib`:** un estado `stove_storage_kwh` o un modelo RC de uno o dos estados permite capturar el desfase entre combustible quemado y calor entregado sin introducir combustión detallada.

### 2.5. Modelo dinámico de equipo y emisiones

En equipos de pellet o calderas de biomasa se han usado modelos dinámicos con eficiencia variable, estados de encendido y emisiones. [La evaluación de modelos dinámicos de calderas y estufas de pellet en TRNSYS](https://ideas.repec.org/a/eee/appene/v86y2009i5p645-656.html) es relevante como referencia de estructura de sistema y validación, aunque una estufa de leña por cargas no debe asumirse equivalente a un equipo de pellet modulado.

La [revisión técnica de modelación y simulación de combustión de estufas de leña](https://arxiv.org/abs/2107.09722) cubre modelos de distinta fidelidad y señala que la combustión, el transporte de especies y la transferencia de calor transitoria requieren una complejidad muy superior a la de un modelo de carga horaria.

**Conclusión:** emisiones y combustión detallada deben ser una extensión, no una dependencia del MVP de consumo térmico.

### 2.6. CFD y co-simulación

Los modelos CFD pueden resolver convección, radiación, flujo de aire, pirólisis, gases y distribución espacial. Son útiles para diseño del artefacto o validación física, pero no son adecuados como núcleo de una librería de perfiles residenciales de bajo coste computacional.

La biblioteca [Modelica Buildings](https://simulationresearch.lbl.gov/modelica/) muestra una alternativa modular: separar zona, equipo, control, almacenamiento y propiedades de combustible mediante componentes conectables. Ese patrón de composición es más relevante para la arquitectura de `tsib` que reproducir el nivel de detalle de sus modelos.

## 3. Matriz comparativa

| Enfoque | Fidelidad del artefacto | Coste | Retroalimentación con 5R1C | Datos requeridos | Adecuación inicial |
| --- | ---: | ---: | ---: | ---: | --- |
| Demanda limitada + eficiencia fija | Baja | Muy bajo | No, si es postproceso | Demanda, eficiencia, PCI | **MVP** |
| Conversor + potencia máxima | Baja-media | Bajo | Parcial | Lo anterior + potencia | **MVP extendido** |
| Eventos de carga + curva de liberación | Media | Bajo-medio | Sí, mediante acoplamiento | Eventos, curva, operación | Segunda etapa |
| RC de almacenamiento de estufa | Media-alta | Medio | Sí | Capacidad, pérdidas, tiempos | Segunda etapa |
| Pellet/biomasa dinámico | Media-alta | Medio-alto | Sí | Curvas de equipo y mediciones | Referencia |
| CFD de combustión y habitación | Muy alta | Muy alto | Sí | Geometría, materiales, combustión | Fuera del MVP |
| Perfil estocástico tipo `simFireplace()` | Baja para energía | Bajo | No | Temperatura, ocupación, semilla | Sólo *timing* auxiliar |

## 4. Auditoría de la implementación actual de tsib

### 4.1. `sim_demand_direct()`

En [`tsib/thermal/model5R1C.py`](../../tsib/thermal/model5R1C.py), `sim_demand_direct()`:

- calcula la demanda horaria en un paso temporal derivado del índice;
- utiliza `Q_ig`, solar, temperatura exterior, ventilación y masa térmica;
- produce `Heating Load`, `Cooling Load`, `Electricity Load`, `T_air`, `T_s` y `T_m`;
- trata `Heating Load` como calor auxiliar necesario para sostener el setpoint;
- permite disponibilidad horaria de calefacción, pero no un equipo de biomasa con estados.

Esto hace posible una integración posterior a la demanda, pero no resuelve por sí solo el problema de sobrecalentamiento de una estufa de pulsos.

### 4.2. `simFireplace()`

En [`tsib/renewables/fireplace.py`](../../tsib/renewables/fireplace.py), `simFireplace()`:

- usa temperatura exterior y actividad de ocupantes;
- activa la estufa bajo un umbral de temperatura;
- genera un perfil estocástico relativo;
- usa `fullloadSteps` como objetivo aproximado de horas equivalentes;
- no recibe PCI, masa, densidad, eficiencia, potencia térmica ni consumo anual;
- no devuelve un balance energético ni calor útil calibrado.

Por tanto, puede servir como generador de eventos o *timing* futuro, pero no debe ser el estimador principal del consumo residencial de leña.

### 4.3. Contrato de integración recomendado

El primer contrato debe ser explícito:

```text
5R1C:
    Heating Load(t) [kW útiles]
        ↓
módulo de estufa:
    useful_heat(t), fuel_input(t), storage(t), unmet/unallocated
        ↓
resultados de consumo y, en etapa posterior, calor interno acoplado
```

El módulo no debe escribir directamente sobre `elecLoad`. Si se acopla la estufa al balance térmico, debe utilizar un canal separado de calor de sistema o una variable de ganancia térmica identificable, no mezclar silenciosamente el calor de leña con las ganancias internas de ocupación.

## 5. Recomendación para tsib-fcr

### 5.1. MVP: balance de demanda y combustible

Implementar primero una función pura que:

1. reciba una serie horaria de `Heating Load`;
2. reciba un objetivo anual de energía de combustible o un escenario regional;
3. convierta combustible a calor útil con `eta`;
4. distribuya el calor sólo sobre pasos con demanda positiva;
5. limite `useful_heat(t)` a `Heating Load(t)`;
6. reporte energía objetivo, asignada, no asignada y demanda no satisfecha;
7. devuelva masa y volumen de leña.

Ecuaciones mínimas:

```text
E_use,target = E_fuel,target × eta

Q_use,assigned(t) = min(Q_heat(t), Q_stove_available(t))

E_use,assigned = sum(Q_use,assigned(t) × dt)

E_fuel,assigned = E_use,assigned / eta

m_wood = E_fuel,assigned × 3.6 / PCI_MJ_per_kg

V_solid = m_wood / density_t_per_solid_m3

V_stere = V_solid / solid_m3_per_stere
```

El MVP es un postproceso de la demanda, por lo que debe declarar que no captura sobrecalentamiento ni retroalimentación de temperatura.

### 5.2. Segunda etapa: eventos y almacenamiento

Añadir un modelo de baja dimensión:

```text
S[t+1] = S[t] + eta_charge × E_combustion[t] - E_release[t]
Q_stove[t] = E_release[t] / dt
Q_stove[t] = Q_conv[t] + Q_rad[t]
```

El controlador podrá generar cargas de leña a partir de:

- demanda prevista;
- temperatura exterior;
- temperatura interior o setpoint;
- presencia/actividad;
- duración mínima entre cargas;
- potencia nominal y mínima;
- capacidad de almacenamiento térmico.

La integración con 5R1C debe compararse entre dos alternativas:

1. **Iteración externa:** ejecutar 5R1C, generar eventos, volver a ejecutar con calor de estufa como entrada y verificar convergencia.
2. **Extensión del paso directo:** añadir un argumento opcional de calor de sistema a `sim_demand_direct()`, manteniendo la compatibilidad de la firma existente.

La segunda alternativa es más limpia para control con retroalimentación, pero requiere modificar y validar el núcleo térmico. No debe implementarse hasta tener un caso sintético de referencia.

## 6. API candidata

La firma se mantendrá abierta hasta terminar la matriz bibliográfica, pero el contrato candidato es:

```python
result = simulate_wood_stove(
    heating_load,
    dt_hours=None,
    fuel_energy_target_kwh=None,
    efficiency=0.50,
    pci_mj_per_kg=15.0,
    density_t_per_solid_m3=0.7,
    solid_m3_per_stere=0.64,
    max_useful_power_kw=None,
    availability=None,
    event_profile=None,
)
```

El resultado debería ser un objeto o diccionario con:

- `useful_heat_kw`;
- `fuel_input_kw`;
- `fuel_energy_kwh`;
- `wood_mass_kg`;
- `wood_volume_solid_m3`;
- `wood_volume_stere`;
- `assigned_useful_energy_kwh`;
- `unallocated_useful_energy_kwh`;
- `unmet_heating_energy_kwh`;
- `storage_kwh` cuando exista modelo dinámico;
- parámetros efectivos y fuente del escenario.

## 7. Decisiones que no deben quedar implícitas

- `Heating Load` es demanda útil, no energía química.
- La eficiencia se aplica entre combustible y calor útil; no debe aplicarse dos veces.
- La energía no asignada no debe forzarse en horas con demanda cero.
- El volumen estéreo no es igual al volumen sólido; la conversión debe ser explícita.
- La estufa puede entregar calor sólo en una zona, aunque la demanda esté agregada para la vivienda.
- Cocina y ACS quedan fuera del primer módulo.
- `elecLoad` no debe ser reducido automáticamente sin una hipótesis explícita de sustitución.
- `simFireplace()` no sustituye el balance anual ni la calibración REDPE.
- Un escenario regional debe distinguir vivienda consumidora, vivienda promedio y expansión al stock.

## 8. Próximos pasos de implementación

1. Convertir esta revisión en una matriz de referencias con ecuaciones, entradas, salidas y validación.
2. Crear un fixture sintético de `Heating Load` con demanda positiva y cero.
3. Implementar el MVP puro y sus pruebas de conservación.
4. Comparar distribución proporcional, potencia limitada y evento de carga.
5. Diseñar el acoplamiento con temperatura sólo después de validar el MVP.
6. Publicar un PR separado con módulo, tests, ejemplo y documentación.

## Referencias principales

1. [ISO 52016-1:2017 — Energy performance of buildings](https://www.iso.org/standard/65696.html).
2. [Pizzuti, Roberto y Arcuri (2016) — EN ISO 13790 frente a TRNSYS](https://www.sciencedirect.com/science/article/pii/S1876610216312346).
3. [Oliveira Panão et al. (2016) — Validación de modelo RC lumped](https://www.sciencedirect.com/science/article/pii/S0378778816302109).
4. [Michalak (2019) — Modelo 4R1C/5R1C con ventilación variable](https://www.sciencedirect.com/science/article/pii/S037877881930787X).
5. [Saastamoinen et al. (2005) — Modelo dinámico simplificado de estufas acumuladoras](https://doi.org/10.1016/j.applthermaleng.2005.02.009).
6. [Georges y Skreiberg (2016) — Procedimiento simplificado para edificios calentados con estufa](https://doi.org/10.1080/19401493.2016.1188988).
7. [Georges et al. (2012) — Integración de estufas en casas pasivas](https://www.sciencedirect.com/science/article/abs/pii/S0378778812006834).
8. [Marigo et al. (2022) — Análisis dinámico de estufa de leña y pellet](https://sfera.unife.it/retrieve/e309ade4-ed9d-3969-e053-3a05fe0a2c94/2022_Energy%20analysis%20of%20a%20wood%20or%20pellet%20stove%20in%20a%20single-family%20house.pdf).
9. [EnergyPlus Input Output Reference — OtherEquipment](https://energyplus.net/assets/nrel_custom/pdfs/pdfs_v23.1.0/InputOutputReference.pdf).
10. [EnergyPlus Engineering Reference — Ideal Loads Air System](https://energyplus.net/assets/nrel_custom/pdfs/pdfs_v24.2.0/EngineeringReference.pdf).
11. [Modelica Buildings — propiedades de combustibles](https://simulationresearch.lbl.gov/modelica/releases/v5.0.0/help/Buildings_Fluid_Data_Fuels.html).
12. [Wood Stove Combustion Modeling and Simulation — revisión técnica](https://arxiv.org/abs/2107.09722).
