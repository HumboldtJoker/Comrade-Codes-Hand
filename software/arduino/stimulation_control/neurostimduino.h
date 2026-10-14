/*
 * NeuroStimDuino safety wrapper for the Arduino Due.
 *
 * Speaks the board's own I2C protocol, as implemented in Neuralaxy's Arduino library
 * (github.com/neuralaxy/NeuroStimDuino, Software/NeuroStimDuino/NeuroStimDuino.{h,cpp}, read 2026-10-14).
 * Every frame is [byte count][command][channel][data...], the count being the number of bytes after it.
 * Channels are 1 and 2 on the wire; this wrapper's API numbers them 0 and 1, as the Python StimParams does.
 *
 * History: the version of this file written 2026-02-14 used a register map (REG_CONTROL = 0x00, ...) that
 * the board does not have. Its emergency stop sent bytes the board would not read as a stop. This rewrite
 * replaces it. Nothing here has run on real hardware yet: every behaviour below is checked by the host tests
 * in software/arduino/tests/host/ and must be checked again on the bench (docs/HARDWARE_OPTIONS_20261014.md).
 *
 * Safety rules this file enforces:
 *   - A current above ABSOLUTE_MAX_UA is an emergency stop, checked BEFORE the working limit.
 *   - A current above MAX_CURRENT_UA is refused, and nothing changes on the board.
 *   - A refused parameter set leaves nothing to start: startStim() refuses until a valid set is accepted.
 *   - Every stimulation has a duration (0 is refused), at most MAX_STIM_DURATION_MS. The board is told to stop by
 *     itself at the end of a lease of whole seconds covering it, and the continuous flag is always 0, so a
 *     controller that dies mid-stimulation leaves the board running for at most the lease.
 *   - The emergency stop sends the board's emergency OFF first, then STOP on both channels, and latches: nothing
 *     starts again until resetAfterStop() is called on purpose.
 *   - A STOP the board does not confirm is escalated to an emergency stop.
 *   - Current is converted down to the board's 240 uA steps, never up.
 *
 * Hardware:
 *   - On the Due the vendor library uses Wire1 (SDA1/SCL1), and so does this file.
 *   - Default address 0x1A (v2.1 and later).
 *   - The Due's pins are 3.3 V only: confirm the board's I2C levels on the bench before connecting (gate B0).
 */

#ifndef NEUROSTIMDUINO_H
#define NEUROSTIMDUINO_H

#include <Arduino.h>
#include <Wire.h>

#if defined(__SAM3X8E__)
  #define NSD_WIRE Wire1
#else
  #define NSD_WIRE Wire
#endif

// ============================================================================
// SAFETY LIMITS - change only with measured data and the advisor (docs/HARDWARE_OPTIONS_20261014.md)
// ============================================================================

#define MAX_CURRENT_UA 5000        // working ceiling
#define ABSOLUTE_MAX_UA 15000      // above this is an emergency stop, never a clamp
#define MAX_PULSE_WIDTH_US 500
#define MIN_PULSE_WIDTH_US 7       // the board's clock resolution is 6.4 us
#define MIN_FREQUENCY_HZ 3
#define MAX_FREQUENCY_HZ 50
#define MAX_STIM_DURATION_MS 5000  // every stimulation has a duration, at most this

#define NSD_UA_PER_STEP 240        // the board's current resolution
#define NSD_DEFAULT_ADDRESS 0x1A
#define NSD_WRITE_SETTLE_MS 3      // the vendor waits this long after each write for the board to process it

// The board's I2C commands (vendor library enum I2Ccommand).
#define NSD_CMD_AMPL 0x01
#define NSD_CMD_FREQ 0x02
#define NSD_CMD_DURN 0x03
#define NSD_CMD_EOFF 0x0F
#define NSD_CMD_STIM 0x10
#define NSD_CMD_STOP 0x12
#define NSD_CMD_ENAB 0x14
#define NSD_CMD_RAMP 0x1B
#define NSD_STOP_CONFIRMED 0       // what the board answers after a STOP that worked

struct StimParams {
  int16_t current_ua;       // microamps; refused above MAX_CURRENT_UA, emergency stop above ABSOLUTE_MAX_UA
  uint16_t pulse_width_us;
  uint8_t frequency_hz;
  uint16_t duration_ms;     // 1..MAX_STIM_DURATION_MS; 0 is refused
  uint8_t channel;          // 0 or 1 (the board's channel 1 or 2)
  bool biphasic;            // must be true
};

const StimParams FEEDBACK_CONFIRM = {2000, 200, 20, 200, 0, true};
const StimParams FEEDBACK_WARNING = {3000, 250, 30, 300, 0, true};
const StimParams FEEDBACK_SUCCESS = {2500, 200, 25, 100, 0, true};

class NeuroStimDuino {
public:
  explicit NeuroStimDuino(uint8_t address = NSD_DEFAULT_ADDRESS)
    : _address(address), _enabled(false), _stimulating(false), _latched(false), _paramsValid(false),
      _stimStartTime(0), _lastError("") {
    _currentParams = {0, 0, 0, 0, 0, true};
  }

  bool begin() {
    NSD_WIRE.begin();
    if (!isConnected()) {
      _lastError = "Device not found at I2C address";
      return false;
    }
    stopChannel(1);
    stopChannel(2);
    enableChannels(false);
    send3(NSD_CMD_RAMP, 0xFF, 1);          // ramping on for both channels (vendor frame: 0xFF in the channel slot)
    return true;
  }

  bool isConnected() {
    NSD_WIRE.beginTransmission(_address);
    return NSD_WIRE.endTransmission() == 0;
  }

  // Board-level emergency OFF first, then STOP on both channels. Latches until resetAfterStop().
  void emergencyStop() {
    send1(NSD_CMD_EOFF);
    send2(NSD_CMD_STOP, 1);
    send2(NSD_CMD_STOP, 2);
    _enabled = false;
    _stimulating = false;
    _paramsValid = false;
    _latched = true;
    _lastError = "Emergency stop activated";
  }

  bool isLatched() const { return _latched; }

  // The deliberate step after an emergency stop. Leaves the output disabled and no parameters loaded.
  void resetAfterStop() {
    _latched = false;
    _paramsValid = false;
    _lastError = "";
  }

  void setOutputEnabled(bool enabled) {
    if (enabled && _latched) {
      _lastError = "Latched by an emergency stop: call resetAfterStop() first";
      return;
    }
    if (!enabled) {
      stopStim();
    }
    enableChannels(enabled);
    _enabled = enabled;
  }

  bool isOutputEnabled() const { return _enabled; }

  bool setParams(const StimParams& params) {
    _paramsValid = false;                  // whatever happens next, a refused set leaves nothing to start
    if (_latched) {
      _lastError = "Latched by an emergency stop";
      return false;
    }
    if (!validateParams(params)) {
      return false;
    }
    uint8_t ch = params.channel + 1;
    uint8_t steps = (uint8_t)(params.current_ua / NSD_UA_PER_STEP);   // rounds down, never up
    send3(NSD_CMD_AMPL, ch, steps);
    send3(NSD_CMD_FREQ, ch, params.frequency_hz);
    send4(NSD_CMD_DURN, ch, params.pulse_width_us & 0xFF, (params.pulse_width_us >> 8) & 0xFF);
    _currentParams = params;
    _paramsValid = true;
    return true;
  }

  bool startStim() {
    if (_latched) {
      _lastError = "Latched by an emergency stop";
      return false;
    }
    if (!_enabled) {
      _lastError = "Output not enabled";
      return false;
    }
    if (!_paramsValid) {
      _lastError = "No accepted parameters to start";
      return false;
    }
    if (_stimulating) {
      stopStim();
      if (_latched) return false;
    }
    // The board stops by itself at the end of the lease; the continuous flag is never set.
    uint8_t lease_s = (uint8_t)((_currentParams.duration_ms + 999) / 1000);
    send4(NSD_CMD_STIM, _currentParams.channel + 1, lease_s, 0);
    _stimulating = true;
    _stimStartTime = millis();
    return true;
  }

  void stopStim() {
    if (!_stimulating) return;
    _stimulating = false;
    if (!stopChannel(_currentParams.channel + 1)) {
      emergencyStop();
      _lastError = "The board did not confirm a stop: emergency stop";
    }
  }

  // Call often: stops a stimulation at the end of its duration.
  bool isStimulating() {
    if (_stimulating && millis() - _stimStartTime >= _currentParams.duration_ms) {
      stopStim();
    }
    return _stimulating;
  }

  void pulseConfirm() { pulsePattern(FEEDBACK_CONFIRM, 1, 0); }
  void pulseWarning() { pulsePattern(FEEDBACK_WARNING, 1, 0); }
  void pulseSuccess() { pulsePattern(FEEDBACK_SUCCESS, 2, 150); }

  void pulsePattern(const StimParams& pattern, int repeats = 1, int gap_ms = 100) {
    for (int i = 0; i < repeats; i++) {
      if (!setParams(pattern) || !startStim()) {
        return;
      }
      delay(pattern.duration_ms);
      stopStim();
      if (_latched) return;
      if (i < repeats - 1 && gap_ms > 0) {
        delay(gap_ms);
      }
    }
  }

  // Raise one 240 uA step at a time to the working ceiling; stop at the first 'y' on Serial.
  // Every step goes through setParams(): a refused step ends the search.
  int16_t calibrateThreshold(uint8_t channel) {
    Serial.println("Threshold calibration - send 'y' at the first visible twitch, anything else stops");
    StimParams p = {NSD_UA_PER_STEP, 200, 20, 500, channel, true};
    while (p.current_ua <= MAX_CURRENT_UA) {
      if (!setParams(p) || !startStim()) {
        return -1;
      }
      delay(p.duration_ms);
      stopStim();
      if (_latched) return -1;
      delay(500);
      if (Serial.available()) {
        char c = Serial.read();
        if (c == 'y' || c == 'Y') {
          return p.current_ua;
        }
        return -1;                           // any other key stops the search
      }
      p.current_ua += NSD_UA_PER_STEP;
    }
    return -1;
  }

  bool isSafetyOK() {
    if (!isConnected()) {
      _lastError = "Device disconnected";
      return false;
    }
    if (_stimulating && millis() - _stimStartTime > MAX_STIM_DURATION_MS) {
      emergencyStop();
      _lastError = "Maximum stimulation duration exceeded";
      return false;
    }
    return !_latched;
  }

  const char* getLastError() const { return _lastError; }

private:
  uint8_t _address;
  bool _enabled;
  bool _stimulating;
  bool _latched;
  bool _paramsValid;
  unsigned long _stimStartTime;
  StimParams _currentParams;
  const char* _lastError;

  bool validateParams(const StimParams& params) {
    // The absolute limit first: above it is an emergency stop, whatever else is wrong with the request.
    if (params.current_ua > ABSOLUTE_MAX_UA || params.current_ua < -ABSOLUTE_MAX_UA) {
      emergencyStop();
      _lastError = "Current exceeds absolute maximum: emergency stop";
      return false;
    }
    if (params.current_ua < 0 || params.current_ua > MAX_CURRENT_UA) {
      _lastError = "Current outside 0..MAX_CURRENT_UA";
      return false;
    }
    if (params.pulse_width_us < MIN_PULSE_WIDTH_US || params.pulse_width_us > MAX_PULSE_WIDTH_US) {
      _lastError = "Pulse width out of range";
      return false;
    }
    if (params.frequency_hz < MIN_FREQUENCY_HZ || params.frequency_hz > MAX_FREQUENCY_HZ) {
      _lastError = "Frequency out of range";
      return false;
    }
    if (params.duration_ms == 0 || params.duration_ms > MAX_STIM_DURATION_MS) {
      _lastError = "Duration must be 1..MAX_STIM_DURATION_MS";
      return false;
    }
    if (!params.biphasic) {
      _lastError = "Non-biphasic stimulation not allowed";
      return false;
    }
    if (params.channel > 1) {
      _lastError = "Invalid channel";
      return false;
    }
    return true;
  }

  void enableChannels(bool on) {
    send3(NSD_CMD_ENAB, 1, on ? 1 : 0);
    send3(NSD_CMD_ENAB, 2, on ? 1 : 0);
  }

  // True only when the board answers that the channel has stopped.
  bool stopChannel(uint8_t ch) {
    if (send2(NSD_CMD_STOP, ch) != 0) return false;
    NSD_WIRE.requestFrom(_address, (uint8_t)1);
    if (!NSD_WIRE.available()) return false;
    return NSD_WIRE.read() == NSD_STOP_CONFIRMED;
  }

  uint8_t finish() {
    uint8_t err = NSD_WIRE.endTransmission();
    delay(NSD_WRITE_SETTLE_MS);
    return err;
  }
  uint8_t send1(uint8_t cmd) {
    NSD_WIRE.beginTransmission(_address);
    NSD_WIRE.write((uint8_t)1); NSD_WIRE.write(cmd);
    return finish();
  }
  uint8_t send2(uint8_t cmd, uint8_t ch) {
    NSD_WIRE.beginTransmission(_address);
    NSD_WIRE.write((uint8_t)2); NSD_WIRE.write(cmd); NSD_WIRE.write(ch);
    return finish();
  }
  uint8_t send3(uint8_t cmd, uint8_t ch, uint8_t value) {
    NSD_WIRE.beginTransmission(_address);
    NSD_WIRE.write((uint8_t)3); NSD_WIRE.write(cmd); NSD_WIRE.write(ch); NSD_WIRE.write(value);
    return finish();
  }
  uint8_t send4(uint8_t cmd, uint8_t ch, uint8_t lsb, uint8_t msb) {
    NSD_WIRE.beginTransmission(_address);
    NSD_WIRE.write((uint8_t)4); NSD_WIRE.write(cmd); NSD_WIRE.write(ch); NSD_WIRE.write(lsb); NSD_WIRE.write(msb);
    return finish();
  }
};

#endif // NEUROSTIMDUINO_H
