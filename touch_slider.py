import time
from adafruit_midi.control_change import ControlChange
from adafruit_debouncer import Debouncer
from config import DEBOUNCE_INTERVAL, ENABLE_TOUCH_LOGGING, ACTIVITY_TIMEOUT, BOTH_PRESSED_TIMEOUT
import config
from logger import get_logger, lazy_format

# Get logger instance
logger = get_logger()

# -----------------------------------------------------------------------------
# Optimized TouchSlider Class with Cached Touch Data
# -----------------------------------------------------------------------------
class TouchSlider:
    def __init__(self, mpr121, config, midi_interface):
        self.mpr121 = mpr121
        self.config = config
        self.midi = midi_interface
        self.value = float(config["initial_value"])
        self.last_sent_value = config["initial_value"]
        self.both_pressed = False
        self.hold_count_down = 0
        self.hold_count_up = 0
        self.enabled = True  # Track if slider is functional
        
        # Cache the touched_pins data to avoid repeated I2C calls
        self.cached_touched_pins = [False] * 12
        self.prev_touch_cache = list(self.cached_touched_pins)
        
        # Create debouncers that use cached data instead of direct I2C access
        self.down_debouncer = Debouncer(
            lambda: self.cached_touched_pins[config["down_pin"]], 
            interval=DEBOUNCE_INTERVAL
        )
        self.up_debouncer = Debouncer(
            lambda: self.cached_touched_pins[config["up_pin"]], 
            interval=DEBOUNCE_INTERVAL
        )
        # Track activity channel state
        self.activity_on = False
        self.last_activity_time = time.monotonic()
        # Track previous pin states for debug printing
        self.prev_down_pin_state = None
        self.prev_up_pin_state = None

    def activity_ping(self):
        self.last_activity_time = time.monotonic()
        activity_cc = self.config.get("activity_channel_cc")
        if activity_cc is not None and not self.activity_on:
            self.midi.send(ControlChange(activity_cc, 127))
            self.activity_on = True

    def activity_check(self):
        activity_cc = self.config.get("activity_channel_cc")
        timeout = BOTH_PRESSED_TIMEOUT if self.both_pressed else ACTIVITY_TIMEOUT
        if activity_cc is not None and self.activity_on:
            if (time.monotonic() - self.last_activity_time) > timeout:
                self.midi.send(ControlChange(activity_cc, 0))
                self.activity_on = False

    def update_touch_cache(self):
        """Update the cached touch data from the MPR121."""
        if not self.enabled:
            return
        
        try:
            # Single I2C read to get all touch states
            self.cached_touched_pins = self.mpr121.touched_pins
            # Only print when pin state changes
            down_pin = self.config["down_pin"]
            up_pin = self.config["up_pin"]
            down_state = self.cached_touched_pins[down_pin]
            up_state = self.cached_touched_pins[up_pin]
            # print(f"Slider {self.config['cc_number']} DOWN pin {down_pin} value: {down_state}")
            # print(f"Slider {self.config['cc_number']} UP pin {up_pin} value: {up_state}")
            if self.prev_down_pin_state != down_state:
                # print(f"Slider {self.config['cc_number']} DOWN pin {down_pin} changed: {down_state}")
                self.prev_down_pin_state = down_state
            if self.prev_up_pin_state != up_state:
                # print(f"Slider {self.config['cc_number']} UP pin {up_pin} changed: {up_state}")
                self.prev_up_pin_state = up_state

            # Print full touch cache only when it changes
            if self.prev_touch_cache != self.cached_touched_pins:
                # print(f"Slider {self.config['cc_number']} FULL touch cache changed: {self.cached_touched_pins}")
                self.prev_touch_cache = list(self.cached_touched_pins)
        
        except Exception as e:
            logger.error(lazy_format("Error updating touch cache for slider {}: {}", 
                                   self.config["cc_number"], e))
            # Mark slider as disabled if we can't communicate with MPR121
            self.enabled = False

    def update(self):
        """Update slider state and return True if changes occurred."""
        if not self.enabled:
            return False
            
        midi_sent = False
        try:
            # Debug: Print lambda value before updating debouncer
            # if self.config["down_pin"] == 2:
            #    print('down lambda', self.config["cc_number"], self.cached_touched_pins[self.config["down_pin"]])
            # if self.config["up_pin"] == 3:
            #    print('up lambda', self.config["cc_number"], self.cached_touched_pins[self.config["up_pin"]])

            # Update debouncers using cached data
            self.down_debouncer.update()
            self.up_debouncer.update()
            
            # Check for both pins pressed
            if self.down_debouncer.value and self.up_debouncer.value:
                if not self.both_pressed and self.config["both_press_cc"] is not None:
                    self.midi.send(ControlChange(self.config["both_press_cc"], 127))
                    midi_sent = True
                    if ENABLE_TOUCH_LOGGING:
                        logger.debug(lazy_format("Touch -> Button ({} | {}-{} | CC {}) ON", hex(self.config["mpr121_address"]), self.config["up_pin"], self.config["down_pin"], self.config["both_press_cc"]))
                    self.both_pressed = True
                    self.activity_ping()
            else:
                if self.both_pressed and self.config["both_press_cc"] is not None:
                    self.midi.send(ControlChange(self.config["both_press_cc"], 0))
                    midi_sent = True
                    if ENABLE_TOUCH_LOGGING:
                        logger.debug(lazy_format("Touch -> Button ({} | {}-{} | CC {}) OFF", hex(self.config["mpr121_address"]), self.config["up_pin"], self.config["down_pin"], self.config["both_press_cc"]))
                    self.both_pressed = False
                    self.activity_ping()
                
                # Update value based on individual touches
                if self.down_debouncer.value:
                    self.hold_count_down += 1
                    step = (self.config["speed_initial"] if self.hold_count_down == 1 
                           else self.config["speed"] + (self.config["accel_rate"] * self.hold_count_down))
                    self.value = max(0, self.value - step)
                    self.activity_ping()
                else:
                    self.hold_count_down = 0
                
                if self.up_debouncer.value:
                    self.hold_count_up += 1
                    step = (self.config["speed_initial"] if self.hold_count_up == 1 
                           else self.config["speed"] + (self.config["accel_rate"] * self.hold_count_up))
                    self.value = min(127, self.value + step)
                    self.activity_ping()
                else:
                    self.hold_count_up = 0
                
                # Send MIDI if value changed
                new_value = int(self.value)
                if new_value != self.last_sent_value:
                    self.midi.send(ControlChange(self.config["cc_number"], new_value))
                    midi_sent = True
                    if ENABLE_TOUCH_LOGGING:
                        logger.debug(lazy_format("Touch -> Slider ({} | {}-{} | CC {}) = {}", hex(self.config["mpr121_address"]), self.config["up_pin"], self.config["down_pin"], self.config["cc_number"], new_value))
                    self.last_sent_value = new_value
                    self.activity_ping()
            # Activity channel logic is now handled by activity_ping and activity_check
        except Exception as e:
            logger.error(lazy_format("Error updating slider {}: {}", self.config["cc_number"], e))
            # Mark slider as disabled if we encounter persistent errors
            self.enabled = False
        
        return midi_sent
    
    def get_status(self):
        """Get status information about this slider."""
        return {
            "cc_number": self.config["cc_number"],
            "both_press_cc": self.config["both_press_cc"],
            "mpr121_address": hex(self.config["mpr121_address"]),
            "down_pin": self.config["down_pin"],
            "up_pin": self.config["up_pin"],
            "enabled": self.enabled,
            "value": int(self.value),
            "both_pressed": self.both_pressed
        }

def create_touch_sliders(mpr121_boards, midi_interface, sliders_config):
    """Create TouchSlider objects for all configured sliders with error handling."""
    touch_sliders = []
    created_count = 0
    skipped_count = 0
    
    logger.info("Creating touch sliders...")
    
    for config in sliders_config:
        mpr121_addr = config["mpr121_address"]
        
        # Check if the required MPR121 board is available
        if mpr121_addr not in mpr121_boards:
            logger.warn(lazy_format("Skipping slider CC {} - MPR121 at 0x{:02X} not available", 
                                   config["cc_number"], mpr121_addr))
            skipped_count += 1
            continue
        
        try:
            # Create the slider
            slider = TouchSlider(
                mpr121_boards[mpr121_addr], 
                config, 
                midi_interface
            )
            touch_sliders.append(slider)
            
            logger.debug(lazy_format("Created slider CC {} using MPR121 0x{:02X}", 
                                   config["cc_number"], mpr121_addr))
            
        except Exception as e:
            logger.error(lazy_format("Failed to create slider CC {}: {}", config["cc_number"], e))
            skipped_count += 1
    
    logger.info(lazy_format("Touch slider creation complete: {} created, {} skipped", 
                           len(touch_sliders), skipped_count))
    
    if len(touch_sliders) == 0:
        logger.error("No touch sliders were created!")
        logger.warn("Touch functionality will not work")
    elif skipped_count > 0:
        logger.warn(lazy_format("{} sliders were skipped due to missing MPR121 boards", skipped_count))
    
    return touch_sliders

def update_touch_cache_for_all_boards(mpr121_boards, touch_sliders):
    """Update touch cache for all sliders (each slider updates its own cache from its board)."""
    for slider in touch_sliders:
        slider.update_touch_cache()

def update_all_sliders(touch_sliders):
    """Update all sliders and return if any changed."""
    display_needs_update = False
    
    for slider in touch_sliders:
        # print(f"Updating slider {slider.config['cc_number']}, enabled={slider.enabled}")
        if slider.enabled:
            if slider.update():
                display_needs_update = True
    
    return display_needs_update

def get_slider_status(touch_sliders):
    """Get status information about all sliders."""
    enabled_sliders = [s for s in touch_sliders if s.enabled]
    disabled_sliders = [s for s in touch_sliders if not s.enabled]
    
    return {
        "total_sliders": len(touch_sliders),
        "enabled_sliders": len(enabled_sliders),
        "disabled_sliders": len(disabled_sliders),
        "enabled_cc_numbers": [s.config["cc_number"] for s in enabled_sliders],
        "disabled_cc_numbers": [s.config["cc_number"] for s in disabled_sliders]
    } 

def activity_check_all_sliders(touch_sliders):
    """Call activity_check for all sliders."""
    for slider in touch_sliders:
        if slider.enabled:
            slider.activity_check() 