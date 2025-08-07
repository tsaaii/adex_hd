# Updated camera_ui.py - Enhanced UI for robust continuous camera feed

import tkinter as tk
from tkinter import ttk
import config
from ui_components import HoverButton
from camera import RobustCameraView  # Updated import - using class method

def create_cameras_panel(self, parent):
    """Create the enhanced cameras panel with robust continuous feed support"""
    # Camera container with improved layout
    camera_frame = ttk.LabelFrame(parent, text="📹 Live Camera Feed - Continuous Monitoring")
    camera_frame.pack(fill=tk.X, padx=5, pady=5)
    
    # Check available USB cameras first
    print("🔍 Detecting available USB cameras...")
    try:
        available_cameras = RobustCameraView.detect_available_cameras()
    except Exception as e:
        print(f"Error detecting cameras: {e}")
        available_cameras = []  # Fallback to empty list
    
    if not available_cameras:
        # No USB cameras detected - show warning
        warning_frame = ttk.Frame(camera_frame)
        warning_frame.pack(fill=tk.X, padx=5, pady=10)
    
    # Container for both cameras side by side
    cameras_container = ttk.Frame(camera_frame, style="TFrame")
    cameras_container.pack(fill=tk.X, padx=5, pady=5)
    cameras_container.columnconfigure(0, weight=1)
    cameras_container.columnconfigure(1, weight=1)
    
    # Front camera panel
    front_camera_index = 0 if 0 in available_cameras else (available_cameras[0] if available_cameras else 0)
    front_panel = ttk.LabelFrame(cameras_container, text=f"🎥 Front Camera (USB {front_camera_index}) - Live Feed")
    front_panel.grid(row=0, column=0, padx=3, pady=2, sticky="nsew")
    
    # Create front camera with robust continuous feed enabled
    self.front_camera = RobustCameraView(front_panel, camera_index=front_camera_index, auto_start=(front_camera_index in available_cameras))
    self.front_camera.save_function = self.image_handler.save_front_image
    
    # Back camera panel
    back_camera_index = 1 if 1 in available_cameras else (available_cameras[1] if len(available_cameras) > 1 else 1)
    back_panel = ttk.LabelFrame(cameras_container, text=f"🎥 Back Camera (USB {back_camera_index}) - Live Feed")
    back_panel.grid(row=0, column=1, padx=3, pady=2, sticky="nsew")
    
    # Create back camera with robust continuous feed enabled
    self.back_camera = RobustCameraView(back_panel, camera_index=back_camera_index, auto_start=(back_camera_index in available_cameras))
    self.back_camera.save_function = self.image_handler.save_back_image
    
    # Load camera settings and configure cameras
    self.load_camera_settings()
    
    # Enhanced status and control section
    controls_frame = ttk.LabelFrame(camera_frame, text="📊 Camera Status & Controls")
    controls_frame.pack(fill=tk.X, padx=5, pady=5)
    
    # Current weighment indicator (enhanced)
    current_weighment_frame = ttk.Frame(controls_frame)
    current_weighment_frame.pack(fill=tk.X, padx=5, pady=3)
    
    # Status indicator with icon
    status_icon_label = ttk.Label(current_weighment_frame, text="⚖️", font=("Segoe UI", 12))
    status_icon_label.pack(side=tk.LEFT, padx=5)
    
    ttk.Label(current_weighment_frame, text="Current Weighment State:", 
             font=("Segoe UI", 10, "bold")).pack(side=tk.LEFT, padx=5)
    
    weighment_status_label = ttk.Label(current_weighment_frame, 
                                      textvariable=self.weighment_state_var,
                                      font=("Segoe UI", 10, "bold"),
                                      foreground=config.COLORS["primary"])
    weighment_status_label.pack(side=tk.LEFT, padx=10)
    
    # Live feed status indicators
    feed_status_frame = ttk.Frame(controls_frame)
    feed_status_frame.pack(fill=tk.X, padx=5, pady=3)
    
    ttk.Label(feed_status_frame, text="📡 Live Feed Status:", 
             font=("Segoe UI", 9, "bold")).pack(side=tk.LEFT, padx=5)
    
    # Front camera status
    self.front_feed_status_var = tk.StringVar(value="Initializing...")
    front_status = ttk.Label(feed_status_frame, 
                            textvariable=self.front_feed_status_var,
                            font=("Segoe UI", 8),
                            foreground="blue")
    front_status.pack(side=tk.LEFT, padx=10)
    
    # Back camera status  
    self.back_feed_status_var = tk.StringVar(value="Initializing...")
    back_status = ttk.Label(feed_status_frame,
                           textvariable=self.back_feed_status_var,
                           font=("Segoe UI", 8),
                           foreground="blue")
    back_status.pack(side=tk.LEFT, padx=10)
    
    # Master camera controls
    master_controls_frame = ttk.Frame(controls_frame)
    master_controls_frame.pack(fill=tk.X, padx=5, pady=3)
    
    # Camera detection button
    detect_btn = HoverButton(master_controls_frame,
                            text="🔍 Detect Cameras",
                            bg=config.COLORS["primary_light"],
                            fg=config.COLORS["text"],
                            padx=8, pady=3,
                            command=self.detect_and_refresh_cameras)
    detect_btn.pack(side=tk.LEFT, padx=5)
    
    # Start/Stop all feeds button
    self.master_feed_btn = HoverButton(master_controls_frame,
                                      text="🔄 Restart All Feeds",
                                      bg=config.COLORS["secondary"],
                                      fg=config.COLORS["button_text"],
                                      padx=8, pady=3,
                                      command=self.restart_all_camera_feeds)
    self.master_feed_btn.pack(side=tk.LEFT, padx=5)
    
    # Quick capture both button
    capture_both_btn = HoverButton(master_controls_frame,
                                  text="📸 Capture Both",
                                  bg=config.COLORS["primary"],
                                  fg=config.COLORS["button_text"],
                                  padx=8, pady=3,
                                  command=self.capture_both_cameras)
    capture_both_btn.pack(side=tk.LEFT, padx=5)
    
    # Image capture status section (enhanced)
    image_status_frame = ttk.LabelFrame(controls_frame, text="🖼️ Image Capture Progress")
    image_status_frame.pack(fill=tk.X, padx=5, pady=3)
    
    # Create a grid for better organization
    status_grid = ttk.Frame(image_status_frame)
    status_grid.pack(fill=tk.X, padx=5, pady=3)
    
    # First weighment images
    ttk.Label(status_grid, text="1st Weighment:", font=("Segoe UI", 9, "bold")).grid(row=0, column=0, sticky="w", padx=5)
    
    self.first_image_status_var = tk.StringVar(value="Front: ❌ Back: ❌")
    self.first_image_status = ttk.Label(status_grid, 
                                       textvariable=self.first_image_status_var, 
                                       foreground="red",
                                       font=("Segoe UI", 9))
    self.first_image_status.grid(row=0, column=1, sticky="w", padx=10)
    
    # Second weighment images
    ttk.Label(status_grid, text="2nd Weighment:", font=("Segoe UI", 9, "bold")).grid(row=1, column=0, sticky="w", padx=5)
    
    self.second_image_status_var = tk.StringVar(value="Front: ❌ Back: ❌")
    self.second_image_status = ttk.Label(status_grid, 
                                        textvariable=self.second_image_status_var, 
                                        foreground="red",
                                        font=("Segoe UI", 9))
    self.second_image_status.grid(row=1, column=1, sticky="w", padx=10)
    
    # Total progress
    ttk.Label(status_grid, text="Total Progress:", font=("Segoe UI", 9, "bold")).grid(row=2, column=0, sticky="w", padx=5)
    
    self.total_image_status_var = tk.StringVar(value="0/4 images captured")
    total_image_status = ttk.Label(status_grid,
                                  textvariable=self.total_image_status_var,
                                  foreground="blue",
                                  font=("Segoe UI", 9, "bold"))
    total_image_status.grid(row=2, column=1, sticky="w", padx=10)
    
    # Action buttons section (enhanced)
    action_buttons_frame = ttk.LabelFrame(camera_frame, text="🔧 Record Management")
    action_buttons_frame.pack(fill=tk.X, padx=5, pady=(5, 8))
    
    # Create button groups
    primary_actions = ttk.Frame(action_buttons_frame)
    primary_actions.pack(side=tk.LEFT, padx=5, pady=5)
    
    secondary_actions = ttk.Frame(action_buttons_frame)
    secondary_actions.pack(side=tk.RIGHT, padx=5, pady=5)
    
    # Primary actions
    save_btn = HoverButton(primary_actions, 
                        text="💾 Save Record", 
                        font=("Segoe UI", 10, "bold"),
                        bg=config.COLORS["secondary"],
                        fg=config.COLORS["button_text"],
                        padx=12, pady=4,
                        command=self.save_callback if self.save_callback else lambda: None)
    save_btn.pack(side=tk.LEFT, padx=3)
    
    clear_btn = HoverButton(primary_actions, 
                        text="🗑️ Clear Form", 
                        font=("Segoe UI", 10),
                        bg=config.COLORS["button_alt"],
                        fg=config.COLORS["button_text"],
                        padx=12, pady=4,
                        command=self.clear_callback if self.clear_callback else lambda: None)
    clear_btn.pack(side=tk.LEFT, padx=3)
    
    # Secondary actions
    view_btn = HoverButton(secondary_actions, 
                        text="📋 View Records", 
                        font=("Segoe UI", 10),
                        bg=config.COLORS["primary"],
                        fg=config.COLORS["button_text"],
                        padx=8, pady=4,
                        command=self.view_callback if self.view_callback else lambda: None)
    view_btn.pack(side=tk.LEFT, padx=3)
    
    exit_btn = HoverButton(secondary_actions, 
                        text="🚪 Exit", 
                        font=("Segoe UI", 10),
                        bg=config.COLORS["error"],
                        fg=config.COLORS["button_text"],
                        padx=8, pady=4,
                        command=self.exit_callback if self.exit_callback else lambda: None)
    exit_btn.pack(side=tk.LEFT, padx=3)
    
    # Start monitoring feed status
    self.monitor_camera_status()

def detect_and_refresh_cameras(self):
    """Detect available cameras and refresh the camera feeds"""
    try:
        print("🔍 Detecting cameras...")
        
        # Stop current feeds
        if hasattr(self, 'front_camera'):
            self.front_camera.stop_continuous_feed()
        if hasattr(self, 'back_camera'):
            self.back_camera.stop_continuous_feed()
        
        # Detect available cameras
        try:
            available_cameras = RobustCameraView.detect_available_cameras()
        except Exception as e:
            print(f"Error detecting cameras in refresh: {e}")
            available_cameras = []  # Fallback to empty list
        
        # Update camera indices and availability
        if hasattr(self, 'front_camera'):
            if 0 in available_cameras:
                self.front_camera.camera_index = 0
                self.front_camera.camera_available = True
                self.front_camera.checked_availability = True
            elif available_cameras:
                self.front_camera.camera_index = available_cameras[0]
                self.front_camera.camera_available = True
                self.front_camera.checked_availability = True
            else:
                self.front_camera.camera_available = False
                self.front_camera.checked_availability = True
        
        if hasattr(self, 'back_camera'):
            if 1 in available_cameras:
                self.back_camera.camera_index = 1
                self.back_camera.camera_available = True
                self.back_camera.checked_availability = True
            elif len(available_cameras) > 1:
                self.back_camera.camera_index = available_cameras[1]
                self.back_camera.camera_available = True
                self.back_camera.checked_availability = True
            else:
                self.back_camera.camera_available = False
                self.back_camera.checked_availability = True
        
        # Restart feeds for available cameras
        self.parent.after(1000, self._restart_available_cameras)
        
        # Show results
        if available_cameras:
            print(f"✅ Detected cameras: {available_cameras}")
        else:
            print("❌ No cameras detected")
            
    except Exception as e:
        print(f"Error detecting cameras: {e}")

def _restart_available_cameras(self):
    """Restart feeds only for available cameras"""
    try:
        if hasattr(self, 'front_camera') and self.front_camera.camera_available:
            self.front_camera.start_continuous_feed()
            
        if hasattr(self, 'back_camera') and self.back_camera.camera_available:
            self.back_camera.start_continuous_feed()
            
    except Exception as e:
        print(f"Error restarting available cameras: {e}")

def restart_all_camera_feeds(self):
    """Restart both camera feeds with camera detection"""
    try:
        # Detect and refresh cameras first
        self.detect_and_refresh_cameras()
        
        # Update master button temporarily
        if hasattr(self, 'master_feed_btn'):
            self.master_feed_btn.config(text="🔄 Restarting...", state=tk.DISABLED)
            self.parent.after(3000, lambda: self.master_feed_btn.config(text="🔄 Restart All Feeds", state=tk.NORMAL))
        
        print("Both camera feeds restarted with detection")
        
    except Exception as e:
        print(f"Error restarting camera feeds: {e}")

def capture_both_cameras(self):
    """Capture current frame from both cameras simultaneously"""
    try:
        captured_count = 0
        
        # Capture front camera
        if hasattr(self, 'front_camera') and self.front_camera.current_frame is not None:
            if self.front_camera.capture_current_frame():
                captured_count += 1
        
        # Capture back camera
        if hasattr(self, 'back_camera') and self.back_camera.current_frame is not None:
            if self.back_camera.capture_current_frame():
                captured_count += 1
        
        if captured_count > 0:
            print(f"Successfully captured frames from {captured_count} camera(s)")
        else:
            print("No cameras available for capture")
            
    except Exception as e:
        print(f"Error capturing both cameras: {e}")

def monitor_camera_status(self):
    """Monitor and update camera feed status with enhanced feedback"""
    try:
        # Update front camera status
        if hasattr(self, 'front_camera') and hasattr(self, 'front_feed_status_var'):
            if not hasattr(self.front_camera, 'camera_available') or not self.front_camera.camera_available:
                status = f"❌ USB {self.front_camera.camera_index} Not Available"
            elif self.front_camera.is_running:
                if self.front_camera.connection_stable:
                    status = f"✅ {self.front_camera.camera_type} {self.front_camera.camera_index} Active"
                else:
                    status = f"⚠️ {self.front_camera.camera_type} {self.front_camera.camera_index} Connecting..."
            else:
                status = f"⏸️ {self.front_camera.camera_type} {self.front_camera.camera_index} Stopped"
            self.front_feed_status_var.set(status)
        
        # Update back camera status
        if hasattr(self, 'back_camera') and hasattr(self, 'back_feed_status_var'):
            if not hasattr(self.back_camera, 'camera_available') or not self.back_camera.camera_available:
                status = f"❌ USB {self.back_camera.camera_index} Not Available"
            elif self.back_camera.is_running:
                if self.back_camera.connection_stable:
                    status = f"✅ {self.back_camera.camera_type} {self.back_camera.camera_index} Active"
                else:
                    status = f"⚠️ {self.back_camera.camera_type} {self.back_camera.camera_index} Connecting..."
            else:
                status = f"⏸️ {self.back_camera.camera_type} {self.back_camera.camera_index} Stopped"
            self.back_feed_status_var.set(status)
        
    except Exception as e:
        print(f"Error monitoring camera status: {e}")
    
    # Schedule next status check
    if hasattr(self, 'parent'):
        self.parent.after(2000, self.monitor_camera_status)  # Check every 2 seconds

def update_image_status_display(self):
    """Update the enhanced image status display"""
    if hasattr(self, 'image_handler') and hasattr(self, 'total_image_status_var'):
        try:
            # Get current image counts
            first_front = bool(self.image_handler.main_form.first_front_image_path)
            first_back = bool(self.image_handler.main_form.first_back_image_path)
            second_front = bool(self.image_handler.main_form.second_front_image_path)
            second_back = bool(self.image_handler.main_form.second_back_image_path)
            
            # Update first weighment status
            first_status = f"Front: {'✅' if first_front else '❌'} Back: {'✅' if first_back else '❌'}"
            if hasattr(self, 'first_image_status_var'):
                self.first_image_status_var.set(first_status)
                if hasattr(self, 'first_image_status'):
                    color = "green" if (first_front and first_back) else "orange" if (first_front or first_back) else "red"
                    self.first_image_status.config(foreground=color)
            
            # Update second weighment status
            second_status = f"Front: {'✅' if second_front else '❌'} Back: {'✅' if second_back else '❌'}"
            if hasattr(self, 'second_image_status_var'):
                self.second_image_status_var.set(second_status)
                if hasattr(self, 'second_image_status'):
                    color = "green" if (second_front and second_back) else "orange" if (second_front or second_back) else "red"
                    self.second_image_status.config(foreground=color)
            
            # Update total count
            total_count = sum([first_front, first_back, second_front, second_back])
            total_status = f"{total_count}/4 images captured"
            self.total_image_status_var.set(total_status)
            
        except Exception as e:
            print(f"Error updating image status display: {e}")

def load_camera_settings(self):
    """Load camera settings and configure robust cameras"""
    try:
        # Get settings storage instance
        settings_storage = self.get_settings_storage()
        if not settings_storage:
            return
            
        # Get camera settings
        camera_settings = settings_storage.get_camera_settings()
        
        if camera_settings:
            # Configure front camera
            front_type = camera_settings.get("front_camera_type", "USB")
            if front_type == "RTSP":
                rtsp_url = settings_storage.get_rtsp_url("front")
                if rtsp_url:
                    self.front_camera.set_rtsp_config(rtsp_url)
                    print(f"Front camera configured for RTSP: {rtsp_url}")
            elif front_type == "HTTP":
                http_url = settings_storage.get_http_url("front")
                if http_url:
                    self.front_camera.set_http_config(http_url)
                    print(f"Front camera configured for HTTP: {http_url}")
            else:
                # USB camera
                front_index = camera_settings.get("front_camera_index", 0)
                self.front_camera.camera_index = front_index
                self.front_camera.camera_type = "USB"
                print(f"Front camera configured for USB index: {front_index}")
            
            # Configure back camera
            back_type = camera_settings.get("back_camera_type", "USB")
            if back_type == "RTSP":
                rtsp_url = settings_storage.get_rtsp_url("back")
                if rtsp_url:
                    self.back_camera.set_rtsp_config(rtsp_url)
                    print(f"Back camera configured for RTSP: {rtsp_url}")
            elif back_type == "HTTP":
                http_url = settings_storage.get_http_url("back")
                if http_url:
                    self.back_camera.set_http_config(http_url)
                    print(f"Back camera configured for HTTP: {http_url}")
            else:
                # USB camera
                back_index = camera_settings.get("back_camera_index", 1)
                self.back_camera.camera_index = back_index
                self.back_camera.camera_type = "USB"
                print(f"Back camera configured for USB index: {back_index}")
                
        print("Camera settings loaded and applied to robust feed system")
                
    except Exception as e:
        print(f"Error loading camera settings: {e}")

def get_settings_storage(self):
    """Get settings storage instance from the main app"""
    # Try to traverse up widget hierarchy to find settings storage
    widget = self.parent
    while widget:
        if hasattr(widget, 'settings_storage'):
            return widget.settings_storage
        if hasattr(widget, 'master'):
            widget = widget.master
        else:
            break
    
    # If not found in hierarchy, create a new instance
    try:
        from settings_storage import SettingsStorage
        return SettingsStorage()
    except:
        return None

def update_camera_settings(self, settings):
    """Update camera settings for robust feed cameras"""
    try:
        print(f"Updating robust camera settings: {settings}")
        
        # Temporarily stop feeds for settings update
        front_was_running = hasattr(self, 'front_camera') and self.front_camera.is_running
        back_was_running = hasattr(self, 'back_camera') and self.back_camera.is_running
        
        if front_was_running:
            self.front_camera.stop_continuous_feed()
        if back_was_running:
            self.back_camera.stop_continuous_feed()
        
        # Apply new settings
        # Front camera
        front_type = settings.get("front_camera_type", "USB")
        if front_type == "RTSP":
            username = settings.get("front_rtsp_username", "")
            password = settings.get("front_rtsp_password", "")
            ip = settings.get("front_rtsp_ip", "")
            port = settings.get("front_rtsp_port", "554")
            endpoint = settings.get("front_rtsp_endpoint", "/stream1")
            
            if ip:
                if username and password:
                    rtsp_url = f"rtsp://{username}:{password}@{ip}:{port}{endpoint}"
                else:
                    rtsp_url = f"rtsp://{ip}:{port}{endpoint}"
                self.front_camera.set_rtsp_config(rtsp_url)
        elif front_type == "HTTP":
            username = settings.get("front_http_username", "")
            password = settings.get("front_http_password", "")
            ip = settings.get("front_http_ip", "")
            port = settings.get("front_http_port", "80")
            endpoint = settings.get("front_http_endpoint", "/mjpeg")
            
            if ip:
                if username and password:
                    http_url = f"http://{username}:{password}@{ip}:{port}{endpoint}"
                else:
                    http_url = f"http://{ip}:{port}{endpoint}"
                self.front_camera.set_http_config(http_url)
        else:
            # USB camera
            self.front_camera.camera_type = "USB"
            self.front_camera.camera_index = settings.get("front_camera_index", 0)
        
        # Back camera
        back_type = settings.get("back_camera_type", "USB")
        if back_type == "RTSP":
            username = settings.get("back_rtsp_username", "")
            password = settings.get("back_rtsp_password", "")
            ip = settings.get("back_rtsp_ip", "")
            port = settings.get("back_rtsp_port", "554")
            endpoint = settings.get("back_rtsp_endpoint", "/stream1")
            
            if ip:
                if username and password:
                    rtsp_url = f"rtsp://{username}:{password}@{ip}:{port}{endpoint}"
                else:
                    rtsp_url = f"rtsp://{ip}:{port}{endpoint}"
                self.back_camera.set_rtsp_config(rtsp_url)
        elif back_type == "HTTP":
            username = settings.get("back_http_username", "")
            password = settings.get("back_http_password", "")
            ip = settings.get("back_http_ip", "")
            port = settings.get("back_http_port", "80")
            endpoint = settings.get("back_http_endpoint", "/mjpeg")
            
            if ip:
                if username and password:
                    http_url = f"http://{username}:{password}@{ip}:{port}{endpoint}"
                else:
                    http_url = f"http://{ip}:{port}{endpoint}"
                self.back_camera.set_http_config(http_url)
        else:
            # USB camera
            self.back_camera.camera_type = "USB"
            self.back_camera.camera_index = settings.get("back_camera_index", 1)
        
        # Restart feeds if they were running
        def restart_feeds():
            if front_was_running:
                self.front_camera.start_continuous_feed()
            if back_was_running:
                self.back_camera.start_continuous_feed()
        
        # Restart feeds after a brief delay
        self.parent.after(1000, restart_feeds)
        
        print("Camera settings updated for robust feed system")
                
    except Exception as e:
        print(f"Error updating camera settings: {e}")