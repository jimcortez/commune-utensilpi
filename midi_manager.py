import usb_midi
import adafruit_midi
from adafruit_midi.control_change import ControlChange
from config import SLIDERS, ENABLE_MIDI_LOGGING
from logger import get_logger, lazy_format
from mpr121_manager import get_led_calibration_manager

# Get logger instance
logger = get_logger()

class MIDIManager:
    def __init__(self):
        self.midi = adafruit_midi.MIDI(
            midi_in=usb_midi.ports[0],
            midi_out=usb_midi.ports[1],
            in_channel=0,    # MIDI Channel 1 (0-based)
            out_channel=0    # MIDI Channel 1
        )
        self.led_calibration_manager = get_led_calibration_manager()
        logger.info("MIDI interface initialized")
    
    def send_control_change(self, cc_number, value):
        """Send a MIDI control change message."""
        self.midi.send(ControlChange(cc_number, value))
    
    def receive_messages(self, touch_sliders, current_time=None):
        """Process incoming MIDI messages and update sliders accordingly."""
        msg = self.midi.receive()
        midi_received = False
        
        while msg is not None:
            midi_received = True
            if isinstance(msg, ControlChange):
                # Find matching slider
                for slider in touch_sliders:
                    if msg.control == slider.config["cc_number"]:
                        slider.value = float(msg.value)
                        slider.last_sent_value = msg.value
                        if ENABLE_MIDI_LOGGING:
                            logger.debug(lazy_format("MIDI In -> Slider (CC {}) = {}", msg.control, msg.value))
                    elif msg.control == slider.config["both_press_cc"]:
                        slider.both_pressed = msg.value >= 64
                        if ENABLE_MIDI_LOGGING:
                            logger.debug(lazy_format("MIDI In -> Button (CC {}) = {}", msg.control, msg.value))
            msg = self.midi.receive()
        
        # Notify LED calibration manager if MIDI was received
        if midi_received and current_time is not None:
            self.led_calibration_manager.on_midi_received(current_time)
    
    def get_interface(self):
        """Get the MIDI interface for use by other modules."""
        return self.midi 