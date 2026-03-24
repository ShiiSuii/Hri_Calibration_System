#include <Wire.h>
#include <Adafruit_PWMServoDriver.h>

Adafruit_PWMServoDriver pwm = Adafruit_PWMServoDriver(0x43);

#define SERVO_FREQ 50
#define AUTO_OFF_TIMEOUT 1000

unsigned long lastCommandTime[16];
bool isEnergized[16];

void setup() {
  Serial.begin(115200);
  Wire.begin(); // Needed for I2C Scan
  pwm.begin();
  pwm.setOscillatorFrequency(27000000);
  pwm.setPWMFreq(SERVO_FREQ);
  
  for(int i=0; i<16; i++) {
    lastCommandTime[i] = 0;
    isEnergized[i] = false;
    pwm.setPWM(i, 0, 4096);
  }
}

void loop() {
  static char buffer[32];
  static int pos = 0;
  
  while(Serial.available() > 0) {
    char c = Serial.read();
    if (c == '\n' || c == '\r') {
      if (pos > 0) {
        buffer[pos] = '\0';
        
        if (buffer[0] == 'S') {
          // I2C Scan command
          Serial.print("I2C_SCAN:");
          int count = 0;
          for(byte address = 1; address < 127; address++ ) {
            Wire.beginTransmission(address);
            byte error = Wire.endTransmission();
            if (error == 0) {
              Serial.print(" 0x");
              if (address < 16) Serial.print("0");
              Serial.print(address, HEX);
              count++;
            }
          }
          if (count == 0) Serial.print(" NONE");
          Serial.println();
        } else {
          int channel = -1;
          int pulse = -1;
          if (sscanf(buffer, "C%d P%d", &channel, &pulse) == 2) {
            if (channel >= 0 && channel <= 15) {
              if (pulse == 0) {
                pwm.setPWM(channel, 0, 4096);
                isEnergized[channel] = false;
              } else {
                pwm.setPWM(channel, 0, pulse);
                isEnergized[channel] = true;
              }
              lastCommandTime[channel] = millis();
            }
          }
        }
        pos = 0;
      }
    } else {
      if (pos < 31) {
        buffer[pos++] = c;
      }
    }
  }

  unsigned long currentMillis = millis();
  for (int i = 0; i < 16; i++) {
    if (isEnergized[i]) {
      if (currentMillis - lastCommandTime[i] > AUTO_OFF_TIMEOUT) {
        pwm.setPWM(i, 0, 4096);
        isEnergized[i] = false;
      }
    }
  }
}
