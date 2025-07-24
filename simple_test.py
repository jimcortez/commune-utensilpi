#!/usr/bin/env python3
"""
Simple MPR121 Test Script
This script tests the simplified MPR121 setup to verify touch detection works.
"""

import time
import board
import adafruit_mpr121
from config import SLIDERS

def simple_mpr121_test():
    """Simple test using the working pattern from the old code."""
    print("=== Simple MPR121 Test ===")
    
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
    mpr121_boards = {}
    
    for addr in expected_addresses:
        print(f"\nTesting MPR121 at 0x{addr:02X}")
        
        try:
            # Use direct MPR121 initialization like the working old code
            mpr = adafruit_mpr121.MPR121(i2c, address=addr)
            mpr121_boards[addr] = mpr
            print(f"✓ MPR121 at 0x{addr:02X} initialized successfully")
            
            # Simple reset like the working old code
            mpr.reset()
            time.sleep(0.1)  # Same delay as working code
            print("✓ Reset completed")
            
            # Test each pin used by sliders
            for config in SLIDERS:
                if config["mpr121_address"] == addr:
                    for pin_num in [config["down_pin"], config["up_pin"]]:
                        print(f"\n--- Pin {pin_num} (CC {config['cc_number']}) ---")
                        
                        try:
                            # Get baseline and filtered data
                            baseline = mpr.baseline_data(pin_num)
                            filtered = mpr.filtered_data(pin_num)
                            touched = mpr.is_touched(pin_num)
                            delta = baseline - filtered
                            
                            print(f"Baseline: {baseline}")
                            print(f"Filtered: {filtered}")
                            print(f"Delta: {delta}")
                            print(f"Touched: {touched}")
                            
                            # Test touch detection
                            print("Touch the sensor and press Enter...")
                            input()
                            
                            baseline2 = mpr.baseline_data(pin_num)
                            filtered2 = mpr.filtered_data(pin_num)
                            touched2 = mpr.is_touched(pin_num)
                            delta2 = baseline2 - filtered2
                            
                            print(f"After touch - Baseline: {baseline2}, Filtered: {filtered2}, Delta: {delta2}, Touched: {touched2}")
                            
                            if touched2:
                                print("✓ Touch detection working!")
                            else:
                                print("✗ Touch not detected")
                                
                        except Exception as e:
                            print(f"✗ Error testing pin {pin_num}: {e}")
            
        except Exception as e:
            print(f"✗ Failed to initialize MPR121 at 0x{addr:02X}: {e}")
    
    # Test continuous monitoring
    if mpr121_boards:
        print("\n=== Continuous Touch Monitoring ===")
        print("Touch sensors to test. Press Ctrl+C to stop.")
        
        try:
            while True:
                for addr, mpr in mpr121_boards.items():
                    touched_state = mpr.touched()
                    if touched_state != 0:
                        print(f"MPR121 0x{addr:02X} touched: 0x{touched_state:04X}")
                time.sleep(0.1)
        except KeyboardInterrupt:
            print("\nTest completed.")

if __name__ == "__main__":
    simple_mpr121_test() 