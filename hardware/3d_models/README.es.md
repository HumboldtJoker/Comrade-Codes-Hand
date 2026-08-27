# Componentes impresos en 3D — Prototipo del Proyecto Mano

## Descripcion general

Estos componentes montan los sensores EMG y la electronica sobre una manga
de compresion deportiva estandar para antebrazo. Disenados para impresion FDM,
sin soportes, altura de capa de 0.2mm, PLA o PETG.

## Lista de piezas

### 1. Clips de sensor EMG (x4) — `emg_clip.stl`
- Soporte con encastre a presion que sujeta una placa BioAmp Candy
- Tiene una base plana con ranuras para coser o fijar con velcro a la manga
- Dimensiones de la placa: 25mm x 10mm (formato Candy)
- El clip agrega ~3mm de altura sobre la superficie de la manga
- Tiempo de impresion: ~15 min cada uno

### 2. Guias de parche de estimulacion (x2) — `stim_guide.stl`
- Anillo delgado que mantiene un parche TENS redondo de 2 pulgadas en posicion
- Suficientemente flexible para conformarse a la curvatura del antebrazo
- Respaldo de velcro para fijacion a la manga
- Tiempo de impresion: ~10 min cada uno

### 3. Caja de electronica para cinturon — `electronics_box.stl`
- Contiene Arduino Due + NeuroStimDuino apilados
- Clip para cinturon en la parte posterior
- Puertos de salida de cables en un extremo (6 cables: 4 EMG + 2 estimulacion)
- Ranuras de ventilacion en la parte superior
- Dimensiones internas: 100mm x 55mm x 35mm
- La tapa se encaja a presion, sin tornillos necesarios
- Tiempo de impresion: ~45 min

### 4. Organizador de cables (x2) — `cable_clip.stl`
- Clip pequeno que encamina los cables a lo largo de la manga
- Evita enganches durante el movimiento del brazo
- Orificios para coser para fijacion
- Tiempo de impresion: ~5 min cada uno

## Ajustes de impresion

| Parametro | Valor |
|-----------|-------|
| Altura de capa | 0.2mm |
| Relleno | 20% (clips), 30% (caja de electronica) |
| Material | PLA (prototipo) o PETG (durable) |
| Soportes | No se necesitan |
| Paredes | 3 |

## Ensamblaje

### Materiales necesarios (no impresos)
- Manga de compresion deportiva para antebrazo ($8-10)
- Tiras adhesivas de velcro ($5)
- Precintos o tiras de velcro ($3)
- Opcional: aguja + hilo para fijacion permanente

### Pasos

1. Colocar la manga de compresion en el antebrazo
2. Marcar las 4 posiciones de electrodos EMG (ver Colocacion de electrodos abajo)
3. Fijar los clips EMG a la manga en las posiciones marcadas (velcro o coser)
4. Fijar las guias de parche de estimulacion en los vientres musculares objetivo
5. Encaminar los cables a traves de los organizadores a lo largo de la manga
6. Enganchar la caja de electronica al cinturon o cintura
7. Encajar las placas BioAmp Candy en los clips EMG
8. Colocar los parches TENS en las guias de estimulacion
9. Conectar todos los cables al Arduino/NeuroStimDuino

### Colocacion de electrodos

```
        PARTE EXTERIOR DEL ANTEBRAZO (dorsal)
    +-----------------------------+
    |                             |
    |   [EMG2: Ext. Digit.]       |  <- extension de dedos
    |                             |
    |   [EMG4: Ext. Carpi]        |  <- extension de muneca
    |                             |
    |   [STIM1: objetivo Ext.]    |  <- canal de estimulacion 1
    |                             |
    +-----------------------------+

        PARTE INTERIOR DEL ANTEBRAZO (ventral)
    +-----------------------------+
    |                             |
    |   [EMG1: Flex. Digit.]      |  <- flexion de dedos
    |                             |
    |   [EMG3: Flex. Carpi]       |  <- flexion de muneca
    |                             |
    |   [STIM2: objetivo Flex.]   |  <- canal de estimulacion 2
    |                             |
    +-----------------------------+

    (Extremo del codo arriba, extremo de la muneca abajo)
```

## Fuente parametrica

Los archivos STL se generan a partir de archivos fuente OpenSCAD (.scad) incluidos
en este directorio. Las dimensiones se pueden ajustar para diferentes tamanos de antebrazo
modificando los parametros en la parte superior de cada archivo.

## Tiempo total de impresion

| Pieza | Cantidad | Tiempo c/u | Total |
|-------|----------|------------|-------|
| Clip EMG | 4 | 15 min | 60 min |
| Guia de estimulacion | 2 | 10 min | 20 min |
| Caja de electronica | 1 | 45 min | 45 min |
| Clip de cable | 2 | 5 min | 10 min |
| **Total** | | | **~2.25 horas** |

Cabe comodamente en una sola sesion de impresion o se puede dividir entre varias impresoras.
