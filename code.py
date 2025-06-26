import time
import board

# Import our modular components
from config import (
    LOOP_DELAY, 
    CALIBRATION_CHECK_INTERVAL, 
    LOG_LEVEL, 
    LOG_TIMESTAMPS
)
from logger import get_logger, set_log_level, LogLevel, lazy_format
from mpr121_manager import (
    scan_i2c, 
    initialize_mpr121_boards, 
    setup_mpr121_sensitivity, 
    periodic_calibration_check,
    perform_led_startup_calibration,
    get_led_calibration_manager,
    get_mpr121_status
)
from midi_manager import MIDIManager
from display_manager import DisplayManager
from touch_slider import create_touch_sliders, update_touch_cache_for_all_boards, update_all_sliders, get_slider_status

# -----------------------------------------------------------------------------
# Main Application
# -----------------------------------------------------------------------------

def print_system_status(mpr121_boards, display_manager, touch_sliders):
    """Print comprehensive system status information."""
    logger = get_logger()
    logger.info("=== System Status ===")
    
    # MPR121 Status
    mpr121_status = get_mpr121_status(mpr121_boards)
    logger.info(lazy_format("MPR121 Boards: {}/{} connected", 
                           mpr121_status["connected_count"], mpr121_status["expected_count"]))
    
    if mpr121_status["missing_count"] > 0:
        logger.warn(lazy_format("Missing MPR121 boards: {}", mpr121_status["missing_addresses"]))
    
    # Display Status
    display_status = display_manager.get_status()
    if display_status["enabled"]:
        logger.info(lazy_format("Display: Enabled ({} labels configured)", display_status["labels_configured"]))
    else:
        logger.warn(lazy_format("Display: Disabled - {}", display_status["error"]))
    
    # Touch Slider Status
    slider_status = get_slider_status(touch_sliders)
    logger.info(lazy_format("Touch Sliders: {}/{} enabled", 
                           slider_status["enabled_sliders"], slider_status["total_sliders"]))
    
    if slider_status["disabled_sliders"] > 0:
        logger.warn(lazy_format("Disabled sliders: CC {}", slider_status["disabled_cc_numbers"]))
    
    # Overall System Health
    if mpr121_status["all_connected"] and slider_status["enabled_sliders"] == slider_status["total_sliders"]:
        logger.info("System Health: EXCELLENT - All components operational")
    elif slider_status["enabled_sliders"] > 0:
        logger.info("System Health: GOOD - Partial functionality available")
    else:
        logger.error("System Health: POOR - No touch functionality available")

def main():
    """Main application function."""
    # Configure logging based on config
    log_level_map = {
        "ERROR": LogLevel.ERROR,
        "WARN": LogLevel.WARN,
        "INFO": LogLevel.INFO,
        "DEBUG": LogLevel.DEBUG
    }
    set_log_level(log_level_map.get(LOG_LEVEL, LogLevel.INFO))
    
    logger = get_logger()
    logger.info("=== Commune Art Installation - Utensils ===")
    logger.info("Initializing system...")
    
    # Initialize I2C and scan for devices
    scan_i2c()
    
    # Initialize MIDI interface
    logger.info("Initializing MIDI interface...")
    try:
        midi_manager = MIDIManager()
        midi_available = True
    except Exception as e:
        logger.error(lazy_format("Failed to initialize MIDI interface: {}", e))
        logger.warn("System will continue without MIDI functionality")
        midi_available = False
        midi_manager = None
    
    # Initialize display
    logger.info("Initializing display...")
    i2c = board.STEMMA_I2C()
    display_manager = DisplayManager(i2c)
    
    # Initialize MPR121 boards
    logger.info("Initializing MPR121 boards...")
    mpr121_boards = initialize_mpr121_boards()
    
    # Setup MPR121 sensitivity with error handling
    if mpr121_boards:
        try:
            setup_mpr121_sensitivity(mpr121_boards)
        except Exception as e:
            logger.error(lazy_format("Error during MPR121 sensitivity setup: {}", e))
            logger.warn("Continuing with default sensitivity settings")
    else:
        logger.warn("No MPR121 boards available - skipping sensitivity setup")
    
    # Create touch sliders
    logger.info("Creating touch sliders...")
    if midi_available and mpr121_boards and midi_manager:
        touch_sliders = create_touch_sliders(mpr121_boards, midi_manager.get_interface())
    else:
        logger.warn("Cannot create touch sliders - missing MIDI or MPR121")
        touch_sliders = []
    
    # Setup display
    display_manager.setup_display(touch_sliders)
    
    # Initial display update
    display_manager.update_display(touch_sliders)
    
    # Calibration monitoring variables
    last_calibration_check = time.monotonic()
    
    # Get LED calibration manager
    led_calibration_manager = get_led_calibration_manager()
    
    # Print system status
    print_system_status(mpr121_boards, display_manager, touch_sliders)
    
    logger.info("=== System Ready ===")
    logger.info("Commune art installation is now running.")
    
    if touch_sliders:
        logger.info("Touch utensils to control MIDI values.")
    else:
        logger.warn("No touch sliders available - touch functionality disabled")
    
    if midi_available:
        logger.info("Waiting for first MIDI messages to start LED calibration timer...")
    else:
        logger.warn("MIDI not available - LED calibration will not work")
    
    logger.info("Press Ctrl+C to exit.")
    
    # Main loop
    try:
        while True:
            current_time = time.monotonic()
            
            # Process incoming MIDI messages
            if midi_available and midi_manager:
                midi_manager.receive_messages(touch_sliders, current_time)
            
            # Check if LED calibration should be triggered
            if led_calibration_manager.should_trigger_led_calibration(current_time):
                led_calibration_manager.mark_led_calibration_triggered()
                logger.info("Triggering LED startup calibration...")
                if mpr121_boards:
                    perform_led_startup_calibration(mpr121_boards)
                else:
                    logger.warn("No MPR121 boards available - skipping LED calibration")
                led_calibration_manager.mark_led_calibration_completed()
            
            # Update touch cache for all MPR121 boards (single I2C read per board)
            if mpr121_boards and touch_sliders:
                update_touch_cache_for_all_boards(mpr121_boards, touch_sliders)
            
            # Update all sliders using cached data
            if touch_sliders:
                display_needs_update = update_all_sliders(touch_sliders)
            else:
                display_needs_update = False
            
            # Update display if needed
            if display_needs_update:
                display_manager.update_display(touch_sliders)
            
            # Periodic calibration health check
            if current_time - last_calibration_check >= CALIBRATION_CHECK_INTERVAL:
                if mpr121_boards:
                    periodic_calibration_check(mpr121_boards)
                else:
                    logger.warn("No MPR121 boards available - skipping periodic calibration check")
                last_calibration_check = current_time
            
            time.sleep(LOOP_DELAY)
            
    except KeyboardInterrupt:
        logger.info("Shutting down Commune art installation...")
        logger.info("Thank you for experiencing the art piece!")
    except Exception as e:
        logger.error(lazy_format("Unexpected error in main loop: {}", e))
        logger.info("System will attempt to continue...")
        # Could add recovery logic here if needed

if __name__ == "__main__":
    main()
