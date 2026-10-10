// RLLS four-probe quick calibration utility.
// Hardware: ESP32-DevKitC V4 / ESP32-WROOM-32 + 4 x DFRobot SEN0308.
// This sketch prints human-readable instructions and is NOT collector JSONL firmware.

#include <Arduino.h>

static const uint32_t BAUD_RATE = 115200;
static const uint8_t PROBE_COUNT = 4;
static const uint8_t ADC_SAMPLES_PER_READING = 16;
static const uint8_t CAPTURE_COUNT = 30;
static const uint16_t CAPTURE_PAUSE_MS = 100;
static const int SOIL_PINS[PROBE_COUNT] = {32, 33, 34, 35};

int dryRaw[PROBE_COUNT] = {0, 0, 0, 0};
int wetRaw[PROBE_COUNT] = {0, 0, 0, 0};
bool hasDry = false;
bool hasWet = false;
bool monitorEnabled = false;
uint32_t lastMonitorMs = 0;

int readAveragedAnalog(int pin) {
  uint32_t total = 0;
  for (uint8_t i = 0; i < ADC_SAMPLES_PER_READING; ++i) {
    total += analogRead(pin);
    delay(3);
  }
  return static_cast<int>(total / ADC_SAMPLES_PER_READING);
}

void sortValues(int values[], uint8_t count) {
  for (uint8_t i = 1; i < count; ++i) {
    const int value = values[i];
    int8_t j = static_cast<int8_t>(i) - 1;
    while (j >= 0 && values[j] > value) {
      values[j + 1] = values[j];
      --j;
    }
    values[j + 1] = value;
  }
}

int medianOf(int values[], uint8_t count) {
  sortValues(values, count);
  if (count % 2 == 1) return values[count / 2];
  return (values[count / 2 - 1] + values[count / 2]) / 2;
}

void printSnapshot() {
  Serial.print("RAW");
  for (uint8_t probe = 0; probe < PROBE_COUNT; ++probe) {
    Serial.print("  soil_0");
    Serial.print(probe + 1);
    Serial.print('=');
    Serial.print(readAveragedAnalog(SOIL_PINS[probe]));
  }
  Serial.println();
}

void captureEndpoint(const char *name, int destination[]) {
  int readings[PROBE_COUNT][CAPTURE_COUNT];
  Serial.print("\nCapturing ");
  Serial.print(name);
  Serial.print(" endpoint: ");
  Serial.print(CAPTURE_COUNT);
  Serial.println(" averaged cycles. Keep probes still...");

  for (uint8_t sample = 0; sample < CAPTURE_COUNT; ++sample) {
    for (uint8_t probe = 0; probe < PROBE_COUNT; ++probe) {
      readings[probe][sample] = readAveragedAnalog(SOIL_PINS[probe]);
    }
    Serial.print('.');
    delay(CAPTURE_PAUSE_MS);
  }
  Serial.println();

  for (uint8_t probe = 0; probe < PROBE_COUNT; ++probe) {
    destination[probe] = medianOf(readings[probe], CAPTURE_COUNT);
    const int minimum = readings[probe][0];
    const int maximum = readings[probe][CAPTURE_COUNT - 1];
    Serial.print(name);
    Serial.print(" soil_0");
    Serial.print(probe + 1);
    Serial.print(": median=");
    Serial.print(destination[probe]);
    Serial.print("  min=");
    Serial.print(minimum);
    Serial.print("  max=");
    Serial.print(maximum);
    Serial.print("  span=");
    Serial.println(maximum - minimum);
  }
}

void printArray(const char *name, const int values[]) {
  Serial.print("static const int ");
  Serial.print(name);
  Serial.print("[PROBE_COUNT] = {");
  for (uint8_t probe = 0; probe < PROBE_COUNT; ++probe) {
    if (probe > 0) Serial.print(", ");
    Serial.print(values[probe]);
  }
  Serial.println("};");
}

void printResult() {
  Serial.println("\n===== CALIBRATION RESULT =====");
  if (!hasDry) Serial.println("DRY endpoint has not been captured. Press d.");
  if (!hasWet) Serial.println("WET endpoint has not been captured. Press w.");
  if (!hasDry || !hasWet) return;

  printArray("DRY_RAW", dryRaw);
  printArray("WET_RAW", wetRaw);
  Serial.println("Endpoint gaps (absolute ADC counts):");
  for (uint8_t probe = 0; probe < PROBE_COUNT; ++probe) {
    Serial.print("soil_0");
    Serial.print(probe + 1);
    Serial.print(" gap=");
    Serial.println(abs(dryRaw[probe] - wetRaw[probe]));
  }
  Serial.println("Copy both arrays into esp32_irrigation_demo.ino after reviewing stability.");
  Serial.println("Values are RAM-only and are lost when the ESP32 restarts.");
}

void printHelp() {
  Serial.println("\nCommands (Serial Monitor, 115200 baud, any line ending):");
  Serial.println("  s  one raw snapshot");
  Serial.println("  m  toggle one-second raw monitor");
  Serial.println("  d  capture DRY endpoint for all four probes");
  Serial.println("  w  capture WET endpoint for all four probes");
  Serial.println("  p  print copy-ready DRY_RAW/WET_RAW arrays");
  Serial.println("  r  clear captured endpoints from RAM");
  Serial.println("  h  show this help");
}

void setup() {
  Serial.begin(BAUD_RATE);
  analogReadResolution(12);
  for (uint8_t probe = 0; probe < PROBE_COUNT; ++probe) {
    pinMode(SOIL_PINS[probe], INPUT);
    analogSetPinAttenuation(SOIL_PINS[probe], ADC_11db);
  }
  delay(500);
  Serial.println("RLLS SEN0308 four-probe quick calibration");
  Serial.println("Verify GPIO32/33/34/35 and 3V3/GND wiring before use.");
  printHelp();
}

void loop() {
  if (monitorEnabled && millis() - lastMonitorMs >= 1000) {
    lastMonitorMs = millis();
    printSnapshot();
  }

  if (!Serial.available()) return;
  const char command = static_cast<char>(tolower(Serial.read()));
  if (command == '\r' || command == '\n' || command == ' ') return;

  switch (command) {
    case 's': printSnapshot(); break;
    case 'm':
      monitorEnabled = !monitorEnabled;
      Serial.print("Raw monitor: ");
      Serial.println(monitorEnabled ? "ON" : "OFF");
      break;
    case 'd':
      monitorEnabled = false;
      captureEndpoint("DRY", dryRaw);
      hasDry = true;
      printResult();
      break;
    case 'w':
      monitorEnabled = false;
      captureEndpoint("WET", wetRaw);
      hasWet = true;
      printResult();
      break;
    case 'p': printResult(); break;
    case 'r':
      hasDry = false;
      hasWet = false;
      Serial.println("Captured endpoints cleared from RAM.");
      break;
    case 'h': printHelp(); break;
    default:
      Serial.print("Unknown command: ");
      Serial.println(command);
      printHelp();
      break;
  }
}
