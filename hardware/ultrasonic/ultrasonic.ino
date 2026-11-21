// Declaring pins used for ultrasonic sensor
const int TRIG_PIN = 9; // Pin to signal sensor to start measuring
const int ECHO_PIN = 10; // Stays HIGH for the duration of the sound's round trip to an object and back

// The duration of the ECHO pulse can be used to calculate the distance to an object,
// since the speed of sound is approximately known.

// How many measurements are being stored for median filtering
const int FILTER_SIZE = 3;

// Array storing the latest 3 raw distance measurements
float recentDistances[FILTER_SIZE];
int readingCount = 0; // Number of valid readings collected (up to FILTER_SIZE)
int nextIndex = 0; // Which array position to overwrite next (the oldest recorded distance)


// Variables for tracking an object's speed relative to the sensor
const int WINDOW_SIZE = 7; // Number of filtered distance measurements used for speed estimation

// Arrays storing the latest 7 filtered distances and the times they were measured
float distanceHistory[WINDOW_SIZE];
unsigned long timeHistory[WINDOW_SIZE];

int historyCount = 0; // Number of measurements currently stored (up to WINDOW_SIZE)
int historyIndex = 0; // Which array position to overwrite next (the oldest measurement)

// We calculate closing speed using the oldest and newest measurements in this rolling window.
// With a new measurement approximately every 60 ms, a full window covers about 360 ms.
// Unlike the previous implementation, speed is recalculated after EVERY new measurement.


// Variables controlling how frequently the sensor takes measurements
const unsigned long SAMPLE_INTERVAL = 60; // Minimum time between the starts of measurements, in milliseconds
unsigned long lastSampleTime = 0; // Time when the previous measurement started


// Function runs once every time Arduino starts or resets
void setup() {
  Serial.begin(9600); // Starts serial communication between Arduino and computer with agreed baud rate (communication speed)

  // Configure pins to receive or send electrical signals
  pinMode(TRIG_PIN, OUTPUT);
  pinMode(ECHO_PIN, INPUT);

  digitalWrite(TRIG_PIN, LOW); // Don't want to trigger a measurement at startup
}


// Function runs continuously, called automatically after setup()
// We use it to continuously measure distances until Arduino is turned off
void loop() {
  unsigned long currentTime = millis(); // Number of milliseconds since Arduino started running

  // Only take a new measurement if at least 60 ms have passed since the previous one started
  if (currentTime - lastSampleTime < SAMPLE_INTERVAL) {
    return; // Skip this iteration of loop(), but Arduino will automatically call it again
  }

  lastSampleTime = currentTime;

  // Reset trigger pin
  digitalWrite(TRIG_PIN, LOW); // Ensure trigger pin is LOW
  delayMicroseconds(2); // Wait 2 microseconds so trigger signal starts from a clean LOW state

  // Send short trigger pulse to ultrasonic sensor
  digitalWrite(TRIG_PIN, HIGH); // Switch to HIGH signal
  delayMicroseconds(10); // Hold HIGH for 10 microseconds
  digitalWrite(TRIG_PIN, LOW); // Bring signal back to LOW

  // Measure echo duration, with a timeout
  unsigned long duration = pulseIn(ECHO_PIN, HIGH, 25000UL); // Measure how long the ECHO signal stays HIGH
  // Returns 0 if a complete HIGH pulse is not detected within the timeout
  // 25000 microseconds = 25 milliseconds

  // Handle missing measurement
  if (duration == 0) {
    Serial.println("No valid echo");

    // Clear measurement histories so we don't calculate speed using outdated measurements
    readingCount = 0;
    nextIndex = 0;
    historyCount = 0;
    historyIndex = 0;

    return;
  }

  // For a valid measurement, calculate distance
  // Speed of sound ~= 0.0343 cm/us, divide by 2 because the sound travelled there and back
  float distanceCm = duration * 0.0343f / 2.0f;

  // Record new raw distance measurement and update oldest index in array
  recentDistances[nextIndex] = distanceCm;
  nextIndex = (nextIndex + 1) % FILTER_SIZE;

  // If array is still in the process of filling, update progress
  if (readingCount < FILTER_SIZE) {
    readingCount++;
  }

  // If the array is full of recent distances, calculate their median
  if (readingCount == FILTER_SIZE) {
    float filteredDistance = medianOfThree(
      recentDistances[0],
      recentDistances[1],
      recentDistances[2]
    );

    // Record the filtered distance and its timestamp in the rolling speed window
    addMeasurement(filteredDistance, millis());

    // Calculate closing speed using the oldest and newest measurements in the window
    float closingSpeed = calculateClosingSpeed();

    Serial.print("Distance: ");
    Serial.print(filteredDistance, 2);
    Serial.print(" cm | Closing speed: ");
    Serial.print(closingSpeed, 2);
    Serial.println(" cm/s");
  }
}


// Function returns the median (middle value) of 3 numbers
float medianOfThree(float a, float b, float c) {
  // Order recent distances from smallest to largest
  if (a > b) {
    float temp = a;
    a = b;
    b = temp;
  }

  if (b > c) {
    float temp = b;
    b = c;
    c = temp;
  }

  if (a > b) {
    float temp = a;
    a = b;
    b = temp;
  }

  // Return the middle one
  return b;
}


// Function adds a new filtered distance and its timestamp to the rolling history
void addMeasurement(float distance, unsigned long timeMs) {

  // Store the new measurement in the oldest available position
  distanceHistory[historyIndex] = distance;
  timeHistory[historyIndex] = timeMs;

  // Move to the next position, wrapping around to 0 when we reach WINDOW_SIZE
  historyIndex = (historyIndex + 1) % WINDOW_SIZE;

  // If the array is still in the process of filling, update progress
  if (historyCount < WINDOW_SIZE) {
    historyCount++;
  }
}


// Positive speed means the object is getting closer to the sensor;
// negative speed means the object is moving farther away.
// This measures relative closing speed, not necessarily the object's actual speed.
float calculateClosingSpeed() {

  // We can't calculate speed with fewer than 2 distance measurements
  if (historyCount < 2) {
    return 0.0f;
  }

  // Find the index of the newest measurement
  // historyIndex points to the NEXT position to overwrite, so subtract 1
  int newestIndex = (historyIndex + WINDOW_SIZE - 1) % WINDOW_SIZE;

  int oldestIndex;

  // If the array isn't full yet, the oldest measurement is still at index 0
  if (historyCount < WINDOW_SIZE) {
    oldestIndex = 0;
  }
  else {
    // Once full, historyIndex points to the oldest measurement
    oldestIndex = historyIndex;
  }

  // Calculate change in distance between oldest and newest measurements
  // Subtract newest from oldest so approaching objects produce positive speed
  float distanceChange =
    distanceHistory[oldestIndex] - distanceHistory[newestIndex];

  // Calculate elapsed time between the two measurements, in milliseconds
  unsigned long elapsedTime =
    timeHistory[newestIndex] - timeHistory[oldestIndex];

  // Avoid division by zero if both measurements have the same timestamp
  if (elapsedTime == 0) {
    return 0.0f;
  }

  // Convert milliseconds to seconds and calculate closing speed in cm/s
  float elapsedSeconds = elapsedTime / 1000.0f;
  float closingSpeed = distanceChange / elapsedSeconds;

  return closingSpeed;
}
