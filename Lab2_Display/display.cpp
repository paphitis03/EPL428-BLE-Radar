#include "display.h"
#include "utilities.h"
#include <Wire.h>
// Use the bus pins initialized by initBoard(), as in the working Display example.
static DISPLAY_MODEL oled(U8G2_R0, U8X8_PIN_NONE);
static bool ready = false;
bool initDisplay() {
    Wire.beginTransmission(LAB_OLED_ADDRESS);
    if (Wire.endTransmission() != 0) {
        Serial.println("OLED address did not ACK; check address/power.");
        ready = false;
        return false;
    }
    // Wire uses a 7-bit address; U8g2 expects the shifted address here.
    oled.setI2CAddress(LAB_OLED_ADDRESS << 1);
    oled.begin(); // Does NOT prove device identity or visible pixels.
    oled.setFlipMode(0);
    oled.setFontMode(1);
    oled.setDrawColor(1);
    oled.setFontDirection(0);
    oled.setFont(u8g2_font_6x12_tr);
    oled.setFontPosBaseline();
    ready = true;
    cleanDisplay();
    refreshDisplay();
    Serial.println("OLED configured; verify the picture on the board.");
    return true;
}
void cleanDisplay() {
    if (ready) oled.clearBuffer(); // RAM only, not the visible screen.
}
void displayMessage(u8g2_uint_t x, u8g2_uint_t baselineY,
                    const char *message) {
    if (ready && message != nullptr) {
        oled.setCursor(x, baselineY);
        oled.print(message);
    }
}
void refreshDisplay() {
    if (ready) oled.sendBuffer();
}
bool displayIsReady() { return ready; }
