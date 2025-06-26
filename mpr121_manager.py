import time
import board
import adafruit_mpr121
from config import (
    MPR121_DEFAULT_TOUCH_THRESHOLD, 
    MPR121_DEFAULT_RELEASE_THRESHOLD,
    SLIDERS,
    LED_CALIBRATION_DELAY,
    LED_CALIBRATION_ENABLED
)
from logger import get_logger, LogLevel, lazy_format

# Get logger instance
logger = get_logger()

# -----------------------------------------------------------------------------
# I2C Bus Setup and Scanner
# -----------------------------------------------------------------------------
i2c = board.STEMMA_I2C()

def scan_i2c():
    """Scan the I2C bus for connected devices and print their addresses."""
    while not i2c.try_lock():
        pass

    try:
        found = i2c.scan()
        if found:
            suffix = "s" if len(found) > 1 else ""
            logger.info(lazy_format("Found {} I2C device{}:", len(found), suffix))
            for addr in found:
                logger.info(lazy_format("  • 0x{:02X}", addr))
        else:
            logger.warn("No I2C devices found.")
    finally:
        i2c.unlock()

# -----------------------------------------------------------------------------
# LED Startup Calibration Management
# -----------------------------------------------------------------------------
class LEDCalibrationManager:
    """Manages LED startup calibration to handle electrical interference."""
    
    def __init__(self):
        self.first_midi_received = False
        self.first_midi_time = None
        self.led_calibration_triggered = False
        self.led_calibration_completed = False
    
    def on_midi_received(self, current_time):
        """Called when first MIDI message is received."""
        if not self.first_midi_received:
            self.first_midi_received = True
            self.first_midi_time = current_time
            logger.info("First MIDI message received - LED startup calibration timer started")
    
    def should_trigger_led_calibration(self, current_time):
        """Check if LED calibration should be triggered."""
        if not LED_CALIBRATION_ENABLED:
            return False
        
        if self.led_calibration_triggered or self.led_calibration_completed:
            return False
        
        if not self.first_midi_received or self.first_midi_time is None:
            return False
        
        time_since_first_midi = current_time - self.first_midi_time
        return time_since_first_midi >= LED_CALIBRATION_DELAY
    
    def mark_led_calibration_triggered(self):
        """Mark that LED calibration has been triggered."""
        self.led_calibration_triggered = True
    
    def mark_led_calibration_completed(self):
        """Mark that LED calibration has been completed."""
        self.led_calibration_completed = True
        logger.info("LED startup calibration completed")

# Global LED calibration manager
led_calibration_manager = LEDCalibrationManager()

def get_led_calibration_manager():
    """Get the global LED calibration manager."""
    return led_calibration_manager

# -----------------------------------------------------------------------------
# MPR121 Sensitivity Control Functions
# -----------------------------------------------------------------------------
def test_threshold_configuration(mpr, pin):
    """Test if threshold configuration is working properly."""
    try:
        # Set a known threshold
        test_threshold = 20
        mpr.touch_threshold(pin, test_threshold)
        
        # Read it back
        actual_threshold = mpr.touch_threshold(pin)
        
        if actual_threshold != test_threshold:
            logger.warn(lazy_format("Threshold configuration bug detected on pin {}!", pin))
            logger.debug(lazy_format("Set: {}, Read: {}", test_threshold, actual_threshold))
            return False
        return True
    except Exception as e:
        logger.error(lazy_format("Error testing threshold configuration on pin {}: {}", pin, e))
        return False

def configure_mpr121_sensitivity(mpr, pin, touch_threshold=None, release_threshold=None):
    """Configure MPR121 sensitivity for a specific pin using default thresholds."""
    try:
        # Use default thresholds if not specified
        if touch_threshold is None:
            touch_threshold = MPR121_DEFAULT_TOUCH_THRESHOLD
        if release_threshold is None:
            release_threshold = MPR121_DEFAULT_RELEASE_THRESHOLD
        
        # Set touch threshold (lower = more sensitive)
        mpr.touch_threshold(pin, touch_threshold)
        
        # Set release threshold (lower = faster release)
        mpr.release_threshold(pin, release_threshold)
        
        logger.debug(lazy_format("  Pin {}: Touch={}, Release={}", pin, touch_threshold, release_threshold))
        return True
        
    except Exception as e:
        logger.error(lazy_format("Error configuring sensitivity for pin {}: {}", pin, e))
        return False

def check_baseline_stability(mpr, pin, samples=5):
    """Check if baseline is stable by taking multiple readings."""
    try:
        readings = []
        for _ in range(samples):
            readings.append(mpr.baseline_data(pin))
            time.sleep(0.01)
        
        variation = max(readings) - min(readings)
        return variation < 5, variation  # Stable if variation < 5
    except Exception as e:
        logger.error(lazy_format("Error checking baseline stability for pin {}: {}", pin, e))
        return False, 0

def allow_calibration_time(mpr, pin, duration=0.2):
    """Allow time for baseline calibration and check if it stabilizes."""
    try:
        start_baseline = mpr.baseline_data(pin)
        time.sleep(duration)
        end_baseline = mpr.baseline_data(pin)
        
        # Check if baseline has stabilized
        stability = abs(end_baseline - start_baseline) < 3
        return stability, start_baseline, end_baseline
    except Exception as e:
        logger.error(lazy_format("Error during calibration time check for pin {}: {}", pin, e))
        return False, 0, 0

def monitor_calibration_health(mpr, addr):
    """Monitor MPR121 calibration health for all pins."""
    logger.info(lazy_format("MPR121 0x{:02X} Calibration Health:", addr))
    
    for config in SLIDERS:
        if config["mpr121_address"] == addr:
            for pin in [config["down_pin"], config["up_pin"]]:
                try:
                    baseline = mpr.baseline_data(pin)
                    filtered = mpr.filtered_data(pin)
                    delta = baseline - filtered
                    
                    # Check baseline stability
                    is_stable, variation = check_baseline_stability(mpr, pin)
                    
                    # Check calibration health
                    health_status = "Healthy"
                    warnings = []
                    
                    if baseline < 50 or baseline > 200:
                        health_status = "WARNING"
                        warnings.append(lazy_format("Baseline out of normal range ({})", baseline))
                    
                    if delta > 50:
                        health_status = "WARNING"
                        warnings.append(lazy_format("Large delta detected ({})", delta))
                    
                    if not is_stable:
                        health_status = "WARNING"
                        warnings.append(lazy_format("Unstable baseline (variation: {})", variation))
                    
                    # Log status based on health
                    if health_status == "Healthy":
                        logger.debug(lazy_format("  Pin {}: {} - Baseline={}, Filtered={}, Delta={}, Stable={}", 
                                               pin, health_status, baseline, filtered, delta, is_stable))
                    else:
                        logger.warn(lazy_format("  Pin {}: {} - Baseline={}, Filtered={}, Delta={}, Stable={}", 
                                              pin, health_status, baseline, filtered, delta, is_stable))
                    
                    if warnings:
                        for warning in warnings:
                            logger.warn(lazy_format("    ⚠️  {}", warning))
                    
                except Exception as e:
                    logger.error(lazy_format("  Pin {}: ERROR - {}", pin, e))

def log_sensitivity_data(mpr, addr):
    """Log sensitivity data for debugging."""
    logger.debug(lazy_format("MPR121 0x{:02X} Sensitivity Data:", addr))
    for config in SLIDERS:
        if config["mpr121_address"] == addr:
            for pin in [config["down_pin"], config["up_pin"]]:
                try:
                    baseline = mpr.baseline_data(pin)
                    filtered = mpr.filtered_data(pin)
                    touch_thresh = mpr.touch_threshold(pin)
                    release_thresh = mpr.release_threshold(pin)
                    logger.debug(lazy_format("  Pin {}: Baseline={}, Filtered={}, Touch={}, Release={}", 
                                           pin, baseline, filtered, touch_thresh, release_thresh))
                except Exception as e:
                    logger.error(lazy_format("  Pin {}: Error reading data - {}", pin, e))

def setup_mpr121_sensitivity(mpr121_boards):
    """Setup MPR121 sensitivity with error checking for all boards."""
    logger.info("MPR121 Sensitivity Configuration")
    
    for addr, mpr in mpr121_boards.items():
        logger.info(lazy_format("Configuring MPR121 at 0x{:02X}", addr))
        
        # Reset and wait for stabilization
        try:
            mpr.reset()
            time.sleep(0.2)
            logger.debug("  Reset completed")
        except Exception as e:
            logger.error(lazy_format("  Error during reset: {}", e))
            continue
        
        # Allow initial calibration time
        logger.debug("  Allowing initial calibration time...")
        time.sleep(0.5)  # Give extra time for baseline stabilization
        
        # Configure each pin with error checking
        pins_configured = 0
        for config in SLIDERS:
            if config["mpr121_address"] == addr:
                for pin in [config["down_pin"], config["up_pin"]]:
                    try:
                        # Test threshold configuration
                        if not test_threshold_configuration(mpr, pin):
                            logger.debug(lazy_format("  Using default configuration for pin {}", pin))
                        
                        # Configure sensitivity with default thresholds
                        if configure_mpr121_sensitivity(mpr, pin):
                            pins_configured += 1
                        
                        # Allow calibration time for this pin
                        is_stable, start_baseline, end_baseline = allow_calibration_time(mpr, pin)
                        if not is_stable:
                            logger.debug(lazy_format("  Pin {}: Baseline still adjusting ({} -> {})", 
                                                   pin, start_baseline, end_baseline))
                        
                    except Exception as e:
                        logger.error(lazy_format("  Error configuring pin {}: {}", pin, e))
        
        logger.info(lazy_format("  Successfully configured {} pins", pins_configured))
        
        # Monitor calibration health
        monitor_calibration_health(mpr, addr)
        
        # Log sensitivity data
        log_sensitivity_data(mpr, addr)

def perform_led_startup_calibration(mpr121_boards):
    """Perform calibration after LED startup to handle electrical interference."""
    logger.info("=== LED Startup Calibration ===")
    logger.info("Re-calibrating MPR121 sensors after LED startup...")
    
    for addr, mpr in mpr121_boards.items():
        logger.info(lazy_format("Re-calibrating MPR121 at 0x{:02X}", addr))
        
        try:
            # Reset the MPR121 to clear any interference effects
            mpr.reset()
            time.sleep(0.3)  # Give extra time for reset and stabilization
            logger.debug("  Reset completed")
            
            # Allow extended calibration time for LED interference to stabilize
            logger.debug("  Allowing extended calibration time for LED interference...")
            time.sleep(1.0)  # Extended time for baseline stabilization
            
            # Re-configure each pin
            pins_configured = 0
            for config in SLIDERS:
                if config["mpr121_address"] == addr:
                    for pin in [config["down_pin"], config["up_pin"]]:
                        try:
                            # Configure sensitivity with default thresholds
                            if configure_mpr121_sensitivity(mpr, pin):
                                pins_configured += 1
                            
                            # Allow calibration time for this pin
                            is_stable, start_baseline, end_baseline = allow_calibration_time(mpr, pin, duration=0.5)
                            if not is_stable:
                                logger.debug(lazy_format("  Pin {}: Baseline adjusting with LED interference ({} -> {})", 
                                                       pin, start_baseline, end_baseline))
                            
                        except Exception as e:
                            logger.error(lazy_format("  Error re-configuring pin {}: {}", pin, e))
            
            logger.info(lazy_format("  Successfully re-configured {} pins", pins_configured))
            
            # Monitor calibration health after LED startup
            monitor_calibration_health(mpr, addr)
            
        except Exception as e:
            logger.error(lazy_format("  Error during LED startup calibration for MPR121 0x{:02X}: {}", addr, e))
    
    logger.info("LED startup calibration completed")

def periodic_calibration_check(mpr121_boards):
    """Perform periodic calibration health check (can be called during operation)."""
    logger.info("Periodic Calibration Health Check")
    
    for addr, mpr in mpr121_boards.items():
        monitor_calibration_health(mpr, addr)

def initialize_mpr121_boards():
    """Initialize all MPR121 boards and return the board dictionary with robust error handling."""
    mpr121_boards = {}
    expected_addresses = set(slider["mpr121_address"] for slider in SLIDERS)
    successful_initializations = 0
    failed_initializations = 0
    
    logger.info("Initializing MPR121 boards...")
    logger.info(lazy_format("Expected MPR121 addresses: {}", [hex(addr) for addr in expected_addresses]))
    
    for addr in expected_addresses:
        try:
            # Test I2C communication first
            if not _test_mpr121_i2c_communication(addr):
                logger.warn(lazy_format("MPR121 at 0x{:02X} not responding on I2C - skipping", addr))
                failed_initializations += 1
                continue
            
            # Try to initialize the MPR121
            mpr = adafruit_mpr121.MPR121(i2c, address=addr)
            mpr121_boards[addr] = mpr
            logger.info(lazy_format("MPR121 initialized at 0x{:02X}", addr))
            
            # Configure touch thresholds
            try:
                mpr.reset()
                time.sleep(0.1)
                logger.debug(lazy_format("  Reset completed for 0x{:02X}", addr))
            except Exception as e:
                logger.warn(lazy_format("  Reset failed for 0x{:02X}: {}", addr, e))
            
            # Debug: Print baseline data
            if logger.is_debug_enabled():
                try:
                    baseline = [(i, mpr.baseline_data(i), mpr.filtered_data(i)) for i in range(12)]
                    logger.debug(lazy_format("MPR121 0x{:02X} baseline data: {}", addr, baseline))
                except Exception as e:
                    logger.warn(lazy_format("  Could not read baseline data for 0x{:02X}: {}", addr, e))
            
            successful_initializations += 1
            
        except ValueError as err:
            logger.error(lazy_format("Failed to initialize MPR121 at 0x{:02X}: {}", addr, err))
            failed_initializations += 1
        except Exception as err:
            logger.error(lazy_format("Unexpected error initializing MPR121 at 0x{:02X}: {}", addr, err))
            failed_initializations += 1
    
    # Summary
    logger.info(lazy_format("MPR121 initialization complete: {} successful, {} failed", 
                           successful_initializations, failed_initializations))
    
    if successful_initializations == 0:
        logger.error("No MPR121 boards were successfully initialized!")
        logger.warn("System will continue but touch functionality will not work")
    elif failed_initializations > 0:
        logger.warn(lazy_format("Some MPR121 boards failed to initialize - {} sliders may not work", 
                               failed_initializations * 2))  # Each board has 2 sliders
    
    return mpr121_boards

def _test_mpr121_i2c_communication(addr):
    """Test if I2C communication works for a specific MPR121 address."""
    try:
        # Try to lock the I2C bus
        if not i2c.try_lock():
            logger.warn("Could not lock I2C bus for MPR121 test")
            return False
        
        try:
            # Scan for devices
            found = i2c.scan()
            if addr in found:
                logger.debug(lazy_format("MPR121 found at 0x{:02X}", addr))
                return True
            else:
                logger.debug(lazy_format("No device found at 0x{:02X}", addr))
                return False
        finally:
            i2c.unlock()
            
    except Exception as e:
        logger.error(lazy_format("I2C communication test failed for 0x{:02X}: {}", addr, e))
        return False

def get_mpr121_status(mpr121_boards):
    """Get status information about MPR121 boards."""
    expected_addresses = set(slider["mpr121_address"] for slider in SLIDERS)
    connected_addresses = set(mpr121_boards.keys())
    missing_addresses = expected_addresses - connected_addresses
    
    return {
        "expected_count": len(expected_addresses),
        "connected_count": len(connected_addresses),
        "missing_count": len(missing_addresses),
        "connected_addresses": [hex(addr) for addr in connected_addresses],
        "missing_addresses": [hex(addr) for addr in missing_addresses],
        "all_connected": len(missing_addresses) == 0
    } 