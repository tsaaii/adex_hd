# Enhanced camera.py - HD Quality Support with Settings Integration
# Incorporates rtsp-test.py improvements for HD quality while maintaining compatibility

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
import psutil
import gc
import sys

# Completely suppress all OpenCV/FFMPEG output (from rtsp-test.py)
cv2.setLogLevel(0)
import warnings
warnings.filterwarnings("ignore")

# Redirect stderr to suppress codec errors (from rtsp-test.py)
class SuppressStderr:
    def __enter__(self):
        self.original_stderr = sys.stderr
        sys.stderr = open(os.devnull, 'w')
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        sys.stderr.close()
        sys.stderr = self.original_stderr

# Import the unified logging system
try:
    from unified_logging import setup_enhanced_logger
    LOGGING_AVAILABLE = True
except ImportError:
    LOGGING_AVAILABLE = False
    print("⚠️ Unified logging not available - falling back to print statements")

import config
from ui_components import HoverButton

class RobustCameraView:
    """Enhanced camera view with HD quality support and settings integration"""
    
    def __init__(self, parent, camera_index=0, camera_type="USB", camera_name="Camera", auto_start=True):
        # Setup logging first
        self.camera_name = camera_name
        self.setup_logging()
        
        self.parent = parent
        self.camera_index = camera_index
        self.camera_type = camera_type
        self.rtsp_url = None
        self.http_url = None
        
        # HD Quality settings (enhanced from rtsp-test.py)
        self.hd_quality_enabled = True
        self.min_hd_width = 1280  # Minimum HD width
        self.min_hd_height = 720  # Minimum HD height
        self.preferred_width = 1920  # Preferred Full HD width
        self.preferred_height = 1080  # Preferred Full HD height
        self.quality_test_attempts = 10  # Test attempts for HD quality
        
        # Performance optimization settings
        self.target_fps = 25  # Enhanced from rtsp-test.py
        self.max_fps = 30
        self.min_fps = 15
        self.adaptive_quality = True
        self.frame_skip_threshold = 80
        
        # Resource monitoring
        self.cpu_usage = 0
        self.memory_usage = 0
        self.last_resource_check = 0
        self.resource_check_interval = 2.0
        
        # Feed control with enhanced safety
        self.is_running = False
        self.should_be_running = True
        self.video_thread = None
        self.cap = None
        self.camera_available = False
        self.auto_reconnect = True
        self.reconnect_delay = 10.0
        self.checked_availability = False
        self.restart_in_progress = False
        
        # Threading events and locks
        self.stop_event = threading.Event()
        self.frame_ready_event = threading.Event()
        self.restart_lock = threading.Lock()
        
        # Frame management
        self.current_frame = None
        self.captured_image = None
        self.frame_lock = threading.Lock()
        self.display_frame = None
        
        # Frame buffer
        self.frame_buffer = {
            'raw_frame': None,
            'processed_frame': None,
            'timestamp': 0,
            'buffer_lock': threading.Lock()
        }
        
        # Connection state tracking
        self.connection_stable = False
        self.last_error_time = 0
        self.error_cooldown = 10
        self.last_successful_frame = None
        self.max_consecutive_failures = 15
        self.initialization_attempts = 0
        self.max_init_attempts = 3
        
        # Performance counters
        self.frame_count = 0
        self.fps_timer = time.time()
        self.last_frame_time = 0
        self.dropped_frames = 0
        self.total_frames = 0
        self.frame_skip_counter = 0
        
        # Zoom functionality
        self.zoom_level = 1.0
        self.min_zoom = 1.0
        self.max_zoom = 5.0
        self.zoom_step = 0.2
        self.pan_x = 0
        self.pan_y = 0
        self.is_panning = False
        self.last_mouse_x = 0
        self.last_mouse_y = 0
        
        # Save function callback
        self.save_function = None
        
        # Create UI and start
        self.create_ui()
        self.start_watchdog()
        
        if auto_start:
            self.start_continuous_feed()
    
    def setup_logging(self):
        """Setup logging for camera operations"""
        if LOGGING_AVAILABLE:
            try:
                self.logger = setup_enhanced_logger(f"camera_{self.camera_name}")
            except Exception as e:
                print(f"Failed to setup enhanced logging: {e}")
                self.logger = None
        else:
            self.logger = None
    
    def set_rtsp_config(self, rtsp_url):
        """Configure RTSP camera settings from settings panel"""
        self.rtsp_url = rtsp_url
        self.camera_type = "RTSP"
        if self.logger:
            self.logger.print_info(f"RTSP configuration updated: {rtsp_url}")
        else:
            print(f"RTSP configuration updated: {rtsp_url}")
    
    def set_http_config(self, http_url):
        """Configure HTTP camera settings from settings panel"""
        self.http_url = http_url
        self.camera_type = "HTTP"
        if self.logger:
            self.logger.print_info(f"HTTP configuration updated: {http_url}")
        else:
            print(f"HTTP configuration updated: {http_url}")
    
    @staticmethod
    def detect_available_cameras(max_cameras=5):
        """Detect available USB cameras"""
        available_cameras = []
        for i in range(max_cameras):
            cap = cv2.VideoCapture(i)
            if cap.isOpened():
                ret, _ = cap.read()
                if ret:
                    available_cameras.append(i)
                cap.release()
        return available_cameras
    
    def create_ui(self):
        """Create optimized camera UI with all control buttons"""
        try:
            # Main frame
            self.frame = ttk.Frame(self.parent)
            self.frame.pack(fill=tk.BOTH, expand=True, padx=3, pady=3)
            
            # Video display canvas
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
            
            # Show initial message
            self.show_status_message("Initializing camera...")
            
            # Controls frame
            controls = ttk.Frame(self.frame)
            controls.pack(fill=tk.X, padx=2, pady=2)
            
            # Main controls
            main_controls = ttk.Frame(controls)
            main_controls.pack(fill=tk.X, pady=1)
            
            # Feed toggle button
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
            if self.logger:
                self.logger.print_error(f"UI creation error: {e}")
            else:
                print(f"UI creation error: {e}")
    
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
            if self.logger:
                self.logger.print_error(f"Error showing status message: {e}")
    
    def start_continuous_feed(self):
        """Start continuous camera feed with enhanced error handling"""
        try:
            with self.restart_lock:
                if self.is_running or self.restart_in_progress:
                    if self.logger:
                        self.logger.print_debug("Camera feed already running or restart in progress")
                    else:
                        print("Camera feed already running or restart in progress")
                    return
                
                self.restart_in_progress = True
            
            if self.logger:
                self.logger.print_info(f"Starting {self.camera_name} continuous feed with HD quality")
            else:
                print(f"Starting {self.camera_name} continuous feed with HD quality")
            
            self.stop_event.clear()
            self.is_running = True
            self.should_be_running = True
            self.initialization_attempts = 0
            
            self.video_thread = threading.Thread(target=self._safe_video_loop, daemon=True)
            self.video_thread.start()
            
            self._schedule_ui_update()
            
            with self.restart_lock:
                self.restart_in_progress = False
            
        except Exception as e:
            if self.logger:
                self.logger.print_error(f"Failed to start continuous feed: {e}")
            else:
                print(f"Failed to start continuous feed: {e}")
            self.is_running = False
            with self.restart_lock:
                self.restart_in_progress = False
    
    def stop_continuous_feed(self):
        """Stop continuous camera feed with enhanced cleanup"""
        try:
            with self.restart_lock:
                if self.restart_in_progress:
                    if self.logger:
                        self.logger.print_debug("Stop requested but restart in progress, waiting...")
                    else:
                        print("Stop requested but restart in progress, waiting...")
                    return
                
                self.restart_in_progress = True
            
            if self.logger:
                self.logger.print_info(f"Stopping {self.camera_name} continuous feed")
            else:
                print(f"Stopping {self.camera_name} continuous feed")
            
            self.should_be_running = False
            self.is_running = False
            self.stop_event.set()
            
            if self.video_thread and self.video_thread.is_alive():
                self.video_thread.join(timeout=5.0)
                if self.video_thread.is_alive():
                    if self.logger:
                        self.logger.print_warning("Video thread did not stop gracefully within timeout")
            
            self._safe_close_camera()
            
            with self.restart_lock:
                self.restart_in_progress = False
            
        except Exception as e:
            if self.logger:
                self.logger.print_error(f"Error stopping continuous feed: {e}")
            else:
                print(f"Error stopping continuous feed: {e}")
            with self.restart_lock:
                self.restart_in_progress = False
    
    def restart_feed(self):
        """Restart camera feed with enhanced safety"""
        try:
            with self.restart_lock:
                if self.restart_in_progress:
                    if self.logger:
                        self.logger.print_debug("Restart already in progress, skipping")
                    else:
                        print("Restart already in progress, skipping")
                    return
                
                self.restart_in_progress = True
            
            if self.logger:
                self.logger.print_info("Restarting camera feed with safety delays")
            else:
                print("Restarting camera feed with safety delays")
            
            if self.is_running:
                self.should_be_running = False
                self.is_running = False
                self.stop_event.set()
                
                if self.video_thread and self.video_thread.is_alive():
                    self.video_thread.join(timeout=3.0)
                
                self._safe_close_camera()
            
            time.sleep(2.0)
            
            with self.restart_lock:
                self.restart_in_progress = False
            
            self.initialization_attempts = 0
            self.start_continuous_feed()
            
        except Exception as e:
            if self.logger:
                self.logger.print_error(f"Error restarting feed: {e}")
            else:
                print(f"Error restarting feed: {e}")
            with self.restart_lock:
                self.restart_in_progress = False
    
    def _safe_video_loop(self):
        """Enhanced video capture loop with comprehensive error handling"""
        try:
            if self.logger:
                self.logger.print_info("Enhanced HD video capture loop started")
            else:
                print("Enhanced HD video capture loop started")
            
            consecutive_failures = 0
            stable_frames = 0
            last_gc_time = time.time()
            
            while not self.stop_event.is_set() and self.is_running:
                try:
                    if self._should_skip_frame():
                        self.frame_skip_counter += 1
                        self.stop_event.wait(0.02)
                        continue
                    
                    if not self.cap or not self._safe_test_camera_connection():
                        if self.initialization_attempts >= self.max_init_attempts:
                            if self.logger:
                                self.logger.print_warning(f"Max initialization attempts reached, waiting...")
                            else:
                                print(f"Max initialization attempts reached, waiting...")
                            self.stop_event.wait(30.0)
                            self.initialization_attempts = 0
                            continue
                        
                        if not self._safe_initialize_camera():
                            consecutive_failures += 1
                            self.initialization_attempts += 1
                            if consecutive_failures > self.max_consecutive_failures:
                                self.stop_event.wait(self.reconnect_delay * 2)
                                consecutive_failures = 0
                            else:
                                self.stop_event.wait(min(consecutive_failures * 2, 10))
                            continue
                        else:
                            consecutive_failures = 0
                            self.initialization_attempts = 0
                    
                    current_time = time.time()
                    target_frame_time = 1.0 / self.target_fps
                    if current_time - self.last_frame_time < target_frame_time:
                        time.sleep(0.04)
                        continue
                    
                    with SuppressStderr():
                        ret, frame = self.cap.read()
                    
                    if ret and frame is not None and frame.size > 0:
                        self.total_frames += 1
                        h, w = frame.shape[:2]
                        
                        if self.camera_type == "RTSP" and self.hd_quality_enabled:
                            if h >= self.min_hd_height and w >= self.min_hd_width:
                                stable_frames += 1
                                current_frame_copy = frame.copy()
                                
                                if stable_frames >= 3:
                                    processed_frame = self._process_frame_optimized(frame)
                                    
                                    try:
                                        with self.frame_buffer['buffer_lock']:
                                            self.frame_buffer['raw_frame'] = current_frame_copy
                                            self.frame_buffer['processed_frame'] = processed_frame
                                            self.frame_buffer['timestamp'] = current_time
                                        
                                        self.frame_ready_event.set()
                                    except Exception as buffer_error:
                                        if self.logger:
                                            self.logger.print_error(f"Buffer update error: {buffer_error}")
                                        continue
                                else:
                                    continue
                            else:
                                stable_frames = 0
                                continue
                        else:
                            stable_frames += 1
                            processed_frame = self._process_frame_optimized(frame)
                            
                            try:
                                with self.frame_buffer['buffer_lock']:
                                    self.frame_buffer['raw_frame'] = frame.copy()
                                    self.frame_buffer['processed_frame'] = processed_frame
                                    self.frame_buffer['timestamp'] = current_time
                                
                                self.frame_ready_event.set()
                            except Exception as buffer_error:
                                if self.logger:
                                    self.logger.print_error(f"Buffer update error: {buffer_error}")
                                continue
                        
                        self.last_frame_time = current_time
                        self.frame_count += 1
                        consecutive_failures = 0
                        self.last_successful_frame = datetime.datetime.now()
                        
                        if not self.connection_stable:
                            self.connection_stable = True
                            if self.logger:
                                self.logger.print_success(f"{self.camera_type} HD connection stable")
                            else:
                                print(f"{self.camera_type} HD connection stable")
                    else:
                        consecutive_failures += 1
                        stable_frames = 0
                        if consecutive_failures > self.max_consecutive_failures:
                            if self.logger:
                                self.logger.print_error("Too many consecutive failures, reinitializing")
                            else:
                                print("Too many consecutive failures, reinitializing")
                            self._safe_close_camera()
                            time.sleep(2)
                            consecutive_failures = 0
                        else:
                            time.sleep(0.1)
                    
                    if current_time - last_gc_time > 60.0:
                        self._update_resource_usage()
                        self._adjust_performance()
                        last_gc_time = current_time
                
                except Exception as loop_error:
                    if self.logger:
                        self.logger.print_error(f"Video loop error: {loop_error}")
                    else:
                        print(f"Video loop error: {loop_error}")
                    consecutive_failures += 1
                    stable_frames = 0
                    self._safe_close_camera()
                    time.sleep(min(consecutive_failures, 10))
            
        except Exception as e:
            if self.logger:
                self.logger.print_error(f"Critical video loop error: {e}")
            else:
                print(f"Critical video loop error: {e}")
        finally:
            self._safe_close_camera()
            if self.logger:
                self.logger.print_info(f"{self.camera_name} video loop ended safely")
            else:
                print(f"{self.camera_name} video loop ended safely")
    
    def _safe_initialize_camera(self):
        """Enhanced camera initialization with HD quality testing"""
        try:
            if self.logger:
                self.logger.print_debug(f"Initializing {self.camera_type} camera with HD quality")
            else:
                print(f"Initializing {self.camera_type} camera with HD quality")
            
            self._safe_close_camera()
            time.sleep(0.5)
            
            if self.camera_type == "RTSP" and self.rtsp_url:
                if self.logger:
                    self.logger.print_info(f"Connecting to RTSP: {self.rtsp_url}")
                else:
                    print(f"Connecting to RTSP: {self.rtsp_url}")
                
                with SuppressStderr():
                    self.cap = cv2.VideoCapture(self.rtsp_url)
                    
                    if not self.cap or not self.cap.isOpened():
                        if self.logger:
                            self.logger.print_warning("Failed to open RTSP stream")
                        else:
                            print("Failed to open RTSP stream")
                        return False
                    
                    self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 3)
                    self.cap.set(cv2.CAP_PROP_FPS, self.target_fps)
                    
                    time.sleep(2)
                    
                    hd_connection_successful = False
                    for attempt in range(self.quality_test_attempts):
                        if self.stop_event.is_set():
                            return False
                        
                        ret, test_frame = self.cap.read()
                        if ret and test_frame is not None and test_frame.size > 0:
                            h, w = test_frame.shape[:2]
                            if h >= self.min_hd_height and w >= self.min_hd_width:
                                hd_connection_successful = True
                                if self.logger:
                                    self.logger.print_success(f"HD Connected ({w}x{h})")
                                else:
                                    print(f"HD Connected ({w}x{h})")
                                break
                        time.sleep(0.1)
                    
                    if not hd_connection_successful:
                        if self.logger:
                            self.logger.print_warning("Could not establish HD quality connection")
                        else:
                            print("Could not establish HD quality connection")
                        self._safe_close_camera()
                        return False
                
            elif self.camera_type == "HTTP" and self.http_url:
                return True
                
            else:  # USB camera
                try:
                    self.cap = cv2.VideoCapture(self.camera_index)
                    if self.cap and self.cap.isOpened():
                        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.preferred_width)
                        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.preferred_height)
                        self.cap.set(cv2.CAP_PROP_FPS, self.target_fps)
                        self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                        
                        ret, test_frame = self.cap.read()
                        if ret and test_frame is not None:
                            h, w = test_frame.shape[:2]
                            if h < self.min_hd_height or w < self.min_hd_width:
                                self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.min_hd_width)
                                self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.min_hd_height)
                    else:
                        if self.logger:
                            self.logger.print_warning(f"Failed to open USB camera {self.camera_index}")
                        else:
                            print(f"Failed to open USB camera {self.camera_index}")
                        return False
                except Exception as usb_error:
                    if self.logger:
                        self.logger.print_error(f"USB camera initialization error: {usb_error}")
                    else:
                        print(f"USB camera initialization error: {usb_error}")
                    return False
            
            success = self._safe_test_camera_connection()
            if success:
                self.camera_available = True
            else:
                self.camera_available = False
                self._safe_close_camera()
            
            return success
            
        except Exception as e:
            if self.logger:
                self.logger.print_error(f"Camera initialization error: {e}")
            else:
                print(f"Camera initialization error: {e}")
            self.camera_available = False
            self._safe_close_camera()
            return False
    
    def _safe_test_camera_connection(self):
        """Test camera connection with HD quality validation"""
        try:
            if self.camera_type == "HTTP":
                return True
            
            if self.cap and self.cap.isOpened():
                for attempt in range(3):
                    if self.stop_event.is_set():
                        return False
                    
                    ret, test_frame = self.cap.read()
                    if ret and test_frame is not None:
                        if self.hd_quality_enabled:
                            h, w = test_frame.shape[:2]
                            if h >= self.min_hd_height and w >= self.min_hd_width:
                                return True
                            else:
                                if attempt == 2:
                                    if self.logger:
                                        self.logger.print_warning(f"Low quality: {w}x{h}, required: {self.min_hd_width}x{self.min_hd_height}")
                                    else:
                                        print(f"Low quality: {w}x{h}, required: {self.min_hd_width}x{self.min_hd_height}")
                        else:
                            return True
                    
                    time.sleep(0.1)
                
                return False
            
            return False
            
        except Exception as e:
            if self.logger:
                self.logger.print_error(f"Camera connection test failed: {e}")
            else:
                print(f"Camera connection test failed: {e}")
            return False
    
    def _safe_close_camera(self):
        """Close camera resources safely"""
        try:
            if hasattr(self, 'cap') and self.cap:
                time.sleep(0.1)
                self.cap.release()
                self.cap = None
                time.sleep(0.1)
        except Exception as e:
            if self.logger:
                self.logger.print_error(f"Error closing camera safely: {e}")
            else:
                print(f"Error closing camera safely: {e}")
        finally:
            self.cap = None
    
    def _should_skip_frame(self):
        """Determine if frame should be skipped for performance"""
        try:
            current_time = time.time()
            if current_time - self.last_resource_check > self.resource_check_interval:
                self._update_resource_usage()
                self.last_resource_check = current_time
            
            if self.cpu_usage > self.frame_skip_threshold:
                return True
            
            return False
        except Exception as e:
            return False
    
    def _update_resource_usage(self):
        """Update system resource usage monitoring"""
        try:
            self.cpu_usage = psutil.cpu_percent(interval=None)
            self.memory_usage = psutil.virtual_memory().percent
        except Exception as e:
            if self.logger:
                self.logger.print_error(f"Resource monitoring error: {e}")
    
    def _adjust_performance(self):
        """Dynamically adjust performance based on system resources"""
        try:
            if self.cpu_usage > 85:
                self.target_fps = max(self.min_fps, self.target_fps - 1)
            elif self.cpu_usage < 50:
                self.target_fps = min(self.max_fps, self.target_fps + 0.5)
            
            if self.memory_usage > 85:
                if self.logger:
                    self.logger.print_warning(f"High memory usage ({self.memory_usage:.1f}%), triggering garbage collection")
                else:
                    print(f"High memory usage ({self.memory_usage:.1f}%), triggering garbage collection")
                gc.collect()
                
        except Exception as e:
            if self.logger:
                self.logger.print_error(f"Performance adjustment error: {e}")
    
    def _process_frame_optimized(self, frame):
        """Enhanced frame processing with HD quality preservation"""
        try:
            if frame is None:
                return None
            
            if self.zoom_level > 1.0 or self.pan_x != 0 or self.pan_y != 0:
                frame = self.apply_zoom_and_pan(frame)
            
            self._add_lightweight_watermark(frame)
            
            return frame
            
        except Exception as e:
            if self.logger:
                self.logger.print_error(f"Frame processing error: {e}")
            return frame
    
    def _add_lightweight_watermark(self, frame):
        """Add lightweight watermark for performance"""
        try:
            pass  # Implement watermark if needed
        except Exception as e:
            pass  # Don't log watermark errors to avoid spam
    
    def _read_frame_with_timeout(self):
        """Read frame with timeout handling"""
        try:
            if self.camera_type == "HTTP":
                return self._read_http_frame_optimized()
            elif self.cap and self.cap.isOpened():
                return self.cap.read()
            else:
                return False, None
        except Exception as e:
            if self.logger:
                self.logger.print_error(f"Frame read error: {e}")
            return False, None
    
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
    
    def _schedule_ui_update(self):
        """Schedule optimized UI updates"""
        if self.is_running and not self.stop_event.is_set():
            self._update_display_optimized()
            self.parent.after_idle(lambda: self.parent.after(66, self._schedule_ui_update))
    
    def _update_display_optimized(self):
        """Enhanced display update preserving HD quality for captures"""
        try:
            # Check if new frame is available
            if not self.frame_ready_event.is_set():
                return
            
            # Get frame from buffer
            with self.frame_buffer['buffer_lock']:
                current_frame = self.frame_buffer['raw_frame']
                display_frame = self.frame_buffer['processed_frame']
                self.frame_ready_event.clear()
            
            if display_frame is None:
                return
            
            # Update current frame for capture (PRESERVE HD QUALITY)
            with self.frame_lock:
                self.current_frame = current_frame  # Store full HD for capture
                self.display_frame = display_frame
            
            # Convert and resize for display using rtsp-test.py approach
            frame_rgb = cv2.cvtColor(display_frame, cv2.COLOR_BGR2RGB)
            
            # Get canvas dimensions for display scaling
            canvas_width = max(self.canvas.winfo_width(), 320)
            canvas_height = max(self.canvas.winfo_height(), 240)
            
            # Enhanced HD display resize (from rtsp-test.py approach)
            h, w = display_frame.shape[:2]
            if canvas_width > 400:  # Larger display - use HD approach from rtsp-test.py
                display_w = 800
                display_h = int(display_w * h / w)
                frame_resized = cv2.resize(frame_rgb, (display_w, display_h), 
                                         interpolation=cv2.INTER_CUBIC)  # CUBIC from rtsp-test.py
                # Scale down to fit canvas if needed
                if display_w > canvas_width or display_h > canvas_height:
                    frame_resized = cv2.resize(frame_resized, (canvas_width, canvas_height),
                                             interpolation=cv2.INTER_LINEAR)
            else:
                # Smaller display - direct resize
                frame_resized = cv2.resize(frame_rgb, (canvas_width, canvas_height), 
                                         interpolation=cv2.INTER_LINEAR)
            
            # Convert to PhotoImage for display
            img = Image.fromarray(frame_resized)
            img_tk = ImageTk.PhotoImage(image=img)
            
            # Update canvas efficiently
            self.canvas.delete("all")
            self.canvas.create_image(canvas_width//2, canvas_height//2, image=img_tk)
            self.canvas.image = img_tk
            
        except Exception as e:
            pass  # Don't log display errors to avoid spam
    
    def start_watchdog(self):
        """Start enhanced watchdog thread for auto-recovery"""
        try:
            def enhanced_watchdog():
                if self.logger:
                    self.logger.print_debug("Enhanced camera watchdog started")
                else:
                    print("Enhanced camera watchdog started")
                
                last_check_time = time.time()
                
                while not self.stop_event.is_set():
                    try:
                        current_time = time.time()
                        
                        # Reduce watchdog frequency to prevent excessive restarts
                        if current_time - last_check_time < 30.0:  # Check every 30 seconds
                            self.stop_event.wait(5.0)
                            continue
                        
                        last_check_time = current_time
                        
                        # Only restart if really needed and not already in progress
                        with self.restart_lock:
                            if self.restart_in_progress:
                                continue
                        
                        # Check if camera should be running but isn't
                        if self.should_be_running and not self.is_running and not self.restart_in_progress:
                            if self.logger:
                                self.logger.print_info("Watchdog: Camera should be running but isn't, restarting...")
                            else:
                                print("Watchdog: Camera should be running but isn't, restarting...")
                            self.start_continuous_feed()
                        
                        # Check for stale connections (extended timeout)
                        elif self.last_successful_frame:
                            time_since_frame = datetime.datetime.now() - self.last_successful_frame
                            if time_since_frame.total_seconds() > 120:  # 2 minutes instead of 30 seconds
                                if self.logger:
                                    self.logger.print_warning("Watchdog: No frames for 2 minutes, restarting feed...")
                                else:
                                    print("Watchdog: No frames for 2 minutes, restarting feed...")
                                self.restart_feed()
                        
                        # Use event wait instead of sleep with longer intervals
                        self.stop_event.wait(self.reconnect_delay)
                        
                    except Exception as e:
                        if self.logger:
                            self.logger.print_error(f"Watchdog error: {e}")
                        else:
                            print(f"Watchdog error: {e}")
                        self.stop_event.wait(30.0)  # Extended wait on error
            
            watchdog_thread = threading.Thread(target=enhanced_watchdog, daemon=True)
            watchdog_thread.start()
            if self.logger:
                self.logger.print_debug("Enhanced camera watchdog enabled")
            else:
                print("Enhanced camera watchdog enabled")
        except Exception as e:
            if self.logger:
                self.logger.print_error(f"Failed to start enhanced watchdog: {e}")
            else:
                print(f"Failed to start enhanced watchdog: {e}")
    
    def toggle_continuous_feed(self):
        """Toggle camera feed with button updates"""
        try:
            if self.is_running:
                self.should_be_running = False
                self.stop_continuous_feed()
                self._update_feed_button("▶️ Start Feed", config.COLORS["primary"])
            else:
                self.should_be_running = True
                self.start_continuous_feed()
                self._update_feed_button("⏹️ Stop Feed", config.COLORS["error"])
        except Exception as e:
            if self.logger:
                self.logger.print_error(f"Error toggling feed: {e}")
    
    def _update_feed_button(self, text, color):
        """Update feed button with error handling"""
        try:
            if (hasattr(self, 'feed_button') and 
                self.feed_button and 
                self.feed_button.winfo_exists()):
                self.feed_button.config(text=text, bg=color)
        except tk.TclError as e:
            if "invalid command name" in str(e):
                if self.logger:
                    self.logger.print_debug("Feed button widget destroyed during update")
            else:
                if self.logger:
                    self.logger.print_error(f"Feed button update error: {e}")
        except Exception as e:
            if self.logger:
                self.logger.print_error(f"Feed button update error: {e}")
    
    def capture_current_frame(self):
        """Capture current HD frame for saving"""
        try:
            if self.logger:
                self.logger.print_info("Capturing current HD frame")
            else:
                print("Capturing current HD frame")
            
            with self.frame_lock:
                if self.current_frame is not None:
                    self.captured_image = self.current_frame.copy()  # Full HD quality preserved
                    
                    # Log the captured frame quality
                    h, w = self.captured_image.shape[:2]
                    if self.logger:
                        self.logger.print_success(f"HD frame captured: {w}x{h}")
                    else:
                        print(f"HD frame captured: {w}x{h}")
                    
                    # Enable save button
                    self.save_button.config(state=tk.NORMAL)
                    self._update_status_safe("Frame captured - ready to save")
                    return True
                else:
                    if self.logger:
                        self.logger.print_warning("No frame available for capture")
                    else:
                        print("No frame available for capture")
                    self._update_status_safe("No frame available")
                    return False
        except Exception as e:
            if self.logger:
                self.logger.print_error(f"Capture error: {str(e)}")
            else:
                print(f"Capture error: {str(e)}")
            self._update_status_safe(f"Capture error: {str(e)}")
            return False
    
    def save_image(self):
        """Save captured HD image with enhanced file safety"""
        try:
            if self.captured_image is None:
                self._update_status_safe("No image to save")
                return False
            
            # Try configured save function first
            if hasattr(self, 'save_function') and self.save_function:
                try:
                    success = self.save_function(self.captured_image)
                    if success:
                        self._update_status_safe("Image saved successfully")
                        self.save_button.config(state=tk.DISABLED)
                        self.captured_image = None
                        return True
                    else:
                        if self.logger:
                            self.logger.print_warning("Configured save function failed, trying fallback")
                        else:
                            print("Configured save function failed, trying fallback")
                except Exception as save_func_error:
                    if self.logger:
                        self.logger.print_error(f"Save function error: {save_func_error}")
                    else:
                        print(f"Save function error: {save_func_error}")
            
            # Fallback save method with file safety
            try:
                # Ensure directory exists
                images_dir = "captured_images"
                os.makedirs(images_dir, exist_ok=True)
                
                # Create safe filename
                timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                safe_camera_name = "".join(c for c in self.camera_name if c.isalnum() or c in (' ', '-', '_')).rstrip()
                filename = f"{images_dir}/camera_{safe_camera_name}_{timestamp}.jpg"
                
                # Ensure filename is unique
                counter = 1
                original_filename = filename
                while os.path.exists(filename):
                    base_name = original_filename.rsplit('.', 1)[0]
                    extension = original_filename.rsplit('.', 1)[1]
                    filename = f"{base_name}_{counter:03d}.{extension}"
                    counter += 1
                
                # Save with high quality
                success = cv2.imwrite(filename, self.captured_image, [cv2.IMWRITE_JPEG_QUALITY, 95])
                
                if success:
                    # Verify file was created and has content
                    if os.path.exists(filename) and os.path.getsize(filename) > 0:
                        if self.logger:
                            self.logger.print_success(f"HD image saved: {filename}")
                        else:
                            print(f"HD image saved: {filename}")
                        
                        self._update_status_safe(f"Image saved: {os.path.basename(filename)}")
                        self.save_button.config(state=tk.DISABLED)
                        self.captured_image = None
                        return True
                    else:
                        if self.logger:
                            self.logger.print_error(f"File created but appears empty: {filename}")
                        self._update_status_safe("Save failed - file empty")
                        return False
                else:
                    if self.logger:
                        self.logger.print_error(f"cv2.imwrite failed for: {filename}")
                    self._update_status_safe("Save failed - write error")
                    return False
                    
            except PermissionError as perm_error:
                if self.logger:
                    self.logger.print_error(f"Permission denied saving image: {perm_error}")
                self._update_status_safe("Save failed - permission denied")
                return False
            except OSError as os_error:
                if self.logger:
                    self.logger.print_error(f"OS error saving image: {os_error}")
                self._update_status_safe("Save failed - disk error")
                return False
            except Exception as fallback_error:
                if self.logger:
                    self.logger.print_error(f"Fallback save error: {fallback_error}")
                self._update_status_safe(f"Save failed: {str(fallback_error)}")
                return False
                
        except Exception as e:
            if self.logger:
                self.logger.print_error(f"Critical save error: {str(e)}")
            self._update_status_safe(f"Save error: {str(e)}")
            return False
    
    def _update_status_safe(self, status):
        """Thread-safe status update"""
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
                        if self.logger:
                            self.logger.print_error(f"Status update error: {e}")
                except Exception as e:
                    if self.logger:
                        self.logger.print_error(f"Status update error: {e}")
            
            if hasattr(self, 'parent') and self.parent:
                self.parent.after_idle(update_status)
        except Exception as e:
            if self.logger:
                self.logger.print_error(f"Safe status update error: {e}")

    def _update_perf_safe(self, perf_text):
        """Thread-safe performance update"""
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
                        if self.logger:
                            self.logger.print_error(f"Performance update error: {e}")
                except Exception as e:
                    if self.logger:
                        self.logger.print_error(f"Performance update error: {e}")
            
            if hasattr(self, 'parent') and self.parent:
                self.parent.after_idle(update_perf)
        except Exception as e:
            if self.logger:
                self.logger.print_error(f"Performance update error: {e}")
    
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
            if self.logger:
                self.logger.print_error(f"Performance counter error: {e}")
    
    def _widget_exists(self, widget):
        """Check if a widget still exists and is valid"""
        try:
            return widget and hasattr(widget, 'winfo_exists') and widget.winfo_exists()
        except:
            return False
    
    # Mouse event handlers for zoom and pan functionality
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
        """Apply zoom and pan efficiently while preserving HD quality"""
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
                'frame_skip_counter': self.frame_skip_counter,
                'hd_quality_enabled': self.hd_quality_enabled,
                'min_resolution': f"{self.min_hd_width}x{self.min_hd_height}"
            }
            return status
        except Exception as e:
            return {'error': str(e)}
    
    def shutdown_camera(self):
        """Enhanced shutdown with comprehensive cleanup"""
        try:
            if self.logger:
                self.logger.print_info(f"{self.camera_name} camera shutdown initiated")
            else:
                print(f"{self.camera_name} camera shutdown initiated")
            
            # Set shutdown flags
            self.should_be_running = False
            self.auto_reconnect = False
            
            # Stop the continuous feed
            self.stop_continuous_feed()
            
            # Wait for threads to finish
            if hasattr(self, 'video_thread') and self.video_thread and self.video_thread.is_alive():
                try:
                    self.video_thread.join(timeout=10.0)
                    if self.video_thread.is_alive():
                        if self.logger:
                            self.logger.print_warning("Video thread did not stop within timeout")
                except Exception as thread_error:
                    if self.logger:
                        self.logger.print_error(f"Error waiting for video thread: {thread_error}")
            
            # Final cleanup
            self._safe_close_camera()
            
            if self.logger:
                self.logger.print_success(f"{self.camera_name} camera shutdown completed")
            else:
                print(f"{self.camera_name} camera shutdown completed")
        except Exception as e:
            if self.logger:
                self.logger.print_error(f"Shutdown error: {e}")
            else:
                print(f"Shutdown error: {e}")
    
    def __del__(self):
        """Enhanced cleanup on destruction"""
        try:
            if hasattr(self, 'logger') and self.logger:
                self.logger.print_info(f"{self.camera_name} camera cleanup started")
            self.shutdown_camera()
        except Exception as e:
            if hasattr(self, 'logger') and self.logger:
                self.logger.print_error(f"Cleanup error: {e}")
            else:
                print(f"Cleanup error: {e}")
    
    # Backward compatibility methods (maintain exact method names)
    def stop_camera(self):
        """Backward compatibility"""
        self.stop_continuous_feed()
    
    def start_camera(self):
        """Backward compatibility"""
        self.start_continuous_feed()
    
    def capture_image(self):
        """Backward compatibility"""
        return self.capture_current_frame()
    
    def _close_camera(self):
        """Backward compatibility - redirect to safe version"""
        self._safe_close_camera()
    
    def _test_camera_connection(self):
        """Backward compatibility - redirect to safe version"""
        return self._safe_test_camera_connection()
    
    def _initialize_camera(self):
        """Backward compatibility - redirect to safe version"""
        return self._safe_initialize_camera()

# Maintain backward compatibility with exact class names
RobustCameraView = RobustCameraView  # Keep original name
ContinuousCameraView = RobustCameraView  # Alias
CameraView = RobustCameraView  # Alias

# Enhanced watermark function (keeping your original structure)
def add_watermark(image, text, ticket_id=None, size="large"):
    """
    Add a watermark to an image with configurable size
    
    Args:
        image: OpenCV image
        text: Watermark text
        ticket_id: Optional ticket ID to include
        size: "normal" (default) or "large" for PDF visibility
    """
    result = image.copy()
    height, width = result.shape[:2]
    
    font = cv2.FONT_HERSHEY_SIMPLEX
    
    # ENHANCED: Adjust font scale and thickness based on size parameter
    if size == "large":
        # Large size for PDF visibility
        font_scale = max(1.5, width / 600)  # Much larger
        thickness = max(4, int(width / 250))  # Much thicker
        bg_alpha = 0.4  # More opaque background
    else:
        # Normal size for regular images
        font_scale = 0.7
        thickness = 2
        bg_alpha = 0.3  # Less opaque background
    
    color = (255, 255, 255)  # White text
    line_spacing = 8  # Space between lines
    
    # Add main watermark at TOP
    if text:
        # Parse the text to extract components
        # Expected format: "Site - Vehicle - Timestamp - Description"
        parts = [part.strip() for part in text.split(' - ')]
        
        if len(parts) >= 4:
            site = parts[0]
            vehicle = parts[1] 
            timestamp = parts[2]
            description = parts[3]
            
            # Create the two lines for top watermark
            line1 = f"{site} - {vehicle}"
            line2 = f"{timestamp} - {description}"
        else:
            # Fallback if format doesn't match
            line1 = text[:len(text)//2] if len(text) > 30 else text
            line2 = text[len(text)//2:] if len(text) > 30 else ""
        
        # Get text dimensions for both lines
        (line1_width, line1_height), line1_baseline = cv2.getTextSize(line1, font, font_scale, thickness)
        (line2_width, line2_height), line2_baseline = cv2.getTextSize(line2, font, font_scale, thickness)
        
        # Calculate total height needed for both lines
        total_height = line1_height + line2_height + line_spacing + max(line1_baseline, line2_baseline)
        
        # Position at top with some padding
        x1 = 10
        y1 = line1_height + 10
        x2 = 10  
        y2 = y1 + line2_height + line_spacing
        
        # ENHANCED: Add semi-transparent background for better readability (size-dependent)
        if size == "large":
            # Larger background for large text
            bg_padding = 15
            bg_x1 = max(0, x1 - bg_padding)
            bg_y1 = max(0, 10 - bg_padding)
            bg_x2 = min(width, max(x1 + line1_width, x2 + line2_width) + bg_padding)
            bg_y2 = min(height, y2 + line2_baseline + bg_padding)
            
            # Draw background
            overlay = result.copy()
            cv2.rectangle(overlay, (bg_x1, bg_y1), (bg_x2, bg_y2), (0, 0, 0), -1)
            result = cv2.addWeighted(result, 1-bg_alpha, overlay, bg_alpha, 0)
            
            # Add white outline for better contrast (large text only)
            outline_thickness = thickness + 2
            cv2.putText(result, line1, (x1, y1), font, font_scale, (255, 255, 255), outline_thickness)
            cv2.putText(result, line2, (x2, y2), font, font_scale, (255, 255, 255), outline_thickness)
        
        # Add the main text lines
        cv2.putText(result, line1, (x1, y1), font, font_scale, color, thickness)
        if line2:  # Only add second line if it exists
            cv2.putText(result, line2, (x2, y2), font, font_scale, color, thickness)
    
    # Add ticket ID at BOTTOM (if provided)
    if ticket_id:
        ticket_text = f"Ticket: {ticket_id}"
        
        # Adjust font size for ticket based on size parameter
        if size == "large":
            ticket_font_scale = max(1.2, width / 800)
            ticket_thickness = max(3, int(width / 300))
        else:
            ticket_font_scale = 1
            ticket_thickness = 2
        
        # Get ticket text dimensions
        (ticket_width, ticket_height), ticket_baseline = cv2.getTextSize(
            ticket_text, font, ticket_font_scale, ticket_thickness)
        
        # Position at bottom-right
        ticket_x = width - ticket_width - 10
        ticket_y = height - 10
        
        # ENHANCED: Add background for ticket (size-dependent)
        if size == "large":
            # Larger background for large ticket text
            bg_padding = 12
            overlay = result.copy()
            cv2.rectangle(overlay, 
                         (ticket_x - bg_padding, ticket_y - ticket_height - bg_padding),
                         (ticket_x + ticket_width + bg_padding, ticket_y + ticket_baseline + bg_padding),
                         (0, 0, 0), -1)
            result = cv2.addWeighted(result, 1-bg_alpha, overlay, bg_alpha, 0)
            
            # Add white outline for ticket text
            outline_thickness = ticket_thickness + 2
            cv2.putText(result, ticket_text, (ticket_x, ticket_y), font, 
                       ticket_font_scale, (255, 255, 255), outline_thickness)
        
        # Add ticket text (yellow for visibility)
        cv2.putText(result, ticket_text, (ticket_x, ticket_y), font, 
                   ticket_font_scale, (0, 255, 255), ticket_thickness)
    
    return result