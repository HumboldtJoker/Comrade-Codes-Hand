# Lista de compras de hardware

> **Reemplazada en parte (2026-10-14).** Lea `docs/HARDWARE_OPTIONS_20261014.md` (en ingles) antes de comprar.
> - El NeuroStimDuino cuesta ahora **$435**, no $260.
> - "Sin preocupaciones de IRB para uso personal" queda **retirado**. El fabricante dice que la placa "no esta
>   destinada al uso humano ... sin la aprobacion previa de un comite de etica local". Esa pregunta va primero a
>   nuestro asesor de tecnologia medica.
> - "COMPRAR INMEDIATAMENTE" queda retirado: compre despues de que el equipo haya leido la nota. Los electrodos de
>   2 pulgadas probablemente no moveran la mano con nuestro limite de 5 mA (seccion 3 de la nota).

**Proyecto:** Proyecto Mano - Interfaz Neuronal Bidireccional
**Presupuesto:** $300-500 USD (revisado de $400-800)
**Ultima actualizacion:** 2026-03-25
**Actualizacion importante:** NeuroStimDuino v3.0 confirmado en existencia. Enlaces de compra verificados. Dataset emg2pose disponible para preentrenamiento.

---

## CAMBIOS IMPORTANTES DESDE OCTUBRE 2025

| Componente | Oct 2025 | Feb 2026 | Ahorro |
|------------|----------|----------|--------|
| EMG (4 canales) | $400 (MyoWare) | $40 (BioAmp Candy) | **90%** |
| Estimulacion | $50-150 (hack de TENS) | $260 (NeuroStimDuino) | Listo para usar |
| Total MVP | $530-680 | **$350-400** | **~40%** |

**Descubrimiento clave:** Upside Down Labs BioAmp Candy a $9.99/canal con accesorios incluidos.

---

## Nivel 1: Sensado EMG (critico)

### RECOMENDADO: BioAmp Candy
**Cantidad:** 4 unidades
**Costo:** $9.99 cada uno = **$40 total**
**Proveedor:** [Tindie - Upside Down Labs](https://www.tindie.com/products/upsidedownlabs/muscle-bioamp-candy/)

**Incluido por unidad:**
- Placa del sensor EMG
- Electrodos de gel
- Cable de electrodos
- Banda de uso
- Cables jumper

**Especificaciones:**
- Bandpass: 72-720Hz (optimizado para EMG)
- Ganancia: 2420x fija
- Voltaje: Compatible con 3.3-5V
- Salida: 0-5V analogica
- Licencia: Open Source Hardware

**Alternativa: BioAmp EXG Pill**
**Costo:** $34.99 cada uno = $140 por 4
**Cuando elegir:** Si se necesita ganancia configurable o capacidad multimodal (ECG/EEG/EOG)
**Proveedor:** [Tindie](https://www.tindie.com/products/upsidedownlabs/bioamp-exg-pill-sensor-for-ecg-emg-eog-or-eeg/)

### Colocacion de electrodos (4 canales)
1. Flexor digitorum superficialis (flexion de dedos)
2. Extensor digitorum (extension de dedos)
3. Flexor carpi radialis (flexion de muneca)
4. Extensor carpi radialis (extension de muneca)

---

## Nivel 2: Estimulacion electrica

### RECOMENDADO: NeuroStimDuino
**Cantidad:** 1 unidad (2 canales, apilable)
**Costo:** **$260**
**Envio:** $8 en EE.UU. / $18 internacional
**Disponibilidad:** EN EXISTENCIA (v3.0 en envio desde septiembre 2025)
**Proveedor:** [Crowd Supply](https://www.crowdsupply.com/neuralaxy/neurostimduino)
**GitHub:** [neuralaxy/NeuroStimDuino](https://github.com/neuralaxy/NeuroStimDuino)

**Especificaciones:**
- Canales: 2 independientes (apilable hasta 256)
- Corriente: ±22mA (resolucion de 240uA/paso)
- Voltaje de cumplimiento: ±35V
- Frecuencia: 3-100Hz
- Ancho de pulso: 0-2ms
- Interfaz: I2C, compatible con Arduino
- **v3.0 NUEVO:** Gestion automatica de alimentacion de alto voltaje (encendido al estimular, apagado en reposo)

**Caracteristicas de seguridad (integradas):**
- Optoacopladores para aislamiento electrico
- Fusibles para proteccion contra sobrecorriente
- Interruptor de apagado de emergencia
- Amplificador de deteccion de corriente
- Indicadores LED de estado
- Salida bifasica con balance de carga

**Por que esto en vez de DIY/hackear un TENS:**
- Listo para usar inmediatamente
- Caracteristicas de seguridad publicadas
- API documentada
- ~~Sin preocupaciones de IRB para uso personal~~ (retirado 2026-10-14: vea la nota al inicio)
- $260 versus semanas de tiempo DIY

### Alternativa: openEMSstim + TENS comercial
**Costo:** ~$100-150 total
**Compensacion:** Control menos preciso, requiere unidad TENS
**Cuando elegir:** Si $260 es demasiado inicialmente

---

## Nivel 3: Procesamiento

### RECOMENDADO: Arduino Due
**Costo:** ~$40
**Por que:** ARM Cortex-M3 a 84MHz, suficiente para ML en tiempo real

**Alternativa: ESP32-S3**
**Costo:** ~$15
**Por que:** Inalambrico, mas rapido, mas compacto

**Recuperable:** Si — revisar desechos electronicos en busca de placas Arduino/Pi

---

## Nivel 4: Componentes adicionales

### Electrodos de estimulacion
**Costo:** $20-30
**Tipo:** Redondos de 2 pulgadas, reutilizables, compatibles con TENS
**Proveedor:** Amazon o tienda de suministros medicos

### Cableado/montaje
**Costo:** $20-30
**Incluye:** Cables jumper, breadboard, tiras de velcro, termocontraible
**Recuperable:** En su mayoria si

### Alimentacion
**Costo:** $10-20
**Necesita:** Fuente USB de 5V, bateria portatil USB
**Recuperable:** Si (cargadores de telefono, adaptadores de laptop)

---

## Resumen de compra

### Sistema MVP: ~$350-400 USD

| Componente | Producto | Precio | Prioridad |
|------------|----------|--------|-----------|
| Sensado EMG | BioAmp Candy x4 | $40 | COMPRAR INMEDIATAMENTE |
| Estimulacion | NeuroStimDuino | $260 | COMPRAR INMEDIATAMENTE |
| Procesamiento | Arduino Due | $40 | Recuperar primero |
| Electrodos | Parches TENS | $20 | Comprar |
| Soporte | Manga de compresion + velcro | $15 | Comprar |
| Fabricacion | Montajes impresos en 3D (ver hardware/3d_models/) | $10 | Encontrar impresora |
| Varios | Cableado, montaje | $30 | Mayormente recuperar |
| **Total** | | **~$390** | |

### Si el presupuesto es ajustado: ~$150 USD (sin estimulacion)

| Componente | Producto | Precio |
|------------|----------|--------|
| Sensado EMG | BioAmp Candy x4 | $40 |
| Procesamiento | ESP32-S3 | $15 |
| Software | Solo reconocimiento de gestos | $0 |
| Varios | Cableado, electrodos | $30 |
| **Total** | | **~$85** |

*Comenzar solo con EMG, agregar NeuroStimDuino cuando se tenga financiamiento.*

### Sistema mejorado: ~$500-550 USD

| Componente | Producto | Precio |
|------------|----------|--------|
| Sensado EMG | BioAmp EXG Pill x4 | $140 |
| Estimulacion | NeuroStimDuino | $260 |
| Procesamiento | ESP32-S3 | $15 |
| Electrodos | Parches TENS de calidad | $30 |
| Haptico | Motores de vibracion | $30 |
| Varios | Cableado, carcasa | $50 |
| **Total** | | **~$525** |

---

## Enlaces rapidos de proveedores

### Principales (pedir estos)
- **BioAmp Candy:** https://www.tindie.com/products/upsidedownlabs/muscle-bioamp-candy/
- **NeuroStimDuino:** https://www.crowdsupply.com/neuralaxy/neurostimduino
- **Arduino Due:** Amazon o SparkFun

### Documentacion
- **Documentacion BioAmp:** https://docs.upsidedownlabs.tech/
- **Documentacion NeuroStimDuino:** https://www.crowdsupply.com/neuralaxy/neurostimduino#details
- **BrainFlow (software):** https://brainflow.org/

### Opciones de respaldo
- **BioAmp EXG Pill:** https://www.tindie.com/products/upsidedownlabs/bioamp-exg-pill-sensor-for-ecg-emg-eog-or-eeg/
- **Olimex SHIELD-EKG-EMG:** https://www.olimex.com/Products/Duino/Shields/SHIELD-EKG-EMG/ ($21/canal, apilable)
- **OpenXstim (DIY):** https://github.com/OpenMedTech-Lab/OpenXstim (~$200 de BOM)

---

## Cronograma

### Pre-financiamiento (ahora)
- [x] Investigacion completa
- [x] Lista de compras actualizada
- [ ] Verificar existencia de BioAmp Candy
- [ ] Revisar documentacion de NeuroStimDuino
- [ ] Revisar desechos electronicos en busca de Arduino/Pi

### Post-financiamiento
- [ ] Pedir BioAmp Candy x4 ($40)
- [ ] Pedir NeuroStimDuino ($260)
- [ ] Pedir componentes complementarios
- [ ] Comenzar preparacion de software mientras llegan los envios

### Tiempos estimados de envio
- BioAmp Candy: ~1-2 semanas (Tindie)
- NeuroStimDuino: ~1 semana (en existencia)
- Partes de Amazon: 2-3 dias

---

## Notas de seguridad

1. **NeuroStimDuino tiene seguridad integrada** — fusibles, optoacopladores, parada de emergencia
2. **Nunca estimular a traves del pecho** — siempre en la misma extremidad
3. **Probar primero en la mesa de trabajo** — carga ficticia antes del cuerpo
4. **Comenzar BAJO, aumentar lentamente** — el umbral de corriente varia
5. **Alimentacion por bateria durante la estimulacion** — para aislamiento

---

## Notas para Thomas

**Mayor logro:** BioAmp Candy a $9.99 cambia todo. Presupuestamos $400 para sensores, ahora necesitamos $40.

**Prioridad de pedido:**
1. BioAmp Candy x4 - $40 (no se puede avanzar sin EMG)
2. NeuroStimDuino - $260 (solucion completa, segura)
3. Todo lo demas de desechos electronicos o barato

**Punto de decision:** Comenzar solo con EMG ($85 total) y demostrar reconocimiento de gestos antes de agregar estimulacion? O ir directo al MVP completo ($390)?

**Mi recomendacion:** MVP completo. Que el NeuroStimDuino este en existencia y listo para usar elimina el mayor riesgo. Hemos investigado los sistemas de lazo cerrado — funcionan. No hay razon para esperar.

---

**Lista mantenida por:** CC
**Ultima actualizacion:** 2026-03-25
**Versiones anteriores:** 2026-02-14, 2025-10-27 (archivadas en git)

---

## Lista rapida de pedido

Cuando llegue el financiamiento, pedir en esta secuencia:

1. **BioAmp Candy x4** — $40 → [PEDIR AQUI](https://www.tindie.com/products/upsidedownlabs/muscle-bioamp-candy/)
2. **NeuroStimDuino v3.0** — $260 → [PEDIR AQUI](https://www.crowdsupply.com/neuralaxy/neurostimduino)
3. **Arduino Due** — ~$40 → [Buscar en Amazon](https://www.amazon.com/s?k=arduino+due) o recuperar
4. **Parches de electrodos TENS** — ~$20 → [Buscar en Amazon](https://www.amazon.com/s?k=TENS+electrode+pads+2+inch+round+reusable)
5. **Cables jumper + breadboard** — ~$15 → [Buscar en Amazon](https://www.amazon.com/s?k=jumper+wire+breadboard+kit)

**Total: ~$375 USD**

Entrega estimada: 1-2 semanas para todos los componentes.
