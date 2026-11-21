// Declaring pins used for ultrasonic sensor
const int TRIG_PIN = 9; // Pin to signal sensor to start measuring
const int ECHO_PIN = 10; // Signals high for entire duration of sounds path to an object and back

// The difference between the time from initiating the measure to receiving the return signal can be used to
// measure the distance to the object the sensor was pointed at.

// Function runs once every time arduino starts or resets
void setup() {
  Serial.begin(9600); // starts serial communication between arduino and computer with agreed baud rate (communication speed)

  // Configure pins to receive or send electrical signals
  pinMode(TRIG_PIN, OUTPUT);
  pinMode(ECHO_PIN, INPUT);

  digitalWrite(TRIG_PIN, LOW); // Don't want to trigger a measurement at startup
}

// Function runs continuously, called automatically after setup()
// We use it to continuously measure distances until arduino is turned off
void loop() {
  // Reset trigger pin
  digitalWrite(TRIG_PIN, LOW); // Ensure trigger pin is low
  delayMicroseconds(2); // Wait 2 microseconds so trigger signal starts from clean low state

  // Send short trigger pulse to ultrasonic
  digitalWrite(TRIG_PIN, HIGH); // Switch to HIGH signal
  delayMicroseconds(10); // Hold high voltage
  digitalWrite(TRIG_PIN, LOW); // Bring back voltage to low

  // Measure echo duration, with a timeout
  unsigned long duration = pulseIn(ECHO_PIN, HIGH, 30000UL); // Measure how long return signal stays HIGH
  // Will return 0 if no pulse detected withing 30000UL

  // Handles missing measurement
  if (duration == 0){
    Serial.println("No valid echo");
  }
  // For a valid measurement, calculates distance
  else{
    // Speed of sound ~= 0.0343 cm/us, divide by 2 because the sound travelled there and back
    float distanceCm = duration * 0.0343f / 2.0f;
    Serial.print("Distance: ");
    Serial.print(distanceCm);
    Serial.println(" cm");

    // Waits 100 milliseconds before taking the next measurement
    delay(100);
  }
}
