Ultrasonic Distance Sensor

This module uses an HC-SR04 ultrasonic sensor connected to an ELEGOO UNO R3 (Arduino-compatible) to measure the distance to nearby objects AND now reports their speed.

The sensor sends an ultrasonic pulse and measures the time required for its echo to return. The Arduino calculates the approximate distance in centimeters and prints the result through serial communication. It also stores 1 older distance measure every 400ms to calculate speed.

This is an initial hardware prototyme. The distance measurment functionality will later be integrated into the Raspberry Pi 5 running QNX. The speed calculation must be updated so it updates on a rolling basis, not every 400ms. The distances and speeds will also be used to categorize readings into various warning states.

Wiring:

VCC - 5V
TRIG - D9
ECHO - D10
GND - GND

Note: The Arduino UNO uses 5V logic. If connecting the HC-SR04 directly to a Raspberry Pi later, the ECHO signal must be reduced to a Pi-safe 3.3V level

Running the Program

Open ultrasonic.ino in Arduino IDE.

Connect the Arduino UNO to your computer using USB.

Select Tools → Board → Arduino Uno.

Select the appropriate serial port.

Upload the sketch.

Open Tools → Serial Monitor.

Set the baud rate to 9600.