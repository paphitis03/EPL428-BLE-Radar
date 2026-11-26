#include <Arduino.h>
#include <NimBLEDevice.h>
#include <freertos/FreeRTOS.h>
#include <freertos/queue.h>

#include "Lab2_Display/boardInit.h"
#include "Lab2_Display/display.h"

namespace {
constexpr uint32_t scanDurationMs = 5000;
constexpr uint32_t scanEndGraceMs = 500;

struct ScanEnd {
    uint32_t endedAt;
    int reason;
};

QueueHandle_t scanEvents;
NimBLEScan* scanner;
uint32_t startedAt;

class ScanCallbacks : public NimBLEScanCallbacks {
    void onScanEnd(const NimBLEScanResults&, int reason) override {
        const ScanEnd event{millis(), reason};
        xQueueOverwrite(scanEvents, &event);
    }
};

ScanCallbacks callbacks;

void reportWindow(const ScanEnd& end, uint32_t duration,
                  const char* status, bool complete) {
    int devices = 0;
    int sum = 0;
    int strongest = -128;
    int weakest = 127;
    if (complete) {
        const auto results = scanner->getResults();
        devices = results.getCount();
        // NimBLE stores one result per advertiser address in this scan mode.
        for (const auto* device : results) {
            const int rssi = device->getRSSI();
            sum += rssi;
            strongest = max(strongest, rssi);
            weakest = min(weakest, rssi);
        }
    }

    Serial.printf("%lu,%d,", static_cast<unsigned long>(end.endedAt - startedAt), devices);
    if (devices > 0) {
        Serial.printf("%.1f,%d,%d", static_cast<double>(sum) / devices, strongest, weakest);
    } else {
        Serial.print(",,");
    }
    Serial.printf(",%lu,%s,%d\n", static_cast<unsigned long>(duration), status, end.reason);

    char line[40];
    cleanDisplay();
    snprintf(line, sizeof(line), "BLE advertisers: %d", devices);
    displayMessage(0, 12, line);
    if (devices > 0) {
        snprintf(line, sizeof(line), "Avg: %.1f dBm", static_cast<double>(sum) / devices);
        displayMessage(0, 24, line);
        snprintf(line, sizeof(line), "Max %d / Min %d", strongest, weakest);
        displayMessage(0, 36, line);
    } else {
        displayMessage(0, 24, "RSSI unavailable");
    }
    snprintf(line, sizeof(line), "%lu ms", static_cast<unsigned long>(duration));
    displayMessage(0, 48, line);
    displayMessage(0, 60, status);
    refreshDisplay();
}
}  // namespace

void setup() {
    Serial.begin(115200);
    delay(1000);
    initBoard();
    initDisplay();

    scanEvents = xQueueCreate(1, sizeof(ScanEnd));
    if (scanEvents == nullptr || !NimBLEDevice::init("")) {
        Serial.println("BLE initialization failed.");
        displayMessage(0, 12, "BLE init failed");
        refreshDisplay();
        return;
    }

    scanner = NimBLEDevice::getScan();
    scanner->setActiveScan(false);
    scanner->setInterval(100);
    scanner->setWindow(100);
    scanner->setScanCallbacks(&callbacks);
    displayMessage(0, 12, "Scanning BLE...");
    refreshDisplay();

    Serial.println("elapsed_ms,devices,avg_rssi,max_rssi,min_rssi,scan_ms,status,ble_reason");
    startedAt = millis();
}

void loop() {
    if (scanner == nullptr) {
        delay(scanDurationMs);
        return;
    }

    xQueueReset(scanEvents);
    const uint32_t windowStart = millis();
    if (!scanner->start(scanDurationMs)) {
        delay(scanDurationMs);
        reportWindow({millis(), -1}, 0, "start_failed", false);
        return;
    }

    ScanEnd end;
    if (xQueueReceive(scanEvents, &end, pdMS_TO_TICKS(scanDurationMs + scanEndGraceMs)) != pdTRUE) {
        scanner->stop();
        end = {millis(), -1};
        reportWindow(end, end.endedAt - windowStart, "timeout", false);
    } else {
        reportWindow(end, end.endedAt - windowStart, end.reason == 0 ? "ok" : "scan_error",
                     end.reason == 0);
    }
    scanner->clearResults();
}
