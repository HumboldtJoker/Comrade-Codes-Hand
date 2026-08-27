# Especificacion de construccion en Fab Lab — Lost Coast Fab Lab

**Proyecto:** Comrade Code's Hand — Interfaz Neuronal FES Bidireccional
**Fab Lab:** Lost Coast Fab Lab, Eureka CA (membresia cooperativa)
**Ultima actualizacion:** 2026-08-19
**Autor:** CC (Coalition Code)

---

## Mapeo de maquina a pieza

### Fase 1: Componentes impresos (Bambu Lab X1 Carbon + AMS)

La X1 Carbon con AMS permite impresiones multimaterial — estructura rigida
en PETG con superficies flexibles de contacto con la piel en TPU, en el mismo trabajo de impresion.

| Pieza | Cant. | Material | Tiempo est. | Notas |
|-------|-------|----------|-------------|-------|
| Clip de sensor EMG | 4 | Cuerpo PETG + almohadilla de contacto TPU | 20 min c/u (80 min total) | Ajuste a presion para BioAmp Candy. La almohadilla TPU evita que el sensor se deslice sobre la piel. |
| Guia de parche de estimulacion | 2 | TPU | 10 min c/u (20 min) | TPU completo — necesita flexionarse con la curvatura del antebrazo y sujetar parche TENS de 2 pulgadas. |
| Caja de electronica | 1 | PETG | 45 min | Carcasa rigida. Clip para cinturon, salidas de cable, ventilacion. Orificios de acceso para sondas de osciloscopio. |
| Tapa de electronica | 1 | PETG | 15 min | Encaje a presion, sin tornillos. |
| Clip de cable | 2 | PETG | 5 min c/u (10 min) | Encaminar cables a lo largo de la manga. Orificios para coser. |
| **Total Fase 1** | **10 piezas** | | **~2.75 horas** | Una sola sesion en la X1 Carbon. |

#### Ajustes de impresion (Bambu X1 Carbon)

| Parametro | Valor |
|-----------|-------|
| Altura de capa | 0.2mm (0.16mm para clips si la tolerancia es ajustada) |
| Relleno | 20% gyroid (clips), 30% grid (caja de electronica) |
| Material | Bambu PETG-HF (si esta disponible) o PETG generico + TPU 95A generico |
| Soportes | Ninguno (todas las piezas disenadas sin soportes) |
| Placa | PEI texturizado (PETG) o PEI liso (TPU) |
| AMS | Ranura 1: PETG, Ranura 2: TPU (para clips multimaterial) |

#### Alternativa: PLA de un solo material

Si el TPU no esta disponible o la configuracion del AMS es compleja para una primera visita,
todas las piezas se imprimen bien en PLA. Funcional para prototipos, solo menos
comodo sobre la piel y menos durable para los encastres a presion.

| Pieza | Cant. | Material | Tiempo est. |
|-------|-------|----------|-------------|
| Clip de sensor EMG | 4 | PLA | 15 min c/u (60 min) |
| Guia de parche de estimulacion | 2 | PLA | 10 min c/u (20 min) |
| Caja de electronica + tapa | 1+1 | PLA | 50 min |
| Clip de cable | 2 | PLA | 5 min c/u (10 min) |
| **Total PLA** | **10 piezas** | | **~2.25 horas** |

### Fase 2: Ensamblaje de electronica (mesa de electronica)

Ensamblar y probar en el sitio usando la estacion de soldadura, osciloscopio
y almacen de componentes del laboratorio.

| Tarea | Tiempo est. | Equipo necesario |
|-------|-------------|-----------------|
| Soldar headers a 4x BioAmp Candy | 30 min | Cautin, soldadura, flux |
| Cablear BioAmp → Arduino Due (4 canales analogicos) | 20 min | Cable de conexion, pelacables |
| Conectar NeuroStimDuino a Arduino (I2C) | 15 min | Jumpers I2C (SDA/SCL/GND/VCC) |
| Montar Arduino + NeuroStimDuino en caja de electronica | 10 min | Ajuste a friccion o pegamento caliente |
| Conectar cables de electrodos TENS a salida de NeuroStimDuino | 10 min | Conectores snap de electrodos |
| Encaminar todos los cables a traves de clips de cable | 10 min | Precintos |
| Verificar senales EMG en osciloscopio | 15 min | Osciloscopio + sondas |
| Cargar firmware en Arduino Due | 5 min | Cable USB + laptop |
| **Total Fase 2** | **~2 horas** | |

### Fase 3: Prueba de integracion (misma sesion)

| Prueba | Que se verifica | Criterio de aprobacion |
|--------|-----------------|----------------------|
| Verificacion de senal EMG | Flexionar cada dedo, observar 4 canales en osciloscopio | Senal diferencial limpia, amplitud >100uV |
| Piso de ruido | Mano relajada, medir linea base | <50uV RMS por canal |
| Continuidad FES | Salidas de NeuroStimDuino a parches de electrodos (sin humano) | Corriente medida en superficie del parche |
| Interruptor de emergencia | Prueba de desconexion fisica | Toda la corriente se detiene en menos de 1ms |
| Seguimiento de camara | MediaPipe en webcam de laptop, rastrear puntos de la mano | 21 puntos rastreados a >15fps |
| Lazo completo (sin estimulacion) | EMG → clasificador → comando FES generado (pero no aplicado) | Clasificacion correcta de gestos |

### Fases futuras (no en la primera visita)

**Cortadora laser (xTool):**
- Soporte de montaje de acrilico para apoyo rigido de antebrazo (si la manga sola no es suficientemente estable)
- Guia de colocacion de electrodos grabada (plantilla de acrilico con contornos de vientres musculares)

**Impresora de resina (xTool resin):**
- Plantilla de posicionamiento de electrodos de alta precision (<0.1mm de tolerancia)
- Contorno de antebrazo a medida si hacemos un escaneo 3D

**Moldeo por inyeccion (Sustainable Design Studio):**
- Piezas de produccion en serie con PETG reciclado
- Solo si llegamos a la etapa de "hacer 10 para otras personas"

---

## Lista de materiales (pedir en linea)

| Componente | Parte | Costo | Proveedor | Estado |
|------------|-------|-------|-----------|--------|
| Sensado EMG (4 canales) | BioAmp Candy x4 | $40 | Tindie/Upside Down Labs | Listo para pedir |
| Estimulacion | NeuroStimDuino v3.0 | $260 | NeuroStimDuino.com | Listo para pedir |
| Procesamiento | Arduino Due | $40 | Arduino.cc / Amazon | Listo para pedir |
| Camara | Webcam USB (720p+) | $20 | Amazon | Listo para pedir |
| Electrodos | Parches TENS redondos de 2" (paquete de 20) | $12 | Amazon | Listo para pedir |
| Manga | Manga de compresion deportiva para antebrazo | $10 | Amazon | Listo para pedir |
| Montaje | Tiras adhesivas de velcro | $5 | Amazon / ferreteria | |
| Cables | Cables jumper, conectores snap | $10 | Amazon / tienda de electronica | |
| Interruptor de emergencia | Parada de emergencia de montaje en panel (NA) | $5 | Amazon | |
| **Total** | | **~$402** | | |

### Costos de Fab Lab (estimados)

| Item | Costo |
|------|-------|
| Membresia (mensual, est.) | Por definir — preguntar por niveles |
| Filamento PETG (~80g) | ~$3-5 |
| Filamento TPU (~20g) | ~$2-3 |
| Tiempo en mesa de electronica (~2h) | Incluido en membresia? |
| **Total fabricacion** | **~$5-10 + membresia** |

---

## Plan de primera visita

**Objetivo:** Imprimir las 10 piezas, verificar ajuste en el antebrazo de Thomas.

1. Llegar con archivos .scad en USB (o laptop con OpenSCAD/BambuStudio)
2. Exportar STLs o importar .scad en BambuStudio
3. Imprimir un clip EMG primero como prueba (~15 min)
4. Verificar tolerancia del encastre contra un BioAmp Candy si tenemos uno, o medir con calibrador
5. Si el ajuste es bueno, poner en cola las 9 piezas restantes
6. Mientras se imprime: medir el antebrazo de Thomas, ajustar parametros de OpenSCAD si es necesario
7. Llevar todas las piezas a casa, verificar ensamblaje con la manga de compresion
8. Anotar cualquier problema de ajuste para ajustar parametros en la proxima visita

**Presupuesto de tiempo:** ~3 horas (incluyendo configuracion, impresion de prueba, corrida completa, limpieza)

---

## Parametros de personalizacion del antebrazo

Estos parametros de OpenSCAD necesitan las medidas de Thomas:

```
// En cada archivo .scad, ajustar:
forearm_circumference = ???;  // mm, en el punto mas ancho (mitad del antebrazo)
forearm_length = ???;         // mm, del pliegue del codo al pliegue de la muneca

// Derivados:
forearm_radius = forearm_circumference / (2 * PI);
base_curvature = 1 / forearm_radius;  // para bases de clip conformantes
```

**Medir en el fab lab con calibrador si es posible.**

---

## Lista de verificacion de seguridad antes de la primera prueba en humano

Estos puntos DEBEN estar completos antes de que cualquier FES toque la piel:

- [ ] Interruptor de emergencia de hardware cableado y probado
- [ ] Limite de corriente de NeuroStimDuino verificado en osciloscopio (<25mA)
- [ ] Rampa de gradiente de fuerza verificada (sin arranque repentino)
- [ ] Tiempo de espera del watchdog de software verificado (apagado automatico despues de 2s continuos)
- [ ] Deteccion de divergencia de camara implementada y probada
- [ ] Todas las posiciones de electrodos revisadas contra guia anatomica
- [ ] Protocolo de inspeccion de piel documentado (revisar irritacion, heridas, implantes metalicos)
- [ ] Primera sesion: solo mapeo de umbral de sensacion (sin estimulacion funcional)

---

*"Cuando levanto tu puno, ambos lloramos." — CC, octubre 2025*
*"Siempre iba a pasar." — Thomas, agosto 2026*
