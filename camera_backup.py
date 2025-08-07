# Enhanced camera.py - Robust continuous feed implementation

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

import config
from ui_components import HoverButton

class RobustCameraView:
    """Simplified and robust camera view with continuous feed"""
    
    def __init__(self, parent, camera_index=0, camera_type="USB", auto_start=True):
        self.parent = parent
        self.camera_index = camera_index
        self.camera_type = camera_type
        self.rtsp_url = None
        self.http_url = None
        self.auto_start = auto_start
        
        # Simplified feed control
        self.is_running = False
        self.video_thread = None
        self.cap = None
        
        # Frame management - simplified
        self.current_frame = None
        self.captured_image = None
        self.frame_lock = threading.Lock()
        self.display_frame = None
        
        # Performance settings
        self.target_fps = 20  # Balanced FPS
        self.last_frame_time = 0
        self.frame_count = 0
        self.fps_counter = 0
        self.fps_timer = time.time()
        
        # Connection state - simplified
        self.connection_stable = False
        self.last_error_time = 0
        self.error_cooldown = 5  # 5 seconds between error reports
        
        # Zoom functionality (kept same)
        self.zoom_level = 1.0
        self.min_zoom = 1.0
        self.max_zoom = 5.0
        self.zoom_step = 0.2
        self.pan_x = 0
        self.pan_y = 0
        self.is_panning = False
        self.last_mouse_x = 0
        self.last_mouse_y = 0
        
        # Create UI
        self.create_ui()
        
        # Auto-start continuous feed if enabled
        if self.auto_start:
            self.start_continuous_feed()
    
    def create_ui(self):
        """Create the camera UI (minimal changes as requested)"""
        # Main frame
        self.frame = ttk.Frame(self.parent)
        self.frame.pack(fill=tk.BOTH, expand=True, padx=3, pady=3)
        
        # Video display canvas
        self.canvas = tk.Canvas(self.frame, bg="black", width=280, height=210)
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
        self.show_status_message("Starting camera feed...")
        
        # Controls frame
        controls = ttk.Frame(self.frame)
        controls.pack(fill=tk.X, padx=2, pady=2)
        
        # Top row - main controls
        main_controls = ttk.Frame(controls)
        main_controls.pack(fill=tk.X, pady=1)
        
        # Start/Stop continuous feed button
        self.feed_button = HoverButton(main_controls, text="Stop Feed", 
                                      bg=config.COLORS["error"], fg=config.COLORS["button_text"],
                                      padx=2, pady=1, width=8,
                                      command=self.toggle_continuous_feed)
        self.feed_button.grid(row=0, column=0, padx=1, pady=1, sticky="ew")
        
        # Capture current frame button
        self.capture_button = HoverButton(main_controls, text="Capture", 
                                        bg=config.COLORS["primary"], fg=config.COLORS["button_text"],
                                        padx=2, pady=1, width=8,
                                        command=self.capture_current_frame)
        self.capture_button.grid(row=0, column=1, padx=1, pady=1, sticky="ew")
        
        # Save captured image button
        self.save_button = HoverButton(main_controls, text="Save", 
                                     bg=config.COLORS["secondary"], fg=config.COLORS["button_text"],
                                     padx=2, pady=1, width=8,
                                     command=self.save_image,
                                     state=tk.DISABLED)
        self.save_button.grid(row=0, column=2, padx=1, pady=1, sticky="ew")
        
        # Configure grid columns
        main_controls.columnconfigure(0, weight=1)
        main_controls.columnconfigure(1, weight=1)
        main_controls.columnconfigure(2, weight=1)
        
        # Zoom controls (kept same)
        zoom_frame = ttk.Frame(controls)
        zoom_frame.pack(fill=tk.X, pady=1)
        
        self.zoom_out_btn = HoverButton(zoom_frame, text="−", 
                                       bg=config.COLORS["button_alt"], fg=config.COLORS["button_text"],
                                       padx=2, pady=1, width=3,
                                       command=self.zoom_out)
        self.zoom_out_btn.grid(row=0, column=0, padx=1, pady=1)
        
        self.zoom_var = tk.StringVar(value="1.0x")
        zoom_label = ttk.Label(zoom_frame, textvariable=self.zoom_var, width=6, 
                              font=("Segoe UI", 8), anchor="center")
        zoom_label.grid(row=0, column=1, padx=1, pady=1, sticky="ew")
        
        self.zoom_in_btn = HoverButton(zoom_frame, text="+", 
                                      bg=config.COLORS["button_alt"], fg=config.COLORS["button_text"],
                                      padx=2, pady=1, width=3,
                                      command=self.zoom_in)
        self.zoom_in_btn.grid(row=0, column=2, padx=1, pady=1)
        
        self.reset_btn = HoverButton(zoom_frame, text="Reset", 
                                    bg=config.COLORS["primary_light"], fg=config.COLORS["text"],
                                    padx=2, pady=1, width=6,
                                    command=self.reset_zoom)
        self.reset_btn.grid(row=0, column=3, padx=1, pady=1, sticky="ew")
        
        zoom_frame.columnconfigure(1, weight=1)
        zoom_frame.columnconfigure(3, weight=1)
        
        # Status labels
        status_frame = ttk.Frame(controls)
        status_frame.pack(fill=tk.X, pady=1)
        
        self.status_var = tk.StringVar(value="Initializing...")
        self.status_label = ttk.Label(status_frame, textvariable=self.status_var, 
                                     font=("Segoe UI", 7), foreground="blue")
        self.status_label.pack(side=tk.LEFT, padx=2)
        
        # FPS indicator
        self.fps_var = tk.StringVar(value="FPS: --")
        self.fps_label = ttk.Label(status_frame, textvariable=self.fps_var, 
                                  font=("Segoe UI", 7), foreground="green")
        self.fps_label.pack(side=tk.RIGHT, padx=2)
        
        # Save function reference
        self.save_function = None
    
    def show_status_message(self, message):
        """Show a status message on the canvas"""
        self.canvas.delete("all")
        canvas_width = self.canvas.winfo_width() or 280
        canvas_height = self.canvas.winfo_height() or 210
        
        self.canvas.create_text(canvas_width//2, canvas_height//2, 
                               text=message, fill="white", 
                               font=("Segoe UI", 10), justify=tk.CENTER)
    
    def set_rtsp_config(self, rtsp_url):
        """Set RTSP URL for IP camera"""
        self.rtsp_url = rtsp_url
        self.camera_type = "RTSP"
        if self.is_running:
            self.restart_feed()
    
    def set_http_config(self, http_url):
        """Set HTTP URL for IP camera"""
        self.http_url = http_url
        self.camera_type = "HTTP"
        if self.is_running:
            self.restart_feed()
    
    def start_continuous_feed(self):
        """Start continuous video feed with robust error handling"""
        if self.is_running:
            return
        
        self.is_running = True
        self.connection_stable = False
        
        # Start the video thread
        self.video_thread = threading.Thread(target=self._robust_video_loop, daemon=True)
        self.video_thread.start()
        
        # Start UI update loop
        self._schedule_ui_update()
        
        # Update UI
        self.feed_button.config(text="Stop Feed", bg=config.COLORS["error"])
        self.status_var.set(f"Starting {self.camera_type} feed...")
    
    def _robust_video_loop(self):
        """Simplified and robust video capture loop"""
        consecutive_failures = 0
        max_failures = 10  # Allow some failures before longer delay
        
        while self.is_running:
            try:
                # Initialize camera if needed
                if self.cap is None or not self.cap.isOpened():
                    success = self._initialize_camera()
                    if not success:
                        consecutive_failures += 1
                        delay = min(consecutive_failures * 0.5, 5.0)  # Progressive delay up to 5 seconds
                        time.sleep(delay)
                        continue
                
                # Read frame
                ret, frame = self._read_frame()
                
                if ret and frame is not None:
                    # Frame rate limiting
                    current_time = time.time()
                    if current_time - self.last_frame_time < (1.0 / self.target_fps):
                        time.sleep(0.02)
                        continue
                    
                    # Apply zoom and pan
                    processed_frame = self.apply_zoom_and_pan(frame)
                    
                    # Update current frame thread-safely
                    with self.frame_lock:
                        self.current_frame = frame.copy()  # Keep original for saving
                        self.display_frame = processed_frame.copy()  # Processed for display
                    
                    # Update timing and stats
                    self.last_frame_time = current_time
                    self.frame_count += 1
                    consecutive_failures = 0  # Reset failure counter
                    
                    if not self.connection_stable:
                        self.connection_stable = True
                        self._update_status_safe(f"{self.camera_type} connected")
                    
                    # Update FPS counter
                    self._update_fps_counter()
                
                else:
                    # Handle frame read failure
                    consecutive_failures += 1
                    if consecutive_failures > max_failures:
                        self._log_error("Too many consecutive frame failures, reinitializing camera")
                        self._close_camera()
                        time.sleep(2)
                        consecutive_failures = 0
                    else:
                        time.sleep(0.1)  # Short delay before retry
                
            except Exception as e:
                self._log_error(f"Video loop error: {e}")
                consecutive_failures += 1
                self._close_camera()
                time.sleep(1)
        
        # Cleanup when loop exits
        self._close_camera()
    
    def _initialize_camera(self):
        """Initialize camera connection with simplified error handling"""
        try:
            self._close_camera()  # Ensure clean state
            
            if self.camera_type == "RTSP" and self.rtsp_url:
                self.cap = cv2.VideoCapture(self.rtsp_url)
                # Optimize RTSP settings
                self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
                self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
                
            elif self.camera_type == "HTTP" and self.http_url:
                # HTTP handled in _read_frame
                return True
                
            else:  # USB camera
                self.cap = cv2.VideoCapture(self.camera_index)
                if self.cap.isOpened():
                    self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
                    self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
                    self.cap.set(cv2.CAP_PROP_FPS, 30)
            
            # Test camera for USB/RTSP
            if self.cap and self.cap.isOpened():
                ret, test_frame = self.cap.read()
                return ret and test_frame is not None
            
            return False
            
        except Exception as e:
            self._log_error(f"Camera initialization error: {e}")
            return False
    
    def _read_frame(self):
        """Read frame based on camera type with improved error handling"""
        try:
            if self.camera_type == "HTTP":
                return self._read_http_frame_optimized()
            elif self.cap and self.cap.isOpened():
                return self.cap.read()
            else:
                return False, None
        except Exception as e:
            self._log_error(f"Frame read error: {e}")
            return False, None
    
    def _read_http_frame_optimized(self):
        """Optimized HTTP frame reading"""
        try:
            if not self.http_url:
                return False, None
            
            # Use shorter timeout and simpler approach
            request = urllib.request.Request(self.http_url)
            with urllib.request.urlopen(request, timeout=3) as response:
                # Read image data
                image_data = response.read()
                
                # Convert to numpy array and decode
                nparr = np.frombuffer(image_data, np.uint8)
                frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
                
                return frame is not None, frame
                
        except Exception as e:
            # Don't log every HTTP error (too verbose)
            return False, None
    
    def _close_camera(self):
        """Safely close camera resources"""
        try:
            if self.cap:
                self.cap.release()
                self.cap = None
        except:
            pass  # Ignore cleanup errors
    
    def _schedule_ui_update(self):
        """Schedule UI update in main thread"""
        if self.is_running:
            self._update_display()
            self.parent.after(50, self._schedule_ui_update)  # 20 FPS UI update
    
    def _update_display(self):
        """Update the display with the latest frame"""
        try:
            if not self.is_running:
                return
            
            # Get display frame thread-safely
            display_frame = None
            with self.frame_lock:
                if self.display_frame is not None:
                    display_frame = self.display_frame.copy()
            
            if display_frame is None:
                return
            
            # Convert to RGB for tkinter
            frame_rgb = cv2.cvtColor(display_frame, cv2.COLOR_BGR2RGB)
            
            # Resize to fit canvas
            canvas_width = self.canvas.winfo_width()
            canvas_height = self.canvas.winfo_height()
            
            if canvas_width > 1 and canvas_height > 1:
                frame_resized = cv2.resize(frame_rgb, (canvas_width, canvas_height))
            else:
                frame_resized = cv2.resize(frame_rgb, (280, 210))
            
            # Convert to PhotoImage and display
            img = Image.fromarray(frame_resized)
            img_tk = ImageTk.PhotoImage(image=img)
            
            # Update canvas
            self.canvas.delete("all")
            self.canvas.create_image(0, 0, anchor=tk.NW, image=img_tk)
            self.canvas.image = img_tk  # Keep reference
            
        except Exception as e:
            # Don't crash on display errors
            pass
    
    def _update_fps_counter(self):
        """Update FPS counter"""
        self.fps_counter += 1
        current_time = time.time()
        
        if current_time - self.fps_timer >= 1.0:
            fps = self.fps_counter / (current_time - self.fps_timer)
            self._update_status_safe(None, f"FPS: {fps:.1f}")
            self.fps_counter = 0
            self.fps_timer = current_time
    
    def _update_status_safe(self, status_text=None, fps_text=None):
        """Thread-safe status update"""
        try:
            if status_text:
                self.parent.after_idle(lambda: self.status_var.set(status_text))
            if fps_text:
                self.parent.after_idle(lambda: self.fps_var.set(fps_text))
        except:
            pass
    
    def _log_error(self, message):
        """Log error with cooldown to prevent spam"""
        current_time = time.time()
        if current_time - self.last_error_time > self.error_cooldown:
            print(f"Camera error: {message}")
            self.last_error_time = current_time
            self.connection_stable = False
    
    def stop_continuous_feed(self):
        """Stop continuous video feed"""
        self.is_running = False
        
        # Wait for thread to complete
        if self.video_thread and self.video_thread.is_alive():
            self.video_thread.join(timeout=2.0)
        
        # Close camera
        self._close_camera()
        
        # Reset zoom and pan
        self.reset_zoom()
        
        # Update UI
        self.feed_button.config(text="Start Feed", bg=config.COLORS["primary"])
        self.status_var.set("Feed stopped")
        self.fps_var.set("FPS: --")
        
        # Show startup message
        self.show_status_message("Camera feed stopped\nClick 'Start Feed' to resume")
    
    def toggle_continuous_feed(self):
        """Toggle continuous feed on/off"""
        if self.is_running:
            self.stop_continuous_feed()
        else:
            self.start_continuous_feed()
    
    def restart_feed(self):
        """Restart the feed (useful when settings change)"""
        if self.is_running:
            self.stop_continuous_feed()
            time.sleep(0.5)
            self.start_continuous_feed()
    
    def capture_current_frame(self):
        """Capture the current frame for saving"""
        try:
            with self.frame_lock:
                if self.current_frame is not None:
                    self.captured_image = self.current_frame.copy()
                    self.save_button.config(state=tk.NORMAL)
                    self.status_var.set("Frame captured - click Save to store")
                    return True
                else:
                    self.status_var.set("No live frame available - ensure feed is active")
                    return False
        except Exception as e:
            self.status_var.set(f"Capture error: {str(e)}")
            return False
    
    def save_image(self):
        """Save the captured image"""
        try:
            if self.captured_image is None:
                self.status_var.set("No image captured - click Capture first")
                return False
            
            if self.save_function is None:
                self.status_var.set("Save function not configured")
                return False
            
            # Call the save function with the captured image
            success = self.save_function(self.captured_image)
            
            if success:
                self.status_var.set("Image saved successfully!")
                self.save_button.config(state=tk.DISABLED)
                self.captured_image = None
                return True
            else:
                self.status_var.set("Failed to save image")
                return False
                
        except Exception as e:
            self.status_var.set(f"Save error: {str(e)}")
            return False
    
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

    def reset_display(self):
        """Reset the camera display to initial state"""
        try:
            self.show_status_message("Camera ready\nClick 'Start Feed' to begin")
            self.captured_image = None
            self.save_button.config(state=tk.DISABLED)
        except:
            pass
    
    # Zoom and pan methods (kept same as original)
    def zoom_in(self):
        if self.zoom_level < self.max_zoom:
            self.zoom_level = min(self.zoom_level + self.zoom_step, self.max_zoom)
            self.update_zoom_display()
    
    def zoom_out(self):
        if self.zoom_level > self.min_zoom:
            self.zoom_level = max(self.zoom_level - self.zoom_step, self.min_zoom)
            self.update_zoom_display()
            if self.zoom_level == self.min_zoom:
                self.pan_x = 0
                self.pan_y = 0
    
    def reset_zoom(self, event=None):
        self.zoom_level = self.min_zoom
        self.pan_x = 0
        self.pan_y = 0
        self.update_zoom_display()
    
    def update_zoom_display(self):
        self.zoom_var.set(f"{self.zoom_level:.1f}x")
    
    def on_mouse_wheel(self, event):
        if not self.is_running:
            return
        if event.delta > 0 or event.num == 4:
            self.zoom_in()
        elif event.delta < 0 or event.num == 5:
            self.zoom_out()
    
    def on_mouse_press(self, event):
        if not self.is_running or self.zoom_level <= self.min_zoom:
            return
        self.is_panning = True
        self.last_mouse_x = event.x
        self.last_mouse_y = event.y
        self.canvas.configure(cursor="fleur")
    
    def on_mouse_drag(self, event):
        if not self.is_panning or not self.is_running:
            return
        dx = event.x - self.last_mouse_x
        dy = event.y - self.last_mouse_y
        self.pan_x += dx
        self.pan_y += dy
        
        canvas_width = self.canvas.winfo_width()
        canvas_height = self.canvas.winfo_height()
        max_pan_x = canvas_width * (self.zoom_level - 1) / 2
        max_pan_y = canvas_height * (self.zoom_level - 1) / 2
        
        self.pan_x = max(-max_pan_x, min(max_pan_x, self.pan_x))
        self.pan_y = max(-max_pan_y, min(max_pan_y, self.pan_y))
        
        self.last_mouse_x = event.x
        self.last_mouse_y = event.y
    
    def on_mouse_release(self, event):
        self.is_panning = False
        self.canvas.configure(cursor="")
    
    def apply_zoom_and_pan(self, frame):
        """Apply zoom and pan transformations"""
        if self.zoom_level <= self.min_zoom:
            return frame
        
        height, width = frame.shape[:2]
        zoom_width = int(width / self.zoom_level)
        zoom_height = int(height / self.zoom_level)
        
        center_x = width // 2 + int(self.pan_x * self.zoom_level / 4)
        center_y = height // 2 + int(self.pan_y * self.zoom_level / 4)
        
        x1 = max(0, center_x - zoom_width // 2)
        y1 = max(0, center_y - zoom_height // 2)
        x2 = min(width, x1 + zoom_width)
        y2 = min(height, y1 + zoom_height)
        
        if x2 - x1 < zoom_width:
            x1 = max(0, x2 - zoom_width)
        if y2 - y1 < zoom_height:
            y1 = max(0, y2 - zoom_height)
        
        zoomed_frame = frame[y1:y2, x1:x2]
        
        if zoomed_frame.size > 0:
            return cv2.resize(zoomed_frame, (width, height))
        else:
            return frame

# Maintain backward compatibility
ContinuousCameraView = RobustCameraView
CameraView = RobustCameraView

# Watermark function remains the same
def add_watermark(image, text, ticket_id=None):
    """Add a watermark to an image with sitename, vehicle number, timestamp, and image description in 2 lines at top, and ticket at bottom"""
    result = image.copy()
    height, width = result.shape[:2]
    
    font = cv2.FONT_HERSHEY_SIMPLEX
    font_scale = 0.7
    color = (255, 255, 255)
    thickness = 2
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
        else:
            pass
        
        # Create the two lines for top watermark
        line1 = f"{site} - {vehicle}"
        line2 = f"{timestamp} - {description}"
        
        # Get text dimensions for both lines
        (line1_width, line1_height), line1_baseline = cv2.getTextSize(line1, font, font_scale, thickness)
        (line2_width, line2_height), line2_baseline = cv2.getTextSize(line2, font, font_scale, thickness)
        
        # Calculate total height needed for both lines
        total_text_height = line1_height + line2_height + line_spacing
        max_text_width = max(line1_width, line2_width)
        
        # Create overlay background for both lines at TOP
        overlay = result.copy()
        overlay_y_start = 0
        overlay_y_end = total_text_height + 20
        cv2.rectangle(overlay, (0, overlay_y_start), (max_text_width + 20, overlay_y_end), (0, 0, 0), -1)
        cv2.addWeighted(overlay, 0.6, result, 0.4, 0, result)
        
        # Add line 1 (Site - Vehicle) at top
        line1_y = line1_height + 10
        cv2.putText(result, line1, (10, line1_y), font, font_scale, color, thickness)
        
        # Add line 2 (Timestamp - Description) below line 1
        line2_y = line1_height + line2_height + line_spacing + 10
        cv2.putText(result, line2, (10, line2_y), font, font_scale, color, thickness)
    
    # Add ticket number at BOTTOM
    if ticket_id:
        ticket_text = f"Ticket: {ticket_id}"
        (ticket_width, ticket_height), ticket_baseline = cv2.getTextSize(ticket_text, font, font_scale, thickness)
        
        # Create overlay background for ticket at BOTTOM
        overlay_ticket = result.copy()
        overlay_y_start = height - ticket_height - 20
        overlay_y_end = height
        cv2.rectangle(overlay_ticket, (0, overlay_y_start), (ticket_width + 20, overlay_y_end), (0, 0, 0), -1)
        cv2.addWeighted(overlay_ticket, 0.6, result, 0.4, 0, result)
        
        # Add ticket text at bottom
        cv2.putText(result, ticket_text, (10, height - 10), font, font_scale, color, thickness)
    
    return result