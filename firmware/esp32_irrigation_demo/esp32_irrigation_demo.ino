// RLLS low-cost irrigation demo — four SEN0308 JSON Lines producer.
// Final hardware: ESP32-DevKitC V4 / ESP32-WROOM-32 + 4 x SEN0308.
// USB Serial carries data only. Do not print ordinary debug text to Serial.
// Use ../esp32_soil_calibration/esp32_soil_calibration.ino to measure endpoints.

#include <Arduino.h>

static const uint32_t BAUD_RATE = 115200;
static const uint32_t SAMPLE_INTERVAL_MS = 1000;
static const uint8_t PROBE_COUNT = 4;
static const uint8_t ADC_SAMPLES = 16;
static const bool USE_SIMULATED_VALUES = true;

// ADC1 inputs. Verify the silkscreen/pinout of the delivered board before wiring.
static const int SOIL_PINS[PROBE_COUNT] = {32, 33, 34, 35};

// PROVISIONAL placeholders. Replace every pair with that probe's measured
// endpoints; do not copy one probe's calibration to the other probes.
static const int DRY_RAW[PROBE_COUNT] = {3200, 3200, 3200, 3200};
static const int WET_RAW[PROBE_COUNT] = {1400, 1400, 1400, 1400};

uint32_t lastSampleMs = 0;

int readAveragedAnalog(int pin, uint8_t samples = ADC_SAMPLES) {
  uint32_t total = 0;
  for (uint8_t i = 0; i < samples; ++i) {
    total += analogRead(pin);
    delay(3);
  }
  return static_cast<int>(total / samples);
}

float soilPercentFromRaw(uint8_t index, int raw) {
  const int dry = DRY_RAW[index];
  const int wet = WET_RAW[index];
  if (dry == wet) return NAN;
  const float pct = 100.0f * (dry - raw) / float(dry - wet);
  return constrain(pct, 0.0f, 100.0f);
}

void readSoilProbe(uint8_t index, int &raw, float &pct, const char *&status) {
  if (USE_SIMULATED_VALUES) {
    raw = 2350 + int(index * 35) + int((millis() / 1000) % 20);
    pct = soilPercentFromRaw(index, raw);
    status = "simulated";
    return;
  }
  raw = readAveragedAnalog(SOIL_PINS[index]);
  pct = soilPercentFromRaw(index, raw);
  status = isnan(pct) ? "read_error" : "ok";
}

void printNullableFloat(float value, uint8_t decimals = 2) {
  if (isnan(value)) Serial.print("null"); else Serial.print(value, decimals);
}

void setup() {
  Serial.begin(BAUD_RATE);
  analogReadResolution(12);
  for (uint8_t i = 0; i < PROBE_COUNT; ++i) {
    pinMode(SOIL_PINS[i], INPUT);
    // SEN0308 output is specified up to about 2.9 V. Verify this attenuation
    // setting with the installed Arduino-ESP32 package and delivered board.
    analogSetPinAttenuation(SOIL_PINS[i], ADC_11db);
  }
}

void loop() {
  const uint32_t now = millis();
  if (now - lastSampleMs < SAMPLE_INTERVAL_MS) return;
  lastSampleMs = now;

  int raw[PROBE_COUNT] = {0, 0, 0, 0};
  float pct[PROBE_COUNT] = {NAN, NAN, NAN, NAN};
  const char *status[PROBE_COUNT];
  for (uint8_t i = 0; i < PROBE_COUNT; ++i) {
    readSoilProbe(i, raw[i], pct[i], status[i]);
  }

  // One JSON object is one four-probe sample cycle. Weather is added later.
  Serial.print("{\"schema_version\":\"2.0.0-demo\",\"device_ms\":");
  Serial.print(now);
  for (uint8_t i = 0; i < PROBE_COUNT; ++i) {
    Serial.print(",\"soil_"); Serial.print(i + 1); Serial.print("_raw\":");
    Serial.print(raw[i]);
    Serial.print(",\"soil_"); Serial.print(i + 1); Serial.print("_moisture_pct\":");
    printNullableFloat(pct[i]);
    Serial.print(",\"soil_"); Serial.print(i + 1); Serial.print("_status\":\"");
    Serial.print(status[i]); Serial.print("\"");
  }
  Serial.print(",\"simulated\":");
  Serial.print(USE_SIMULATED_VALUES ? "true" : "false");
  Serial.println("}");
}
