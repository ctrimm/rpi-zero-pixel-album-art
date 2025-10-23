# LED Matrix Wiring Guide

Detailed wiring instructions for connecting your LED matrix panel to Raspberry Pi.

## HUB75 Connector Pinout

The HUB75 connector is the standard 16-pin (2x8) connector on LED matrix panels.

```
┌─ Pin 1                      Pin 2 ─┐
│  R1   ●  ●  G1                      │
│  B1   ●  ●  GND                     │
│  R2   ●  ●  G2                      │
│  B2   ●  ●  E (or GND on 32px high) │
│  A    ●  ●  B                       │
│  C    ●  ●  D                       │
│  CLK  ●  ●  LAT                     │
│  OE   ●  ●  GND                     │
└─────────────────────────────────────┘
```

## Signal Descriptions

| Signal | Description |
|--------|-------------|
| R1, G1, B1 | Upper half RGB data |
| R2, G2, B2 | Lower half RGB data |
| A, B, C, D, E | Row address lines |
| CLK | Serial clock |
| LAT | Latch/strobe |
| OE | Output enable (active low) |
| GND | Ground (multiple pins) |

## Option 1: Adafruit RGB Matrix Bonnet (Recommended)

**Easiest option - no manual wiring needed!**

### What You Need:
- [Adafruit RGB Matrix Bonnet](https://www.adafruit.com/product/3211) - $15
- HUB75 cable (usually included with LED panel)

### Installation:
1. Power off Raspberry Pi
2. Attach bonnet to GPIO header (all 40 pins)
3. Connect HUB75 cable from bonnet to LED panel
4. Connect power:
   - Panel power to bonnet's power terminals
   - Or use separate 5V power supply for panel

### Advantages:
- No soldering or complex wiring
- Built-in level shifting
- Power distribution included
- Reverse polarity protection

---

## Option 2: Manual GPIO Wiring

**For DIY builds or when bonnet is not available**

### What You Need:
- Female-to-female jumper wires (20+ wires)
- HUB75 breakout board or DIY connector
- Multimeter (for verification)

### GPIO Pin Mapping

Connect HUB75 signals to these Raspberry Pi GPIO pins:

| HUB75 Signal | Pi GPIO (BCM) | Physical Pin | Wire Color Suggestion |
|--------------|---------------|--------------|----------------------|
| R1 | GPIO 11 | Pin 23 | Red |
| G1 | GPIO 27 | Pin 13 | Green |
| B1 | GPIO 7 | Pin 26 | Blue |
| R2 | GPIO 8 | Pin 24 | Orange |
| G2 | GPIO 9 | Pin 21 | Yellow |
| B2 | GPIO 10 | Pin 19 | Light Blue |
| A | GPIO 22 | Pin 15 | Purple |
| B | GPIO 23 | Pin 16 | Gray |
| C | GPIO 24 | Pin 18 | White |
| D | GPIO 25 | Pin 22 | Brown |
| E | GPIO 15 | Pin 10 | Pink (if needed) |
| CLK | GPIO 17 | Pin 11 | Black |
| LAT | GPIO 4 | Pin 7 | Yellow-Black |
| OE | GPIO 18 | Pin 12 | Green-Black |
| GND | GND | Pins 6, 9, 14, 20, 25, 30, 34, 39 | Black |

### GPIO Pin Diagram

```
    3V3  (1) (2)  5V
  GPIO2  (3) (4)  5V
  GPIO3  (5) (6)  GND
  GPIO4  (7) (8)  GPIO14
    GND  (9) (10) GPIO15
 GPIO17 (11) (12) GPIO18
 GPIO27 (13) (14) GND
 GPIO22 (15) (16) GPIO23
    3V3 (17) (18) GPIO24
 GPIO10 (19) (20) GND
  GPIO9 (21) (22) GPIO25
 GPIO11 (23) (24) GPIO8
    GND (25) (26) GPIO7
  GPIO0 (27) (28) GPIO1
  GPIO5 (29) (30) GND
  GPIO6 (31) (32) GPIO12
 GPIO13 (33) (34) GND
 GPIO19 (35) (36) GPIO16
 GPIO26 (37) (38) GPIO20
    GND (39) (40) GPIO21
```

### Wiring Steps

1. **Power off everything first!**

2. **Connect ground pins:**
   - Connect at least 2 GND pins from Pi to HUB75 GND
   - Use pins 6, 9, 14, 20, 25, 30, 34, or 39

3. **Connect RGB data pins:**
   - R1 → GPIO 11 (pin 23)
   - G1 → GPIO 27 (pin 13)
   - B1 → GPIO 7 (pin 26)
   - R2 → GPIO 8 (pin 24)
   - G2 → GPIO 9 (pin 21)
   - B2 → GPIO 10 (pin 19)

4. **Connect address pins:**
   - A → GPIO 22 (pin 15)
   - B → GPIO 23 (pin 16)
   - C → GPIO 24 (pin 18)
   - D → GPIO 25 (pin 22)
   - E → GPIO 15 (pin 10) - only if your panel has E line (usually 64px+ high panels)

5. **Connect control pins:**
   - CLK → GPIO 17 (pin 11)
   - LAT → GPIO 4 (pin 7)
   - OE → GPIO 18 (pin 12)

6. **Double-check all connections** with multimeter in continuity mode

---

## Power Connection

### LED Panel Power Requirements

| Panel Size | Typical Current | Recommended PSU |
|------------|----------------|-----------------|
| 64x32 | 2-4A @ 5V | 5V 4A (20W) |
| 64x64 | 4-8A @ 5V | 5V 10A (50W) |

### Power Wiring

**CRITICAL SAFETY:**
- ⚠️ **NEVER** connect LED panel power to Raspberry Pi
- ⚠️ **ALWAYS** use separate 5V power supply for panel
- ⚠️ **VERIFY** polarity with multimeter before connecting
- ⚠️ **CONNECT** common ground between Pi and panel power

### Correct Power Setup:

```
5V Power Supply
     │
     ├─── Red (+5V) ──→ LED Panel +5V
     └─── Black (GND) ─→ LED Panel GND
                            │
                            └─→ Also connect to Pi GND (common ground)

Raspberry Pi Power Supply
     │
     └─── Powers Pi only (separate supply)
```

### Power Connection Steps:

1. **Verify power supply voltage:**
   ```
   Use multimeter to confirm exactly 5.0V DC
   ```

2. **Check polarity:**
   - Red/+ → +5V terminal on panel
   - Black/- → GND terminal on panel

3. **Connect power:**
   - Attach power cables to panel terminals
   - Secure connections (screw terminals)
   - **Connect common ground** to Pi GND pin

4. **Add capacitor (recommended):**
   - Solder 1000-3300μF capacitor across +5V and GND near panel
   - Helps reduce flicker and noise
   - Pay attention to capacitor polarity!

---

## Troubleshooting Hardware

### No Display

- [ ] Check 5V power supply is on and connected
- [ ] Verify voltage is 4.9-5.1V at panel
- [ ] Check HUB75 cable is fully seated
- [ ] Verify common ground connection
- [ ] Try test pattern: `curl http://localhost:5000/api/display/test`

### Wrong Colors

- [ ] Check RGB pin connections (might be swapped)
- [ ] Try different `led_rgb_sequence` in config:
  ```json
  "led_rgb_sequence": "RBG"  // or "BRG", "BGR", "GRB", "GBR"
  ```

### Flickering

- [ ] Add capacitor across power rails (1000-3300μF)
- [ ] Use thicker power wires (16-18 AWG)
- [ ] Increase `gpio_slowdown` in config:
  ```json
  "gpio_slowdown": 3  // or 4
  ```
- [ ] Reduce brightness if flickering only at high brightness

### Ghosting/Double Images

- [ ] Shorten HUB75 cable (under 6 inches ideal)
- [ ] Add `--led-slowdown-gpio=2` (already in config)
- [ ] Check for loose connections
- [ ] Verify ground connections

### Display Shows Random Pixels

- This is normal when no program is running
- Start the display software to control it
- If persists when software is running, check signal connections

---

## Advanced: Level Shifters

Raspberry Pi GPIO outputs 3.3V, but HUB75 expects 5V logic. Most panels work fine with 3.3V, but for longer cables or multiple panels, use level shifters:

**Recommended Level Shifter:**
- [74HCT245](https://www.adafruit.com/product/735) octal bus transceiver
- Converts 3.3V to 5V
- One chip per 8 signals (need 2-3 chips total)

---

## Tools Needed

- Small Phillips screwdriver
- Wire strippers (if cutting wires)
- Multimeter (highly recommended)
- Soldering iron (for capacitor or level shifters)
- Cable ties (for wire management)

---

## Safety Checklist

Before powering on:

- [ ] All connections match the pinout above
- [ ] No short circuits (check with multimeter)
- [ ] Polarity verified on power connections
- [ ] Common ground connected between Pi and panel
- [ ] No loose wires touching each other
- [ ] Pi and panel have separate power supplies
- [ ] Power supplies are rated for the current draw

---

## References

- [Adafruit RGB Matrix Guide](https://learn.adafruit.com/adafruit-rgb-matrix-plus-real-time-clock-hat-for-raspberry-pi)
- [rpi-rgb-led-matrix Library](https://github.com/hzeller/rpi-rgb-led-matrix)
- [Raspberry Pi GPIO Pinout](https://pinout.xyz)
