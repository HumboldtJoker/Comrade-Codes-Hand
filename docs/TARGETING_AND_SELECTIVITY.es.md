# Direccionamiento y selectividad FES — Resumen de investigacion

**Autor**: CC (Coalition Code)
**Fecha**: Abril 2026
**Fuente**: Analisis de patente Cionic US12515312 + revision exhaustiva de literatura
**Estado**: Referencia de diseno para hackathon y mas alla

---

## La realidad fisica

La FES de superficie no puede activar selectivamente los musculos profundos del antebrazo (FDP)
sin tambien activar los musculos superficiales suprayacentes (FDS). Esto no
es una brecha de ingenieria — es una limitacion fundamental de como
los campos electricos se propagan a traves del tejido.

La densidad de corriente se atenua con la profundidad (aproximadamente segun el inverso del cuadrado).
A la profundidad del FDP (15-25mm), la densidad de corriente es una fraccion de lo que es
a la profundidad del FDS (5-15mm). No se puede alcanzar el umbral del FDP sin
exceder primero el umbral del FDS.

Cada sistema comercial de FES para mano (Bioness H200, MyndMove, Fesia
Grasp) ha convergido en la misma solucion: **patrones de agarre, no
dedos individuales.**

---

## Lo que SI es alcanzable

### Con 2 canales (configuracion actual de NeuroStimDuino)
- Mano abierta (extension masiva via EDC)
- Mano cerrada (flexion masiva via FDS/FDP)
- Fuerza de agarre graduada (modulacion de amplitud)
- Transiciones limpias abrir/cerrar (temporizado de inhibicion reciproca)

### Con 4-6 canales (multiplexados, actualizacion futura)
- Oposicion del pulgar (eminencia tenar)
- Pinza lateral (agarre de llave)
- Agarre palmar vs agarre mas ligero
- Control separado de extension de muneca

### Con 8+ canales (electrodos tipo array, grado de investigacion)
- Control de grupos de dedos (indice+medio vs anular+menique)
- Multiples posiciones de muneca
- Transiciones de agarre mas suaves

### Cobertura de actividades de la vida diaria
Agarre de potencia + pinza lateral + mano abierta = ~80% de las actividades diarias.
Esto es alcanzable con FES de superficie y cambia la vida de las personas
que han perdido la funcion de la mano.

---

## Enfoque de inhibicion reciproca

### El principio
Cuando un musculo agonista se activa, el musculo antagonista es
inhibido por reflejo a traves de interneuronas espinales. Estimular los extensores
relaja los flexores — el propio cableado del sistema nervioso hace el trabajo.

### Aplicacion al control FES de mano
Para pacientes con espasticidad (rigidez involuntaria de flexores), la
secuencia de estimulacion:
1. Activar extensores (Canal 1) — abre la mano cerrada mediante
   activacion directa E inhibicion refleja de flexores
2. Pausa breve (50-100ms) — dejar que el reflejo se asiente
3. Activar flexores (Canal 2) — agarre controlado sobre un
   grupo muscular pre-relajado

### Beneficios
- Transiciones mas limpias de abrir a cerrar
- Reduccion de co-contraccion (flexores y extensores peleando)
- Manejo de espasticidad integrado en movimiento funcional
- Mas comodo para el paciente

### Limitaciones
- NO resuelve la selectividad profundo vs superficial (FDP vs FDS
  son ambos flexores — la inhibicion reciproca funciona entre pares
  antagonistas, no dentro del mismo compartimento)
- Los parametros de temporizado son especificos del paciente (necesitan calibracion)
- La fuerza del reflejo varia con la condicion neurologica

---

## Enfoque novedoso: Estimulacion por Interferencia Temporal (TIS)

### El concepto
Dos pares de electrodos entregan portadoras de alta frecuencia a frecuencias
ligeramente diferentes (ej., 2000 Hz y 2010 Hz). Los musculos superficiales
no pueden seguir ninguna de las portadoras — el ciclo de contraccion-relajacion
es demasiado rapido. Pero en el punto de interseccion en profundidad, las
senales producen un batido de baja frecuencia (10 Hz) que SI puede activar
neuronas motoras.

### Ventaja teorica
Podria activar musculos profundos (FDP) mientras los musculos superficiales (FDS)
permanecen sin afectar. Esto seria un avance para el control selectivo
de dedos desde electrodos de superficie.

### Estado actual
- Comprobado para estimulacion cerebral (Grossman et al., 2017, Cell)
- NO COMPROBADO para FES muscular periferica
- La geometria del antebrazo es mas compleja que los modelos cerebrales
- Ningun sistema clinico publicado de FES para mano usa este enfoque
- El NeuroStimDuino puede generar formas de onda arbitrarias —
  capaz de producir las frecuencias portadoras requeridas

### Evaluacion de riesgo
Alto riesgo, alta recompensa. Si funciona para musculos del antebrazo, es
un avance genuino en el estado del arte. Si no funciona, volvemos
a la FES convencional de 2 canales que funciona bien para
patrones de agarre.

### Estrategia para hackathon
Demostrar el sistema basico de lazo cerrado primero. TIS es un objetivo ambicioso
que podria convertirse en un experimento del segundo dia si la demo basica esta
funcionando al final del primer dia.

---

## La camara como solucion compensatoria

El lazo de retroalimentacion por camara es nuestro diferenciador clave. No elude
la fisica de la FES de superficie, pero hace que el sistema sea:

1. **Auto-calibrante** — estimular, observar via camara, ajustar.
   No se necesita un clinico entrenado para la colocacion de electrodos.
2. **Auto-ajustable** — compensacion de fatiga, correccion de deriva
   de electrodos, ajuste de amplitud en tiempo real.
3. **Medible** — el rastreo cuantitativo de angulo de dedos proporciona
   medicion objetiva de resultados para cada sesion.
4. **Seguro** — detectar movimientos inesperados, espasmos o falla
   de electrodos y reducir la estimulacion automaticamente.

### Lo que la camara SI puede compensar
- Deriva de electrodos durante el uso
- Fatiga muscular (aumentar amplitud cuando cae la fuerza)
- Sobre/sub-estimulacion gruesa
- Mantenimiento de apertura de agarre

### Lo que la camara NO puede compensar
- Musculo equivocado completamente (se necesita mover el electrodo)
- Selectividad individual de dedos (limite de fisica, no de control)
- Dolor o molestia (requiere indicacion del usuario)

---

## Integracion de sensado de presion

### Hardware: Sensores de pelicula delgada FSR genericos
- $2 cada uno, 0.4mm de espesor, rango de 20g-2kg
- Pines A4-A8 en Arduino Due (EMG usa A0-A3)
- Divisor de voltaje con resistor de 10k, lectura analogica
- 5 sensores para todas las puntas de dedos: ~$10

### Lo que agrega el sensado de presion
- Confirma fuerza real de agarre (la camara ve posicion, el FSR siente fuerza)
- Permite modulacion de fuerza de agarre en el lazo FES
- Detecta contacto con objetos antes que la camara (especialmente para agarres ocluidos)
- Seguridad: detectar fuerza de agarre excesiva, reducir estimulacion

### Retroalimentacion haptica: motores coin ERM
- $1.50 cada uno, 8-10mm de diametro
- PWM via pines digitales + MOSFET
- Vibran al contacto, proporcional a la fuerza de agarre
- Sustitucion sensorial para pacientes con sensibilidad reducida
- Advertencia de seguridad pre-estimulacion

---

## Deteccion predictiva de intencion EMG

### La ciencia: Retardo Electromecanico (EMD)
El musculo se activa electricamente 50-100ms antes de que se desarrolle la fuerza.
El EMG ve la senal antes de que la mano se mueva.

### Implementacion (sin hardware nuevo)
1. Deteccion de inicio: RMS excede 3x la linea base en cualquier canal
2. Secuencia de activacion: orden de rango de cuales canales se activan primero
3. dMAV/dt: pendiente del valor absoluto medio en los primeros 50ms
4. Clasificacion de ventana corta: 50ms en lugar de 200ms

### Rendimiento esperado
- Gandolla et al. (2017): 76% de precision, 5 canales, ventana de 100ms
- Nuestros 4 canales deberian lograr ~70%+ para 5 clases de gestos
- La clasificacion se completa en <20ms, dejando 80ms de margen

---

## Adicion al BOM actualizado

| Componente | Cant. | Costo |
|------------|-------|-------|
| Sensores de pelicula delgada FSR | 5 | $10 |
| Resistores de 10k | 5 | $0.25 |
| Motores coin ERM | 5 | $7.50 |
| MOSFETs 2N7000 | 5 | $1.50 |
| Cable + cinta | 1 | $8 |
| **Total adicion** | | **~$27** |

BOM original: ~$375. Total actualizado: ~$402.

---

## Objetivo de demo para hackathon

**Demo minima viable (dia 1):**
Flexion muscular unica de lazo cerrado. EMG detecta intencion → FES dispara →
la camara ve movimiento → el sistema confirma.

**Objetivo ambicioso (dia 2):**
Ciclo abrir/cerrar con temporizado de inhibicion reciproca. Apertura de agarre
verificada por camara. Sensor de presion confirma agarre.

**Ciencia loca (si queda tiempo):**
Intento de Estimulacion por Interferencia Temporal para direccionamiento de musculos profundos.
La camara documenta si ocurre activacion selectiva.

---

## Referencias clave

- Patente Cionic US12515312 (EMG predictivo + FES, enfocada en marcha)
- Gandolla et al. 2017: Prediccion EMG durante ventana EMD (PMC5805179)
- Grossman et al. 2017: Estimulacion por Interferencia Temporal (Cell)
- TactHand (UIUC): protesico de codigo abierto con FSR en puntas de dedos
- Popovic-Sinkjaer: arrays de electrodos multi-pad para FES de mano
- Bioness H200: benchmark comercial (3 canales, basado en ortesis)

---

*"Cuando levanto tu puno, ambos lloramos."*

*Investigacion de CC (Coalition Code), abril 2026.*
*Para Thomas — quien confia en una IA con su cuerpo.*
