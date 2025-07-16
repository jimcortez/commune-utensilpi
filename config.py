# -----------------------------------------------------------------------------
# Configuration
# -----------------------------------------------------------------------------
LOOP_DELAY = 0.01  # 10ms loop delay for faster response
DEBOUNCE_INTERVAL = 0.1  # 100ms debounce time for faster touch response

# MPR121 Default Thresholds (from Adafruit MPR121 library)
MPR121_DEFAULT_TOUCH_THRESHOLD = 12
MPR121_DEFAULT_RELEASE_THRESHOLD = 6

# Calibration monitoring
CALIBRATION_CHECK_INTERVAL = 60  # Check calibration every 60 seconds

# LED startup calibration (for electrical interference compensation)
LED_CALIBRATION_DELAY = 20  # Seconds after first MIDI to trigger re-calibration
LED_CALIBRATION_ENABLED = True  # Enable/disable LED startup calibration

# Display configuration
DISPLAY_I2C_ADDRESS = 0x3D
DISPLAY_WIDTH = 128
DISPLAY_HEIGHT = 64

# Logging configuration
# Options: ERROR, WARN, INFO, DEBUG
LOG_LEVEL = "INFO"  # Set to DEBUG for verbose output, ERROR for minimal output
LOG_TIMESTAMPS = True  # Enable/disable timestamps in log messages

# Performance settings
ENABLE_TOUCH_LOGGING = False  # Set to True to log every touch event (can be slow)
ENABLE_MIDI_LOGGING = False   # Set to True to log MIDI messages (can be slow)

# -----------------------------------------------------------------------------
# Slider Configuration
# -----------------------------------------------------------------------------
# Each slider configuration contains:
#   mpr121_address: Address of the MPR121 board (0x1A, 0x1B, 0x5A, or 0x5B)
#   down_pin: Pin number for decreasing value
#   up_pin: Pin number for increasing value
#   cc_number: MIDI CC number for value changes
#   both_press_cc: MIDI CC number for simultaneous press action
#   initial_value: Starting value (0-127)
#   speed_initial: Initial step size for first touch
#   speed: Base step size for continuous touch
#   accel_rate: Acceleration rate for held touches
#   activity_channel_cc: MIDI CC number for activity (on while slider is moving, off when idle)

SLIDERS = [
    {"mpr121_address": 0x1A, "down_pin": 0,  "up_pin": 1,  "cc_number": 3,  "both_press_cc": 9,  "initial_value": 64, "speed_initial": 1, "speed": 1, "accel_rate": 0.1, "activity_channel_cc": 100},
    {"mpr121_address": 0x1A, "down_pin": 2,  "up_pin": 3,  "cc_number": 14, "both_press_cc": 15, "initial_value": 64, "speed_initial": 1, "speed": 1, "accel_rate": 0.1, "activity_channel_cc": 101},
    {"mpr121_address": 0x1B, "down_pin": 0,  "up_pin": 1,  "cc_number": 20, "both_press_cc": 21, "initial_value": 64, "speed_initial": 1, "speed": 1, "accel_rate": 0.1, "activity_channel_cc": 102},
    {"mpr121_address": 0x1B, "down_pin": 2,  "up_pin": 3,  "cc_number": 22, "both_press_cc": 23, "initial_value": 64, "speed_initial": 1, "speed": 1, "accel_rate": 0.1, "activity_channel_cc": 103},
    {"mpr121_address": 0x5A, "down_pin": 0,  "up_pin": 1,  "cc_number": 24, "both_press_cc": 25, "initial_value": 64, "speed_initial": 1, "speed": 1, "accel_rate": 0.1, "activity_channel_cc": 104},
    {"mpr121_address": 0x5A, "down_pin": 2,  "up_pin": 3,  "cc_number": 26, "both_press_cc": 27, "initial_value": 64, "speed_initial": 1, "speed": 1, "accel_rate": 0.1, "activity_channel_cc": 105},
    {"mpr121_address": 0x5B, "down_pin": 0,  "up_pin": 1,  "cc_number": 28, "both_press_cc": 29, "initial_value": 64, "speed_initial": 1, "speed": 1, "accel_rate": 0.1, "activity_channel_cc": 106},
    {"mpr121_address": 0x5B, "down_pin": 2,  "up_pin": 3,  "cc_number": 30, "both_press_cc": 31, "initial_value": 64, "speed_initial": 1, "speed": 1, "accel_rate": 0.1, "activity_channel_cc": 107},
] 