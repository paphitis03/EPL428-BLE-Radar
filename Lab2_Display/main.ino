#include "boardInit.h"
#include "display.h"
static bool ready = false;
static bool boardReady = false;
void setup() {
    Serial.begin(115200);
    delay(1000); // bounded wait; do not wait forever for Serial
    boardReady = initBoard();
    if (!boardReady) {
        Serial.println("Continuing with OLED test using existing board power.");
    }
    scanSensorBus();
    ready = initDisplay();
}
void loop() {
    if (!ready) {
        Serial.println("Display unavailable: check the startup I2C scan at 115200 baud.");
        delay(1000);
        return;
    }
   cleanDisplay();
   displayMessage(0, 16, "EPL428 - Konstantinos Paphitis");
   displayMessage(0, 32, boardReady ? "Display ready" : "PMU not detected");
   refreshDisplay();
   delay(1000);
   cleanDisplay();
   displayMessage(0, 16, "Test1");
   displayMessage(0, 32, "OK");
   refreshDisplay();
   delay(1000);







}
