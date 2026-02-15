/*
 * NeuroStimDuino Interface Library
 *
 * Wrapper for controlling NeuroStimDuino electrical stimulator
 * via I2C from Arduino Due.
 *
 * Safety-first design with multiple layers of protection.
 *
 * Author: CC (Coalition Code)
 * Date: 2026-02-14
 *
 * Hardware:
 *   - NeuroStimDuino connected via I2C
 *   - Default I2C address: 0x50
 *   - SDA: Pin 20 (Arduino Due)
 *   - SCL: Pin 21 (Arduino Due)
 */

#ifndef NEUROSTIMDUINO_H
#define NEUROSTIMDUINO_H

#include <Wire.h>

// ============================================================================
// SAFETY LIMITS - DO NOT EXCEED
// ============================================================================

// Maximum safe current for surface stimulation (microamps)
// Research says 22mA max for NeuroStimDuino, but we start much lower
#define MAX_CURRENT_UA 5000     // 5mA - conservative start
#define ABSOLUTE_MAX_UA 15000   // 15mA - never exceed this

// Maximum pulse width (microseconds)
#define MAX_PULSE_WIDTH_US 500  // 500us - comfortable range

// Frequency limits (Hz)
#define MIN_FREQUENCY_HZ 3
#define MAX_FREQUENCY_HZ 50     // Higher frequencies can be painful

// Maximum continuous stimulation time (milliseconds)
#define MAX_STIM_DURATION_MS 5000  // 5 seconds max continuous

// ============================================================================
// STIMULATION PARAMETERS
// ============================================================================

struct StimParams {
  int16_t current_ua;       // Current in microamps (-22000 to +22000)
  uint16_t pulse_width_us;  // Pulse width in microseconds
  uint8_t frequency_hz;     // Stimulation frequency
  uint16_t duration_ms;     // Total duration
  uint8_t channel;          // Channel 0 or 1
  bool biphasic;            // Charge-balanced biphasic (ALWAYS true for safety)
};

// ============================================================================
// FEEDBACK PATTERNS - Pre-defined safe stimulation patterns
// ============================================================================

// Confirmation pulse - brief, gentle feedback
const StimParams FEEDBACK_CONFIRM = {
  .current_ua = 2000,      // 2mA - gentle
  .pulse_width_us = 200,
  .frequency_hz = 20,
  .duration_ms = 200,      // 200ms burst
  .channel = 0,
  .biphasic = true
};

// Warning pulse - slightly stronger
const StimParams FEEDBACK_WARNING = {
  .current_ua = 3000,      // 3mA
  .pulse_width_us = 250,
  .frequency_hz = 30,
  .duration_ms = 300,
  .channel = 0,
  .biphasic = true
};

// Success pattern - double pulse
const StimParams FEEDBACK_SUCCESS = {
  .current_ua = 2500,
  .pulse_width_us = 200,
  .frequency_hz = 25,
  .duration_ms = 100,
  .channel = 0,
  .biphasic = true
};

// ============================================================================
// NEUROSTIMDUINO CLASS
// ============================================================================

class NeuroStimDuino {
public:
  // Constructor with I2C address
  NeuroStimDuino(uint8_t address = 0x50);

  // Initialize I2C communication
  bool begin();

  // Check if device is responding
  bool isConnected();

  // Emergency stop - immediately halt all stimulation
  void emergencyStop();

  // Enable/disable output (safety interlock)
  void setOutputEnabled(bool enabled);
  bool isOutputEnabled();

  // Set stimulation parameters (with safety checks)
  bool setParams(const StimParams& params);

  // Start stimulation with current parameters
  bool startStim();

  // Stop stimulation
  void stopStim();

  // Check if currently stimulating
  bool isStimulating();

  // Get current stimulation status
  void getStatus(int16_t& current, uint16_t& pulseWidth, uint8_t& frequency);

  // High-level feedback functions
  void pulseConfirm();       // Brief confirmation
  void pulseWarning();       // Warning signal
  void pulseSuccess();       // Success double-pulse
  void pulsePattern(const StimParams& pattern, int repeats = 1, int gap_ms = 100);

  // Calibration - find comfortable threshold for user
  int16_t calibrateThreshold(uint8_t channel);

  // Safety status
  bool isSafetyOK();
  String getLastError();

private:
  uint8_t _address;
  bool _enabled;
  bool _stimulating;
  unsigned long _stimStartTime;
  StimParams _currentParams;
  String _lastError;

  // Safety validation
  bool validateParams(const StimParams& params);

  // I2C communication
  void writeRegister(uint8_t reg, uint8_t value);
  void writeRegister16(uint8_t reg, int16_t value);
  uint8_t readRegister(uint8_t reg);
  int16_t readRegister16(uint8_t reg);

  // NeuroStimDuino register addresses (from datasheet)
  static const uint8_t REG_CONTROL = 0x00;
  static const uint8_t REG_CURRENT_CH0 = 0x01;
  static const uint8_t REG_CURRENT_CH1 = 0x02;
  static const uint8_t REG_PULSE_WIDTH = 0x03;
  static const uint8_t REG_FREQUENCY = 0x04;
  static const uint8_t REG_STATUS = 0x05;

  // Control register bits
  static const uint8_t CTRL_ENABLE = 0x01;
  static const uint8_t CTRL_START = 0x02;
  static const uint8_t CTRL_STOP = 0x04;
  static const uint8_t CTRL_BIPHASIC = 0x08;
};

// ============================================================================
// IMPLEMENTATION
// ============================================================================

NeuroStimDuino::NeuroStimDuino(uint8_t address)
  : _address(address), _enabled(false), _stimulating(false),
    _stimStartTime(0), _lastError("") {
  _currentParams = {0, 0, 0, 0, 0, true};
}

bool NeuroStimDuino::begin() {
  Wire.begin();

  // Check device presence
  Wire.beginTransmission(_address);
  if (Wire.endTransmission() != 0) {
    _lastError = "Device not found at I2C address";
    return false;
  }

  // Ensure output is disabled on startup
  setOutputEnabled(false);
  stopStim();

  return true;
}

bool NeuroStimDuino::isConnected() {
  Wire.beginTransmission(_address);
  return Wire.endTransmission() == 0;
}

void NeuroStimDuino::emergencyStop() {
  // Immediate halt - no validation, just stop
  writeRegister(REG_CONTROL, CTRL_STOP);
  writeRegister16(REG_CURRENT_CH0, 0);
  writeRegister16(REG_CURRENT_CH1, 0);
  _enabled = false;
  _stimulating = false;
  _lastError = "Emergency stop activated";
}

void NeuroStimDuino::setOutputEnabled(bool enabled) {
  if (enabled) {
    writeRegister(REG_CONTROL, CTRL_ENABLE | CTRL_BIPHASIC);
  } else {
    stopStim();
    writeRegister(REG_CONTROL, 0);
  }
  _enabled = enabled;
}

bool NeuroStimDuino::isOutputEnabled() {
  return _enabled;
}

bool NeuroStimDuino::validateParams(const StimParams& params) {
  // Current limits
  if (abs(params.current_ua) > MAX_CURRENT_UA) {
    _lastError = "Current exceeds safe limit";
    return false;
  }
  if (abs(params.current_ua) > ABSOLUTE_MAX_UA) {
    _lastError = "Current exceeds absolute maximum";
    emergencyStop();
    return false;
  }

  // Pulse width limits
  if (params.pulse_width_us > MAX_PULSE_WIDTH_US) {
    _lastError = "Pulse width too long";
    return false;
  }

  // Frequency limits
  if (params.frequency_hz < MIN_FREQUENCY_HZ || params.frequency_hz > MAX_FREQUENCY_HZ) {
    _lastError = "Frequency out of safe range";
    return false;
  }

  // Duration limits
  if (params.duration_ms > MAX_STIM_DURATION_MS) {
    _lastError = "Duration too long";
    return false;
  }

  // Must be biphasic for safety
  if (!params.biphasic) {
    _lastError = "Non-biphasic stimulation not allowed";
    return false;
  }

  // Channel validation
  if (params.channel > 1) {
    _lastError = "Invalid channel";
    return false;
  }

  return true;
}

bool NeuroStimDuino::setParams(const StimParams& params) {
  if (!validateParams(params)) {
    return false;
  }

  _currentParams = params;

  // Set registers
  if (params.channel == 0) {
    writeRegister16(REG_CURRENT_CH0, params.current_ua);
    writeRegister16(REG_CURRENT_CH1, 0);
  } else {
    writeRegister16(REG_CURRENT_CH0, 0);
    writeRegister16(REG_CURRENT_CH1, params.current_ua);
  }

  writeRegister(REG_PULSE_WIDTH, params.pulse_width_us / 10);  // Register in 10us units
  writeRegister(REG_FREQUENCY, params.frequency_hz);

  return true;
}

bool NeuroStimDuino::startStim() {
  if (!_enabled) {
    _lastError = "Output not enabled";
    return false;
  }

  if (_stimulating) {
    stopStim();  // Stop any existing stimulation first
  }

  writeRegister(REG_CONTROL, CTRL_ENABLE | CTRL_BIPHASIC | CTRL_START);
  _stimulating = true;
  _stimStartTime = millis();

  return true;
}

void NeuroStimDuino::stopStim() {
  writeRegister(REG_CONTROL, _enabled ? (CTRL_ENABLE | CTRL_BIPHASIC) : 0);
  _stimulating = false;
}

bool NeuroStimDuino::isStimulating() {
  // Auto-stop if duration exceeded
  if (_stimulating && _currentParams.duration_ms > 0) {
    if (millis() - _stimStartTime >= _currentParams.duration_ms) {
      stopStim();
    }
  }
  return _stimulating;
}

void NeuroStimDuino::getStatus(int16_t& current, uint16_t& pulseWidth, uint8_t& frequency) {
  current = readRegister16(REG_CURRENT_CH0);
  pulseWidth = readRegister(REG_PULSE_WIDTH) * 10;
  frequency = readRegister(REG_FREQUENCY);
}

// High-level feedback functions
void NeuroStimDuino::pulseConfirm() {
  pulsePattern(FEEDBACK_CONFIRM, 1, 0);
}

void NeuroStimDuino::pulseWarning() {
  pulsePattern(FEEDBACK_WARNING, 1, 0);
}

void NeuroStimDuino::pulseSuccess() {
  // Double pulse for success
  pulsePattern(FEEDBACK_SUCCESS, 2, 150);
}

void NeuroStimDuino::pulsePattern(const StimParams& pattern, int repeats, int gap_ms) {
  for (int i = 0; i < repeats; i++) {
    if (setParams(pattern)) {
      startStim();
      delay(pattern.duration_ms);
      stopStim();

      if (i < repeats - 1 && gap_ms > 0) {
        delay(gap_ms);
      }
    }
  }
}

int16_t NeuroStimDuino::calibrateThreshold(uint8_t channel) {
  // Start at minimum and increase until user feels it
  // This would be done interactively with serial commands
  // Returns the threshold current in microamps

  Serial.println("Threshold calibration - press 'y' when you feel stimulation");

  StimParams calibParams = {
    .current_ua = 500,  // Start at 500uA
    .pulse_width_us = 200,
    .frequency_hz = 20,
    .duration_ms = 500,
    .channel = channel,
    .biphasic = true
  };

  while (calibParams.current_ua <= MAX_CURRENT_UA) {
    Serial.print("Testing ");
    Serial.print(calibParams.current_ua);
    Serial.println("uA...");

    setParams(calibParams);
    startStim();
    delay(calibParams.duration_ms);
    stopStim();

    delay(500);  // Wait for user input

    if (Serial.available()) {
      char c = Serial.read();
      if (c == 'y' || c == 'Y') {
        Serial.print("Threshold found: ");
        Serial.print(calibParams.current_ua);
        Serial.println("uA");
        return calibParams.current_ua;
      }
    }

    // Increase by 500uA steps
    calibParams.current_ua += 500;
  }

  Serial.println("Threshold not found within safe limits");
  return -1;
}

bool NeuroStimDuino::isSafetyOK() {
  // Check all safety conditions
  if (!isConnected()) {
    _lastError = "Device disconnected";
    return false;
  }

  // Check for overlong stimulation
  if (_stimulating && millis() - _stimStartTime > MAX_STIM_DURATION_MS) {
    emergencyStop();
    _lastError = "Maximum stimulation duration exceeded";
    return false;
  }

  return true;
}

String NeuroStimDuino::getLastError() {
  return _lastError;
}

// I2C communication helpers
void NeuroStimDuino::writeRegister(uint8_t reg, uint8_t value) {
  Wire.beginTransmission(_address);
  Wire.write(reg);
  Wire.write(value);
  Wire.endTransmission();
}

void NeuroStimDuino::writeRegister16(uint8_t reg, int16_t value) {
  Wire.beginTransmission(_address);
  Wire.write(reg);
  Wire.write((value >> 8) & 0xFF);
  Wire.write(value & 0xFF);
  Wire.endTransmission();
}

uint8_t NeuroStimDuino::readRegister(uint8_t reg) {
  Wire.beginTransmission(_address);
  Wire.write(reg);
  Wire.endTransmission();
  Wire.requestFrom(_address, (uint8_t)1);
  return Wire.read();
}

int16_t NeuroStimDuino::readRegister16(uint8_t reg) {
  Wire.beginTransmission(_address);
  Wire.write(reg);
  Wire.endTransmission();
  Wire.requestFrom(_address, (uint8_t)2);
  int16_t value = Wire.read() << 8;
  value |= Wire.read();
  return value;
}

#endif // NEUROSTIMDUINO_H
