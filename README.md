# Commune - Utensils Component

**Commune** is an interactive art installation by Jim Cortez. This repository contains the code for the **utensils component** - a system that transforms everyday utensils into MIDI controllers using capacitive touch sensors.

## What This Does

This code runs on an Adafruit QtPy RP2040 microcontroller and turns 8 utensils (forks, spoons, knives, etc.) into MIDI controllers. When you touch a utensil, it sends MIDI messages to control lighting software or other MIDI devices.

## Hardware

- **Adafruit QtPy RP2040** - Main controller
- **4 MPR121 Capacitive Touch Sensor Boards** - Detect utensil touches
- **OLED Display** - Shows which utensils are being touched
- **8 Utensils** - Connected to the touch sensors with wire

## Quick Start

1. **Install CircuitPython** on your QtPy RP2040
2. **Install dependencies**:
   ```bash
   ./install.sh
   ```
3. **Connect hardware** (see Hardware Setup below)
4. **Copy code** to the QtPy board
5. **Touch utensils** to send MIDI messages

## Hardware Setup

### MPR121 Boards
Connect 4 MPR121 boards to the QtPy's I2C bus:

| Board | Address | SDA | SCL | VCC | GND |
|-------|---------|-----|-----|-----|-----|
| 1     | 0x1A    | SDA | SCL | 3.3V| GND |
| 2     | 0x1B    | SDA | SCL | 3.3V| GND |
| 3     | 0x5A    | SDA | SCL | 3.3V| GND |
| 4     | 0x5B    | SDA | SCL | 3.3V| GND |

### Utensil Connections
Each utensil connects to two pins on an MPR121 board:
- **Down Pin**: Decreases the MIDI value
- **Up Pin**: Increases the MIDI value
- **Both Pins**: Sends a button press

### Slider Mapping
| Utensil | MPR121 | Down | Up | CC Number | Button CC |
|---------|--------|------|----|-----------|-----------|
| 1       | 0x1A   | 0    | 1  | 3         | 9         |
| 2       | 0x1A   | 2    | 3  | 14        | 15        |
| 3       | 0x1B   | 0    | 1  | 20        | 21        |
| 4       | 0x1B   | 2    | 3  | 22        | 23        |
| 5       | 0x5A   | 0    | 1  | 24        | 25        |
| 6       | 0x5A   | 2    | 3  | 26        | 27        |
| 7       | 0x5B   | 0    | 1  | 28        | 29        |
| 8       | 0x5B   | 2    | 3  | 30        | 31        |

### Special Features

#### Activity Channels
Each slider has an activity channel (CC 100-107) that turns ON while the slider is being touched and OFF when idle.

#### All Both-Press Toggle
When all sliders are simultaneously in the "both-press" state (both pins touched) for 3 seconds, a special toggle activates (CC 108). This toggle:
- Stays active for 10-30 seconds (minimum 10s, maximum 30s)
- Can only be triggered once per minute (60-second cooldown)
- Automatically deactivates when any slider leaves the both-press state (after minimum duration)
- Can be configured in `config.py`

## How It Works

1. **Touch Detection**: MPR121 boards detect when utensils are touched
2. **MIDI Output**: Sends MIDI CC messages (0-127) via USB
3. **Display Feedback**: OLED shows which utensils are active
4. **Error Handling**: Continues working even if some hardware is missing

## Features

- **8 Touch Sliders**: Each utensil controls a different MIDI parameter
- **Dual Function**: Each utensil can be a slider or button
- **Acceleration**: Hold to change values faster
- **Robust**: Works with missing hardware components
- **Calibration**: Automatic touch sensor calibration
- **LED Interference Handling**: Re-calibrates when LED lights turn on

## Configuration

The system behavior can be customized by editing `config.py`:

### Basic Settings
- `LOOP_DELAY`: Main loop delay (default: 0.01s)
- `DEBOUNCE_INTERVAL`: Touch debounce time (default: 0.1s)
- `LOG_LEVEL`: Logging verbosity (ERROR, WARN, INFO, DEBUG)

### All Both-Press Toggle Settings
- `ALL_BOTH_PRESS_TOGGLE_ENABLED`: Enable/disable the feature (default: True)
- `ALL_BOTH_PRESS_CC_NUMBER`: MIDI CC number for the toggle (default: 108)
- `ALL_BOTH_PRESS_STABLE_TIME`: Time all sliders must be both-pressed before triggering (default: 3.0s)
- `ALL_BOTH_PRESS_MIN_DURATION`: Minimum toggle duration (default: 10.0s)
- `ALL_BOTH_PRESS_MAX_DURATION`: Maximum toggle duration (default: 30.0s)
- `ALL_BOTH_PRESS_COOLDOWN`: Cooldown period between triggers (default: 60.0s)

### Slider Configuration
Each slider can be configured with:
- `mpr121_address`: I2C address of the MPR121 board
- `down_pin`/`up_pin`: Pin numbers for decreasing/increasing values
- `cc_number`: MIDI CC number for value changes
- `both_press_cc`: MIDI CC number for simultaneous press action
- `activity_channel_cc`: MIDI CC number for activity indication
- `speed_initial`/`speed`/`accel_rate`: Control response sensitivity

## Troubleshooting

- **No touch response**: Check wire connections to utensils
- **Missing MPR121**: Code will work with fewer boards
- **MIDI not working**: Check USB connection and MIDI software settings
- **Display issues**: Code continues without display

## Dependencies

Required CircuitPython libraries:
- `adafruit_midi`
- `adafruit_mpr121`
- `adafruit_displayio_ssd1306`
- `adafruit_display_text`
- `adafruit_debouncer`

## About This Component

This is just one part of the larger Commune art installation. The utensils component provides the touch interface that participants use to interact with the piece. Other components handle lighting, sound, and other aspects of the installation.

## License

Part of the Commune art installation by Jim Cortez. Use freely. 

---

## CLI Slider Emulator for Testing (test_tool/slider_cli.py)

This project includes a command-line tool to emulate the touch sliders and send real MIDI messages for development and testing on standard Python (not CircuitPython).

### Setup

1. **Python Version**: Ensure you are using Python 3.11 (see `.python-version` in `test_tool/`).
2. **Install Dependencies**:
   - From the project root, run:
     ```sh
     pip install -r test_tool/pyproject.toml
     ```
     Or, if using pip directly:
     ```sh
     pip install urwid mido python-rtmidi
     ```

### Usage

1. **Run the CLI Tool**:
   ```sh
   cd test_tool
   python slider_cli.py
   ```
2. **Select MIDI Output**:
   - The tool prints available MIDI output ports at startup. Edit the `MidiInterface` line in `slider_cli.py` to use your desired port name (e.g., `'MadMapper In'`).

3. **Controls**:
   - **Arrow keys / j/k**: Move focus between sliders
   - **Right/+**: Increase slider value
   - **Left/-**: Decrease slider value
   - **Space**: Trigger both-press (special CC)
   - **b**: Release both-press
   - **q**: Quit

4. **Activity Channel**:
   - The tool emulates the activity channel logic, including extended activity when both are pressed.

### Notes
- The tool uses the same config as the hardware, so any changes to `config.py` are reflected in the emulator.
- All MIDI messages are sent using the `mido` library and require a working MIDI backend (e.g., `python-rtmidi`).
- This tool does not affect the CircuitPython code and is for development/testing only. 