#include <Wire.h>
#include <LiquidCrystal_I2C.h>
#include <DHT.h>

// ── Configuration ──────────────────────────────────────────
#define DHT_PIN     2
#define DHT_TYPE    DHT11
#define LCD_ADDRESS 0x27   // Try 0x3F if display stays blank
#define CANDIDATE   "Kayiranga Simbi Kelia"   // ← change this

// ── Objects ────────────────────────────────────────────────
LiquidCrystal_I2C lcd(LCD_ADDRESS, 16, 2);
DHT dht(DHT_PIN, DHT_TYPE);

// ── Scroll state ───────────────────────────────────────────
String candidate = CANDIDATE;
int scrollPos    = 0;
unsigned long lastScroll = 0;
unsigned long lastRead   = 0;
float temperature        = 0.0;

// ── Setup ──────────────────────────────────────────────────
void setup() {
  Serial.begin(9600);

  lcd.init();
  lcd.backlight();
  lcd.clear();

  dht.begin();

  delay(2000);  // DHT11 needs settling time
}

// ── Helpers ────────────────────────────────────────────────

// Reads temperature with retry; returns NaN on failure
float readTemperature() {
  float t = dht.readTemperature();
  if (isnan(t)) {
    delay(500);
    t = dht.readTemperature();
  }
  return t;
}

// Displays a 16-char window of the candidate name, scrolling
void scrollName() {
  String padded = candidate + "                "; // 16 trailing spaces
  String window = padded.substring(scrollPos, scrollPos + 16);
  lcd.setCursor(0, 0);
  lcd.print(window);

  scrollPos++;
  if (scrollPos > (int)candidate.length()) scrollPos = 0;
}

// ── Main loop ──────────────────────────────────────────────
void loop() {
  unsigned long now = millis();

  // Read temperature every 2 seconds
  if (now - lastRead >= 2000) {
    lastRead = now;
    float t = readTemperature();

    if (!isnan(t)) {
      temperature = t;

      // Send over Serial
      Serial.print("TEMP:");
      Serial.println(temperature, 1);  // e.g. "TEMP:24.5"

      // Update row 2
      lcd.setCursor(0, 1);
      lcd.print("Temp: ");
      lcd.print(temperature, 1);
      lcd.print((char)223);  // degree symbol
      lcd.print("C   ");     // trailing spaces clear old chars
    } else {
      Serial.println("TEMP:ERR");
      lcd.setCursor(0, 1);
      lcd.print("Sensor error    ");
    }
  }

  // Scroll name every 350 ms (only if name > 16 chars)
  if (candidate.length() > 16) {
    if (now - lastScroll >= 350) {
      lastScroll = now;
      scrollName();
    }
  } else {
    // Name fits — print it once, no scrolling
    lcd.setCursor(0, 0);
    lcd.print(candidate);
    // Pad to 16 chars
    for (int i = candidate.length(); i < 16; i++) lcd.print(' ');
  }
}