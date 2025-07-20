# -----------------------------------------------------------------------------
# MPR121 Library with I2C Logging
# -----------------------------------------------------------------------------
"""
Logged MPR121 Library Wrapper

This module wraps the Adafruit MPR121 library and adds comprehensive I2C logging
to all operations while maintaining the same interface.
"""

import time
import board
import adafruit_mpr121
from i2c_logger import log_i2c_read, log_i2c_write, log_batch_read
from logger import get_logger, lazy_format

# Get logger instance
logger = get_logger()

# Import config to check if debug logging is enabled
try:
    from config import ENABLE_I2C_DEBUG_LOGGING
except ImportError:
    # Default to False if config not available
    ENABLE_I2C_DEBUG_LOGGING = False

class LoggedMPR121Channel:
    """Logged wrapper for MPR121_Channel with I2C logging."""
    
    def __init__(self, mpr121, channel):
        self._mpr121 = mpr121
        self._channel = channel
    
    @property
    def value(self):
        """Get whether the touch pad is being touched or not."""
        # This calls touched() which we log in the main class
        return self._mpr121.touched() & (1 << self._channel) != 0
    
    @property
    def raw_value(self):
        """Get the raw touch measurement."""
        # This calls filtered_data() which we log in the main class
        return self._mpr121.filtered_data(self._channel)
    
    @property
    def threshold(self):
        """Get the touch threshold."""
        buf = bytearray(1)
        register = 0x41 + 2 * self._channel  # MPR121_TOUCHTH_0 + 2 * channel
        self._mpr121._read_register_bytes(register, buf, 1)
        log_i2c_read(self._mpr121._address, register, 1, f"MPR121_Channel[{self._channel}].threshold")
        return buf[0]
    
    @threshold.setter
    def threshold(self, new_thresh):
        """Set the touch threshold."""
        register = 0x41 + 2 * self._channel  # MPR121_TOUCHTH_0 + 2 * channel
        self._mpr121._write_register_byte(register, new_thresh)
        log_i2c_write(self._mpr121._address, register, new_thresh, f"MPR121_Channel[{self._channel}].threshold")
    
    @property
    def release_threshold(self):
        """Get the release threshold."""
        buf = bytearray(1)
        register = 0x42 + 2 * self._channel  # MPR121_RELEASETH_0 + 2 * channel
        self._mpr121._read_register_bytes(register, buf, 1)
        log_i2c_read(self._mpr121._address, register, 1, f"MPR121_Channel[{self._channel}].release_threshold")
        return buf[0]
    
    @release_threshold.setter
    def release_threshold(self, new_thresh):
        """Set the release threshold."""
        register = 0x42 + 2 * self._channel  # MPR121_RELEASETH_0 + 2 * channel
        self._mpr121._write_register_byte(register, new_thresh)
        log_i2c_write(self._mpr121._address, register, new_thresh, f"MPR121_Channel[{self._channel}].release_threshold")

class LoggedMPR121:
    """Logged wrapper for MPR121 with comprehensive I2C logging."""
    
    def __init__(self, i2c, address=0x5A):
        """Initialize the logged MPR121 wrapper."""
        self._mpr121 = adafruit_mpr121.MPR121(i2c, address)
        self._i2c = i2c
        self._address = address
        # Use simple list without type hints for CircuitPython compatibility
        self._channels = [None] * 12
        if ENABLE_I2C_DEBUG_LOGGING:
            logger.debug(lazy_format("LoggedMPR121 initialized at 0x{:02X}", address))
    
    def __getitem__(self, key):
        """Get a channel wrapper."""
        if key < 0 or key > 11:
            raise IndexError("pin must be a value 0-11")
        if self._channels[key] is None:
            self._channels[key] = LoggedMPR121Channel(self, key)
        return self._channels[key]
    
    @property
    def touched_pins(self):
        """Get a tuple of the touched state for all pins."""
        touched = self.touched()
        return tuple(bool(touched >> i & 1) for i in range(12))
    
    def _write_register_byte(self, register, value):
        """Write a byte value to the specified register with logging."""
        log_i2c_write(self._address, register, value, f"MPR121._write_register_byte")
        self._mpr121._write_register_byte(register, value)
    
    def _read_register_bytes(self, register, result, length=None):
        """Read register bytes with logging."""
        if length is None:
            length = len(result)
        log_i2c_read(self._address, register, length, f"MPR121._read_register_bytes")
        self._mpr121._read_register_bytes(register, result, length)
    
    def reset(self):
        """Reset the MPR121 with logging."""
        if ENABLE_I2C_DEBUG_LOGGING:
            logger.debug(lazy_format("MPR121 0x{:02X} reset started", self._address))
        
        # Log all the register writes during reset
        self._mpr121.reset()
        
        if ENABLE_I2C_DEBUG_LOGGING:
            logger.debug(lazy_format("MPR121 0x{:02X} reset completed", self._address))
    
    def filtered_data(self, pin):
        """Get the filtered data register value with logging."""
        if pin < 0 or pin > 11:
            raise ValueError("Pin must be a value 0-11.")
        
        register = 0x04 + pin * 2  # MPR121_FILTDATA_0L + pin * 2
        log_i2c_read(self._address, register, 2, f"MPR121.filtered_data({pin})")
        
        result = self._mpr121.filtered_data(pin)
        if ENABLE_I2C_DEBUG_LOGGING:
            logger.debug(lazy_format("MPR121 0x{:02X} filtered_data({}) = {}", self._address, pin, result))
        return result
    
    def baseline_data(self, pin):
        """Get the baseline data register value with logging."""
        if pin < 0 or pin > 11:
            raise ValueError("Pin must be a value 0-11.")
        
        register = 0x1E + pin  # MPR121_BASELINE_0 + pin
        log_i2c_read(self._address, register, 1, f"MPR121.baseline_data({pin})")
        
        result = self._mpr121.baseline_data(pin)
        if ENABLE_I2C_DEBUG_LOGGING:
            logger.debug(lazy_format("MPR121 0x{:02X} baseline_data({}) = {}", self._address, pin, result))
        return result
    
    def touched(self):
        """Get the touch state of all pins with logging."""
        register = 0x00  # MPR121_TOUCHSTATUS_L
        log_i2c_read(self._address, register, 2, f"MPR121.touched()")
        
        result = self._mpr121.touched()
        if ENABLE_I2C_DEBUG_LOGGING:
            logger.debug(lazy_format("MPR121 0x{:02X} touched() = 0x{:04X}", self._address, result))
        return result
    
    def is_touched(self, pin):
        """Get if pin is being touched with logging."""
        if pin < 0 or pin > 11:
            raise ValueError("Pin must be a value 0-11.")
        
        touches = self.touched()  # This will be logged by touched()
        result = (touches & (1 << pin)) > 0
        if ENABLE_I2C_DEBUG_LOGGING:
            logger.debug(lazy_format("MPR121 0x{:02X} is_touched({}) = {}", self._address, pin, result))
        return result

def create_logged_mpr121(i2c, address=0x5A):
    """Create a logged MPR121 instance."""
    return LoggedMPR121(i2c, address) 