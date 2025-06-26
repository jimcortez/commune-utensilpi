import displayio
import terminalio
import adafruit_displayio_ssd1306
from adafruit_display_text import label
from config import DISPLAY_I2C_ADDRESS, DISPLAY_WIDTH, DISPLAY_HEIGHT, SLIDERS
from logger import get_logger, lazy_format

# Get logger instance
logger = get_logger()

# Release any existing displays
displayio.release_displays()

class DisplayManager:
    def __init__(self, i2c):
        self.i2c = i2c
        self.display_enabled = False
        self.display = None
        self.splash = None
        self.slider_labels = []
        self.initialization_error = None
        
        self._initialize_display()
    
    def _initialize_display(self):
        """Initialize the OLED display with robust error handling."""
        try:
            # Test I2C communication first
            if not self._test_i2c_communication():
                logger.warn("Display I2C communication failed - display disabled")
                self.display_enabled = False
                return
            
            # Try to initialize the display
            display_bus = displayio.I2CDisplay(self.i2c, device_address=DISPLAY_I2C_ADDRESS)
            self.display = adafruit_displayio_ssd1306.SSD1306(
                display_bus, 
                width=DISPLAY_WIDTH, 
                height=DISPLAY_HEIGHT
            )
            self.splash = displayio.Group()
            self.display.root_group = self.splash
            self.display_enabled = True
            logger.info("Display initialized successfully")
            
        except ValueError as err:
            self.initialization_error = str(err)
            logger.warn(lazy_format("Display initialization failed: {}", err))
            logger.info("System will continue without display")
            self.display_enabled = False
        except Exception as err:
            self.initialization_error = str(err)
            logger.error(lazy_format("Unexpected display error: {}", err))
            logger.info("System will continue without display")
            self.display_enabled = False
    
    def _test_i2c_communication(self):
        """Test if I2C communication works for the display address."""
        try:
            # Try to lock the I2C bus
            if not self.i2c.try_lock():
                logger.warn("Could not lock I2C bus for display test")
                return False
            
            try:
                # Scan for devices at the display address
                found = self.i2c.scan()
                if DISPLAY_I2C_ADDRESS in found:
                    logger.debug(lazy_format("Display found at 0x{:02X}", DISPLAY_I2C_ADDRESS))
                    return True
                else:
                    logger.warn(lazy_format("No display found at 0x{:02X}", DISPLAY_I2C_ADDRESS))
                    logger.debug(lazy_format("Available I2C devices: {}", [hex(addr) for addr in found]))
                    return False
            finally:
                self.i2c.unlock()
                
        except Exception as e:
            logger.error(lazy_format("I2C communication test failed: {}", e))
            return False
    
    def setup_display(self, touch_sliders):
        """Initialize display labels with error handling."""
        if not self.display_enabled:
            logger.info("Display not enabled, skipping setup")
            return
        
        if self.splash is None:
            logger.warn("Display splash is None, cannot setup labels")
            return
        
        try:
            self.slider_labels = []
            NUM_COLS = 2
            NUM_ROWS = 4
            COL_WIDTH = 64
            ROW_HEIGHT = 12
            
            for i, _ in enumerate(touch_sliders):
                if i >= NUM_COLS * NUM_ROWS:
                    break
                    
                col = i // NUM_ROWS
                row = i % NUM_ROWS
                x_pos = col * COL_WIDTH
                y_pos = (row * ROW_HEIGHT) + 12

                text_label = label.Label(
                    font=terminalio.FONT,
                    text=f"S{i}: {SLIDERS[i]['initial_value']}",
                    color=0xFFFF,
                    x=x_pos,
                    y=y_pos
                )
                self.slider_labels.append(text_label)
                self.splash.append(text_label)
            
            logger.info(lazy_format("Display setup complete with {} labels", len(self.slider_labels)))
            
        except Exception as e:
            logger.error(lazy_format("Error setting up display labels: {}", e))
            logger.info("System will continue without display labels")
            self.slider_labels = []
    
    def update_display(self, touch_sliders):
        """Update display with current slider states with error handling."""
        if not self.display_enabled:
            return
        
        if not self.slider_labels:
            return
            
        try:
            for i, slider in enumerate(touch_sliders):
                if i >= len(self.slider_labels):
                    break
                    
                status = 'B' if slider.both_pressed else (
                    'D' if slider.down_debouncer.value else (
                    'U' if slider.up_debouncer.value else ''))
                
                cc_num = (slider.config["both_press_cc"] if slider.both_pressed 
                         else slider.config["cc_number"])
                val = "127" if slider.both_pressed else f"{int(slider.value):03}"
                
                self.slider_labels[i].text = f"{i}|{cc_num:02}|{val}|{status}"
                
        except Exception as e:
            logger.error(lazy_format("Error updating display: {}", e))
            # Don't disable display on update errors, just log them
    
    def is_enabled(self):
        """Check if display is enabled."""
        return self.display_enabled
    
    def get_status(self):
        """Get display status information."""
        if self.display_enabled:
            return {
                "enabled": True,
                "labels_configured": len(self.slider_labels),
                "error": None
            }
        else:
            return {
                "enabled": False,
                "labels_configured": 0,
                "error": self.initialization_error
            } 