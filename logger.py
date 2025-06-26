import time
from enum import Enum

class LogLevel(Enum):
    """Log levels in order of increasing verbosity."""
    ERROR = 0
    WARN = 1
    INFO = 2
    DEBUG = 3

class Logger:
    """Simple logging system for CircuitPython with configurable verbosity and lazy evaluation."""
    
    def __init__(self, level=LogLevel.INFO, enable_timestamps=True):
        self.level = level
        self.enable_timestamps = enable_timestamps
        self.start_time = time.monotonic()
    
    def _format_message(self, level_name, message):
        """Format log message with optional timestamp."""
        if self.enable_timestamps:
            elapsed = time.monotonic() - self.start_time
            return f"[{elapsed:6.1f}s] {level_name}: {message}"
        else:
            return f"{level_name}: {message}"
    
    def _log(self, level, level_name, message_or_callable):
        """Internal logging method with lazy evaluation support."""
        if level.value <= self.level.value:
            # If message is a callable, execute it to get the actual message
            if callable(message_or_callable):
                message = message_or_callable()
            else:
                message = message_or_callable
            
            formatted = self._format_message(level_name, message)
            print(formatted)
    
    def error(self, message_or_callable):
        """Log error messages (always shown)."""
        self._log(LogLevel.ERROR, "ERROR", message_or_callable)
    
    def warn(self, message_or_callable):
        """Log warning messages."""
        self._log(LogLevel.WARN, "WARN", message_or_callable)
    
    def info(self, message_or_callable):
        """Log info messages."""
        self._log(LogLevel.INFO, "INFO", message_or_callable)
    
    def debug(self, message_or_callable):
        """Log debug messages (most verbose)."""
        self._log(LogLevel.DEBUG, "DEBUG", message_or_callable)
    
    def set_level(self, level):
        """Change the logging level."""
        self.level = level
    
    def is_debug_enabled(self):
        """Check if debug logging is enabled."""
        return self.level.value >= LogLevel.DEBUG.value
    
    def is_info_enabled(self):
        """Check if info logging is enabled."""
        return self.level.value >= LogLevel.INFO.value

# Global logger instance
logger = Logger(level=LogLevel.INFO)

def set_log_level(level):
    """Set the global logging level."""
    logger.set_level(level)

def get_logger():
    """Get the global logger instance."""
    return logger

# Convenience functions for lazy evaluation
def lazy_format(template, *args, **kwargs):
    """Create a callable that formats a string template with the given arguments."""
    return lambda: template.format(*args, **kwargs)

def lazy_fstring(template_func):
    """Create a callable that executes an f-string template function."""
    return template_func 