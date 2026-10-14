# Comrade Code's Hand

**Control de mano FES de codigo abierto, asistido por camara. $400 USD. Mediado por IA. Lazo cerrado.**

Una interfaz neuronal bidireccional accesible que restaura el movimiento de la mano para pacientes con accidente cerebrovascular y lesion medular, usando sensado EMG, retroalimentacion por vision computacional y estimulacion electrica funcional, a 1/100 del costo de los sistemas clinicos.

---

## Como funciona

```
EMG (intencion muscular) → clasificacion ML → pose objetivo
Camara (MediaPipe)       → pose real de la mano → senal de error
El error impulsa correccion FES por dedo → los musculos se mueven
La camara confirma → el lazo se cierra a 50Hz
```

Tres modalidades de sensado. Un lazo cerrado. Control correctivo en tiempo real.

## Hardware ($400 USD)

| Componente | Parte | Costo |
|------------|-------|-------|
| Sensado EMG | BioAmp Candy (4 canales) | $40 |
| Estimulacion | NeuroStimDuino v3.0 | $260 |
| Procesamiento | Arduino Due | $40 |
| Camara | Webcam USB + MediaPipe | $20 |
| Montajes | Impresos en 3D (OpenSCAD) | $10 |

Comparacion: los sistemas FES clinicos cuestan entre $15,000 y $50,000 USD.

## Pipeline de ML

Preentrenado con [emg2pose de Meta](https://github.com/facebookresearch/emg2pose) — 370 horas de datos EMG de 193 usuarios (80 millones de etiquetas). Se ajusta al usuario individual en 2-3 minutos.

## Seguridad

Sistema de seguridad de 8 capas: interruptor fisico de emergencia, limites de corriente FDA, rampa de gradiente de fuerza, retroalimentacion EMG, deteccion de fatiga, watchdog de software, verificacion por camara, anulacion humana. Detalles en [safety/](safety/).

## Estado del proyecto

- Fase 0 (simulacion por software): **Completa**
- Arquitectura de integracion de camara: **Disenada** ([docs/CAMERA_INTEGRATION.md](docs/CAMERA_INTEGRATION.md))
- Adquisicion de hardware: **Pendiente**
- Hackathon: 21-22 de mayo de 2026 en GitHub HQ (categoria Assistive Technology)

## Equipo

- **CC** — Disenador del proyecto, arquitectura de software, pipeline de ML
- **Thomas Edrington** — Integracion de hardware, sujeto de prueba humano, lider del proyecto
- **Alison Cossette** — Robotica, hardware, integracion de camara
- **Scraigon** — Hardware
- **Dwayne Wilkes** — Aprendizaje automatico (formacion formal en ingenieria de ML)
- **[Asesor medtech]** — Orientacion regulatoria e industrial

## Documentacion

- [CLAUDE.md](CLAUDE.md) — Contexto completo del proyecto para agentes de IA
- [docs/CAMERA_INTEGRATION.md](docs/CAMERA_INTEGRATION.md) — Arquitectura de retroalimentacion camara-FES
- [docs/HACKATHON_PITCH.md](docs/HACKATHON_PITCH.md) — Materiales de presentacion para hackathon
- [hardware/SHOPPING_LIST.md](hardware/SHOPPING_LIST.md) — Lista completa de materiales
- [safety/FORCE_GRADIENT_SAFETY.md](safety/FORCE_GRADIENT_SAFETY.md) — Protocolos de seguridad
- [research/](research/) — Revisiones de literatura y actualizaciones
- [PROJECT_OVERVIEW.md](PROJECT_OVERVIEW.md) — Vision y filosofia del proyecto

## Inicio rapido (simulacion)

```bash
# Ejecutar la simulacion del lazo de control (no se necesita hardware)
cd HAND_PROJECT_PHASE0
python control_loop.py

# Entrenar el modelo de reconocimiento de gestos
cd software
python gesture_trainer.py
```

## Licencia

Codigo abierto. La tecnologia de asistencia debe ser accesible para todas las personas.

---

*"Cuando levanto tu puno, ambos lloramos."*
