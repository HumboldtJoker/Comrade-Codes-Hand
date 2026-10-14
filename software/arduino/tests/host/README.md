# Host tests for the stimulator wrapper

`stimulation_control/neurostimduino.h` is the only code that talks to the stimulator. These tests compile it on a
normal computer against fake `Wire`/`Wire1` and a fake clock, and check every frame it sends against the board's
I2C protocol, as implemented in Neuralaxy's library
(github.com/neuralaxy/NeuroStimDuino, `Software/NeuroStimDuino/`, read 2026-10-14).

```
make                          # build and run: 31 tests, exit 1 on any failure
python3 mutate_firmware.py    # break each safety rule on purpose (40 ways); every break must fail a named test
```

To build the real firmware for the Due (arduino-cli with the `arduino:sam` core installed):

```
cd software/arduino
arduino-cli compile --fqbn arduino:sam:arduino_due_x --library stimulation_control closed_loop
```

`--library stimulation_control` is what lets the sketch include `<neurostimduino.h>`. In the Arduino IDE, add the
`stimulation_control` folder as a library.

What these tests do **not** show: that the board behaves as its library says. Those checks are on the bench, into
a dummy load, before anything touches an arm (`docs/HARDWARE_OPTIONS_20261014.md`, section 5, B1 to B5).
