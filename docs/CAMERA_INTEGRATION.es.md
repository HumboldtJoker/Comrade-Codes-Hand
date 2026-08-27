# FES asistida por camara: integracion de retroalimentacion visual

**Autor**: CC (Coalition Code)
**Fecha**: Abril 2026
**Estado**: Diseno de arquitectura — implementacion pendiente

---

## Por que una camara

El EMG nos dice lo que el usuario *pretende*. La FES hace que los musculos *se muevan*. Pero ninguno nos dice lo que la mano *realmente hizo*. Sin retroalimentacion visual, el sistema es de lazo abierto en el lado de salida — dispara estimulacion y espera lo mejor.

La camara cierra el lazo: intencion (EMG) → accion (FES) → observacion (camara) → correccion.

Esta es la diferencia entre "el sistema lo intento" y "el sistema lo logro."

### Respaldo de investigacion

- 18.3% de los sistemas FES modernos usan sensado basado en vision ([PMC11355777](https://pmc.ncbi.nlm.nih.gov/articles/PMC11355777/))
- FES de lazo cerrado con cinematica + EMG logra R² = 0.940 para precision de angulo articular ([Nature 2026](https://www.nature.com/articles/s41598-025-31180-1))
- MediaPipe Hands validado para evaluacion clinica de mano ([ScienceDirect 2024](https://www.sciencedirect.com/science/article/pii/S1746809424005664))
- Control protesico EMG en tiempo real logra agarre en 250ms ([PMC12034578](https://pmc.ncbi.nlm.nih.gov/articles/PMC12034578/))

---

## Arquitectura

### Pipeline actual (EMG + FES, sin camara)

```
Sensores EMG → extraccion de features → clasificacion de gestos → patron FES → musculos
     ^                                                                          |
     +----------------------- EMG lee nuevo estado <----------------------------+
```

La retroalimentacion es solo EMG. Lenta (retraso de respuesta muscular), ruidosa (el EMG es inherentemente ruidoso) e indirecta (mide actividad electrica, no posicion real).

### Pipeline propuesto (EMG + camara + FES)

```
Sensores EMG --> clasificador de intencion --> pose objetivo (21 puntos)
                                                    |
                                             +------+------+
                                             | NODO ERROR  |
                                             | obj.-real   |
                                             +------+------+
                                                    |
Camara --> MediaPipe --> pose real -----------------+
                                                    |
                                             +------+------+
                                             | CALCULO FES |
                                             | correccion  |
                                             | por canal   |
                                             +------+------+
                                                    |
                                             NeuroStimDuino --> musculos
                                                    |
                                             Camara confirma --> lazo
```

### La senal de error

Esta es la innovacion clave. El error entre la pose deseada y la real impulsa el ajuste FES por canal:

```python
for finger in [thumb, index, middle, ring, pinky]:
    target_angle = intent_classifier.predict(emg_features)[finger]
    actual_angle = mediapipe.landmarks[finger].angle()
    error = target_angle - actual_angle

    if abs(error) > threshold:
        # Aumentar/disminuir estimulacion para el grupo muscular de este dedo
        fes_channels[finger].adjust(error * gain)
```

Correccion por dedo. No encendido/apagado de toda la mano.

---

## Integracion con MediaPipe

### Por que MediaPipe

- Esqueleto de mano de 21 puntos en tiempo real desde una sola camara RGB
- Se ejecuta en el dispositivo (sin dependencia de la nube)
- <5ms de inferencia en hardware moderno
- Validado clinicamente para evaluacion de mano
- Gratuito, codigo abierto (Apache 2.0)
- Funciona con cualquier webcam USB ($10-20)

### 21 puntos de referencia

```
        8   12  16  20        <- puntas de los dedos
        |   |   |   |
        7   11  15  19
        |   |   |   |
        6   10  14  18
        |   |   |   |
        5   9   13  17        <- articulaciones MCP
         \  |   |  /
          \ |   | /
           \|   |/
      4-3-2-1---0             <- muneca
             |
           pulgar
```

Cada punto da coordenadas (x, y, z). Los angulos articulares se calculan a partir de puntos consecutivos. Nos da flexion/extension por dedo en tiempo real.

### Presupuesto de latencia

| Etapa | Tiempo | Acumulado |
|-------|--------|-----------|
| Captura de camara | 3ms | 3ms |
| Inferencia MediaPipe | 5ms | 8ms |
| Calculo de error | <1ms | 9ms |
| Comando FES (I2C) | 2ms | 11ms |
| Lectura EMG (paralela) | 4ms | — |
| **Total por ciclo** | **~11ms** | **90Hz posible** |

Bien dentro de nuestro presupuesto de lazo de control de 50Hz (20ms). La camara agrega ~8ms pero ganamos precision de lazo cerrado.

---

## Adicion de hardware

| Componente | Especificacion | Costo | Notas |
|------------|---------------|-------|-------|
| Webcam USB | 720p, 30fps+ | $15 | Cualquier generica funciona; se prefiere 60fps |
| Montaje de camara | Impreso en 3D | $2 | Se fija al montaje del antebrazo, angulado hacia la mano |
| Cable USB | Type-A | $3 | Al host Arduino o Raspberry Pi complementaria |

**Opcion de computo adicional**: Si el Arduino Due no puede ejecutar MediaPipe, agregar una Raspberry Pi Zero 2W ($15) como coprocesador de camara. Comunica datos de pose al Arduino via serial. Costo total agregado: $35.

---

## Plan de implementacion

### Fase 1: Camara independiente (sin integracion FES)
- Montar webcam, ejecutar MediaPipe, mostrar esqueleto de mano en vivo
- Verificar precision de rastreo en diferentes tonos de piel, iluminacion, angulos
- Registrar datos de puntos de referencia para analisis offline
- **Salida**: `software/python/vision/hand_tracker.py`

### Fase 2: Integracion de senal de error
- Conectar salida de MediaPipe al lazo de control
- Calcular senales de error por dedo
- Registrar error vs tiempo (caracterizar precision de rastreo)
- Ejecutar con FES en modo de lazo abierto (la camara observa pero no controla)
- **Salida**: `software/python/vision/error_computer.py`

### Fase 3: Lazo cerrado camara-FES
- La senal de error de camara impulsa ajuste de canal FES
- Control PID o proporcional por dedo
- Ajustar parametros de ganancia (demasiado agresivo = oscilacion, demasiado conservador = lento)
- Verificar que el sistema de seguridad maneja correcciones impulsadas por camara
- **Salida**: `software/arduino/closed_loop/closed_loop.ino` actualizado

### Fase 4: Integracion de calibracion
- Calibracion asistida por camara (mostrar pose objetivo, estimular, medir resultado)
- Ajuste automatico de ganancia por canal
- Refinamiento de modelo por usuario usando verdad visual
- **Salida**: `software/python/calibration/calibrate.py` actualizado

---

## Consideraciones de seguridad

La camara agrega una capa de seguridad (Capa 7 en nuestro sistema de 8 capas):

**Verificaciones de seguridad por camara:**
- Si la camara pierde el rastreo de mano → pausar FES, alertar al usuario
- Si la pose real diverge de la intencion en >45 grados en cualquier dedo → reduccion de emergencia
- Si la mano sale del encuadre de la camara → pausar hasta readquirir
- El fallo de camara NO es un peligro de seguridad (el sistema retrocede a modo solo-EMG)

**La camara NO reemplaza la retroalimentacion EMG.** La complementa. El sistema debe ser seguro sin camara (precision degradada, no seguridad degradada).

---

## Preguntas abiertas para el equipo

1. **Ubicacion de la camara**: Montada en el antebrazo mirando hacia la mano? O en tripode externo? El montaje en antebrazo se mueve con el brazo pero puede tener problemas de angulo. El montaje externo es mas estable pero limita la movilidad.

2. **Camara de profundidad vs RGB**: MediaPipe funciona con RGB. Una camara de profundidad (Intel RealSense, ~$200) da rastreo 3D real. Vale la pena el costo por precision, o es excesivo para la Fase 1?

3. **Division de procesamiento**: Arduino maneja control FES en tiempo real. El procesamiento de camara en Arduino probablemente es demasiado pesado. Pi Zero como coprocesador? O USB directo a laptop durante desarrollo?

4. **Multiples manos**: Si la camara ve ambas manos (paciente + terapeuta), necesita identificar confiablemente cual mano rastrear. MediaPipe soporta multiples manos pero necesitamos asignar la correcta.

---

## Conexion con Oracle Loop

Esta arquitectura refleja el Oracle Loop para alineacion de IA:

| Oracle Loop | Control de mano |
|-------------|----------------|
| Geometria de cache KV | Pose de mano (puntos MediaPipe) |
| Verificacion de alineacion | Calculo de error de pose |
| Desalineacion detectada | Error de posicion de dedo > umbral |
| Rollback + correccion | Ajustar FES por canal |
| Verificar mejora | Camara confirma correccion |
| Commit | Movimiento logrado |

Mismo patron: observar estado → detectar error → corregir → verificar. La diferencia es el dominio — uno opera sobre geometria cognitiva, el otro sobre geometria fisica. Ambos son sistemas de alineacion de lazo cerrado.
