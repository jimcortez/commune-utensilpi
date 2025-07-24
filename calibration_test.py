#!/usr/bin/env python3
# MPR121 Calibration Test Script
#
# This script helps diagnose MPR121 calibration issues and explains what the data means.

import time
import board
import adafruit_mpr121
from config import SLIDERS

def test_mpr121_calibration():
    """Test MPR121 calibration and provide detailed explanations."""
    print("=== MPR121 Calibration Test ===")
    
    # Initialize I2C
    i2c = board.STEMMA_I2C()
    
    # Scan for MPR121 boards
    print("Scanning for MPR121 boards...")
    while not i2c.try_lock():
        pass
    try:
        found = i2c.scan()
        print(f"Found I2C devices: {[hex(addr) for addr in found]}")
    finally:
        i2c.unlock()
    
    # Test each expected MPR121 board
    expected_addresses = set(slider["mpr121_address"] for slider in SLIDERS)
    
    for addr in expected_addresses:
        print(f"\nTesting MPR121 at 0x{addr:02X}")
        
        try:
            # Initialize MPR121
            mpr = adafruit_mpr121.MPR121(i2c, address=addr)
            print(f"✓ MPR121 at 0x{addr:02X} initialized successfully")
            
            # Reset and wait for calibration
            mpr.reset()
            time.sleep(0.5)
            print("✓ Reset completed, allowing calibration time...")
            
            # Test each pin used by sliders
            for config in SLIDERS:
                if config["mpr121_address"] == addr:
                    for pin_num in [config["down_pin"], config["up_pin"]]:
                        print(f"\n--- Pin {pin_num} (CC {config['cc_number']}) ---")
                        
                        try:
                            # Use batch read to get all sensor data at once
                            touched_state, baselines, filtered_data = get_all_sensor_data(mpr)
                            
                            baseline = baselines[pin_num]
                            filtered = filtered_data[pin_num]
                            touched = bool(touched_state & (1 << pin_num))
                            delta = baseline - filtered
                            
                            print(f"Baseline: {baseline}")
                            print(f"Filtered: {filtered}")
                            print(f"Delta: {delta}")
                            print(f"Touched: {touched}")
                            
                            # Health assessment
                            if baseline < 40:
                                print("⚠️  WARNING: Very low baseline - may indicate electrical interference or sensor issues")
                                if touched:
                                    print("   Note: Sensor is currently being touched, which affects baseline")
                            elif baseline > 1018:
                                print("⚠️  WARNING: Extremely high baseline - sensor may be dirty or poorly connected")
                            
                            if delta > 48 and not touched:
                                print("⚠️  WARNING: Large delta detected when not touched - possible interference")
                            elif delta < -48:
                                print("⚠️  WARNING: Negative delta - unusual, check for electrical interference")
                            
                            if touched and delta > 48:
                                print("✓ Normal: Large delta detected while touching - sensor working correctly")
                            
                            # Check if pin is stable
                            print("\nChecking baseline stability...")
                            stable_readings = []
                            for _ in range(5):
                                baselines = get_all_baselines(mpr)
                                stable_readings.append(baselines[pin_num])
                                time.sleep(0.1)
                            
                            variation = max(stable_readings) - min(stable_readings)
                            print(f"Baseline variation over 5 readings: {variation}")
                            
                            if variation < 20:
                                print("✓ Baseline is stable")
                            else:
                                print("⚠️  WARNING: Baseline is unstable - sensor may still be calibrating")
                            
                        except Exception as e:
                            print(f"✗ Error testing pin {pin_num}: {e}")
            
        except Exception as e:
            print(f"✗ Error testing MPR121 at 0x{addr:02X}: {e}")
    
    # Print I2C statistics
    # i2c_logger = get_i2c_logger() # This line is removed as per the edit hint
    # i2c_logger.print_statistics() # This line is removed as per the edit hint

def get_all_sensor_data(mpr):
    """
    Read all touch, baseline, and filtered data in minimal I2C calls.
    
    Returns:
        tuple: (touched_state, baselines, filtered_data)
    """
    try:
        # 1 I2C call for touch status (registers 0x00-0x01)
        touched = mpr.touched()
        
        # 1 I2C call for all baselines (registers 0x1E-0x29)
        baseline_buf = bytearray(12)
        mpr._read_register_bytes(0x1E, baseline_buf, 12)  # MPR121_BASELINE_0 = 0x1E
        baselines = [baseline_buf[i] << 2 for i in range(12)]
        
        # 1 I2C call for all filtered data (registers 0x04-0x1B)
        filtered_buf = bytearray(24)  # 12 pins × 2 bytes each
        mpr._read_register_bytes(0x04, filtered_buf, 24)  # MPR121_FILTDATA_0L = 0x04
        filtered = [((filtered_buf[i*2+1] << 8) | filtered_buf[i*2]) & 0xFFFF for i in range(12)]
        
        return touched, baselines, filtered
        
    except Exception as e:
        print(f"Error in batch sensor data read: {e}")
        # Fallback to individual reads
        touched = mpr.touched()
        baselines = [mpr.baseline_data(i) for i in range(12)]
        filtered = [mpr.filtered_data(i) for i in range(12)]
        return touched, baselines, filtered

def get_all_baselines(mpr):
    """
    Read all baseline data in a single I2C call.
    
    Returns:
        list: 12 baseline values (0-1020)
    """
    try:
        baseline_buf = bytearray(12)
        mpr._read_register_bytes(0x1E, baseline_buf, 12)  # MPR121_BASELINE_0 = 0x1E
        return [baseline_buf[i] << 2 for i in range(12)]
    except Exception as e:
        print(f"Error in batch baseline read: {e}")
        # Fallback to individual reads
        return [mpr.baseline_data(i) for i in range(12)]

if __name__ == "__main__":
    test_mpr121_calibration() 