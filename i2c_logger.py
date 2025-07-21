# -----------------------------------------------------------------------------
# I2C Traffic Logger
# -----------------------------------------------------------------------------
"""
I2C Traffic Logger

This module provides comprehensive logging of all I2C operations in the project.
It tracks I2C reads, writes, scans, and provides detailed statistics.
"""

import time
from logger import get_logger, lazy_format

# Get logger instance
logger = get_logger()

# Import config to check if history and debug logging are enabled
from config import ENABLE_I2C_HISTORY, ENABLE_I2C_DEBUG_LOGGING

class I2CLogger:
    """Tracks and logs all I2C operations."""
    
    def __init__(self):
        self.i2c_operations = {
            'reads': 0,
            'writes': 0,
            'scans': 0,
            'total_calls': 0,
            'start_time': time.monotonic(),
            'last_reset_time': time.monotonic()
        }
        self.operation_history = []
        self.max_history = 500  # Keep last 50 operations to reduce memory usage
    
    def log_i2c_read(self, device_addr, register, bytes_read, caller_info=""):
        """Log an I2C read operation."""
        if not ENABLE_I2C_DEBUG_LOGGING:
            return  # Skip all tracking when debug logging is disabled
            
        operation = {
            'type': 'READ',
            'device_addr': device_addr,
            'register': register,
            'bytes_read': bytes_read,
            'timestamp': time.monotonic(),
            'caller': caller_info
        }
        
        self.i2c_operations['reads'] += 1
        self.i2c_operations['total_calls'] += 1
        self._add_to_history(operation)
        
        logger.debug(lazy_format("I2C READ: 0x{:02X} reg=0x{:02X} bytes={} caller={}", 
                               device_addr, register, bytes_read, caller_info))
    
    def log_i2c_write(self, device_addr, register, value, caller_info=""):
        """Log an I2C write operation."""
        if not ENABLE_I2C_DEBUG_LOGGING:
            return  # Skip all tracking when debug logging is disabled
            
        operation = {
            'type': 'WRITE',
            'device_addr': device_addr,
            'register': register,
            'value': value,
            'timestamp': time.monotonic(),
            'caller': caller_info
        }
        
        self.i2c_operations['writes'] += 1
        self.i2c_operations['total_calls'] += 1
        self._add_to_history(operation)
        
        logger.debug(lazy_format("I2C WRITE: 0x{:02X} reg=0x{:02X} val=0x{:02X} caller={}", 
                               device_addr, register, value, caller_info))
    
    def log_i2c_scan(self, devices_found, caller_info=""):
        """Log an I2C scan operation."""
        if not ENABLE_I2C_DEBUG_LOGGING:
            return  # Skip all tracking when debug logging is disabled
            
        operation = {
            'type': 'SCAN',
            'devices_found': devices_found,
            'timestamp': time.monotonic(),
            'caller': caller_info
        }
        
        self.i2c_operations['scans'] += 1
        self.i2c_operations['total_calls'] += 1
        self._add_to_history(operation)
        
        logger.debug(lazy_format("I2C SCAN: found={} caller={}", 
                               [hex(addr) for addr in devices_found], caller_info))
    
    def log_batch_read(self, device_addr, start_register, total_bytes, caller_info=""):
        """Log a batch I2C read operation."""
        if not ENABLE_I2C_DEBUG_LOGGING:
            return  # Skip all tracking when debug logging is disabled
            
        operation = {
            'type': 'BATCH_READ',
            'device_addr': device_addr,
            'start_register': start_register,
            'total_bytes': total_bytes,
            'timestamp': time.monotonic(),
            'caller': caller_info
        }
        
        self.i2c_operations['reads'] += 1
        self.i2c_operations['total_calls'] += 1
        self._add_to_history(operation)
        
        logger.debug(lazy_format("I2C BATCH_READ: 0x{:02X} start_reg=0x{:02X} bytes={} caller={}", 
                               device_addr, start_register, total_bytes, caller_info))
    
    def _add_to_history(self, operation):
        """Add operation to history, maintaining max size."""
        if not ENABLE_I2C_HISTORY:
            return  # Skip history storage if disabled
            
        self.operation_history.append(operation)
        if len(self.operation_history) > self.max_history:
            self.operation_history.pop(0)
        
        # Periodically clear history to save memory (every 100 operations)
        if self.i2c_operations['total_calls'] % 100 == 0:
            # Keep only the last 10 operations to save memory
            if len(self.operation_history) > 10:
                self.operation_history = self.operation_history[-10:]
    
    def get_statistics(self):
        """Get current I2C operation statistics."""
        if not ENABLE_I2C_DEBUG_LOGGING:
            return {
                'total_operations': 0,
                'reads': 0,
                'writes': 0,
                'scans': 0,
                'runtime_seconds': 0,
                'operations_per_second': 0,
                'reads_per_second': 0,
                'writes_per_second': 0,
                'scans_per_second': 0
            }
            
        current_time = time.monotonic()
        runtime = current_time - self.i2c_operations['start_time']
        
        stats = {
            'total_operations': self.i2c_operations['total_calls'],
            'reads': self.i2c_operations['reads'],
            'writes': self.i2c_operations['writes'],
            'scans': self.i2c_operations['scans'],
            'runtime_seconds': runtime,
            'operations_per_second': self.i2c_operations['total_calls'] / runtime if runtime > 0 else 0,
            'reads_per_second': self.i2c_operations['reads'] / runtime if runtime > 0 else 0,
            'writes_per_second': self.i2c_operations['writes'] / runtime if runtime > 0 else 0,
            'scans_per_second': self.i2c_operations['scans'] / runtime if runtime > 0 else 0
        }
        
        return stats
    
    def print_statistics(self):
        """Print current I2C statistics."""
        if not ENABLE_I2C_DEBUG_LOGGING:
            logger.info("=== I2C Traffic Statistics ===")
            logger.info("I2C tracking: DISABLED (memory optimized)")
            return
            
        stats = self.get_statistics()
        
        logger.info("=== I2C Traffic Statistics ===")
        logger.info(lazy_format("Runtime: {:.1f}s", stats['runtime_seconds']))
        logger.info(lazy_format("Total Operations: {}", stats['total_operations']))
        logger.info(lazy_format("  Reads: {} ({:.1f}/s)", stats['reads'], stats['reads_per_second']))
        logger.info(lazy_format("  Writes: {} ({:.1f}/s)", stats['writes'], stats['writes_per_second']))
        logger.info(lazy_format("  Scans: {} ({:.1f}/s)", stats['scans'], stats['scans_per_second']))
        logger.info(lazy_format("Operations/sec: {:.1f}", stats['operations_per_second']))
        if not ENABLE_I2C_HISTORY:
            logger.info("I2C operation history: DISABLED (memory optimized)")
        else:
            logger.info("I2C operation history: ENABLED")
        logger.info("I2C debug logging: ENABLED")
    
    def reset_statistics(self):
        """Reset I2C statistics."""
        self.i2c_operations = {
            'reads': 0,
            'writes': 0,
            'scans': 0,
            'total_calls': 0,
            'start_time': time.monotonic(),
            'last_reset_time': time.monotonic()
        }
        self.operation_history.clear()
        logger.info("I2C statistics reset")
    
    def get_recent_operations(self, count=10):
        """Get the most recent I2C operations."""
        if not ENABLE_I2C_HISTORY:
            return []
        return self.operation_history[-count:] if self.operation_history else []
    
    def print_recent_operations(self, count=10):
        """Print the most recent I2C operations."""
        if not ENABLE_I2C_HISTORY:
            logger.info("I2C operation history is disabled")
            return
            
        recent = self.get_recent_operations(count)
        if not recent:
            logger.info("No recent I2C operations")
            return
        
        logger.info(lazy_format("=== Recent I2C Operations (last {}) ===", count))
        for op in recent:
            if op['type'] == 'READ':
                logger.info(lazy_format("READ:  0x{:02X} reg=0x{:02X} bytes={} caller={}", 
                                      op['device_addr'], op['register'], op['bytes_read'], op['caller']))
            elif op['type'] == 'WRITE':
                logger.info(lazy_format("WRITE: 0x{:02X} reg=0x{:02X} val=0x{:02X} caller={}", 
                                      op['device_addr'], op['register'], op['value'], op['caller']))
            elif op['type'] == 'BATCH_READ':
                logger.info(lazy_format("BATCH: 0x{:02X} start_reg=0x{:02X} bytes={} caller={}", 
                                      op['device_addr'], op['start_register'], op['total_bytes'], op['caller']))
            elif op['type'] == 'SCAN':
                logger.info(lazy_format("SCAN:  found={} caller={}", 
                                      [hex(addr) for addr in op['devices_found']], op['caller']))

# Global I2C logger instance
i2c_logger = I2CLogger()

def get_i2c_logger():
    """Get the global I2C logger instance."""
    return i2c_logger

def log_i2c_read(device_addr, register, bytes_read, caller_info=""):
    """Convenience function to log I2C read."""
    i2c_logger.log_i2c_read(device_addr, register, bytes_read, caller_info)

def log_i2c_write(device_addr, register, value, caller_info=""):
    """Convenience function to log I2C write."""
    i2c_logger.log_i2c_write(device_addr, register, value, caller_info)

def log_i2c_scan(devices_found, caller_info=""):
    """Convenience function to log I2C scan."""
    i2c_logger.log_i2c_scan(devices_found, caller_info)

def log_batch_read(device_addr, start_register, total_bytes, caller_info=""):
    """Convenience function to log batch I2C read."""
    i2c_logger.log_batch_read(device_addr, start_register, total_bytes, caller_info) 