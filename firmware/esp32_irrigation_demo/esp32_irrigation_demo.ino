// RLLS low-cost irrigation demo — four SEN0308 JSON Lines producer.
// Current hardware: ESP32-DevKitC V4 / ESP32-WROOM-32 + 4 x SEN0308.
// Bench programming/collection uses PC USB. Standalone operation may use a
// regulated 5 V solar-manager output, but never connect both power sources
// unless the power path has been explicitly isolated and verified.
// USB Serial carries data only. Do not print ordinary debug text to Serial.
// Use ../esp32_soil_calibration/esp32_soil_calibration.ino to measure endpoints.

#include <Arduino.h>
#include <FS.h>
#include <LittleFS.h>
#include <Preferences.h>

static const uint32_t BAUD_RATE = 115200;
static const uint32_t SAMPLE_INTERVAL_MS = 1000;
// The USB stream remains one sample/second. Flash logging is deliberately
// slower to reduce flash wear and file growth. Change only after estimating
// the required retention time on the selected partition scheme.
static const uint32_t LOCAL_LOG_INTERVAL_MS = 60000;
static const size_t LOCAL_LOG_MAX_BYTES = 1024UL * 1024UL;
static const size_t LOCAL_LOG_RESERVE_BYTES = 64UL * 1024UL;
static const char *LOCAL_LOG_PATH = "/soil_log.jsonl";
static const bool LOCAL_LOG_DEFAULT_ENABLED = true;
static const uint8_t PROBE_COUNT = 4;
static const uint8_t ADC_SAMPLES = 16;
static const bool USE_SIMULATED_VALUES = false;

// Keep all four true for the final installation. For first-probe bring-up use:
// {true, false, false, false}. Disabled probes are emitted as JSON null with
// status "disabled"; missing values must never be represented as zero.
static const bool PROBE_ENABLED[PROBE_COUNT] = {true, true, true, true};

// Current test wiring: soil_01/02/03 use ADC1; soil_04 uses GPIO26 (ADC2).
// ADC2 conflicts with Wi-Fi on classic ESP32. This USB/Serial firmware does
// not enable Wi-Fi; revisit soil_04 wiring before adding ESP32-side Wi-Fi.
// Always verify the silkscreen/pinout of the delivered board before wiring.
static const int SOIL_PINS[PROBE_COUNT] = {32, 33, 34, 26};

// PROVISIONAL bench calibration captured on 2026-10-18. DRY_RAW is the
// measured dry reference and WET_RAW is the DFRobot water endpoint. Repeat
// calibration after the final power wiring, insertion depth and soil protocol
// are fixed; do not copy one probe's endpoints to another probe.
static const int DRY_RAW[PROBE_COUNT] = {1907, 959, 408, 740};
static const int WET_RAW[PROBE_COUNT] = {0, 0, 0, 0};

uint32_t lastSampleMs = 0;
uint32_t lastLocalLogMs = 0;
uint32_t bootId = 0;
bool firstLocalRecord = true;
bool localLogEnabled = LOCAL_LOG_DEFAULT_ENABLED;
bool localStorageReady = false;
String serialCommand;

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
  if (!PROBE_ENABLED[index]) {
    raw = 0;  // Internal placeholder only; the JSON writer emits null below.
    pct = NAN;
    status = "disabled";
    return;
  }
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

void printNullableFloatTo(Print &output, float value, uint8_t decimals = 2) {
  if (isnan(value)) output.print("null"); else output.print(value, decimals);
}

void writeDataRecord(
  Print &output,
  uint32_t now,
  const int raw[PROBE_COUNT],
  const float pct[PROBE_COUNT],
  const char *const status[PROBE_COUNT]
) {
  output.print("{\"schema_version\":\"2.0.0-demo\",\"device_ms\":");
  output.print(now);
  for (uint8_t i = 0; i < PROBE_COUNT; ++i) {
    output.print(",\"soil_"); output.print(i + 1); output.print("_raw\":");
    if (PROBE_ENABLED[i]) output.print(raw[i]); else output.print("null");
    output.print(",\"soil_"); output.print(i + 1); output.print("_moisture_pct\":");
    printNullableFloatTo(output, pct[i]);
    output.print(",\"soil_"); output.print(i + 1); output.print("_status\":\"");
    output.print(status[i]); output.print("\"");
  }
  output.print(",\"simulated\":");
  output.print(USE_SIMULATED_VALUES ? "true" : "false");
  output.println("}");
}

size_t localLogLimitBytes() {
  if (!localStorageReady) return 0;
  const size_t total = LittleFS.totalBytes();
  if (total <= LOCAL_LOG_RESERVE_BYTES) return 0;
  return min(LOCAL_LOG_MAX_BYTES, total - LOCAL_LOG_RESERVE_BYTES);
}

void appendBootMarker() {
  if (!localStorageReady) return;
  File file = LittleFS.open(LOCAL_LOG_PATH, FILE_APPEND);
  if (!file) return;
  file.print("#RLLS_BOOT id=");
  file.print(bootId, HEX);
  file.println(" clock=unsynced");
  file.close();
}

void startLocalStorage() {
  Preferences preferences;
  preferences.begin("rlls-log", false);
  const bool formattedBefore = preferences.getBool("fs-ready", false);

  // First try a non-destructive mount. A brand-new, unformatted filesystem is
  // formatted once. After that marker is set, a mount failure never triggers
  // automatic formatting, protecting an existing log from silent deletion.
  localStorageReady = LittleFS.begin(false);
  if (!localStorageReady && !formattedBefore) {
    localStorageReady = LittleFS.begin(true);
    if (localStorageReady) preferences.putBool("fs-ready", true);
  } else if (localStorageReady && !formattedBefore) {
    preferences.putBool("fs-ready", true);
  }
  preferences.end();

  if (localStorageReady) appendBootMarker();
}

void appendLocalRecord(
  uint32_t now,
  const int raw[PROBE_COUNT],
  const float pct[PROBE_COUNT],
  const char *const status[PROBE_COUNT]
) {
  if (!localLogEnabled || !localStorageReady) return;
  File file = LittleFS.open(LOCAL_LOG_PATH, FILE_APPEND);
  if (!file) return;
  const size_t limit = localLogLimitBytes();
  if (limit == 0 || file.size() >= limit) {
    file.close();
    localLogEnabled = false;  // Stop; never overwrite old measurements.
    return;
  }
  writeDataRecord(file, now, raw, pct, status);
  file.flush();
  file.close();
}

void printLogStatus() {
  size_t bytes = 0;
  if (localStorageReady && LittleFS.exists(LOCAL_LOG_PATH)) {
    File file = LittleFS.open(LOCAL_LOG_PATH, FILE_READ);
    if (file) {
      bytes = file.size();
      file.close();
    }
  }
  Serial.print("#RLLS_LOG_STATUS mounted=");
  Serial.print(localStorageReady ? 1 : 0);
  Serial.print(" enabled=");
  Serial.print(localLogEnabled ? 1 : 0);
  Serial.print(" bytes=");
  Serial.print(bytes);
  Serial.print(" limit_bytes=");
  Serial.print(localLogLimitBytes());
  Serial.print(" interval_ms=");
  Serial.print(LOCAL_LOG_INTERVAL_MS);
  Serial.println(" clock=unsynced");
}

void dumpLocalLog() {
  if (!localStorageReady) {
    Serial.println("#RLLS_LOG_ERROR storage_not_mounted");
    return;
  }
  File file = LittleFS.open(LOCAL_LOG_PATH, FILE_READ);
  if (!file) {
    Serial.println("#RLLS_LOG_BEGIN bytes=0");
    Serial.println("#RLLS_LOG_END");
    return;
  }
  Serial.print("#RLLS_LOG_BEGIN bytes=");
  Serial.println(file.size());
  uint8_t buffer[256];
  while (file.available()) {
    const size_t count = file.read(buffer, sizeof(buffer));
    Serial.write(buffer, count);
  }
  file.close();
  // Keep the end marker on its own line even if power loss left the final
  // stored record without a newline. The downloader will then reject that
  // incomplete record instead of silently merging it with the marker.
  Serial.println();
  Serial.println("#RLLS_LOG_END");
}

void clearLocalLog() {
  if (!localStorageReady) {
    Serial.println("#RLLS_LOG_ERROR storage_not_mounted");
    return;
  }
  const bool removed = !LittleFS.exists(LOCAL_LOG_PATH) || LittleFS.remove(LOCAL_LOG_PATH);
  if (removed) {
    localLogEnabled = LOCAL_LOG_DEFAULT_ENABLED;
    appendBootMarker();
    Serial.println("#RLLS_LOG_CLEARED");
  } else {
    Serial.println("#RLLS_LOG_ERROR clear_failed");
  }
}

void handleSerialCommand(const String &input) {
  String command = input;
  command.trim();
  command.toUpperCase();
  if (command == "LOG STATUS") {
    printLogStatus();
  } else if (command == "LOG DUMP") {
    dumpLocalLog();
  } else if (command == "LOG ON") {
    localLogEnabled = localStorageReady;
    Serial.println(localLogEnabled ? "#RLLS_LOG_ON" : "#RLLS_LOG_ERROR storage_not_mounted");
  } else if (command == "LOG OFF") {
    localLogEnabled = false;
    Serial.println("#RLLS_LOG_OFF");
  } else if (command == "LOG CLEAR") {
    clearLocalLog();
  } else if (command.length() > 0) {
    Serial.println("#RLLS_LOG_ERROR unknown_command");
  }
}

void readSerialCommands() {
  while (Serial.available()) {
    const char incoming = static_cast<char>(Serial.read());
    if (incoming == '\n' || incoming == '\r') {
      if (serialCommand.length() > 0) {
        handleSerialCommand(serialCommand);
        serialCommand = "";
      }
    } else if (serialCommand.length() < 64) {
      serialCommand += incoming;
    } else {
      serialCommand = "";
    }
  }
}

void setup() {
  Serial.begin(BAUD_RATE);
  bootId = esp_random();
  analogReadResolution(12);
  for (uint8_t i = 0; i < PROBE_COUNT; ++i) {
    pinMode(SOIL_PINS[i], INPUT);
    // SEN0308 output is specified up to about 2.9 V. Verify this attenuation
    // setting with the installed Arduino-ESP32 package and delivered board.
    analogSetPinAttenuation(SOIL_PINS[i], ADC_11db);
  }
  startLocalStorage();
}

void loop() {
  readSerialCommands();
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
  writeDataRecord(Serial, now, raw, pct, status);

  if (firstLocalRecord || now - lastLocalLogMs >= LOCAL_LOG_INTERVAL_MS) {
    appendLocalRecord(now, raw, pct, status);
    firstLocalRecord = false;
    lastLocalLogMs = now;
  }
}
