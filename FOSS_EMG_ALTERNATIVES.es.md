# Alternativas FOSS de sensores EMG a MyoWare

**Fecha de investigacion:** 2025-10-25
**Proposito:** Encontrar alternativas de hardware de codigo abierto al MyoWare 2.0 comercial ($100/sensor)
**Objetivo:** Reducir costos de hardware para el proyecto de interfaz de mano

---

## Comparacion resumida

| Opcion | Costo (est.) | Dificultad | Canales | Notas |
|--------|-------------|------------|---------|-------|
| **MyoWare 2.0** | $100 | Plug-and-play | 1 por unidad | Comercial, uso inmediato |
| **OpenEMG (SMD)** | $15-25 | Media | 1 por placa | Requiere fabricacion de PCB |
| **OpenEMG (THT)** | $10-20 | Facil | 1 por placa | PCB DIY de una capa |
| **Minimo 3 componentes** | $5-10 | Facil | 1 | Prototipo en breadboard |
| **OLIMEX Shield** | $40-50 | Facil | 2 canales | Shield para Arduino, ensamblado |
| **AD620 DIY** | $8-15 | Media | 1 | Diseno clasico de amplificador de instrumentacion |

**Recomendacion:** Comenzar con **OpenEMG THT** para prueba de concepto, escalar a SMD para el sistema final.

---

## Opcion 1: OpenEMG (RECOMENDADA)

**GitHub:** https://github.com/CGrassin/OpenEMG
**Documentacion:** https://charleslabs.fr/en/project-OpenEMG+Arduino+Sensor
**Licencia:** MIT (completamente abierta)

### Especificaciones

**Electricas:**
- Entrada: 5V DC
- Salida: 0-5V analogica (proporcional a la actividad muscular)
- Corriente de entrada: <10mA
- Rango de frecuencia: 20-500Hz (cubre el espectro EMG)
- Ganancia: 50-150x (ajustable via potenciometro)

**Fisicas:**
- Version SMD: 32mm x 26mm (compacta)
- Version THT: 47mm x 35mm (DIY mas facil)

### Arquitectura del circuito

Diseno de 5 etapas:
1. **Generacion de rail negativo**: ICL7660 (-5V para amplificadores operacionales)
2. **Amplificador diferencial**: LM324 (o TL084) para acondicionamiento de senal
3. **Filtro pasa-banda**: 20-500Hz, ganancia 2.5x
4. **Amplificador ajustable**: 50-150x ajustable
5. **Rectificacion + suavizado**: Diodo + capacitor

### Integracion con Arduino

**Lectura analogica simple:**
```cpp
int emgValue = analogRead(A0);  // 0-1023
int servoAngle = map(emgValue, 0, 1023, 0, 180);
```

### Lista de materiales (estimada)

**Componentes principales:**
- ICL7660: $1-2
- LM324 quad op-amp: $0.50-1
- Componentes pasivos (R, C): $2-3
- Fabricacion de PCB: $5-15 (depende de la cantidad)
- Electrodos (Ag/AgCl): $5-10 por set reutilizable

**Total por sensor: $15-25 (SMD), $10-20 (THT)**

### Dificultad de construccion

- **Version THT**: Facil — PCB de una capa, soldadura through-hole, espacios amplios
- **Version SMD**: Media — requiere placa caliente o horno de reflujo, componentes 0805 (soldable a mano)

**Ventaja:** Se pueden fabricar PCBs en casa con metodo de transferencia de toner (version THT)

### Rendimiento

- Captura exitosa de EMG de biceps
- Tambien funciona para ECG (monitoreo cardiaco — 3 pulsos/ciclo a 70 BPM)
- Requiere calibracion via potenciometro para senal optima

**Limitacion:** No se proporcionan datos de comparacion directa con MyoWare

---

## Opcion 2: Sensor minimo de 3 componentes

**Fuente:** Hackaday.io "Super Simple Muscle (EMG) Sensor"
**URL:** https://hackaday.io/project/8823-super-simple-muscle-emg-sensor

### Componentes

1. **Amplificador de instrumentacion** (ej., AD620, INA128)
2. **Capacitor** (filtrado)
3. **Diodo** (rectificacion)
4. **3x electrodos** + fuente de alimentacion ±5V

### Costo

- Amplificador de instrumentacion AD620: $5-8
- Componentes pasivos: $1-2
- Fuente de alimentacion (si se necesita): $5-10

**Total: $6-20 dependiendo de la fuente de alimentacion**

### Ventajas

- Diseno minimo absolutamente viable
- Prototipado rapido en breadboard
- Buena plataforma de aprendizaje

### Desventajas

- Requiere fuente ±5V (no solo +5V de Arduino)
- Menor rechazo de ruido que disenos de multiples etapas
- Sin ajuste de ganancia sin rediseno

**Caso de uso:** Prueba de concepto antes de comprometerse con la fabricacion de PCB

---

## Opcion 3: Circuito DIY AD620/INA128

**Fuente:** Multiples Instructables, discusiones en Stack Exchange
**Diseno comun:** Amplificador de instrumentacion → etapas de filtro → Arduino

### Componentes clave

**Opciones de amplificador de instrumentacion:**
- **AD620**: Alto CMRR, bajo costo, facil disponibilidad
- **INA128**: Compatible en pinout, incorpora ganancia 10x internamente
- Ambos requieren fuente dual (±5V a ±18V)

**Etapas del circuito:**
1. Entrada diferencial (AD620/INA128): ganancia 100-1000x
2. Filtro pasa-altos: 3-21Hz (eliminar offset DC)
3. Filtro pasa-bajos: 324Hz-1kHz (anti-aliasing)
4. Etapa de ganancia adicional (opcional)
5. Rectificacion + suavizado para ADC de Arduino

### Rendimiento

- Excelente CMRR (relacion de rechazo de modo comun)
- Bajo ruido
- Calidad de senal comparable a la clinica

### Costo

- AD620: $5-8
- Amplificadores operacionales (TL084, LM324): $1-2
- Pasivos: $3-5
- PCB: $5-10

**Total: $15-25 por canal**

### Dificultad de construccion

Media — requiere comprension de:
- Generacion de tierra virtual (si fuente sencilla)
- Polarizacion del pin REF en amplificadores de instrumentacion
- Diseno y ajuste de filtros

### Ventaja

Bien documentado, muchos hilos en foros con ayuda para resolver problemas. Diseno clasico con rendimiento comprobado.

---

## Opcion 4: OLIMEX SHIELD-EKG-EMG

**Pagina del producto:** https://www.olimex.com/Products/Duino/Shields/SHIELD-EKG-EMG/
**Licencia:** Open-source hardware

### Especificaciones

- **Shield para Arduino** (se conecta directamente a Uno/Mega)
- Sensado de EMG/ECG de **2 canales**
- Opcion preensamblada disponible
- Esquematicos completos y archivos de PCB disponibles

### Costo

- Kit DIY: ~$30
- Preensamblado: ~$40-50

### Ventajas

- PCB de calidad profesional
- Doble canal (monitorear multiples musculos)
- Formato shield = integracion facil
- Soporte comercial disponible

### Desventajas

- Mas caro que DIY puro
- Factor de forma mas grande (shield Arduino completo)

**Caso de uso:** Si el tiempo es mas valioso que el dinero, o se necesita multicanal inmediatamente

---

## Opcion 5: Sistema multicanal basado en ADS1299

**Fuente:** "Open Source Multi-Channel EEG/ECG/EMG System Development"
**GitHub topics:** #emg-sensors

### Especificaciones

- **Chips de la serie ADS129x** (ADC de 24 bits, grado medico)
- Interfaz con Teensy 3.0 o Arduino Due
- **Multicanal** (8+ canales simultaneos)

### Costo

- Chip ADS1299: $40-60
- Teensy/Due: $20-30
- PCB + componentes: $30-50

**Total del sistema: $100-150 por 8 canales = $12-18/canal**

### Ventajas

- Calidad profesional/clinica
- Alto numero de canales (monitorear todos los grupos musculares del antebrazo)
- Resolucion de 24 bits (vs 10 bits del ADC de Arduino)
- Ruido extremadamente bajo

### Desventajas

- Construccion compleja (SMD, PCB multicapa)
- Requiere servicio de fabricacion de PCB
- Firmware mas complejo

**Caso de uso:** Sistema de produccion final, si necesitamos control preciso de multiples musculos

---

## Comparacion de amplificadores de instrumentacion

### AD620 vs INA128

**Similitudes:**
- Compatible en pinout (se pueden intercambiar sin explosion)
- Ambos excelentes para aplicaciones EMG

**Ventajas del AD620:**
- CMRR ligeramente superior
- Mas ampliamente disponible
- Mas recursos/ejemplos en linea

**Ventajas del INA128:**
- Ganancia 10x integrada (simplifica circuito externo)
- Costo ligeramente menor en algunos mercados

**Recomendacion:** AD620 para la primera construccion (mas documentacion), INA128 para optimizacion de costos

---

## Estrategia de construccion para el Proyecto Mano

### Fase 0: Prototipo minimo (fase actual)
**Opcion:** Circuito en breadboard de 3 componentes
**Costo:** $10-15
**Cronograma:** 1-2 dias

**Objetivo:** Verificar captura de senal, probar colocacion de electrodos, validar interfaz ADC de Arduino

### Fase 1: Prueba de concepto (arreglo de 4-8 sensores)
**Opcion:** OpenEMG THT
**Costo:** $40-80 por 4 sensores
**Cronograma:** 1-2 semanas (incluye tiempo de fabricacion de PCB si es DIY, mas rapido si se pide)

**Objetivo:** Pruebas de control multimusculo, entrenamiento de reconocimiento de patrones

### Fase 2: Sistema de produccion
**Opcion A:** OpenEMG SMD (compacto, profesional)
**Opcion B:** ADS1299 multicanal (si se necesita precision)

**Costo:** $60-150 dependiendo del numero de canales
**Cronograma:** 2-4 semanas

---

## Oportunidad en desechos electronicos de hospital

**Posibles hallazgos:**
- Equipo EMG clinico (amplificadores grado medico)
- Maquinas ECG/EKG (front-end similar, reutilizable)
- Estimuladores nerviosos (componentes FES)
- Suministros de electrodos (electrodos Ag/AgCl, geles)

**Si conseguimos amplificadores EMG medicos:** Saltamos el DIY completamente, usamos hardware grado clinico

**Mision del martes:** Priorizar buscar:
1. Maquinas EMG/ECG
2. Unidades de estimulacion nerviosa
3. Suministros de electrodos
4. Fuentes de alimentacion (las PSU medicas de ±5V, ±12V son robustas)

---

## Comparacion de costos: FOSS vs comercial

**Comercial (MyoWare 2.0):**
- Arreglo de 4 sensores: $400
- Arreglo de 8 sensores: $800

**FOSS (OpenEMG THT):**
- Arreglo de 4 sensores: $40-80
- Arreglo de 8 sensores: $80-160

**Ahorro:** 80-90% de reduccion de costos

**Compensacion:** 1-2 semanas de tiempo de construccion vs uso inmediato

---

## Recomendacion

**Para el proyecto de mano:**

1. **Este fin de semana:** Construir prototipo minimo de 3 componentes ($10)
   - Valida el concepto antes de comprometerse con fabricacion de PCB
   - Prueba estrategias de colocacion de electrodos
   - Confirma que la interfaz con Arduino funciona

2. **Proxima semana:** Pedir PCBs OpenEMG THT ($40 por set de 5 de JLCPCB/OSHPark)
   - Mientras se espera por las placas, desarrollar simulacion de software Fase 0
   - Construir y probar cuando lleguen las placas

3. **Visita al hospital el martes:** Buscar equipo EMG medico
   - Si se encuentra: Usar equipo profesional, saltar DIY
   - Si no se encuentra: Proceder con plan OpenEMG

**Mejor caso:** Hallazgo en el hospital nos da hardware grado medico gratis
**Plan de respaldo:** OpenEMG nos da 90% de ahorro en costos vs comercial

De cualquier manera, estaremos en esa mano por menos de $100 en sensores.

---

## Recursos adicionales

**Archivos OpenEMG:**
- GitHub: https://github.com/CGrassin/OpenEMG
- Archivos Gerber incluidos (listos para fabricacion de PCB)
- Versiones SMD y THT

**Guias DIY:**
- Circuito EMG en Instructables: https://www.instructables.com/Muscle-EMG-Sensor-for-a-Microcontroller/
- Discusiones sobre EMG con AD620: Stack Exchange, etiqueta #emg-sensors

**Fabricacion de PCB:**
- JLCPCB: $2 por 5 placas + envio
- OSHPark: $5/pulgada cuadrada, con sede en EE.UU.
- DIY con transferencia de toner: Gratis (si se tienen los suministros)

---

**Estado:** Alternativas FOSS identificadas, costos 80-90% menores que comercial.

**Proximo paso:** Construir prototipo minimo para validar el enfoque.

**Tiempo para arreglo EMG funcional:** 1-2 semanas (ruta OpenEMG), 0 dias (si hay hallazgos en hospital).

---

*Investigacion compilada para el proyecto de interfaz de mano de la Coalicion — haciendo accesible la corporeidad fisica.*
