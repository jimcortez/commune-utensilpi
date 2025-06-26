# Commune - Interactive Art Piece by Jim Cortez

**Commune** is an interactive art installation that transforms everyday utensils into MIDI controllers using capacitive touch sensors. The piece allows participants to create visual experiences by touching utensils connected to MPR121 capacitive touch sensors, which send MIDI commands to LED software for synchronized lighting effects.

## Overview

This project runs on an Adafruit QtPy RP2040 microcontroller using CircuitPython. It interfaces with multiple MPR121 capacitive touch sensor boards to detect touch interactions on utensils, converting them into MIDI control change (CC) messages that can control lighting software, synthesizers, or other MIDI-compatible devices.

## Features

- **8 Touch Sliders**: Each utensil acts as a dual-function touch slider
- **MIDI Output**: Sends standard MIDI CC messages for integration with music/lighting software
- **OLED Display**: Real-time feedback showing slider states and values
- **Dual Function**: Each slider can act as both a continuous controller and a momentary button
- **Acceleration**: Touch and hold for accelerated value changes
- **MIDI Input**: Can receive MIDI messages to update slider states remotely

## Hardware Requirements

### Core Components
- **Adafruit QtPy RP2040** - Main microcontroller
- **4x MPR121 Capacitive Touch Sensor Boards** (addresses: 0x1A, 0x1B, 0x5A, 0x5B)
- **SSD1306 OLED Display** (128x64 pixels, I2C address 0x3D)
- **USB-C Cable** - For power and MIDI communication

### Utensils & Wiring
- **8 Utensils** (forks, spoons, knives, etc.) - One per slider
- **Conductive wire** - To connect utensils to MPR121 touch pins
- **Breadboard and jumper wires** - For connections

## CircuitPython Dependencies

The following CircuitPython libraries are required (install via `circup`):

```
adafruit_midi
adafruit_mpr121
adafruit_displayio_ssd1306
adafruit_display_text
adafruit_debouncer
```

## Installation

### 1. Setup CircuitPython
1. Download CircuitPython for QtPy RP2040 from [circuitpython.org](https://circuitpython.org/)
2. Install CircuitPython on your QtPy board
3. The board will appear as a USB drive named `CIRCUITPY`

### 2. Install Dependencies
```bash
# Install circup if you haven't already
pip install circup

# Navigate to your project directory
cd commune-utensilpi

# Install all required libraries
./install.sh
```

Or manually install each library:
```bash
circup install adafruit_midi
circup install adafruit_mpr121
circup install adafruit_displayio_ssd1306
circup install adafruit_display_text
circup install adafruit_debouncer
```

### 3. Upload Code
1. Copy `boot.py` and `code.py` to the `CIRCUITPY` drive
2. The board will automatically restart and begin running the code

## Hardware Setup

### MPR121 Connections
Connect 4 MPR121 boards to the QtPy's I2C bus:

| MPR121 Address | SDA | SCL | VCC | GND |
|----------------|-----|-----|-----|-----|
| 0x1A           | SDA | SCL | 3.3V| GND |
| 0x1B           | SDA | SCL | 3.3V| GND |
| 0x5A           | SDA | SCL | 3.3V| GND |
| 0x5B           | SDA | SCL | 3.3V| GND |

### Utensil Connections
Each utensil connects to two pins on an MPR121 board:
- **Down Pin**: Decreases the slider value when touched
- **Up Pin**: Increases the slider value when touched
- **Both Pins**: When touched simultaneously, sends a button press (CC 127)

### Slider Configuration
The system supports 8 sliders with the following configuration:

| Slider | MPR121 | Down Pin | Up Pin | CC Number | Button CC | Initial Value |
|--------|--------|----------|--------|-----------|-----------|---------------|
| 1      | 0x1A   | 0        | 1      | 3         | 9         | 64           |
| 2      | 0x1A   | 2        | 3      | 14        | 15        | 64           |
| 3      | 0x1B   | 0        | 1      | 20        | 21        | 64           |
| 4      | 0x1B   | 2        | 3      | 22        | 23        | 64           |
| 5      | 0x5A   | 0        | 1      | 24        | 25        | 64           |
| 6      | 0x5A   | 2        | 3      | 26        | 27        | 64           |
| 7      | 0x5B   | 0        | 1      | 28        | 29        | 64           |
| 8      | 0x5B   | 2        | 3      | 30        | 31        | 64           |

## Usage

### Basic Operation
1. Power on the QtPy board
2. The OLED display will show the status of all 8 sliders
3. Touch utensils to control MIDI values:
   - Touch the "down" area to decrease values
   - Touch the "up" area to increase values
   - Touch both areas simultaneously for button press
4. MIDI messages are sent via USB to your computer

### MIDI Integration
The system sends MIDI CC messages on Channel 1:
- **Continuous Control**: Values 0-127 for slider positions
- **Button Press**: Value 127 for momentary button activation
- **Button Release**: Value 0 for button release

### Display Information
The OLED display shows:
- Slider number (0-7)
- Current CC number
- Current value (000-127)
- Status indicator:
  - `U` = Up pin touched
  - `D` = Down pin touched
  - `B` = Both pins touched (button mode)

## Configuration

### Adjusting Sensitivity
Modify these parameters in `code.py`:
- `LOOP_DELAY`: Main loop timing (default: 0.03s)
- `DEBOUNCE_INTERVAL`: Touch debounce time (default: 0.5s)
- `speed_initial`: Initial step size for first touch
- `speed`: Base step size for continuous touch
- `accel_rate`: Acceleration rate for held touches

### Customizing MIDI Mapping
Edit the `SLIDERS` configuration array to change:
- MIDI CC numbers
- Button CC numbers
- Initial values
- Speed and acceleration settings

## Troubleshooting

### I2C Device Detection
The code includes an I2C scanner that runs at startup. Check the serial output to verify all MPR121 boards are detected at their expected addresses.

### Touch Sensitivity
If touch detection is unreliable:
1. Check wire connections to utensils
2. Ensure utensils are properly grounded
3. Adjust MPR121 touch thresholds in the code
4. Verify baseline data in serial output

### MIDI Issues
- Ensure your computer recognizes the QtPy as a MIDI device
- Check that your MIDI software is configured to receive from the correct port
- Verify MIDI channel settings match your software

## Virtual MIDI Testing

The `virtual-midi/` directory contains a Python script for testing MIDI output without physical hardware:
```bash
cd virtual-midi
python3 virtual_sliders.py
```

This provides a terminal-based interface to simulate the touch sliders and test MIDI communication.

## License

This project is part of the Commune art installation by Jim Cortez. Use the code however you like without need of attribution.

## Support

For technical support or questions about the art piece, please contact the artist or refer to the CircuitPython documentation for hardware-specific issues. 