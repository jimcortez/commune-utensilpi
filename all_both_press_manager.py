import time
from adafruit_midi.control_change import ControlChange
from config import (
    ALL_BOTH_PRESS_TOGGLE_ENABLED,
    ALL_BOTH_PRESS_CC_NUMBER,
    ALL_BOTH_PRESS_STABLE_TIME,
    ALL_BOTH_PRESS_MIN_DURATION,
    ALL_BOTH_PRESS_MAX_DURATION,
    ALL_BOTH_PRESS_COOLDOWN
)
from logger import get_logger, lazy_format

# Get logger instance
logger = get_logger()

class AllBothPressManager:
    """
    Manages the "all both-press" toggle feature that activates when all sliders
    are in the both-press state for a configurable duration.
    """
    
    def __init__(self, midi_interface):
        self.midi = midi_interface
        self.enabled = ALL_BOTH_PRESS_TOGGLE_ENABLED
        self.cc_number = ALL_BOTH_PRESS_CC_NUMBER
        
        # Timing configuration
        self.stable_time = ALL_BOTH_PRESS_STABLE_TIME
        self.min_duration = ALL_BOTH_PRESS_MIN_DURATION
        self.max_duration = ALL_BOTH_PRESS_MAX_DURATION
        self.cooldown = ALL_BOTH_PRESS_COOLDOWN
        
        # State tracking
        self.all_both_pressed = False
        self.toggle_active = False
        self.stable_start_time = None
        self.toggle_start_time = None
        self.last_trigger_time = -self.cooldown  # Allow immediate triggering
        
        if self.enabled:
            logger.info(lazy_format("All Both-Press Toggle enabled (CC {})", self.cc_number))
            logger.info(lazy_format("  Stable time: {}s, Min duration: {}s, Max duration: {}s, Cooldown: {}s",
                                   self.stable_time, self.min_duration, self.max_duration, self.cooldown))
        else:
            logger.info("All Both-Press Toggle disabled")
    
    def update(self, touch_sliders, current_time):
        """
        Update the all both-press state based on current slider states.
        
        Args:
            touch_sliders: List of TouchSlider objects
            current_time: Current monotonic time
            
        Returns:
            bool: True if the toggle state changed, False otherwise
        """
        if not self.enabled or not touch_sliders:
            return False
        
        # Count enabled sliders and check their both-press states
        enabled_sliders = [s for s in touch_sliders if s.enabled]
        if not enabled_sliders:
            return False
        
        all_both_pressed_now = all(slider.both_pressed for slider in enabled_sliders)
        
        # State change detection
        if all_both_pressed_now != self.all_both_pressed:
            self.all_both_pressed = all_both_pressed_now
            
            if self.all_both_pressed:
                # All sliders just entered both-press state
                self.stable_start_time = current_time
                logger.debug("All sliders entered both-press state - starting stable timer")
            else:
                # At least one slider left both-press state
                self.stable_start_time = None
                logger.debug("At least one slider left both-press state - resetting stable timer")
        
        # Check if we should trigger the toggle
        if (self.all_both_pressed and 
            not self.toggle_active and 
            self.stable_start_time is not None and
            current_time - self.stable_start_time >= self.stable_time and
            current_time - self.last_trigger_time >= self.cooldown):
            
            # Trigger the toggle
            self.toggle_active = True
            self.toggle_start_time = current_time
            self.last_trigger_time = current_time
            
            # Send MIDI CC ON
            try:
                self.midi.send(ControlChange(self.cc_number, 127))
                logger.info(lazy_format("All Both-Press Toggle ACTIVATED (CC {})", self.cc_number))
            except Exception as e:
                logger.error(lazy_format("Failed to send All Both-Press Toggle MIDI: {}", e))
            
            return True
        
        # Check if we should deactivate the toggle
        if self.toggle_active:
            toggle_duration = current_time - self.toggle_start_time
            
            # Deactivate if minimum duration reached and not all sliders are still both-pressed
            if (toggle_duration >= self.min_duration and not self.all_both_pressed) or \
               toggle_duration >= self.max_duration:
                
                self.toggle_active = False
                self.toggle_start_time = None
                
                # Send MIDI CC OFF
                try:
                    self.midi.send(ControlChange(self.cc_number, 0))
                    logger.info(lazy_format("All Both-Press Toggle DEACTIVATED (CC {}) after {}s", 
                                           self.cc_number, toggle_duration))
                except Exception as e:
                    logger.error(lazy_format("Failed to send All Both-Press Toggle MIDI: {}", e))
                
                return True
        
        return False
    
    def get_status(self):
        """Get current status information about the all both-press toggle."""
        return {
            "enabled": self.enabled,
            "cc_number": self.cc_number,
            "all_both_pressed": self.all_both_pressed,
            "toggle_active": self.toggle_active,
            "stable_start_time": self.stable_start_time,
            "toggle_start_time": self.toggle_start_time,
            "last_trigger_time": self.last_trigger_time,
            "stable_time": self.stable_time,
            "min_duration": self.min_duration,
            "max_duration": self.max_duration,
            "cooldown": self.cooldown
        } 