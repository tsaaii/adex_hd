# Enhanced weighbridge.py with comprehensive logging

import serial
import serial.tools.list_ports
import threading
import time
import re
import datetime
import os

# Import the unified logging system
try:
    from unified_logging import setup_enhanced_logger
    LOGGING_AVAILABLE = True
except ImportError:
    LOGGING_AVAILABLE = False
    print("⚠️ Unified logging not available - falling back to print statements")

import config

class WeighbridgeManager:
    """Enhanced weighbridge manager with comprehensive logging and test mode support"""
    
    def __init__(self, weight_callback=None):
        """Initialize weighbridge manager with logging
        
        Args:
            weight_callback: Function to call with weight updates
        """
        # Setup logging first
        self.setup_logging()
        
        self.logger.print_info("Initializing WeighbridgeManager")
        
        self.weight_callback = weight_callback
        self.serial_connection = None
        self.is_connected = False
        self.reading_thread = None
        self.should_read = False
        
        # Test mode support
        self.test_mode = False
        self.last_test_weight = 0.0
        
        # Weight reading configuration
        self.last_weight = 0.0
        self.weight_tolerance = 1.0  # kg tolerance for stable readings
        self.stable_readings_required = 3
        self.stable_count = 0
        
        # Connection monitoring
        self.connection_attempts = 0
        self.max_connection_attempts = 3
        self.last_successful_read = None
        
        self.logger.print_success("WeighbridgeManager initialized successfully")
        
    def setup_logging(self):
        """Setup enhanced logging for weighbridge operations"""
        try:
            if LOGGING_AVAILABLE:
                self.logger = setup_enhanced_logger("weighbridge", config.LOGS_FOLDER)
                self.logger.info("Enhanced logging initialized for WeighbridgeManager")
            else:
                # Fallback logger
                self.logger = self._create_fallback_logger()
        except Exception as e:
            print(f"⚠️ Could not setup weighbridge logging: {e}")
            self.logger = self._create_fallback_logger()
    
    def _create_fallback_logger(self):
        """Create a fallback logger that prints to console"""
        class FallbackLogger:
            def info(self, msg): print(f"INFO: WeighbridgeManager - {msg}")
            def warning(self, msg): print(f"WARNING: WeighbridgeManager - {msg}")
            def error(self, msg): print(f"ERROR: WeighbridgeManager - {msg}")
            def debug(self, msg): print(f"DEBUG: WeighbridgeManager - {msg}")
            def critical(self, msg): print(f"CRITICAL: WeighbridgeManager - {msg}")
            def print_info(self, msg): print(f"ℹ️ WeighbridgeManager - {msg}")
            def print_success(self, msg): print(f"✅ WeighbridgeManager - {msg}")
            def print_warning(self, msg): print(f"⚠️ WeighbridgeManager - {msg}")
            def print_error(self, msg): print(f"❌ WeighbridgeManager - {msg}")
            def print_debug(self, msg): print(f"🔍 WeighbridgeManager - {msg}")
        
        return FallbackLogger()
        
    def set_test_mode(self, enabled):
        """Set test mode on/off
        
        Args:
            enabled (bool): True to enable test mode, False to disable
        """
        self.test_mode = enabled
        
        if enabled:
            self.logger.print_warning(f"Test mode ENABLED - weighbridge will simulate readings")
            # Disconnect real weighbridge if connected
            if self.is_connected:
                self.logger.print_info("Disconnecting real weighbridge due to test mode activation")
                self.disconnect()
        else:
            self.logger.print_info("Test mode DISABLED - switching to real weighbridge mode")
    
    def get_available_ports(self):
        """Get list of available COM ports with logging
        
        Returns:
            list: Available COM port names
        """
        try:
            self.logger.print_debug("Scanning for available COM ports")
            ports = serial.tools.list_ports.comports()
            port_list = [port.device for port in ports]
            
            if port_list:
                self.logger.print_success(f"Found {len(port_list)} COM ports: {', '.join(port_list)}")
            else:
                self.logger.print_warning("No COM ports found")
                
            return port_list
            
        except Exception as e:
            self.logger.print_error(f"Error getting COM ports: {e}")
            return []
    
    def connect(self, port, baud_rate=9600, data_bits=8, parity='None', stop_bits=1.0):
        """Connect to weighbridge with comprehensive logging
        
        Args:
            port: COM port (e.g., 'COM1')
            baud_rate: Baud rate (default 9600)
            data_bits: Data bits (default 8)
            parity: Parity setting (default 'None')
            stop_bits: Stop bits (default 1.0)
            
        Returns:
            bool: True if connection successful
        """
        self.connection_attempts += 1
        
        try:
            self.logger.print_info(f"Connection attempt #{self.connection_attempts} to weighbridge")
            self.logger.print_debug(f"Parameters: Port={port}, Baud={baud_rate}, Data={data_bits}, Parity={parity}, Stop={stop_bits}")
            
            if self.test_mode:
                self.logger.print_warning("Test mode enabled - simulating weighbridge connection")
                self.is_connected = True
                self._start_test_mode_thread()
                self.logger.print_success("Test mode weighbridge connection established")
                return True
                
            # Validate parameters
            if not port:
                self.logger.print_error("No COM port specified")
                return False
                
            # Convert parity string to serial constant
            parity_map = {
                'None': serial.PARITY_NONE,
                'Odd': serial.PARITY_ODD,
                'Even': serial.PARITY_EVEN,
                'Mark': serial.PARITY_MARK,
                'Space': serial.PARITY_SPACE
            }
            
            parity_setting = parity_map.get(parity, serial.PARITY_NONE)
            self.logger.print_debug(f"Using parity setting: {parity} -> {parity_setting}")
            
            # Create serial connection
            self.logger.print_info(f"Establishing serial connection to {port}")
            self.serial_connection = serial.Serial(
                port=port,
                baudrate=baud_rate,
                bytesize=data_bits,
                parity=parity_setting,
                stopbits=stop_bits,
                timeout=1
            )
            
            # Test the connection
            if self.serial_connection.is_open:
                self.logger.print_success(f"Serial port {port} opened successfully")
                
                # Start reading thread
                self.should_read = True
                self.reading_thread = threading.Thread(target=self._read_weight_loop, daemon=True)
                self.reading_thread.start()
                self.logger.print_info("Weight reading thread started")
                
                self.is_connected = True
                self.connection_attempts = 0  # Reset on successful connection
                self.last_successful_read = datetime.datetime.now()
                
                self.logger.print_success(f"Weighbridge connected successfully on {port}")
                return True
            else:
                self.logger.print_error(f"Failed to open serial port {port}")
                return False
            
        except serial.SerialException as e:
            self.logger.print_error(f"Serial connection error: {e}")
            return False
        except Exception as e:
            self.logger.print_error(f"Unexpected error connecting to weighbridge: {e}")
            return False
    
    def disconnect(self):
        """Disconnect from weighbridge with logging
        
        Returns:
            bool: True if disconnection successful
        """
        try:
            self.logger.print_info("Initiating weighbridge disconnection")
            
            # Stop reading thread
            self.should_read = False
            if self.reading_thread and self.reading_thread.is_alive():
                self.logger.print_debug("Stopping weight reading thread")
                self.reading_thread.join(timeout=2)
                if self.reading_thread.is_alive():
                    self.logger.print_warning("Reading thread did not stop gracefully")
                else:
                    self.logger.print_success("Reading thread stopped successfully")
            
            # Close serial connection
            if self.serial_connection and self.serial_connection.is_open:
                self.logger.print_debug("Closing serial connection")
                self.serial_connection.close()
                self.logger.print_success("Serial connection closed")
            
            self.is_connected = False
            self.serial_connection = None
            
            self.logger.print_success("Weighbridge disconnected successfully")
            return True
            
        except Exception as e:
            self.logger.print_error(f"Error disconnecting from weighbridge: {e}")
            return False
    
    def _start_test_mode_thread(self):
        """Start the test mode simulation thread"""
        try:
            self.should_read = True
            self.reading_thread = threading.Thread(target=self._read_weight_loop, daemon=True)
            self.reading_thread.start()
            self.logger.print_debug("Test mode simulation thread started")
        except Exception as e:
            self.logger.print_error(f"Error starting test mode thread: {e}")
    
    def _read_weight_loop(self):
        """Main weight reading loop with comprehensive logging"""
        self.logger.print_info("Weight reading loop started")
        consecutive_errors = 0
        max_consecutive_errors = 5
        
        while self.should_read:
            try:
                if self.test_mode:
                    # Simulate weight readings in test mode
                    self._simulate_test_weight()
                    time.sleep(0.5)  # Update every 500ms
                    continue
                
                if self.serial_connection and self.serial_connection.is_open:
                    # Check for data available
                    if self.serial_connection.in_waiting > 0:
                        # Read from serial port
                        line = self.serial_connection.readline().decode('utf-8', errors='ignore').strip()
                        
                        if line:
                            self.logger.print_debug(f"Raw data received: '{line}'")
                            weight = self._parse_weight(line)
                            
                            if weight is not None:
                                self._process_weight(weight)
                                consecutive_errors = 0  # Reset error counter on successful read
                                self.last_successful_read = datetime.datetime.now()
                            else:
                                self.logger.print_warning(f"Could not parse weight from: '{line}'")
                    
                    # Check for timeout
                    if self.last_successful_read:
                        time_since_last_read = datetime.datetime.now() - self.last_successful_read
                        if time_since_last_read.total_seconds() > 30:  # 30 seconds timeout
                            self.logger.print_warning("No data received for 30 seconds - connection may be unstable")
                            self.last_successful_read = datetime.datetime.now()  # Reset to prevent spam
                
                time.sleep(0.1)  # Small delay to prevent CPU spinning
                
            except Exception as e:
                consecutive_errors += 1
                self.logger.print_error(f"Error in weight reading loop (#{consecutive_errors}): {e}")
                
                if consecutive_errors >= max_consecutive_errors:
                    self.logger.print_critical(f"Too many consecutive errors ({consecutive_errors}), stopping weight reading")
                    break
                
                time.sleep(1)  # Longer delay after error
        
        self.logger.print_info("Weight reading loop stopped")
    
    def _simulate_test_weight(self):
        """Simulate weight readings for test mode"""
        try:
            import random
            
            # Generate realistic weight variations
            base_weights = [5000, 12000, 18000, 25000, 30000]  # Common vehicle weights
            selected_base = random.choice(base_weights)
            variation = random.uniform(-100, 100)  # ±100 kg variation
            
            simulated_weight = selected_base + variation
            self.last_test_weight = simulated_weight
            
            self.logger.print_debug(f"Simulated weight: {simulated_weight:.2f} kg")
            self._process_weight(simulated_weight)
            
        except Exception as e:
            self.logger.print_error(f"Error in test weight simulation: {e}")
    
    def _parse_weight(self, data_line):
        """Parse weight from received data with logging - UPDATED with new format support
        
        Args:
            data_line: Raw data string from weighbridge
            
        Returns:
            float: Parsed weight in kg, or None if parsing failed
        """
        try:
            # Check for the new "Wt:" format first (e.g., "1600Wt:    1500Wt:    1500Wt:")
            wt_pattern = r'^(\d{2,5})[^0-9]+.*Wt:$'
            wt_matches = re.findall(wt_pattern, data_line)
            
            if wt_matches:
                # Found weights in "NumberWt:" format
                weights = [int(match) for match in wt_matches]
                #self.logger.print_debug(f"Found weights in Wt: format: {weights}")
                
                # Use the first weight value (you can modify this logic as needed)
                # Alternative approaches:
                # - Use the last weight: weight = weights[-1]
                # - Use average: weight = sum(weights) / len(weights)
                # - Use maximum: weight = max(weights)
                weight = weights[0]
                
                self.logger.print_debug(f"Selected weight from Wt: format: {weight} kg")
                return float(weight)
            
            # Common weight patterns from different weighbridge models (existing patterns)
            patterns = [
                r'(\d+\.?\d*)\s*kg',  # "1234.5 kg" or "1234 kg"
                r'(\d+\.?\d*)\s*KG',  # "1234.5 KG"
                r'(\d+\.?\d*)',       # Just the number
                r'.*?(\d+\.?\d*)\s*$',
                r'(\d{2,5})[^0-9]*Wt:$',
                r'(\d{2,5})[^0-9]*.*Wt:$',
                r'(\d{2,5})[^0-9]*.*Wt :$',
                r'^(\d{2,5})[^0-9]+.*Wt: $',
                r'^(\d{2,5}).*Wt:$',
                r'^(\d{2,5}).*Wt :$',
                r'^(\d{2,5}).*Wt: $'                                # Number at end of string
            ]
            
            for pattern in patterns:
                match = re.search(pattern, data_line)
                if match:
                    weight_str = match.group(1)
                    weight = float(weight_str)
                    #self.logger.print_debug(f"Parsed weight: {weight} kg from pattern: {pattern}")
                    return weight
            
            self.logger.print_warning(f"No weight pattern matched for data: '{data_line}'")
            return None
            
        except ValueError as e:
            self.logger.print_warning(f"Could not convert weight to float: {e}")
            return None
        except Exception as e:
            self.logger.print_error(f"Error parsing weight: {e}")
            return None
    
    def _process_weight(self, weight):
        """Process parsed weight with stability checking and logging"""
        try:
            # Check for reasonable weight range
            if weight < 0 or weight > 100000:  # 0-100 tons range
                self.logger.print_warning(f"Weight out of reasonable range: {weight} kg")
                return
            
            # Check weight stability
            if abs(weight - self.last_weight) <= self.weight_tolerance:
                self.stable_count += 1
            else:
                self.stable_count = 0
                self.logger.print_debug(f"Weight changed by {abs(weight - self.last_weight):.2f} kg")
            
            self.last_weight = weight
            
            # Only report stable weights
            if self.stable_count >= self.stable_readings_required:
                if self.weight_callback:
                    self.weight_callback(weight)
                    self.logger.print_debug(f"Stable weight reported: {weight:.2f} kg")
                else:
                    self.logger.print_debug(f"Stable weight (no callback): {weight:.2f} kg")
                    
        except Exception as e:
            self.logger.print_error(f"Error processing weight: {e}")
    
    def get_current_weight(self):
        """Get the current weight reading
        
        Returns:
            float: Current weight in kg
        """
        return self.last_weight
    
    def get_connection_status(self):
        """Get detailed connection status with logging
        
        Returns:
            dict: Connection status information
        """
        try:
            status = {
                'connected': self.is_connected,
                'test_mode': self.test_mode,
                'port': getattr(self.serial_connection, 'port', None) if self.serial_connection else None,
                'last_weight': self.last_weight,
                'stable_count': self.stable_count,
                'connection_attempts': self.connection_attempts,
                'last_successful_read': self.last_successful_read.isoformat() if self.last_successful_read else None
            }
            
            self.logger.print_debug(f"Connection status requested: {status}")
            return status
            
        except Exception as e:
            self.logger.print_error(f"Error getting connection status: {e}")
            return {
                'connected': False,
                'test_mode': self.test_mode,
                'error': str(e)
            }
    
    def __del__(self):
        """Cleanup when object is destroyed"""
        try:
            if hasattr(self, 'logger'):
                self.logger.print_info("WeighbridgeManager cleanup started")
            self.disconnect()
            if hasattr(self, 'logger'):
                self.logger.print_success("WeighbridgeManager cleanup completed")
        except Exception as e:
            if hasattr(self, 'logger'):
                self.logger.print_error(f"Error during cleanup: {e}")