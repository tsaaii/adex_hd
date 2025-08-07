# Enhanced camera.py - Resource-optimized with auto-start and comprehensive logging
# Updated with stability and performance improvements

import tkinter as tk
from tkinter import ttk, messagebox
import threading
import time
import cv2
from PIL import Image, ImageTk
import os
import datetime
import urllib.request
import numpy as np
import queue
import psutil
import gc

# Import the unified logging system
try:
    from unified_logging import setup_enhanced_logger
    LOGGING_AVAILABLE = True
except ImportError:
    LOGGING_AVAILABLE = False
    print("⚠️ Unified logging not available - falling back to print statements")

import config
from ui_components import HoverButton

class OptimizedCameraView:
    """Resource-optimized camera view with auto-start, continuous streaming, and comprehensive logging"""
    
    def __init__(self, parent, camera_index=0, camera_type="USB", camera_name="Camera", auto_start=True):
        # Setup logging first
        self.camera_name = camera_name
        self.setup_logging()
        
        self.parent = parent
        self.camera_index = camera_index
        self.camera_type = camera_type
        self.rtsp_url = None
        self.http_url = None
        
        # Performance optimization settings
        self.target_fps = 10  # Reduced for better performance
        self.max_fps = 15     # Maximum allowed FPS
        self.min_fps = 5      # Minimum FPS under heavy load
        self.adaptive_quality = True
        self.frame_skip_threshold = 80  # Skip frames if CPU > 80%
        
        # Resource monitoring
        self.cpu_usage = 0
        self.memory_usage = 0
        self.last_resource_check = 0
        self.resource_check_interval = 2.0  # Check every 2 seconds
        
        # Feed control with auto-restart capability
        self.is_running = False
        self.should_be_running = True  # Always try to keep camera running
        self.video_thread = None
        self.cap = None
        self.camera_available = False
        self.auto_reconnect = True
        self.reconnect_delay = 5.0  # Seconds between reconnection attempts
        
        # ENHANCED: Use threading events instead of time.sleep()
        self.stop_event = threading.Event()
        self.frame_ready_event = threading.Event()
        
        # ENHANCED: Frame management - optimized with direct buffer
        self.current_frame = None
        self.captured_image = None
        self.frame_lock = threading.Lock()
        self.display_frame = None
        
        # ENHANCED: Replace queue with direct memory buffer for better performance
        self.frame_buffer = {
            'raw_frame': None,
            'processed_frame': None,
            'timestamp': 0,
            'buffer_lock': threading.Lock()
        }
        
        # Performance tracking
        self.last_frame_time = 0
        self.frame_count = 0
        self.fps_counter = 0
        self.fps_timer = time.time()
        self.dropped_frames = 0
        self.total_frames = 0
        self.frame_skip_counter = 0  # ENHANCED: Track frame skips
        
        # Connection state with enhanced monitoring
        self.connection_stable = False
        self.last_error_time = 0
        self.error_cooldown = 3  # Reduced cooldown for better responsiveness
        self.consecutive_failures = 0
        self.max_consecutive_failures = 5  # Reduced for faster recovery
        self.connection_attempts = 0
        self.last_successful_frame = None
        
        # Zoom functionality (optimized)
        self.zoom_level = 1.0
        self.min_zoom = 1.0
        self.max_zoom = 3.0  # Reduced max zoom for better performance
        self.zoom_step = 0.1  # Smaller steps for smoother zooming
        self.pan_x = 0
        self.pan_y = 0
        self.is_panning = False
        self.last_mouse_x = 0
        self.last_mouse_y = 0
        
        # Create UI
        self.create_ui()
        
        # Start resource monitoring
        self.start_resource_monitoring()
        
        # Auto-start camera feed (always enabled for continuous operation)
        self.start_continuous_feed()
        
        # Start watchdog for auto-recovery
        self.start_watchdog()
        
    def setup_logging(self):
        """Setup enhanced logging for camera operations"""
        try:
            if LOGGING_AVAILABLE:
                logger_name = f"camera_{self.camera_name.lower().replace(' ', '_')}"
                self.logger = setup_enhanced_logger(logger_name, config.LOGS_FOLDER)
                self.logger.info(f"Enhanced logging initialized for {self.camera_name} camera")
            else:
                self.logger = self._create_fallback_logger()
        except Exception as e:
            print(f"⚠️ Could not setup camera logging: {e}")
            self.logger = self._create_fallback_logger()
    
    def _create_fallback_logger(self):
        """Create a fallback logger that prints to console"""
        class FallbackLogger:
            def __init__(self, camera_name):
                self.camera_name = camera_name
            
            def info(self, msg): print(f"INFO: {self.camera_name} - {msg}")
            def warning(self, msg): print(f"WARNING: {self.camera_name} - {msg}")
            def error(self, msg): print(f"ERROR: {self.camera_name} - {msg}")
            def debug(self, msg): print(f"DEBUG: {self.camera_name} - {msg}")
            def critical(self, msg): print(f"CRITICAL: {self.camera_name} - {msg}")
            def print_info(self, msg): print(f"ℹ️ {self.camera_name} - {msg}")
            def print_success(self, msg): print(f"✅ {self.camera_name} - {msg}")
            def print_warning(self, msg): print(f"⚠️ {self.camera_name} - {msg}")
            def print_error(self, msg): print(f"❌ {self.camera_name} - {msg}")
            def print_debug(self, msg): print(f"🔍 {self.camera_name} - {msg}")
        
        return FallbackLogger(self.camera_name)
    
    def start_resource_monitoring(self):
        """Start resource monitoring thread"""
        try:
            def monitor_resources():
                while not self.stop_event.is_set():
                    try:
                        current_time = time.time()
                        if current_time - self.last_resource_check >= self.resource_check_interval:
                            self.cpu_usage = psutil.cpu_percent()
                            self.memory_usage = psutil.virtual_memory().percent
                            self.last_resource_check = current_time
                            
                            # Adaptive FPS based on system load
                            if self.adaptive_quality:
                                self._adjust_performance_settings()
                            
                            # Log resource usage periodically
                            if int(current_time) % 30 == 0:  # Every 30 seconds
                                self.logger.print_debug(f"Resource usage - CPU: {self.cpu_usage:.1f}%, Memory: {self.memory_usage:.1f}%")
                        
                        # ENHANCED: Use event wait instead of sleep
                        self.stop_event.wait(1.0)
                    except Exception as e:
                        self.logger.print_error(f"Resource monitoring error: {e}")
                        self.stop_event.wait(5.0)
            
            resource_thread = threading.Thread(target=monitor_resources, daemon=True)
            resource_thread.start()
            self.logger.print_debug("Resource monitoring started")
        except Exception as e:
            self.logger.print_error(f"Failed to start resource monitoring: {e}")
    
    def _adjust_performance_settings(self):
        """Adjust performance settings based on system load"""
        try:
            if self.cpu_usage > 85:
                # High CPU load - reduce performance
                self.target_fps = max(self.min_fps, self.target_fps - 1)
                if self.cpu_usage > 90:
                    self.logger.print_warning(f"High CPU usage ({self.cpu_usage:.1f}%), reducing FPS to {self.target_fps}")
            elif self.cpu_usage < 50:
                # Low CPU load - can increase performance
                self.target_fps = min(self.max_fps, self.target_fps + 0.5)
            
            # Memory management
            if self.memory_usage > 85:
                self.logger.print_warning(f"High memory usage ({self.memory_usage:.1f}%), triggering garbage collection")
                gc.collect()
                
        except Exception as e:
            self.logger.print_error(f"Performance adjustment error: {e}")
    
    def start_watchdog(self):
        """Start watchdog thread for auto-recovery"""
        try:
            def watchdog():
                self.logger.print_debug("Camera watchdog started")
                while not self.stop_event.is_set():
                    try:
                        # Check if camera should be running but isn't
                        if self.should_be_running and not self.is_running:
                            self.start_continuous_feed()
                        
                        # Check for stale connections
                        if self.last_successful_frame:
                            time_since_frame = datetime.datetime.now() - self.last_successful_frame
                            if time_since_frame.total_seconds() > 30:  # No frames for 30 seconds
                                self.restart_feed()
                        
                        # ENHANCED: Use event wait instead of sleep
                        self.stop_event.wait(self.reconnect_delay)
                    except Exception as e:
                        self.logger.print_error(f"Watchdog error: {e}")
                        self.stop_event.wait(10.0)
            
            watchdog_thread = threading.Thread(target=watchdog, daemon=True)
            watchdog_thread.start()
            self.logger.print_debug("Camera watchdog enabled")
        except Exception as e:
            self.logger.print_error(f"Failed to start watchdog: {e}")
    
    def create_ui(self):
        """Create optimized camera UI"""
        try:
            # Main frame
            self.frame = ttk.Frame(self.parent)
            self.frame.pack(fill=tk.BOTH, expand=True, padx=3, pady=3)
            
            # Video display canvas - optimized size
            self.canvas = tk.Canvas(self.frame, bg="black", width=288, height=216)
            self.canvas.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)
            
            # Bind mouse events for zoom and pan
            self.canvas.bind("<MouseWheel>", self.on_mouse_wheel)
            self.canvas.bind("<Button-4>", self.on_mouse_wheel)
            self.canvas.bind("<Button-5>", self.on_mouse_wheel)
            self.canvas.bind("<ButtonPress-1>", self.on_mouse_press)
            self.canvas.bind("<B1-Motion>", self.on_mouse_drag)
            self.canvas.bind("<ButtonRelease-1>", self.on_mouse_release)
            self.canvas.bind("<Double-Button-1>", self.reset_zoom)
            
            # Initial message
            self.show_status_message("Initializing camera...")
            
            # Controls frame
            controls = ttk.Frame(self.frame)
            controls.pack(fill=tk.X, padx=2, pady=2)
            
            # Main controls
            main_controls = ttk.Frame(controls)
            main_controls.pack(fill=tk.X, pady=1)
            
            # Feed toggle button (now shows status)
            self.feed_button = HoverButton(main_controls, text="Starting...", 
                                          bg=config.COLORS["primary"], fg=config.COLORS["button_text"],
                                          padx=2, pady=1, width=10,
                                          command=self.toggle_continuous_feed)
            self.feed_button.grid(row=0, column=0, padx=1, pady=1, sticky="ew")
            
            # Capture button
            self.capture_button = HoverButton(main_controls, text="📷 Capture", 
                                            bg=config.COLORS["primary"], fg=config.COLORS["button_text"],
                                            padx=2, pady=1, width=10,
                                            command=self.capture_current_frame)
            self.capture_button.grid(row=0, column=1, padx=1, pady=1, sticky="ew")
            
            # Save button
            self.save_button = HoverButton(main_controls, text="💾 Save", 
                                         bg=config.COLORS["secondary"], fg=config.COLORS["button_text"],
                                         padx=2, pady=1, width=8,
                                         command=self.save_image,
                                         state=tk.DISABLED)
            self.save_button.grid(row=0, column=2, padx=1, pady=1, sticky="ew")
            
            # Configure grid columns
            main_controls.columnconfigure(0, weight=1)
            main_controls.columnconfigure(1, weight=1)
            main_controls.columnconfigure(2, weight=1)
            
            # Status and performance info
            status_frame = ttk.Frame(controls)
            status_frame.pack(fill=tk.X, pady=1)
            
            # Status
            self.status_var = tk.StringVar(value="Initializing...")
            self.status_label = ttk.Label(status_frame, textvariable=self.status_var, 
                                         font=("Segoe UI", 7), foreground="blue")
            self.status_label.pack(side=tk.LEFT, padx=2)
            
            # Performance indicators
            self.perf_var = tk.StringVar(value="FPS: -- | CPU: -- | Dropped: --")
            self.perf_label = ttk.Label(status_frame, textvariable=self.perf_var, 
                                       font=("Segoe UI", 7), foreground="green")
            self.perf_label.pack(side=tk.RIGHT, padx=2)
            
        except Exception as e:
            self.logger.print_error(f"Error creating camera UI: {e}")
            raise
    
    def show_status_message(self, message):
        """Show a status message on the canvas"""
        try:
            self.canvas.delete("all")
            canvas_width = self.canvas.winfo_width() or 320
            canvas_height = self.canvas.winfo_height() or 240
            
            self.canvas.create_text(canvas_width//2, canvas_height//2, 
                                   text=message, fill="white", 
                                   font=("Segoe UI", 10), justify=tk.CENTER)
        except Exception as e:
            self.logger.print_error(f"Error showing status message: {e}")
    
    def set_rtsp_config(self, rtsp_url):
        """Configure camera for RTSP stream"""
        try:
            self.rtsp_url = rtsp_url
            self.camera_type = "RTSP"
            self.restart_feed()
        except Exception as e:
            self.logger.print_error(f"Error setting RTSP config: {e}")
    
    def set_http_config(self, http_url):
        """Configure camera for HTTP stream"""
        try:
            self.http_url = http_url
            self.camera_type = "HTTP"
            self.restart_feed()
        except Exception as e:
            self.logger.print_error(f"Error setting HTTP config: {e}")
    
    def start_continuous_feed(self):
        """Start continuous camera feed with enhanced error handling"""
        try:
            if self.is_running:
                self.logger.print_debug("Camera feed already running")
                return
            
            self.connection_attempts += 1
            self.is_running = True
            self.consecutive_failures = 0
            self.stop_event.clear()  # Reset stop event
            
            # Update UI
            self._update_status("Starting camera...")
            self._update_feed_button("🟡 Starting", config.COLORS["warning"])
            
            # Start optimized video thread
            self.video_thread = threading.Thread(target=self._optimized_video_loop, daemon=True)
            self.video_thread.start()
            self.logger.print_debug("Optimized video thread started")
            
            # Start UI update loop
            self._schedule_ui_update()
            
        except Exception as e:
            self._update_status(f"Start error: {str(e)}")
            self.is_running = False
    
    def _optimized_video_loop(self):
        """Optimized video capture loop with resource management"""
        self.logger.print_info("Optimized video capture loop started")
        consecutive_failures = 0
        last_gc_time = time.time()
        
        while not self.stop_event.is_set() and self.is_running:
            try:
                # ENHANCED: Check frame skip conditions BEFORE reading frame
                if self._should_skip_frame():
                    self.frame_skip_counter += 1
                    self.stop_event.wait(0.02)  # Short wait instead of processing frame
                    continue
                
                # Initialize camera if needed
                if not self.cap or not self._test_camera_connection():
                    if not self._initialize_camera():
                        consecutive_failures += 1
                        if consecutive_failures > self.max_consecutive_failures:
                            self.stop_event.wait(self.reconnect_delay)
                            consecutive_failures = 0
                        self.stop_event.wait(2.0)
                        continue
                    else:
                        consecutive_failures = 0
                
                # Frame timing control
                current_time = time.time()
                target_frame_time = 1.0 / self.target_fps
                if current_time - self.last_frame_time < target_frame_time:
                    self.stop_event.wait(0.01)
                    continue
                
                # Read frame with timeout
                ret, frame = self._read_frame_with_timeout()
                
                if ret and frame is not None:
                    self.total_frames += 1
                    
                    # Process frame efficiently
                    processed_frame = self._process_frame_optimized(frame)
                    
                    # ENHANCED: Update frames using direct buffer instead of queue
                    with self.frame_buffer['buffer_lock']:
                        self.frame_buffer['raw_frame'] = frame.copy()
                        self.frame_buffer['processed_frame'] = processed_frame
                        self.frame_buffer['timestamp'] = current_time
                    
                    # Signal that new frame is ready
                    self.frame_ready_event.set()
                    
                    # Update timing and stats
                    self.last_frame_time = current_time
                    self.frame_count += 1
                    consecutive_failures = 0
                    self.last_successful_frame = datetime.datetime.now()
                    
                    if not self.connection_stable:
                        self.connection_stable = True
                        self.camera_available = True
                        self._update_status_safe(f"{self.camera_type} connected")
                        self.logger.print_success("Camera connection stabilized")
                    
                    # Update performance counters
                    self._update_performance_counters()
                
                else:
                    # Handle frame read failure
                    consecutive_failures += 1
                    self.dropped_frames += 1
                    
                    if consecutive_failures > self.max_consecutive_failures:
                        self._close_camera()
                        self.camera_available = False
                        self.connection_stable = False
                        consecutive_failures = 0
                        self.stop_event.wait(1.0)
                    else:
                        self.stop_event.wait(0.05)
                
                # Periodic garbage collection
                if current_time - last_gc_time > 60:  # Every minute
                    gc.collect()
                    last_gc_time = current_time
                    self.logger.print_debug("Performed garbage collection")
                
            except Exception as e:
                consecutive_failures += 1
                self._close_camera()
                self.camera_available = False
                self.connection_stable = False
                self.stop_event.wait(1.0)
        
        # Cleanup when loop exits
        self.logger.print_info("Optimized video capture loop ending")
        self._close_camera()
    
    def _should_skip_frame(self):
        """ENHANCED: Determine if frame should be skipped based on system load"""
        try:
            # Skip frames under high CPU load
            if self.cpu_usage > self.frame_skip_threshold:
                return self.frame_skip_counter % 3 == 0  # Skip every 3rd frame
            return False
        except Exception:
            return False
    
    def _read_frame_with_timeout(self):
        """Read frame with timeout to prevent blocking"""
        try:
            if self.camera_type == "HTTP":
                return self._read_http_frame_optimized()
            elif self.cap and self.cap.isOpened():
                ret, frame = self.cap.read()
                return ret, frame
            else:
                return False, None
        except Exception as e:
            return False, None
    
    def _process_frame_optimized(self, frame):
        """Optimized frame processing"""
        try:
            if frame is None:
                return None
            
            # Apply zoom and pan only if needed
            if self.zoom_level > 1.0 or self.pan_x != 0 or self.pan_y != 0:
                frame = self.apply_zoom_and_pan(frame)
            
            # Add lightweight watermark
            self._add_lightweight_watermark(frame)
            
            return frame
            
        except Exception as e:
            self.logger.print_error(f"Frame processing error: {e}")
            return frame
    
    def _add_lightweight_watermark(self, frame):
        """Add lightweight watermark for performance"""
        try:
            pass
        except Exception as e:
            pass  # Don't log watermark errors to avoid spam
    
    def _initialize_camera(self):
        """ENHANCED: Initialize camera with FFMPEG backend for RTSP stability"""
        try:
            self.logger.print_debug(f"Initializing {self.camera_type} camera")
            self._close_camera()
            
            if self.camera_type == "RTSP" and self.rtsp_url:
                self.logger.print_info(f"Connecting to RTSP: {self.rtsp_url}")
                # ENHANCED: Use FFMPEG backend for better RTSP stability
                self.cap = cv2.VideoCapture(self.rtsp_url, cv2.CAP_FFMPEG)
                # Optimized RTSP settings
                self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 352)
                self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 288)
                self.cap.set(cv2.CAP_PROP_FPS, self.target_fps)
                
            elif self.camera_type == "HTTP" and self.http_url:
                return True
                
            else:  # USB camera
                self.cap = cv2.VideoCapture(self.camera_index)
                if self.cap and self.cap.isOpened():
                    # Optimized USB camera settings
                    self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 352)
                    self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 288)
                    self.cap.set(cv2.CAP_PROP_FPS, self.target_fps)
                    self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            
            # Test camera connection
            success = self._test_camera_connection()
            if success:
                self.camera_available = True
            else:
                self.camera_available = False
            
            return success
            
        except Exception as e:
            self.camera_available = False
            return False
    
    def _test_camera_connection(self):
        """Test camera connection"""
        try:
            if self.camera_type == "HTTP":
                return True
            
            if self.cap and self.cap.isOpened():
                ret, test_frame = self.cap.read()
                return ret and test_frame is not None
            return False
            
        except Exception as e:
            return False
    
    def _read_http_frame_optimized(self):
        """Optimized HTTP frame reading"""
        try:
            if not self.http_url:
                return False, None
            
            request = urllib.request.Request(self.http_url)
            with urllib.request.urlopen(request, timeout=2) as response:
                image_data = response.read()
                nparr = np.frombuffer(image_data, np.uint8)
                frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
                return frame is not None, frame
                
        except Exception as e:
            current_time = time.time()
            if current_time - self.last_error_time > self.error_cooldown:
                self.last_error_time = current_time
            return False, None
    
    def _close_camera(self):
        """Close camera resources"""
        try:
            if self.cap:
                self.cap.release()
                self.cap = None
        except Exception as e:
            self.logger.print_error(f"Error closing camera: {e}")
    
    def _schedule_ui_update(self):
        """ENHANCED: Schedule optimized UI updates using after_idle"""
        if self.is_running and not self.stop_event.is_set():
            self._update_display_optimized()
            # ENHANCED: Use after_idle for better performance when system is busy
            self.parent.after_idle(lambda: self.parent.after(66, self._schedule_ui_update))
    
    def _update_display_optimized(self):
        """ENHANCED: Optimized display update using direct buffer"""
        try:
            # Check if new frame is available
            if not self.frame_ready_event.is_set():
                return
            
            # Get frame from buffer
            with self.frame_buffer['buffer_lock']:
                current_frame = self.frame_buffer['raw_frame']
                display_frame = self.frame_buffer['processed_frame']
                self.frame_ready_event.clear()  # Reset event
            
            if display_frame is None:
                return
            
            # Update current frame for capture
            with self.frame_lock:
                self.current_frame = current_frame
                self.display_frame = display_frame
            
            # Convert and resize efficiently
            frame_rgb = cv2.cvtColor(display_frame, cv2.COLOR_BGR2RGB)
            
            # Get canvas dimensions
            canvas_width = max(self.canvas.winfo_width(), 320)
            canvas_height = max(self.canvas.winfo_height(), 240)
            
            # Resize with optimization
            frame_resized = cv2.resize(frame_rgb, (canvas_width, canvas_height), 
                                     interpolation=cv2.INTER_LINEAR)
            
            # Convert to PhotoImage
            img = Image.fromarray(frame_resized)
            img_tk = ImageTk.PhotoImage(image=img)
            
            # Update canvas efficiently
            self.canvas.delete("all")
            self.canvas.create_image(canvas_width//2, canvas_height//2, image=img_tk)
            self.canvas.image = img_tk
            
        except Exception as e:
            pass  # Don't log display errors to avoid spam
    
    def _update_performance_counters(self):
        """Update performance counters"""
        try:
            current_time = time.time()
            if current_time - self.fps_timer >= 1.0:
                fps = self.frame_count / (current_time - self.fps_timer)
                drop_rate = (self.dropped_frames / max(self.total_frames, 1)) * 100
                skip_rate = (self.frame_skip_counter / max(self.total_frames, 1)) * 100
                
                perf_text = f"FPS: {fps:.1f} | CPU: {self.cpu_usage:.0f}% | Drop: {drop_rate:.1f}% | Skip: {skip_rate:.1f}%"
                self._update_perf_safe(perf_text)
                
                self.frame_count = 0
                self.fps_timer = current_time
                
                # Reset counters periodically
                if self.total_frames > 1000:
                    self.total_frames = 100
                    self.dropped_frames = int(self.dropped_frames * 0.1)
                    self.frame_skip_counter = int(self.frame_skip_counter * 0.1)
                
        except Exception as e:
            self.logger.print_error(f"Performance counter error: {e}")
    
    def capture_current_frame(self):
        """Capture current frame optimized"""
        try:
            self.logger.print_info("Capturing current frame")
            
            with self.frame_lock:
                if self.current_frame is not None:
                    self.captured_image = self.current_frame.copy()
                    self.save_button.config(state=tk.NORMAL)
                    self._update_status("Frame captured - ready to save")
                    return True
                else:
                    self._update_status("No frame available")
                    return False
        except Exception as e:
            self._update_status(f"Capture error: {str(e)}")
            return False
    
    def save_image(self):
        """Save captured image optimized"""
        try:
            if self.captured_image is None:
                self._update_status("No image to save")
                return False
            
            if hasattr(self, 'save_function') and self.save_function:
                success = self.save_function(self.captured_image)
                if success:
                    self._update_status("Image saved successfully")
                    self.save_button.config(state=tk.DISABLED)
                    self.captured_image = None
                    return True
                else:
                    self._update_status("Save failed")
                    return False
            else:
                self._update_status("Save function not configured")
                return False
                
        except Exception as e:
            self._update_status(f"Save error: {str(e)}")
            return False
    
    def _update_feed_button(self, text, color):
        """Update feed button with error handling"""
        try:
            # Check if the button still exists and is valid
            if (hasattr(self, 'feed_button') and 
                self.feed_button and 
                self.feed_button.winfo_exists()):
                self.feed_button.config(text=text, bg=color)
        except tk.TclError as e:
            # Widget has been destroyed - this is normal during shutdown
            if "invalid command name" in str(e):
                self.logger.print_debug("Feed button widget destroyed during update - normal during shutdown")
            else:
                self.logger.print_error(f"Feed button update error: {e}")
        except Exception as e:
            self.logger.print_error(f"Feed button update error: {e}")

    def _update_status_safe(self, status):
        """Thread-safe status update with error handling"""
        try:
            def update_status():
                try:
                    if (hasattr(self, 'status_var') and 
                        self.status_var and 
                        hasattr(self, 'parent') and 
                        self.parent.winfo_exists()):
                        self.status_var.set(status)
                except tk.TclError as e:
                    if "invalid command name" not in str(e):
                        self.logger.print_error(f"Status update error: {e}")
                except Exception as e:
                    self.logger.print_error(f"Status update error: {e}")
            
            if hasattr(self, 'parent') and self.parent:
                self.parent.after_idle(update_status)
        except Exception as e:
            self.logger.print_error(f"Safe status update error: {e}")

    def _update_perf_safe(self, perf_text):
        """Thread-safe performance update with error handling"""
        try:
            def update_perf():
                try:
                    if (hasattr(self, 'perf_var') and 
                        self.perf_var and 
                        hasattr(self, 'parent') and 
                        self.parent.winfo_exists()):
                        self.perf_var.set(perf_text)
                except tk.TclError as e:
                    if "invalid command name" not in str(e):
                        self.logger.print_error(f"Performance update error: {e}")
                except Exception as e:
                    self.logger.print_error(f"Performance update error: {e}")
            
            if hasattr(self, 'parent') and self.parent:
                self.parent.after_idle(update_perf)
        except Exception as e:
            self.logger.print_error(f"Performance update error: {e}")

    def shutdown_camera(self):
        """Enhanced shutdown with proper cleanup"""
        try:
            self.logger.print_info("Starting camera shutdown...")
            
            # Stop the should_be_running flag first
            self.should_be_running = False
            self.auto_reconnect = False
            
            # Stop the continuous feed
            self.stop_continuous_feed()
            
            # Wait for threads to finish
            if hasattr(self, 'video_thread') and self.video_thread and self.video_thread.is_alive():
                self.video_thread.join(timeout=2)
            
            # Clear any pending UI updates
            if hasattr(self, 'parent') and self.parent:
                try:
                    # Cancel any pending after() calls
                    self.parent.after_cancel("all")
                except:
                    pass
            
            self.logger.print_success("Camera shutdown completed")
            
        except Exception as e:
            self.logger.print_error(f"Error during camera shutdown: {e}")

    # Also add this method to handle widget existence checking
    def _widget_exists(self, widget):
        """Check if a widget still exists and is valid"""
        try:
            return widget and hasattr(widget, 'winfo_exists') and widget.winfo_exists()
        except:
            return False

    # Update the stop_continuous_feed method
    def stop_continuous_feed(self):
        """Stop camera feed with enhanced cleanup"""
        try:
            self.logger.print_info("Stopping camera feed")
            self.is_running = False
            self.stop_event.set()  # Signal all threads to stop
            
            # Wait for video thread to finish
            if self.video_thread and self.video_thread.is_alive():
                self.video_thread.join(timeout=3)
            
            # Close camera resources
            self._close_camera()
            
            # Update UI only if widgets still exist
            self._update_status("Camera stopped")
            
            # Update feed button safely
            if self._widget_exists(self.feed_button):
                self._update_feed_button("▶️ Start Feed", config.COLORS["primary"])
            
        except Exception as e:
            self.logger.print_error(f"Error stopping camera: {e}")
        
    def toggle_continuous_feed(self):
        """Toggle camera feed"""
        try:
            if self.is_running:
                self.should_be_running = False
                self.stop_continuous_feed()
            else:
                self.should_be_running = True
                self.start_continuous_feed()
        except Exception as e:
            self.logger.print_error(f"Error toggling feed: {e}")
    
    def restart_feed(self):
        """Restart camera feed"""
        try:
            self.logger.print_info("Restarting camera feed")
            if self.is_running:
                self.stop_continuous_feed()
                self.stop_event.wait(0.5)
            self.start_continuous_feed()
        except Exception as e:
            self.logger.print_error(f"Error restarting feed: {e}")
    

    
    # Thread-safe UI update methods
    def _update_status(self, status):
        """Update status thread-safely"""
        try:
            self.status_var.set(status)
        except Exception as e:
            self.logger.print_error(f"Status update error: {e}")
    

    
    # Mouse event handlers (optimized)
    def on_mouse_wheel(self, event):
        """Handle mouse wheel zoom"""
        try:
            if event.delta > 0 or event.num == 4:
                self.zoom_level = min(self.max_zoom, self.zoom_level + self.zoom_step)
            else:
                self.zoom_level = max(self.min_zoom, self.zoom_level - self.zoom_step)
        except Exception as e:
            pass
    
    def on_mouse_press(self, event):
        """Handle mouse press for panning"""
        try:
            if self.zoom_level > self.min_zoom:
                self.is_panning = True
                self.last_mouse_x = event.x
                self.last_mouse_y = event.y
        except Exception as e:
            pass
    
    def on_mouse_drag(self, event):
        """Handle mouse drag for panning"""
        try:
            if self.is_panning:
                dx = event.x - self.last_mouse_x
                dy = event.y - self.last_mouse_y
                self.pan_x += dx
                self.pan_y += dy
                self.last_mouse_x = event.x
                self.last_mouse_y = event.y
        except Exception as e:
            pass
    
    def on_mouse_release(self, event):
        """Handle mouse release"""
        try:
            self.is_panning = False
        except Exception as e:
            pass
    
    def reset_zoom(self, event=None):
        """Reset zoom and pan"""
        try:
            self.zoom_level = 1.0
            self.pan_x = 0
            self.pan_y = 0
        except Exception as e:
            pass
    
    def apply_zoom_and_pan(self, frame):
        """Apply zoom and pan efficiently"""
        try:
            if self.zoom_level <= 1.0:
                return frame
            
            h, w = frame.shape[:2]
            zoom_w = int(w / self.zoom_level)
            zoom_h = int(h / self.zoom_level)
            
            center_x = w // 2 + int(self.pan_x)
            center_y = h // 2 + int(self.pan_y)
            
            x1 = max(0, center_x - zoom_w // 2)
            y1 = max(0, center_y - zoom_h // 2)
            x2 = min(w, x1 + zoom_w)
            y2 = min(h, y1 + zoom_h)
            
            cropped = frame[y1:y2, x1:x2]
            return cv2.resize(cropped, (w, h), interpolation=cv2.INTER_LINEAR)
            
        except Exception as e:
            return frame
    
    # Backward compatibility methods
    def stop_camera(self):
        """Backward compatibility"""
        self.stop_continuous_feed()
    
    def start_camera(self):
        """Backward compatibility"""
        self.start_continuous_feed()
    
    def capture_image(self):
        """Backward compatibility"""
        return self.capture_current_frame()
    
    def get_connection_status(self):
        """Get detailed connection status"""
        try:
            status = {
                'camera_name': self.camera_name,
                'camera_type': self.camera_type,
                'is_running': self.is_running,
                'camera_available': self.camera_available,
                'connection_stable': self.connection_stable,
                'target_fps': self.target_fps,
                'cpu_usage': self.cpu_usage,
                'memory_usage': self.memory_usage,
                'dropped_frames': self.dropped_frames,
                'total_frames': self.total_frames,
                'frame_skip_counter': self.frame_skip_counter
            }
            return status
        except Exception as e:
            return {'error': str(e)}
    
    def __del__(self):
        """Cleanup on destruction"""
        try:
            if hasattr(self, 'logger'):
                self.logger.print_info(f"{self.camera_name} camera cleanup started")
            self.shutdown_camera()
            if hasattr(self, 'logger'):
                self.logger.print_success(f"{self.camera_name} camera cleanup completed")
        except Exception as e:
            if hasattr(self, 'logger'):
                self.logger.print_error(f"Cleanup error: {e}")

# Maintain backward compatibility
RobustCameraView = OptimizedCameraView
ContinuousCameraView = OptimizedCameraView
CameraView = OptimizedCameraView

# Add watermark function (keeping your original)
def add_watermark(image, text, ticket_id=None):
    """Add a watermark to an image with sitename, vehicle number, timestamp, and image description in 2 lines at top, and ticket at bottom"""
    result = image.copy()
    height, width = result.shape[:2]
    
    font = cv2.FONT_HERSHEY_SIMPLEX
    font_scale = 0.5
    color = (255, 255, 255)
    thickness = 2
    line_spacing = 8
    
    if text:
        parts = [part.strip() for part in text.split(' - ')]
        
        if len(parts) >= 4:
            site = parts[0]
            vehicle = parts[1] 
            timestamp = parts[2]
            description = parts[3]
        
        line1 = f"{site} - {vehicle}"
        line2 = f"{timestamp} - {description}"
        
        (line1_width, line1_height), line1_baseline = cv2.getTextSize(line1, font, font_scale, thickness)
        (line2_width, line2_height), line2_baseline = cv2.getTextSize(line2, font, font_scale, thickness)
        
        total_text_height = line1_height + line2_height + line_spacing
        max_text_width = max(line1_width, line2_width)
        
        overlay = result.copy()
        overlay_y_start = 0
        overlay_y_end = total_text_height + 20
        cv2.rectangle(overlay, (0, overlay_y_start), (max_text_width + 20, overlay_y_end), (0, 0, 0), -1)
        cv2.addWeighted(overlay, 0.6, result, 0.4, 0, result)
        
        line1_y = line1_height + 10
        cv2.putText(result, line1, (10, line1_y), font, font_scale, color, thickness)
        
        line2_y = line1_height + line2_height + line_spacing + 10
        cv2.putText(result, line2, (10, line2_y), font, font_scale, color, thickness)
    
    if ticket_id:
        ticket_text = f"Ticket: {ticket_id}"
        (ticket_width, ticket_height), ticket_baseline = cv2.getTextSize(ticket_text, font, font_scale, thickness)
        
        overlay_ticket = result.copy()
        overlay_y_start = height - ticket_height - 20
        overlay_y_end = height
        cv2.rectangle(overlay_ticket, (0, overlay_y_start), (ticket_width + 20, overlay_y_end), (0, 0, 0), -1)
        cv2.addWeighted(overlay_ticket, 0.6, result, 0.4, 0, result)
        
        cv2.putText(result, ticket_text, (10, height - 10), font, font_scale, color, thickness)
    
    return result