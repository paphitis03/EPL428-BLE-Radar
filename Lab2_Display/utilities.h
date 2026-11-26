#pragma once
// Revised lab configuration for the supplied T-Beam S3 Supreme only.
// Do not use these pins/power settings for other LilyGO models.
// PDF p.2 reverses PMU SDA/SCL labels; archived code and vendor guide use 42/41.
#include <Arduino.h>
constexpr uint8_t LAB_I2C_SDA = 17;
constexpr uint8_t LAB_I2C_SCL = 18;
constexpr uint8_t LAB_PMU_SDA = 42;
constexpr uint8_t LAB_PMU_SCL = 41;
constexpr uint8_t LAB_OLED_ADDRESS = 0x3C; // VERIFY on each physical board.
constexpr float SEALEVELPRESSURE_HPA = 1013.25F; // assumed, not local weather
#define DISPLAY_MODEL U8G2_SH1106_128X64_NONAME_F_HW_I2C
