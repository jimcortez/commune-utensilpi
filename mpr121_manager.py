import time
import board
import adafruit_mpr121
from i2c_logger import log_batch_read, log_i2c_read, log_i2c_write, log_i2c_scan
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
        log_i2c_scan(found, "scan_i2c")
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
# Optimized MPR121 Batch Reading Methods
# -----------------------------------------------------------------------------
def get_all_sensor_data(mpr):
    """
    Read all touch, baseline, and filtered data in minimal I2C calls.
    
    Returns:
        tuple: (touched_state, baselines, filtered_data)
        - touched_state: 12-bit integer representing touch states
        - baselines: list of 12 baseline values (0-1020)
        - filtered_data: list of 12 filtered data values (0-65535)
    """
    try:
        # 1 I2C call for touch status (registers 0x00-0x01)
        touched = mpr.touched()
        
        # 1 I2C call for all baselines (registers 0x1E-0x29)
        baseline_buf = bytearray(12)
        mpr._read_register_bytes(0x1E, baseline_buf, 12)  # MPR121_BASELINE_0 = 0x1E
        log_batch_read(mpr._address, 0x1E, 12, "get_all_sensor_data.baselines")
        baselines = [baseline_buf[i] << 2 for i in range(12)]
        
        # 1 I2C call for all filtered data (registers 0x04-0x1B)
        filtered_buf = bytearray(24)  # 12 pins × 2 bytes each
        mpr._read_register_bytes(0x04, filtered_buf, 24)  # MPR121_FILTDATA_0L = 0x04
        log_batch_read(mpr._address, 0x04, 24, "get_all_sensor_data.filtered")
        filtered = [((filtered_buf[i*2+1] << 8) | filtered_buf[i*2]) & 0xFFFF for i in range(12)]
        
        return touched, baselines, filtered
        
    except Exception as e:
        logger.error(lazy_format("Error in batch sensor data read: {}", e))
        # Fallback to individual reads if batch read fails
        return _fallback_sensor_data_read(mpr)

def _fallback_sensor_data_read(mpr):
    """Fallback method using individual pin reads if batch read fails."""
    try:
        touched = mpr.touched()
        baselines = [mpr.baseline_data(i) for i in range(12)]
        filtered = [mpr.filtered_data(i) for i in range(12)]
        return touched, baselines, filtered
    except Exception as e:
        logger.error(lazy_format("Fallback sensor data read also failed: {}", e))
        return 0, [0] * 12, [0] * 12

def get_all_baselines(mpr):
    """
    Read all baseline data in a single I2C call.
    
    Returns:
        list: 12 baseline values (0-1020)
    """
    try:
        baseline_buf = bytearray(12)
        mpr._read_register_bytes(0x1E, baseline_buf, 12)  # MPR121_BASELINE_0 = 0x1E
        log_batch_read(mpr._address, 0x1E, 12, "get_all_baselines")
        return [baseline_buf[i] << 2 for i in range(12)]
    except Exception as e:
        logger.error(lazy_format("Error in batch baseline read: {}", e))
        # Fallback to individual reads
        return [mpr.baseline_data(i) for i in range(12)]

def get_all_filtered_data(mpr):
    """
    Read all filtered data in a single I2C call.
    
    Returns:
        list: 12 filtered data values (0-65535)
    """
    try:
        filtered_buf = bytearray(24)  # 12 pins × 2 bytes each
        mpr._read_register_bytes(0x04, filtered_buf, 24)  # MPR121_FILTDATA_0L = 0x04
        log_batch_read(mpr._address, 0x04, 24, "get_all_filtered_data")
        return [((filtered_buf[i*2+1] << 8) | filtered_buf[i*2]) & 0xFFFF for i in range(12)]
    except Exception as e:
        logger.error(lazy_format("Error in batch filtered data read: {}", e))
        # Fallback to individual reads
        return [mpr.filtered_data(i) for i in range(12)]

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
            if LED_CALIBRATION_ENABLED:
                logger.info("First MIDI message received - LED startup calibration timer started")
            else:
                logger.debug("First MIDI message received (LED calibration disabled)")
    
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
def has_threshold_methods(mpr):
    """Check if the MPR121 object has threshold configuration methods."""
    return hasattr(mpr, '__getitem__')  # Check if channel access is available

def test_threshold_configuration(mpr, pin):
    """Test if threshold configuration is working properly."""
    try:
        # Check if threshold methods are available
        if not has_threshold_methods(mpr):
            logger.debug(lazy_format("Threshold configuration not available on pin {} - using defaults", pin))
            return True  # Not an error, just not supported
        
        # Set a known threshold using the correct channel access method
        test_threshold = 20
        mpr[pin].threshold = test_threshold
        
        # Read it back
        actual_threshold = mpr[pin].threshold
        
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
        # Check if threshold methods are available
        if not has_threshold_methods(mpr):
            logger.debug(lazy_format("Threshold configuration not available on pin {} - using defaults", pin))
            return True  # Not an error, just not supported
        
        # Use default thresholds if not specified
        if touch_threshold is None:
            touch_threshold = MPR121_DEFAULT_TOUCH_THRESHOLD
        if release_threshold is None:
            release_threshold = MPR121_DEFAULT_RELEASE_THRESHOLD
        
        # Set touch threshold (lower = more sensitive)
        mpr[pin].threshold = touch_threshold
        
        # Set release threshold (lower = faster release)
        mpr[pin].release_threshold = release_threshold
        
        logger.debug(lazy_format("  Pin {}: Touch={}, Release={}", pin, touch_threshold, release_threshold))
        return True
        
    except Exception as e:
        logger.error(lazy_format("Error configuring sensitivity for pin {}: {}", pin, e))
        return False

def check_baseline_stability(mpr, pin, samples=5):
    """Check if baseline is stable by taking multiple readings using batch reads."""
    try:
        readings = []
        for _ in range(samples):
            # Use batch read to get all baselines at once
            baselines = get_all_baselines(mpr)
            readings.append(baselines[pin])
            time.sleep(0.01)
        
        variation = max(readings) - min(readings)
        return variation < 20, variation  # Stable if variation < 20 (5*4 corrected scale)
    except Exception as e:
        logger.error(lazy_format("Error checking baseline stability for pin {}: {}", pin, e))
        return False, 0

def allow_calibration_time(mpr, pin, duration=0.2):
    """Allow time for baseline calibration and check if it stabilizes using batch reads."""
    try:
        # Use batch read to get all baselines at once
        start_baselines = get_all_baselines(mpr)
        start_baseline = start_baselines[pin]
        time.sleep(duration)
        end_baselines = get_all_baselines(mpr)
        end_baseline = end_baselines[pin]
        
        # Check if baseline has stabilized
        stability = abs(end_baseline - start_baseline) < 3
        return stability, start_baseline, end_baseline
    except Exception as e:
        logger.error(lazy_format("Error during calibration time check for pin {}: {}", pin, e))
        return False, 0, 0

def monitor_calibration_health(mpr, addr):
    """Monitor MPR121 calibration health for all pins using optimized batch reads."""
    logger.info(lazy_format("MPR121 0x{:02X} Calibration Health:", addr))
    
    try:
        # Single batch read for all sensor data (3 I2C calls instead of 36+)
        touched_state, baselines, filtered_data = get_all_sensor_data(mpr)
        
        for config in SLIDERS:
            if config["mpr121_address"] == addr:
                for pin in [config["down_pin"], config["up_pin"]]:
                    try:
                        baseline = baselines[pin]
                        filtered = filtered_data[pin]
                        delta = baseline - filtered
                        
                        # Check if pin is currently being touched
                        is_touched = bool(touched_state & (1 << pin))
                        
                        # Check baseline stability
                        is_stable, variation = check_baseline_stability(mpr, pin)
                        
                        # Check calibration health
                        health_status = "Healthy"
                        warnings = []
                        recommendations = []
                        
                        # Check if pin is being touched during calibration
                        if is_touched:
                            health_status = "WARNING"
                            warnings.append("Sensor is currently being touched - this affects calibration")
                            recommendations.append("Remove any objects touching the sensor")
                            recommendations.append("Wait for sensor to stabilize without touch")
                            recommendations.append("Check if utensil is accidentally touching the sensor")
                        
                        # Check baseline range (MPR121 baseline is 0-1020, but varies by environment)
                        if baseline < 40:  # 10 * 4 (very low baseline indicates issues)
                            health_status = "WARNING"
                            if is_touched:
                                warnings.append(lazy_format("Baseline very low ({}) - likely due to current touch", baseline))
                            else:
                                warnings.append(lazy_format("Baseline very low ({}) - may indicate electrical interference", baseline))
                                recommendations.append("Check for electrical interference from nearby components")
                                recommendations.append("Try cleaning the sensor area")
                                recommendations.append("Verify sensor connections are secure")
                        elif baseline > 1018:  # Only warn for extremely high baseline (very close to max 1020)
                            health_status = "WARNING"
                            warnings.append(lazy_format("Baseline extremely high ({}) - sensor may be dirty or poorly connected", baseline))
                            recommendations.append("Clean the sensor surface")
                            recommendations.append("Check electrical connections")
                            recommendations.append("Verify sensor is properly grounded")
                        
                        # Check delta (difference between baseline and filtered)
                        # MPR121 touch threshold is typically 12, so significant deltas should be >48 (12*4)
                        if delta > 48:  # 12 * 4 (corrected scale)
                            health_status = "WARNING"
                            if is_touched:
                                warnings.append(lazy_format("Large delta detected ({}) - sensor is detecting touch", delta))
                            else:
                                warnings.append(lazy_format("Large delta detected ({}) - sensor may be interfered with", delta))
                                recommendations.append("Check for electrical interference")
                                recommendations.append("Verify sensor is not near metal objects")
                        elif delta < -48:  # -12 * 4 (corrected scale)
                            health_status = "WARNING"
                            warnings.append(lazy_format("Negative delta detected ({}) - filtered data higher than baseline", delta))
                            recommendations.append("This is unusual - check for electrical interference")
                            recommendations.append("Try resetting the MPR121 board")
                            recommendations.append("Verify sensor connections and grounding")
                        
                        # Check stability
                        if not is_stable:
                            health_status = "WARNING"
                            warnings.append(lazy_format("Unstable baseline (variation: {}) - sensor is still calibrating", variation))
                            recommendations.append("Wait for sensor to finish calibrating")
                            recommendations.append("Check for environmental changes")
                            recommendations.append("Ensure sensor is not being touched")
                        
                        # Log status based on health
                        if health_status == "Healthy":
                            logger.debug(lazy_format("  Pin {}: {} - Baseline={}, Filtered={}, Delta={}, Stable={}, Touched={}", 
                                                   pin, health_status, baseline, filtered, delta, is_stable, is_touched))
                        else:
                            logger.warn(lazy_format("  Pin {}: {} - Baseline={}, Filtered={}, Delta={}, Stable={}, Touched={}", 
                                                  pin, health_status, baseline, filtered, delta, is_stable, is_touched))
                        
                        if warnings:
                            for warning in warnings:
                                logger.warn(lazy_format("    ⚠️  {}", warning))
                        
                        if recommendations:
                            logger.info(lazy_format("    💡 Recommendations for Pin {}:", pin))
                            for rec in recommendations:
                                logger.info(lazy_format("      • {}", rec))
                        
                        # Special note about <closure> messages
                        if is_touched and baseline < 50:
                            logger.info(lazy_format("    📝 Note: The '<closure>' message you may see is from the Adafruit library"))
                            logger.info(lazy_format("    indicating the sensor detects a touch. This is normal when touching the sensor."))
                            logger.info(lazy_format("    For proper calibration, ensure no objects are touching the sensor."))
                        
                    except Exception as e:
                        logger.error(lazy_format("  Pin {}: ERROR - {}", pin, e))
                        
    except Exception as e:
        logger.error(lazy_format("Error in batch calibration health monitoring for MPR121 0x{:02X}: {}", addr, e))
        # Fallback to individual pin monitoring
        _fallback_calibration_health_monitoring(mpr, addr)

def _fallback_calibration_health_monitoring(mpr, addr):
    """Fallback calibration health monitoring using individual pin reads."""
    logger.warn(lazy_format("Using fallback calibration monitoring for MPR121 0x{:02X}", addr))
    
    for config in SLIDERS:
        if config["mpr121_address"] == addr:
            for pin in [config["down_pin"], config["up_pin"]]:
                try:
                    baseline = mpr.baseline_data(pin)
                    filtered = mpr.filtered_data(pin)
                    delta = baseline - filtered
                    is_touched = mpr.touched_pins[pin]
                    
                    logger.debug(lazy_format("  Pin {}: Baseline={}, Filtered={}, Delta={}, Touched={}", 
                                           pin, baseline, filtered, delta, is_touched))
                    
                except Exception as e:
                    logger.error(lazy_format("  Pin {}: ERROR - {}", pin, e))

def log_sensitivity_data(mpr, addr):
    """Log sensitivity data for debugging using optimized batch reads."""
    logger.debug(lazy_format("MPR121 0x{:02X} Sensitivity Data:", addr))
    
    try:
        # Use batch read to get all sensor data at once
        touched_state, baselines, filtered_data = get_all_sensor_data(mpr)
        
        for config in SLIDERS:
            if config["mpr121_address"] == addr:
                for pin in [config["down_pin"], config["up_pin"]]:
                    try:
                        baseline = baselines[pin]
                        filtered = filtered_data[pin]
                        
                        # Check if threshold methods are available
                        if has_threshold_methods(mpr):
                            touch_thresh = mpr[pin].threshold
                            release_thresh = mpr[pin].release_threshold
                            logger.debug(lazy_format("  Pin {}: Baseline={}, Filtered={}, Touch={}, Release={}", 
                                                   pin, baseline, filtered, touch_thresh, release_thresh))
                        else:
                            logger.debug(lazy_format("  Pin {}: Baseline={}, Filtered={}, Touch=default, Release=default", 
                                                   pin, baseline, filtered))
                    except Exception as e:
                        logger.error(lazy_format("  Pin {}: Error reading data - {}", pin, e))
                        
    except Exception as e:
        logger.error(lazy_format("Error in batch sensitivity data read for MPR121 0x{:02X}: {}", addr, e))
        # Fallback to individual reads
        _fallback_sensitivity_data_read(mpr, addr)

def _fallback_sensitivity_data_read(mpr, addr):
    """Fallback sensitivity data read using individual pin reads."""
    logger.warn(lazy_format("Using fallback sensitivity data read for MPR121 0x{:02X}", addr))
    
    for config in SLIDERS:
        if config["mpr121_address"] == addr:
            for pin in [config["down_pin"], config["up_pin"]]:
                try:
                    baseline = mpr.baseline_data(pin)
                    filtered = mpr.filtered_data(pin)
                    
                    # Check if threshold methods are available
                    if has_threshold_methods(mpr):
                        touch_thresh = mpr[pin].threshold
                        release_thresh = mpr[pin].release_threshold
                        logger.debug(lazy_format("  Pin {}: Baseline={}, Filtered={}, Touch={}, Release={}", 
                                               pin, baseline, filtered, touch_thresh, release_thresh))
                    else:
                        logger.debug(lazy_format("  Pin {}: Baseline={}, Filtered={}, Touch=default, Release=default", 
                                               pin, baseline, filtered))
                except Exception as e:
                    logger.error(lazy_format("  Pin {}: Error reading data - {}", pin, e))

def setup_mpr121_sensitivity(mpr121_boards):
    """Setup MPR121 sensitivity with error checking for all boards."""
    logger.info("MPR121 Sensitivity Configuration")
    
    # Check if threshold configuration is supported
    if mpr121_boards:
        sample_mpr = next(iter(mpr121_boards.values()))
        if has_threshold_methods(sample_mpr):
            logger.info("Threshold configuration supported - configuring sensitivity")
        else:
            logger.info("Threshold configuration not supported - using default sensitivity")
    
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
    
    # Provide summary explanation
    logger.info("=== Calibration Data Explanation ===")
    logger.info("• Baseline: The sensor's reference level when not touched (typically 40-1018)")
    logger.info("• Filtered: Current sensor reading (changes when touched)")
    logger.info("• Delta: Difference between baseline and filtered (baseline - filtered)")
    logger.info("• Stable: Whether the baseline is consistent (True = good, False = still calibrating)")
    logger.info("• Touched: Whether the sensor currently detects a touch (True = being touched)")
    logger.info("")
    logger.info("MPR121 Default Thresholds (from Adafruit library):")
    logger.info("• Touch Threshold: 12 (triggers when delta > 12)")
    logger.info("• Release Threshold: 6 (releases when delta < 6)")
    logger.info("")
    logger.info("Normal operation:")
    logger.info("• Baseline: 40-1018, stable (varies by environment)")
    logger.info("• Delta: 0-48 when not touched, >48 when touched")
    logger.info("• Touched: False during calibration, True when utensil is touched")
    logger.info("")
    logger.info("Common issues:")
    logger.info("• Very low baseline (<40): Sensor may be touched or electrically interfered with")
    logger.info("• Extremely high baseline (>1018): Sensor may be dirty or poorly connected")
    logger.info("• Large delta when not touched: Electrical interference or sensor malfunction")
    logger.info("• Unstable baseline: Sensor still calibrating or environmental changes")
    logger.info("• Negative delta: Unusual - filtered data higher than baseline")

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
            
            # Use direct MPR121 initialization like the working old code
            mpr = adafruit_mpr121.MPR121(i2c, address=addr)
            mpr121_boards[addr] = mpr
            logger.info(lazy_format("MPR121 initialized at 0x{:02X}", addr))
            
            # Simple reset like the working old code
            try:
                mpr.reset()
                time.sleep(0.1)  # Same delay as working code
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
            log_i2c_scan(found, f"_test_mpr121_i2c_communication(0x{addr:02X})")
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