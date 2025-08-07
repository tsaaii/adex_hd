# Fixed unified_logging.py - Handles None streams and other edge cases

import logging
import sys
import os
import datetime
import threading
import traceback

try:
    import config
except ImportError:
    # Fallback if config is not available
    class Config:
        LOGS_FOLDER = "logs"
    config = Config()

class SafeStreamHandler(logging.StreamHandler):
    """Safe stream handler that handles None streams gracefully"""
    
    def __init__(self, stream=None):
        # Ensure we have a valid stream
        if stream is None:
            # Try to get a valid stdout/stderr
            try:
                if hasattr(sys, '__stdout__') and sys.__stdout__ is not None:
                    stream = sys.__stdout__
                elif hasattr(sys, '__stderr__') and sys.__stderr__ is not None:
                    stream = sys.__stderr__
                else:
                    # Create a dummy stream that doesn't crash
                    import io
                    stream = io.StringIO()
            except:
                import io
                stream = io.StringIO()
        
        super().__init__(stream)
    
    def emit(self, record):
        """Emit a record with error handling"""
        try:
            # Check if stream is still valid
            if self.stream is None or not hasattr(self.stream, 'write'):
                # Try to recover with a valid stream
                try:
                    if hasattr(sys, '__stdout__') and sys.__stdout__ is not None:
                        self.stream = sys.__stdout__
                    elif hasattr(sys, '__stderr__') and sys.__stderr__ is not None:
                        self.stream = sys.__stderr__
                    else:
                        # Can't recover, just return silently
                        return
                except:
                    return
            
            # Try the normal emit
            super().emit(record)
        except (AttributeError, OSError, ValueError) as e:
            # If emit fails, try to print to stderr directly
            try:
                if hasattr(sys, '__stderr__') and sys.__stderr__ is not None:
                    sys.__stderr__.write(f"Logging error: {e}\n")
                    sys.__stderr__.write(f"Failed to log: {record.getMessage()}\n")
            except:
                pass  # Ultimate fallback - do nothing
        except Exception:
            # Catch any other logging errors silently
            pass

class SafeFileHandler(logging.FileHandler):
    """Safe file handler with better error handling"""
    
    def __init__(self, filename, mode='a', encoding='utf-8', delay=False):
        # Ensure directory exists
        try:
            os.makedirs(os.path.dirname(filename), exist_ok=True)
        except:
            pass
            
        super().__init__(filename, mode, encoding, delay)
    
    def emit(self, record):
        """Emit a record with error handling"""
        try:
            super().emit(record)
        except (OSError, ValueError, UnicodeEncodeError) as e:
            # If file writing fails, try to print to console
            try:
                safe_print(f"File logging error: {e}")
                safe_print(f"Failed to log: {record.getMessage()}")
            except:
                pass
        except Exception:
            # Catch any other file logging errors silently
            pass

def safe_print(message):
    """Print message safely, handling None streams"""
    try:
        # Try stdout first
        if hasattr(sys, 'stdout') and sys.stdout is not None:
            print(message)
            return
        
        # Try __stdout__ 
        if hasattr(sys, '__stdout__') and sys.__stdout__ is not None:
            sys.__stdout__.write(str(message) + '\n')
            sys.__stdout__.flush()
            return
            
        # Try stderr
        if hasattr(sys, 'stderr') and sys.stderr is not None:
            sys.stderr.write(str(message) + '\n')
            sys.stderr.flush()
            return
            
        # Try __stderr__
        if hasattr(sys, '__stderr__') and sys.__stderr__ is not None:
            sys.__stderr__.write(str(message) + '\n')
            sys.__stderr__.flush()
            return
            
    except Exception:
        pass  # Ultimate fallback - do nothing

class StreamRedirector:
    """FIXED: Safe stream redirector that handles None streams"""
    
    def __init__(self, original_stream, stream_type="STDOUT"):
        self.original_stream = original_stream
        self.stream_type = stream_type
        self.buffer = []
        
        # Ensure we have a fallback stream
        if self.original_stream is None:
            if stream_type == "STDOUT":
                self.original_stream = sys.__stdout__ if hasattr(sys, '__stdout__') else None
            else:
                self.original_stream = sys.__stderr__ if hasattr(sys, '__stderr__') else None
    
    def write(self, message):
        """FIXED: Write with comprehensive error handling"""
        try:
            # Store in buffer
            self.buffer.append(message)
            
            # Try to write to original stream
            if self.original_stream and hasattr(self.original_stream, 'write'):
                try:
                    self.original_stream.write(message)
                    if hasattr(self.original_stream, 'flush'):
                        self.original_stream.flush()
                except:
                    pass  # Don't crash if original write fails
            
        except Exception:
            # If all else fails, store in buffer for later
            try:
                self.buffer.append(message)
            except:
                pass  # Ultimate fallback
    
    def flush(self):
        """FIXED: Flush with error handling"""
        try:
            if self.original_stream and hasattr(self.original_stream, 'flush'):
                self.original_stream.flush()
        except Exception:
            pass  # Don't crash if flush fails

class UnifiedLogger:
    """FIXED: Enhanced unified logger with better error handling"""
    
    def __init__(self, log_folder=None, app_name="advitia_app"):
        """Initialize unified logging with comprehensive error handling"""
        
        # Initialize basic attributes first
        self.app_name = app_name
        self.log_folder = log_folder or getattr(config, 'LOGS_FOLDER', 'logs')
        self.lock = threading.Lock()
        
        # Store original streams safely
        self.original_stdout = self._get_safe_stream('stdout')
        self.original_stderr = self._get_safe_stream('stderr')
        
        # Initialize log files
        self._initialize_log_files()
        
        # Setup the logger
        self._setup_logger()
        
        # Print initialization message safely
        safe_print(f"📋 Unified logging initialized:")
        safe_print(f"   📄 Combined log: {self.combined_log_file}")
        safe_print(f"   🖨️  Print log: {self.print_log_file}")
        safe_print(f"   📱 App log: {self.app_log_file}")
    
    def _get_safe_stream(self, stream_name):
        """Get a stream safely, with fallbacks"""
        try:
            # Try the normal stream first
            stream = getattr(sys, stream_name, None)
            if stream is not None:
                return stream
            
            # Try the backup stream
            backup_name = f"__{stream_name}__"
            backup_stream = getattr(sys, backup_name, None)
            if backup_stream is not None:
                return backup_stream
                
            # Return None if no valid stream found
            return None
            
        except Exception:
            return None
    
    def _initialize_log_files(self):
        """Initialize log file paths"""
        try:
            # Ensure log folder exists
            os.makedirs(self.log_folder, exist_ok=True)
            
            # Generate log filenames with current date
            today = datetime.datetime.now()
            date_str = today.strftime("%Y-%m-%d")
            
            self.combined_log_file = os.path.join(self.log_folder, f"{self.app_name}_combined_{date_str}.log")
            self.print_log_file = os.path.join(self.log_folder, f"{self.app_name}_prints_{date_str}.log")
            self.app_log_file = os.path.join(self.log_folder, f"{self.app_name}_app_{date_str}.log")
            
        except Exception as e:
            # Fallback to current directory
            safe_print(f"⚠️ Could not create log folder: {e}")
            today = datetime.datetime.now()
            date_str = today.strftime("%Y-%m-%d")
            self.combined_log_file = f"{self.app_name}_combined_{date_str}.log"
            self.print_log_file = f"{self.app_name}_prints_{date_str}.log" 
            self.app_log_file = f"{self.app_name}_app_{date_str}.log"
    
    def _setup_logger(self):
        """Setup the main logger with safe handlers"""
        try:
            # Get or create the main logger
            self.logger = logging.getLogger(self.app_name)
            self.logger.setLevel(logging.DEBUG)
            
            # Clear any existing handlers to avoid duplicates
            for handler in self.logger.handlers[:]:
                try:
                    self.logger.removeHandler(handler)
                    handler.close()
                except:
                    pass
            
            # Create formatters
            detailed_formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s'
            )
            
            simple_formatter = logging.Formatter(
                '%(asctime)s - %(levelname)s - %(message)s'
            )
            
            # Handler 1: Combined log file (everything)
            try:
                combined_handler = SafeFileHandler(self.combined_log_file)
                combined_handler.setLevel(logging.DEBUG)
                combined_handler.setFormatter(detailed_formatter)
                self.logger.addHandler(combined_handler)
            except Exception as e:
                safe_print(f"⚠️ Could not create combined log handler: {e}")
            
            # Handler 2: App-specific log file
            try:
                app_handler = SafeFileHandler(self.app_log_file)
                app_handler.setLevel(logging.INFO)
                app_handler.setFormatter(detailed_formatter)
                self.logger.addHandler(app_handler)
            except Exception as e:
                safe_print(f"⚠️ Could not create app log handler: {e}")
            
            # Handler 3: Safe console output
            try:
                console_handler = SafeStreamHandler(self.original_stdout)
                console_handler.setLevel(logging.INFO)
                console_handler.setFormatter(simple_formatter)
                self.logger.addHandler(console_handler)
            except Exception as e:
                safe_print(f"⚠️ Could not create console handler: {e}")
            
            # Test the logger
            try:
                self.logger.info("Unified logging system initialized")
            except Exception as e:
                safe_print(f"⚠️ Logger test failed: {e}")
                
        except Exception as e:
            safe_print(f"⚠️ Error setting up logger: {e}")
            # Create a fallback logger
            self.logger = self._create_fallback_logger()
    
    def _create_fallback_logger(self):
        """Create a fallback logger that just prints"""
        class FallbackLogger:
            def debug(self, msg): safe_print(f"DEBUG: {msg}")
            def info(self, msg): safe_print(f"INFO: {msg}")
            def warning(self, msg): safe_print(f"WARNING: {msg}")
            def error(self, msg): safe_print(f"ERROR: {msg}")
            def critical(self, msg): safe_print(f"CRITICAL: {msg}")
        
        return FallbackLogger()
    
    def restore_stdout(self):
        """Restore original stdout safely"""
        try:
            if self.original_stdout is not None:
                sys.stdout = self.original_stdout
        except Exception:
            pass

class EnhancedLogger:
    """FIXED: Enhanced logger with safe error handling"""
    
    def __init__(self, name="advitia_app", log_folder=None):
        self.name = name
        self.log_folder = log_folder or getattr(config, 'LOGS_FOLDER', 'logs')
        
        # Setup the logger safely
        self._setup_logger()
    
    def _setup_logger(self):
        """Setup logger with comprehensive error handling"""
        try:
            # Get or create the main logger
            self.logger = logging.getLogger(self.name)
            
            # Only setup if not already configured
            if not self.logger.handlers:
                self.logger.setLevel(logging.DEBUG)
                self._setup_handlers()
        except Exception as e:
            safe_print(f"⚠️ Error setting up enhanced logger: {e}")
            self.logger = self._create_fallback_logger()
    
    def _setup_handlers(self):
        """Setup logging handlers with error handling"""
        try:
            # Create log filename
            today = datetime.datetime.now()
            date_str = today.strftime("%Y-%m-%d")
            log_file = os.path.join(self.log_folder, f"{self.name.lower()}_enhanced_{date_str}.log")
            
            # Ensure log directory exists
            os.makedirs(self.log_folder, exist_ok=True)
            
            # Formatter
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s'
            )
            
            # File handler - SAFE VERSION
            try:
                file_handler = SafeFileHandler(log_file)
                file_handler.setLevel(logging.DEBUG)
                file_handler.setFormatter(formatter)
                self.logger.addHandler(file_handler)
            except Exception as e:
                safe_print(f"⚠️ Could not create file handler: {e}")
            
            # Console handler - SAFE VERSION
            try:
                console_handler = SafeStreamHandler()
                console_handler.setLevel(logging.INFO)
                console_handler.setFormatter(logging.Formatter('%(levelname)s - %(message)s'))
                self.logger.addHandler(console_handler)
            except Exception as e:
                safe_print(f"⚠️ Could not create console handler: {e}")
                
        except Exception as e:
            safe_print(f"⚠️ Error setting up enhanced logger: {e}")
    
    def _create_fallback_logger(self):
        """Create a fallback logger"""
        class FallbackLogger:
            def debug(self, msg): safe_print(f"DEBUG: {msg}")
            def info(self, msg): safe_print(f"INFO: {msg}")
            def warning(self, msg): safe_print(f"WARNING: {msg}")
            def error(self, msg): safe_print(f"ERROR: {msg}")
            def critical(self, msg): safe_print(f"CRITICAL: {msg}")
        
        return FallbackLogger()
    
    # Standard logging methods with error handling
    def debug(self, message):
        """Debug level logging"""
        try:
            self.logger.debug(message)
        except:
            safe_print(f"DEBUG: {message}")
    
    def info(self, message):
        """Info level logging"""
        try:
            self.logger.info(message)
        except:
            safe_print(f"INFO: {message}")
    
    def warning(self, message):
        """Warning level logging"""
        try:
            self.logger.warning(message)
        except:
            safe_print(f"WARNING: {message}")
    
    def error(self, message):
        """Error level logging"""
        try:
            self.logger.error(message)
        except:
            safe_print(f"ERROR: {message}")
    
    def critical(self, message):
        """Critical level logging"""
        try:
            self.logger.critical(message)
        except:
            safe_print(f"CRITICAL: {message}")
    
    # Print-style methods that also log
    def print_info(self, message):
        """Print and log info message"""
        try:
            safe_print(f"ℹ️ {message}")
            self.logger.info(message)
        except:
            safe_print(f"ℹ️ {message}")
    
    def print_success(self, message):
        """Print and log success message"""
        try:
            safe_print(f"✅ {message}")
            self.logger.info(f"SUCCESS: {message}")
        except:
            safe_print(f"✅ {message}")
    
    def print_warning(self, message):
        """Print and log warning message"""
        try:
            safe_print(f"⚠️ {message}")
            self.logger.warning(message)
        except:
            safe_print(f"⚠️ {message}")
    
    def print_error(self, message):
        """Print and log error message"""
        try:
            safe_print(f"❌ {message}")
            self.logger.error(message)
        except:
            safe_print(f"❌ {message}")
    
    def print_debug(self, message):
        """Print and log debug message"""
        try:
            safe_print(f"🔍 {message}")
            self.logger.debug(message)
        except:
            safe_print(f"🔍 {message}")

# Easy-to-use functions for your existing code
def setup_unified_logging(app_name="advitia_app", log_folder=None):
    """FIXED: Setup unified logging with better error handling
    
    Args:
        app_name (str): Application name
        log_folder (str): Log folder path
        
    Returns:
        UnifiedLogger: Configured unified logger
    """
    try:
        log_folder = log_folder or getattr(config, 'LOGS_FOLDER', 'logs')
        return UnifiedLogger(log_folder, app_name)
    except Exception as e:
        safe_print(f"⚠️ Could not setup unified logging: {e}")
        # Return a dummy logger that just prints
        class DummyLogger:
            def __init__(self):
                pass
            def restore_stdout(self):
                pass
        return DummyLogger()

def setup_enhanced_logger(name="advitia_app", log_folder=None):
    """FIXED: Setup enhanced logger with better error handling
    
    Args:
        name (str): Logger name
        log_folder (str): Log folder path
        
    Returns:
        EnhancedLogger: Configured enhanced logger
    """
    try:
        log_folder = log_folder or getattr(config, 'LOGS_FOLDER', 'logs')
        return EnhancedLogger(name, log_folder)
    except Exception as e:
        safe_print(f"⚠️ Could not setup enhanced logger: {e}")
        return EnhancedLogger(name, ".")

# Exception handler for logging errors
def log_exception(exc_type, exc_value, exc_traceback):
    """Log uncaught exceptions"""
    try:
        if issubclass(exc_type, KeyboardInterrupt):
            # Let KeyboardInterrupt through normally
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return
        
        # Format the exception
        error_msg = ''.join(traceback.format_exception(exc_type, exc_value, exc_traceback))
        
        # Try to log it
        try:
            logger = logging.getLogger('advitia_app')
            logger.error(f"Uncaught exception: {error_msg}")
        except:
            pass
        
        # Also print safely
        safe_print(f"❌ Uncaught exception: {error_msg}")
        
    except Exception:
        # Ultimate fallback
        try:
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
        except:
            pass

# Install the exception handler
sys.excepthook = log_exception