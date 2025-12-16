/*
 * Piezo Sensor Pressure Detection Module
 * Part of Robotic Arm Feedback System
 * 
 * This sketch reads analog values from a piezo sensor and sends
 * pressure readings over serial communication.
 * 
 * Wiring:
 * - Piezo sensor positive lead -> A0
 * - Piezo sensor negative lead -> GND
 * - 1M ohm resistor in parallel with the piezo sensor (recommended)
 */

const int PIEZO_PIN = A0;           // Analog pin connected to piezo sensor
const int SAMPLE_RATE_MS = 100;     // Sampling rate in milliseconds (0.1 seconds)
const int THRESHOLD = 10;           // Minimum value to register as pressure
const int CALIBRATION_SAMPLES = 50; // Number of samples for baseline calibration

// Calibration variables
int baselineValue = 0;
bool isCalibrated = false;

// Moving average filter
const int FILTER_SIZE = 5;
int filterBuffer[FILTER_SIZE];
int filterIndex = 0;

void setup() {
  Serial.begin(115200);
  
  // Wait for serial connection
  while (!Serial) {
    delay(10);
  }
  
  Serial.println("PIEZO_SENSOR_INIT");
  Serial.println("Calibrating baseline... Keep sensor still.");
  
  // Calibrate baseline
  calibrateBaseline();
  
  Serial.print("Baseline calibrated: ");
  Serial.println(baselineValue);
  Serial.println("READY");
}

void loop() {
  // Read raw sensor value
  int rawValue = analogRead(PIEZO_PIN);
  
  // Apply moving average filter
  int filteredValue = applyFilter(rawValue);
  
  // Calculate pressure relative to baseline
  int pressureValue = filteredValue - baselineValue;
  
  // Clamp negative values to 0
  if (pressureValue < 0) {
    pressureValue = 0;
  }
  
  // Calculate pressure percentage (0-100%)
  // Arduino analog read gives 0-1023, so max pressure diff is ~1023
  float pressurePercent = (pressureValue / 1023.0) * 100.0;
  
  // Determine pressure level category
  String pressureLevel = getPressureLevel(pressurePercent);
  
  // Send data in JSON-like format for easy parsing
  Serial.print("{\"raw\":");
  Serial.print(rawValue);
  Serial.print(",\"filtered\":");
  Serial.print(filteredValue);
  Serial.print(",\"pressure\":");
  Serial.print(pressureValue);
  Serial.print(",\"percent\":");
  Serial.print(pressurePercent, 2);
  Serial.print(",\"level\":\"");
  Serial.print(pressureLevel);
  Serial.print("\",\"timestamp\":");
  Serial.print(millis());
  Serial.println("}");
  
  delay(SAMPLE_RATE_MS);
}

void calibrateBaseline() {
  long sum = 0;
  
  for (int i = 0; i < CALIBRATION_SAMPLES; i++) {
    sum += analogRead(PIEZO_PIN);
    delay(5);
  }
  
  baselineValue = sum / CALIBRATION_SAMPLES;
  
  // Initialize filter buffer with baseline
  for (int i = 0; i < FILTER_SIZE; i++) {
    filterBuffer[i] = baselineValue;
  }
  
  isCalibrated = true;
}

int applyFilter(int newValue) {
  filterBuffer[filterIndex] = newValue;
  filterIndex = (filterIndex + 1) % FILTER_SIZE;
  
  long sum = 0;
  for (int i = 0; i < FILTER_SIZE; i++) {
    sum += filterBuffer[i];
  }
  
  return sum / FILTER_SIZE;
}

String getPressureLevel(float percent) {
  if (percent < 5.0) {
    return "NONE";
  } else if (percent < 20.0) {
    return "LIGHT";
  } else if (percent < 50.0) {
    return "MODERATE";
  } else if (percent < 80.0) {
    return "HIGH";
  } else {
    return "CRITICAL";
  }
}

// Command handler for recalibration via serial
void serialEvent() {
  while (Serial.available()) {
    String command = Serial.readStringUntil('\n');
    command.trim();
    
    if (command == "CALIBRATE") {
      Serial.println("Recalibrating...");
      calibrateBaseline();
      Serial.print("New baseline: ");
      Serial.println(baselineValue);
      Serial.println("CALIBRATION_COMPLETE");
    } else if (command == "STATUS") {
      Serial.print("STATUS:{\"baseline\":");
      Serial.print(baselineValue);
      Serial.print(",\"calibrated\":");
      Serial.print(isCalibrated ? "true" : "false");
      Serial.println("}");
    }
  }
}

