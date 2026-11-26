#include "boardInit.h"
#include <XPowersLib.h>
// Use the public channel-specific XPowers API.
static XPowersAXP2101 pmu(Wire1, LAB_PMU_SDA, LAB_PMU_SCL);
bool initBoard() {
    // Keep the display bus available even if PMU detection fails.
    Wire.begin(LAB_I2C_SDA, LAB_I2C_SCL);
    Wire.setTimeOut(50);
    Wire1.begin(LAB_PMU_SDA, LAB_PMU_SCL);
    if (!pmu.init()) {
        Serial.println("ERROR: AXP2101 not found. Check board and power.");
        return false;
    }
    // Sensor supplies from the supplied Supreme PMU initialisation.
    // Do not alter charging settings or the ESP32 supply in this lab.
    pmu.setALDO1Voltage(3300);
    pmu.enableALDO1();
    pmu.setALDO2Voltage(3300);
    pmu.enableALDO2();
    delay(50);
    Serial.println("Board ready: SDA=17, SCL=18; PMU on Wire1.");
    return true;
}
void scanSensorBus() {
    Serial.println("I2C scan on Wire (17/18); ACK is not a device ID:");
    unsigned count = 0;
    for (uint8_t address = 1; address < 127; ++address) {
        Wire.beginTransmission(address);
        if (Wire.endTransmission() == 0) {
            Serial.printf("  ACK at 0x%02X\n", address);
            ++count;
        }
    }
    Serial.printf("Scan complete: %u address(es).\n", count);
}
