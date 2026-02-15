/*
 * EMG Acquisition for Hand Project
 *
 * Hardware: Arduino Due + 4x BioAmp Candy sensors
 * Purpose: Read EMG signals from forearm muscles, extract features, send to PC
 *
 * Author: CC (Coalition Code)
 * Date: 2026-02-14
 *
 * Pin Configuration:
 *   A0 - Flexor digitorum superficialis (finger flexion)
 *   A1 - Extensor digitorum (finger extension)
 *   A2 - Flexor carpi radialis (wrist flexion)
 *   A3 - Extensor carpi radialis (wrist extension)
 *
 * Serial Protocol:
 *   Output: "EMG,ch0,ch1,ch2,ch3,mav0,mav1,mav2,mav3,timestamp\n"
 *   Input:  "STIM,channel,intensity,duration\n" (future)
 */

// ============================================================================
// CONFIGURATION
// ============================================================================

// Analog pins for EMG sensors
const int EMG_PINS[] = {A0, A1, A2, A3};
const int NUM_CHANNELS = 4;

// Sampling configuration
const int SAMPLE_RATE = 1000;  // Hz (1ms per sample)
const unsigned long SAMPLE_INTERVAL_US = 1000000 / SAMPLE_RATE;

// Feature extraction window
const int WINDOW_SIZE = 200;  // samples (200ms at 1kHz)
int sampleBuffer[NUM_CHANNELS][WINDOW_SIZE];
int bufferIndex = 0;
bool bufferFull = false;

// Moving Average Value (MAV) - key EMG feature
float mavValues[NUM_CHANNELS] = {0, 0, 0, 0};

// Timing
unsigned long lastSampleTime = 0;
unsigned long sampleCount = 0;

// Serial communication
const long SERIAL_BAUD = 115200;
bool streamingEnabled = true;

// ============================================================================
// SETUP
// ============================================================================

void setup() {
  // Initialize serial
  Serial.begin(SERIAL_BAUD);
  while (!Serial) {
    ; // Wait for serial port to connect (needed for native USB)
  }

  // Configure analog pins
  analogReadResolution(12);  // Arduino Due supports 12-bit ADC (0-4095)

  // Initialize buffer
  for (int ch = 0; ch < NUM_CHANNELS; ch++) {
    for (int i = 0; i < WINDOW_SIZE; i++) {
      sampleBuffer[ch][i] = 0;
    }
  }

  // Startup message
  Serial.println("# Hand Project EMG Acquisition");
  Serial.println("# Channels: 4 (A0-A3)");
  Serial.println("# Sample Rate: 1000 Hz");
  Serial.println("# Resolution: 12-bit");
  Serial.println("# Commands: START, STOP, STATUS, FEATURES");
  Serial.println("# Format: EMG,raw0,raw1,raw2,raw3,mav0,mav1,mav2,mav3,timestamp");
  Serial.println("READY");

  lastSampleTime = micros();
}

// ============================================================================
// MAIN LOOP
// ============================================================================

void loop() {
  unsigned long currentTime = micros();

  // Check for serial commands
  handleSerialCommands();

  // Sample at fixed rate
  if (currentTime - lastSampleTime >= SAMPLE_INTERVAL_US) {
    lastSampleTime = currentTime;

    // Read all channels
    int rawValues[NUM_CHANNELS];
    for (int ch = 0; ch < NUM_CHANNELS; ch++) {
      rawValues[ch] = analogRead(EMG_PINS[ch]);

      // Store in circular buffer
      sampleBuffer[ch][bufferIndex] = rawValues[ch];
    }

    // Update buffer index
    bufferIndex = (bufferIndex + 1) % WINDOW_SIZE;
    if (bufferIndex == 0) {
      bufferFull = true;
    }

    // Calculate features every sample (sliding window)
    if (bufferFull) {
      calculateMAV();
    }

    // Stream data if enabled
    if (streamingEnabled) {
      sendDataPacket(rawValues, currentTime);
    }

    sampleCount++;
  }
}

// ============================================================================
// FEATURE EXTRACTION
// ============================================================================

void calculateMAV() {
  // Mean Absolute Value - most reliable EMG amplitude feature
  // MAV = (1/N) * sum(|x[i] - baseline|)

  for (int ch = 0; ch < NUM_CHANNELS; ch++) {
    float sum = 0;
    int baseline = 2048;  // 12-bit midpoint (adjust during calibration)

    for (int i = 0; i < WINDOW_SIZE; i++) {
      sum += abs(sampleBuffer[ch][i] - baseline);
    }

    mavValues[ch] = sum / WINDOW_SIZE;
  }
}

// Calculate additional features for gesture recognition
void calculateAllFeatures(float* mav, float* zc, float* wl, float* ssc) {
  // Zero Crossings, Waveform Length, Slope Sign Changes
  // These are the classic Hudgins feature set for EMG

  for (int ch = 0; ch < NUM_CHANNELS; ch++) {
    int baseline = 2048;
    int threshold = 50;  // Noise threshold for zero crossing

    float mavSum = 0;
    int zcCount = 0;
    float wlSum = 0;
    int sscCount = 0;

    int prevSample = sampleBuffer[ch][0] - baseline;
    int prevDiff = 0;

    for (int i = 0; i < WINDOW_SIZE; i++) {
      int sample = sampleBuffer[ch][i] - baseline;

      // MAV
      mavSum += abs(sample);

      // Zero Crossings
      if (i > 0) {
        if ((prevSample > threshold && sample < -threshold) ||
            (prevSample < -threshold && sample > threshold)) {
          zcCount++;
        }

        // Waveform Length
        wlSum += abs(sample - prevSample);

        // Slope Sign Changes
        int diff = sample - prevSample;
        if (i > 1) {
          if ((prevDiff > threshold && diff < -threshold) ||
              (prevDiff < -threshold && diff > threshold)) {
            sscCount++;
          }
        }
        prevDiff = diff;
      }
      prevSample = sample;
    }

    mav[ch] = mavSum / WINDOW_SIZE;
    zc[ch] = (float)zcCount;
    wl[ch] = wlSum / WINDOW_SIZE;
    ssc[ch] = (float)sscCount;
  }
}

// ============================================================================
// SERIAL COMMUNICATION
// ============================================================================

void sendDataPacket(int* rawValues, unsigned long timestamp) {
  // Format: EMG,raw0,raw1,raw2,raw3,mav0,mav1,mav2,mav3,timestamp
  Serial.print("EMG,");

  // Raw values
  for (int ch = 0; ch < NUM_CHANNELS; ch++) {
    Serial.print(rawValues[ch]);
    Serial.print(",");
  }

  // MAV features
  for (int ch = 0; ch < NUM_CHANNELS; ch++) {
    Serial.print(mavValues[ch], 2);
    Serial.print(",");
  }

  // Timestamp (microseconds)
  Serial.println(timestamp);
}

void sendFullFeatures() {
  // Send complete feature set for gesture recognition
  float mav[NUM_CHANNELS], zc[NUM_CHANNELS], wl[NUM_CHANNELS], ssc[NUM_CHANNELS];
  calculateAllFeatures(mav, zc, wl, ssc);

  Serial.print("FEATURES,");

  // MAV
  for (int ch = 0; ch < NUM_CHANNELS; ch++) {
    Serial.print(mav[ch], 2);
    Serial.print(",");
  }

  // Zero Crossings
  for (int ch = 0; ch < NUM_CHANNELS; ch++) {
    Serial.print(zc[ch], 0);
    Serial.print(",");
  }

  // Waveform Length
  for (int ch = 0; ch < NUM_CHANNELS; ch++) {
    Serial.print(wl[ch], 2);
    Serial.print(",");
  }

  // Slope Sign Changes
  for (int ch = 0; ch < NUM_CHANNELS; ch++) {
    Serial.print(ssc[ch], 0);
    if (ch < NUM_CHANNELS - 1) Serial.print(",");
  }

  Serial.println();
}

void handleSerialCommands() {
  if (Serial.available() > 0) {
    String command = Serial.readStringUntil('\n');
    command.trim();
    command.toUpperCase();

    if (command == "START") {
      streamingEnabled = true;
      Serial.println("OK,STREAMING");
    }
    else if (command == "STOP") {
      streamingEnabled = false;
      Serial.println("OK,STOPPED");
    }
    else if (command == "STATUS") {
      Serial.print("STATUS,");
      Serial.print(streamingEnabled ? "STREAMING" : "STOPPED");
      Serial.print(",SAMPLES=");
      Serial.print(sampleCount);
      Serial.print(",BUFFER=");
      Serial.println(bufferFull ? "FULL" : "FILLING");
    }
    else if (command == "FEATURES") {
      // Send one full feature set
      if (bufferFull) {
        sendFullFeatures();
      } else {
        Serial.println("ERROR,BUFFER_NOT_FULL");
      }
    }
    else if (command == "PING") {
      Serial.println("PONG");
    }
    else if (command.startsWith("BASELINE")) {
      // Future: calibrate baseline per channel
      Serial.println("OK,BASELINE_SET");
    }
  }
}

// ============================================================================
// UTILITY FUNCTIONS
// ============================================================================

// LED feedback (Arduino Due has LED on pin 13)
void blinkStatus(int times, int delayMs) {
  pinMode(13, OUTPUT);
  for (int i = 0; i < times; i++) {
    digitalWrite(13, HIGH);
    delay(delayMs);
    digitalWrite(13, LOW);
    delay(delayMs);
  }
}
