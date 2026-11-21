// Declaring pins used for ultrasonic sensor
const int TRIG_PIN = 9; // Pin to signal sensor to start measuring
const int ECHO_PIN = 10; // Signals high for entire duration of sounds path to an object and back

// The difference between the time from initiating the measure to receiving the return signal can be used to
// measure the distance to the object the sensor was pointed at.

// How many measurements are being stored
const int FILTER_SIZE = 3;

// Array storing the latest 3 measurements
float recentDistances[FILTER_SIZE];
int readingCount = 0; // Number of valid readings collected
int nextIndex = 0; // Which array position to overwrite next (the oldest recorded distance)

// Variables for tracking objects relative speed to user
const unsigned long SPEED_WINDOW_MS = 400; // Change in time between 2 positions used for calculating velocity

float previousDistance = 0.0f; // older filtered distance
unsigned long previousTime = 0; // when older distance was measured

bool hasPreviousMeasurement = false; // do we have an older distance stored?

float latestClosingSpeed = 0.0f;

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

    // Record new distance measure and update oldest index in array
    recentDistances[nextIndex] = distanceCm;
    nextIndex = (nextIndex + 1) % FILTER_SIZE;

    // If array is still in the process of filling, update progress
    if (readingCount < FILTER_SIZE){
      readingCount++;
    }

    // If the array is full of recent distances, report their median
    if (readingCount == FILTER_SIZE){
      float filteredDistance = medianOfThree(recentDistances[0], recentDistances[1], recentDistances[2]);

      unsigned long currentTime = millis();

      float closingSpeed = calculateClosingSpeed(filteredDistance, currentTime);

      Serial.print("Distance: ");
      Serial.print(filteredDistance);
      Serial.print("cm | Closing speed: ");
      Serial.print(closingSpeed);
      Serial.println(" cm/s");
    }
    
    // Waits 60 milliseconds before taking the next measurement
    delay(60);
  }
}

float medianOfThree(float a, float b, float c){
  // Order recent distances
  if (a > b){
    float temp = a;
    a = b;
    b = temp;
  }

  if (b > c){
    float temp = b;
    b = c;
    c = temp;
  }

  if (a > b){
    float temp = a;
    a = b;
    b = temp;
  }

  // Return the middle one
  return b;
}

// Positive speed for obstacle getting closer, negative if moving away
float calculateClosingSpeed(float currentDistance, unsigned long currentTime){
  
  //We can't calculate speed if this is the first distance measurement
  if(!hasPreviousMeasurement){
    previousDistance = currentDistance;
    previousTime = currentTime;
    hasPreviousMeasurement = true;
    return 0.0f;
  }

  unsigned long elapsedTime = currentTime - previousTime;

  // If 400ms haven't passed since previous measure, return 0
  if (elapsedTime < SPEED_WINDOW_MS){
    return latestClosingSpeed;
  }

  float elapsedSeconds = elapsedTime / 1000.0f;
  latestClosingSpeed = (previousDistance - currentDistance) / elapsedSeconds;
  previousDistance = currentDistance;
  previousTime = currentTime;

  return latestClosingSpeed;
}
