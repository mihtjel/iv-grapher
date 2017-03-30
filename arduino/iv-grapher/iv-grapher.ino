/* SPI SETUP:
    SCLK pin 52
    MOSI pin 51
    CS   pin 53
*/

#include <SPI.h>

const int DACPIN = 43;
const int ADCPIN = 44;
const int VSCALE = 40;
const int ISCALE = 41;

const uint8_t dacconf = 0b01110000;
const uint8_t adcconf1 = 0b00001100;
const uint8_t adcconf2 = 0b00001101;

int data = 0;
int count = 0;

boolean highVoltage = true;
boolean highCurrent = false;

void inline readADC() {
    uint16_t recv;
    /* Output format:
       set current;voltage drop;actual current;high/low voltage;high/low current
       Currents and voltage is 0-4095
       high/low indicators are 0 or 1
    */
    digitalWrite(ADCPIN, LOW);
    SPI.transfer(adcconf1);
    recv = SPI.transfer16(0x0000);
    digitalWrite(ADCPIN, HIGH);
    Serial.print(data);
    Serial.print(";");
    Serial.print(recv&0x1FFF, DEC);
    digitalWrite(ADCPIN, LOW);
    SPI.transfer(adcconf2);
    recv = SPI.transfer16(0x0000);
    digitalWrite(ADCPIN, HIGH);
    Serial.print(";");
    Serial.print(recv&0x1FFF, DEC);
    Serial.print(";");
    Serial.print(highVoltage, DEC);
    Serial.print(";");
    Serial.print(highCurrent, DEC);
    // Newline at the end
    Serial.println("");
}

void setDAC(uint16_t value) {
      noInterrupts();
      digitalWrite(DACPIN, LOW);
      SPI.transfer((dacconf & 0xF0) | (0x0F & (value >> 8)));
      SPI.transfer(value & 0x00FF);
      digitalWrite(DACPIN, HIGH);
      interrupts();
}

void setup() {
  Serial.begin(14400);
  Serial.println("Setup");
  SPI.setClockDivider(SPI_CLOCK_DIV32);
  SPI.begin();

  pinMode(DACPIN, OUTPUT);
  pinMode(ADCPIN, OUTPUT);
  pinMode(VSCALE, OUTPUT);
  pinMode(ISCALE, OUTPUT);
  digitalWrite(DACPIN, HIGH);
  digitalWrite(ADCPIN, HIGH);
  digitalWrite(VSCALE, HIGH);  
  digitalWrite(ISCALE, LOW);

  digitalWrite(DACPIN, LOW);
  SPI.transfer((dacconf & 0xF0) | (0x0F & (data >> 8)));
  SPI.transfer(data & 0x00FF);
  digitalWrite(DACPIN, HIGH);

  noInterrupts();
  TCCR1A = 0;
  TCCR1B = 0;
  TCNT1 = 0;
  TCCR1B |= (1 << CS11);
  TIMSK1 |= (1 << TOIE1);
  interrupts();
  
  Serial.println("Setup done");
}

ISR(TIMER1_OVF_vect) {
  TCNT1 = 0;
  readADC();
}

void loop() {
  int in = Serial.read();
  if (in != -1) {
    if (in == '+') {
      data++;
    }
    if (in == '-') {
      data--;
    }
    if (in == 'v') {
      digitalWrite(VSCALE, LOW);
      highVoltage = false;
    }
    if (in == 'V') {
      digitalWrite(VSCALE, HIGH);
      highVoltage = true;
    }
    if (in == 'c') {
      digitalWrite(ISCALE, LOW);
      highCurrent = false;
    }
    if (in == 'C') {
      digitalWrite(ISCALE, HIGH);
      highCurrent = true;
    }
    if (in == 's' || in == 'S') {
      // Read set value
      boolean done = false;
      uint16_t inputdata = 0;
      while (!done) {
        while (!Serial.available());
        in = Serial.read();
        if (in == '\n') {
          done = true;
        } else if (in >= '0' && in <= '9') {
          inputdata = inputdata * 10;
          inputdata += (in - '0');
        } else {
          inputdata = data;
          done = true;
        }
      }
      if (inputdata < 4096) {
        // Valid input data
        data = inputdata; 
      }
    }
    setDAC(data);
  }
}

