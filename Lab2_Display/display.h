#pragma once
#include <Arduino.h>
#include <U8g2lib.h>
// Revised API: draw to RAM first, then explicitly refresh once per frame.
bool initDisplay();
void cleanDisplay();
void displayMessage(u8g2_uint_t x, u8g2_uint_t baselineY,
                    const char *message);
void refreshDisplay();
bool displayIsReady();
