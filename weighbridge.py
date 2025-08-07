import serial
import serial.tools.list_ports
import threading
import time
import re
import datetime
import os
import signal
import sys
from contextlib import contextmanager

# Import the unified logging system - maintain compatibility
try:
    from unified_logging import setup_enhanced_logger
    LOGGING_AVAILABLE = True
except ImportError:
    LOGGING_AVAILABLE = False

import config

class WeighbridgeManager:
    """Fast weighbridge manager - optimized for :XX pattern with full compatibility"""
    
    def __init__(self, weight_callback=None):
        """Initialize weighbridge manager - maintains original interface"""
        # Setup logging (but minimal for speed)
        self.setup_logging()
        
        self.weight_callback = weight_callback
        self.serial_connection = None
        self.is_connected = False
        self.reading_thread = None
        self.should_read = False
        
        # Test mode support - REQUIRED for compatibility
        self.test_mode = False
        self.last_test_weight = 0.0
        
        # Weight reading configuration - from config
        self.last_weight = 0.0
        self.weight_tolerance = getattr(config, 'WEIGHT_TOLERANCE', 1.0)
        self.stable_readings_required = getattr(config, 'STABLE_READINGS_REQUIRED', 3)
        self.stable_count = 0
        
        # Connection monitoring - REQUIRED for compatibility
        self.connection_attempts = 0
        self.max_connection_attempts = 3
        self.last_successful_read = None
        self.consecutive_errors = 0
        self.max_consecutive_errors = 3
        self.reconnect_delay = 2.0
        
        # FAST: Pre-compile only the colon pattern
        self.colon_pattern = re.compile(r':(\d+)')
        
        # Register signal handlers for graceful shutdown
        self._register_signal_handlers()
    
    def setup_logging(self):
        """Minimal logging setup for compatibility"""
        try:
            if LOGGING_AVAILABLE:
                self.logger = setup_enhanced_logger("weighbridge", config.LOGS_FOLDER)
            else:
                self.logger = self._create_fallback_logger()
        except Exception as e:
            self.logger = self._create_fallback_logger()
    
    def _create_fallback_logger(self):
        """Create a minimal fallback logger"""
        class FastLogger:
            def info(self, msg): pass  # Silent for speed
            def warning(self, msg): pass
            def error(self, msg): print(f"ERROR: {msg}")  # Only errors
            def debug(self, msg): pass
            def critical(self, msg): print(f"CRITICAL: {msg}")
            def print_info(self, msg): pass
            def print_success(self, msg): pass
            def print_warning(self, msg): pass
            def print_error(self, msg): print(f"❌ {msg}")
            def print_debug(self, msg): pass
            def print_critical(self, msg): print(f"🚨 {msg}")
        
        return FastLogger()
    
    def _register_signal_handlers(self):
        """Register signal handlers - REQUIRED for compatibility"""
        try:
            def signal_handler(signum, frame):
                self.close()
                sys.exit(0)
            
            signal.signal(signal.SIGINT, signal_handler)
            signal.signal(signal.SIGTERM, signal_handler)
        except Exception as e:
            pass  # Silent for speed
    
    def set_test_mode(self, enabled):
        """Set test mode - REQUIRED method for compatibility"""
        self.test_mode = enabled
        
        if enabled:
            # Disconnect real weighbridge if connected
            if self.is_connected:
                self.disconnect()
        
    def get_available_ports(self):
        """Get available COM ports - REQUIRED method for compatibility"""
        try:
            ports = serial.tools.list_ports.comports()
            return [port.device for port in ports]
        except Exception as e:
            return []
    
    def connect(self, port, baud_rate=9600, data_bits=8, parity="None", stop_bits=1.0):
        """Connect to weighbridge - maintains original interface signature"""
        try:
            # Validate parameters - REQUIRED for compatibility
            is_valid, error_msg = self._validate_serial_parameters(port, baud_rate, data_bits, parity, stop_bits)
            if not is_valid:
                self.logger.print_error(error_msg)
                return False
            
            # Close existing connection
            if self.serial_connection and self.serial_connection.is_open:
                self.serial_connection.close()
                time.sleep(0.1)
            
            # Convert parity - REQUIRED for compatibility
            parity_map = {
                'None': serial.PARITY_NONE,
                'Odd': serial.PARITY_ODD,
                'Even': serial.PARITY_EVEN,
                'Mark': serial.PARITY_MARK,
                'Space': serial.PARITY_SPACE
            }
            parity_setting = parity_map.get(parity, serial.PARITY_NONE)
            
            # FAST: Create serial connection with optimized settings
            self.serial_connection = serial.Serial(
                port=port,
                baudrate=baud_rate,
                bytesize=data_bits,
                parity=parity_setting,
                stopbits=stop_bits,
                timeout=0.02,  # FAST: Very short timeout
                write_timeout=1.0,
                exclusive=True
            )
            
            if self.serial_connection.is_open:
                # Quick buffer clear
                self.serial_connection.reset_input_buffer()
                self.serial_connection.reset_output_buffer()
                
                # Reset counters
                self.consecutive_errors = 0
                
                # Start FAST reading thread
                self.should_read = True
                self.reading_thread = threading.Thread(target=self._fast_read_weight_loop, daemon=True)
                self.reading_thread.start()
                
                self.is_connected = True
                self.connection_attempts = 0
                self.last_successful_read = datetime.datetime.now()
                
                return True
            else:
                return False
            
        except Exception as e:
            self.logger.print_error(f"Connection error: {e}")
            return False
    
    def _validate_serial_parameters(self, port, baud_rate, data_bits, parity, stop_bits):
        """Validate serial parameters - REQUIRED for compatibility"""
        try:
            if not port or not isinstance(port, str):
                return False, "Invalid port specified"
            
            valid_baud_rates = [300, 600, 1200, 2400, 4800, 9600, 14400, 19200, 28800, 38400, 57600, 115200]
            if baud_rate not in valid_baud_rates:
                return False, f"Invalid baud rate: {baud_rate}"
            
            if data_bits not in [5, 6, 7, 8]:
                return False, f"Invalid data bits: {data_bits}"
            
            valid_parity = ['None', 'Odd', 'Even', 'Mark', 'Space']
            if parity not in valid_parity:
                return False, f"Invalid parity: {parity}"
            
            if stop_bits not in [1, 1.5, 2]:
                return False, f"Invalid stop bits: {stop_bits}"
            
            return True, ""
            
        except Exception as e:
            return False, f"Validation error: {e}"
    
    def _fast_read_weight_loop(self):
        """OPTIMIZED: Fast weight reading loop for colon pattern only"""
        while self.should_read:
            try:
                if self.test_mode:
                    # Test mode simulation - REQUIRED for compatibility
                    self._simulate_test_weight()
                    time.sleep(0.5)
                    continue
                
                if self.serial_connection and self.serial_connection.is_open:
                    if self.serial_connection.in_waiting > 0:
                        try:
                            # FAST: Quick read and decode
                            line = self.serial_connection.readline().decode('utf-8', errors='ignore').strip()
                            
                            if line:
                                # FAST: Only check colon pattern
                                weight = self._parse_colon_weight_fast(line)
                                
                                if weight is not None:
                                    self._process_weight(weight)
                                    self.consecutive_errors = 0
                                    self.last_successful_read = datetime.datetime.now()
                        
                        except serial.SerialException as e:
                            self.consecutive_errors += 1
                            if self.consecutive_errors >= self.max_consecutive_errors:
                                break
                            time.sleep(self.reconnect_delay)
                            continue
                
                # FAST: Minimal delay
                time.sleep(0.005)  # 5ms delay for maximum speed
                
            except Exception as e:
                self.consecutive_errors += 1
                if self.consecutive_errors >= self.max_consecutive_errors:
                    break
                time.sleep(0.01)
    
    def _parse_colon_weight_fast(self, data_line):
        """OPTIMIZED: Fast parsing for colon pattern only"""
        try:
            # FAST: Only check colon pattern (:XX)
            match = self.colon_pattern.search(data_line)
            if match:
                return float(match.group(1))
            return None
        except:
            return None
    
    def _simulate_test_weight(self):
        """Test mode simulation - REQUIRED for compatibility"""
        try:
            import random
            base_weights = [5000, 12000, 18000, 25000, 30000]
            selected_base = random.choice(base_weights)
            variation = random.uniform(-100, 100)
            
            simulated_weight = selected_base + variation
            self.last_test_weight = simulated_weight
            self._process_weight(simulated_weight)
            
        except Exception as e:
            pass  # Silent for speed
    
    def _process_weight(self, weight):
        """Process weight with stability checking - REQUIRED for compatibility"""
        try:
            # Range check
            if weight < 0 or weight > 100000:
                return
            
            # Stability check
            if abs(weight - self.last_weight) <= self.weight_tolerance:
                self.stable_count += 1
            else:
                self.stable_count = 0
            
            self.last_weight = weight
            
            # Only report stable weights - REQUIRED for compatibility
            if self.stable_count >= self.stable_readings_required:
                if self.weight_callback:
                    self.weight_callback(weight)
                    
        except Exception as e:
            pass  # Silent for speed
    
    def disconnect(self):
        """Disconnect - REQUIRED method for compatibility"""
        try:
            # Stop reading thread
            self.should_read = False
            if self.reading_thread and self.reading_thread.is_alive():
                self.reading_thread.join(timeout=2)
            
            # Close serial connection
            if self.serial_connection and self.serial_connection.is_open:
                self.serial_connection.close()
            
            self.is_connected = False
            self.consecutive_errors = 0
            self.serial_connection = None
            
            return True
            
        except Exception as e:
            return False
    
    def close(self):
        """Cleanup method - REQUIRED for compatibility"""
        try:
            return self.disconnect()
        except Exception as e:
            return False
    
    def get_current_weight(self):
        """Get current weight - REQUIRED method for compatibility"""
        return self.last_weight
    
    def get_connection_status(self):
        """Get connection status - REQUIRED method for compatibility"""
        try:
            status = {
                'connected': self.is_connected,
                'test_mode': self.test_mode,
                'port': getattr(self.serial_connection, 'port', None) if self.serial_connection else None,
                'last_weight': self.last_weight,
                'stable_count': self.stable_count,
                'connection_attempts': self.connection_attempts,
                'consecutive_errors': self.consecutive_errors,
                'last_successful_read': self.last_successful_read.isoformat() if self.last_successful_read else None
            }
            return status
        except Exception as e:
            return {
                'connected': False,
                'test_mode': self.test_mode,
                'error': str(e)
            }
    
    def __del__(self):
        """Destructor - REQUIRED for compatibility"""
        try:
            self.close()
        except Exception as e:
            pass

# Context manager - REQUIRED for compatibility
@contextmanager
def open_weighbridge(*args, **kwargs):
    """Context manager for safe weighbridge operations"""
    mgr = WeighbridgeManager()
    try:
        if mgr.connect(*args, **kwargs):
            yield mgr
        else:
            raise RuntimeError("Failed to connect to weighbridge")
    finally:
        mgr.close()