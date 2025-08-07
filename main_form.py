
# Fixed main_form.py - Resolved import issues and save functionality

import tkinter as tk
from tkinter import ttk, messagebox
import os
import datetime
import cv2
from PIL import Image, ImageTk
import threading
import config
from ui_components import HoverButton
from camera import CameraView, add_watermark

# Import modular components
from form_validation import FormValidator
from weight_manager import WeightManager
from vehicle_autocomplete import VehicleAutocomplete
from image_handler import ImageHandler

class MainForm:
    """Main data entry form for vehicle information"""
    
    def __init__(self, parent, notebook=None, summary_update_callback=None, data_manager=None, 
                save_callback=None, view_callback=None, clear_callback=None, exit_callback=None):
        """Initialize the main form
        
        Args:
            parent: Parent widget
            notebook: Notebook for tab switching
            summary_update_callback: Function to call to update summary view
            data_manager: Data manager instance for checking existing entries
            save_callback: Callback for save button
            view_callback: Callback for view records button
            clear_callback: Callback for clear button
            exit_callback: Callback for exit button
        """
        self.parent = parent
        self.notebook = notebook
        self.summary_update_callback = summary_update_callback
        self.data_manager = data_manager
        self.save_callback = save_callback
        self.view_callback = view_callback
        self.clear_callback = clear_callback
        self.exit_callback = exit_callback
        
        # Initialize form variables
        self.init_variables()
        
        # Initialize helper components
        self.weight_manager = WeightManager(self)
        self.form_validator = FormValidator(self)
        self.vehicle_autocomplete = VehicleAutocomplete(self)
        self.image_handler = ImageHandler(self)
        
        # Camera lock to prevent both cameras from being used simultaneously
        self.camera_lock = threading.Lock()
        
        # Create UI elements
        self.create_form(parent)
        self.create_cameras_panel(parent)
        
        # Initialize vehicle autocomplete
        self.vehicle_autocomplete.refresh_cache()

                # Initialize logger property
        self._setup_logger()
        
        self.logger.info("MainForm initialized")

    def _setup_logger(self):
        """Setup logger for MainForm"""
        try:
            import logging
            self.logger = logging.getLogger('MainForm')
            
            # If no handlers, add a basic one
            if not self.logger.handlers:
                handler = logging.StreamHandler()
                formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
                handler.setFormatter(formatter)
                self.logger.addHandler(handler)
                self.logger.setLevel(logging.INFO)
                
        except Exception as e:
            # Fallback logger
            class FallbackLogger:
                def info(self, msg): print(f"MainForm INFO: {msg}")
                def warning(self, msg): print(f"MainForm WARNING: {msg}")
                def error(self, msg): print(f"MainForm ERROR: {msg}")
                def debug(self, msg): print(f"MainForm DEBUG: {msg}")
            
            self.logger = FallbackLogger()
            print(f"MainForm logger setup failed: {e}, using fallback")

    def create_form(self, parent):
        """Create the main data entry form with weighment panel including current weight display"""
        # Vehicle Information Frame
        form_frame = ttk.LabelFrame(parent, text="Vehicle Information")
        form_frame.pack(fill=tk.X, padx=5, pady=5)
        
        # Set background color for better visibility
        form_inner = ttk.Frame(form_frame, style="TFrame")
        form_inner.pack(fill=tk.BOTH, padx=5, pady=5)
        
        # Configure grid columns for better distribution
        for i in range(3):  # 3 columns
            form_inner.columnconfigure(i, weight=1)  # Equal weight
        
        # =================== ROW 0: First row of labels ===================
        # Ticket No - Column 0
        ttk.Label(form_inner, text="Ticket No:").grid(row=0, column=0, sticky=tk.W, padx=3, pady=3)
        
        # Site Name - Column 1
        ttk.Label(form_inner, text="Site Name:").grid(row=0, column=1, sticky=tk.W, padx=3, pady=3)
        
        # Agency Name - Column 2
        ttk.Label(form_inner, text="Agency Name:").grid(row=0, column=2, sticky=tk.W, padx=3, pady=3)
        
        # =================== ROW 1: First row of entries ===================
        # Ticket No Entry - Column 0 (READ-ONLY)
        ticket_entry = ttk.Entry(form_inner, textvariable=self.rst_var, width=config.STD_WIDTH, state="readonly")
        ticket_entry.grid(row=1, column=0, sticky=tk.W, padx=3, pady=3)
        
        # New Ticket button
        auto_ticket_btn = HoverButton(form_inner, text="New", 
                                    bg=config.COLORS["primary"], 
                                    fg=config.COLORS["button_text"],
                                    padx=4, pady=1,
                                    command=self.generate_next_ticket_number)
        auto_ticket_btn.grid(row=1, column=0, sticky=tk.E, padx=(0, 5), pady=3)
        
        # Site Name Entry - Column 1
        self.site_combo = ttk.Combobox(form_inner, textvariable=self.site_var, state="readonly", width=config.STD_WIDTH)
        self.site_combo['values'] = ('Guntur',)
        self.site_combo.grid(row=1, column=1, sticky=tk.W, padx=3, pady=3)
        
        # Agency Name Combobox - Column 2 (now a dropdown)
        self.agency_combo = ttk.Combobox(form_inner, textvariable=self.agency_var, state="readonly", width=config.STD_WIDTH)
        self.agency_combo['values'] = ('Default Agency',)  # Default value, will be updated from settings
        self.agency_combo.grid(row=1, column=2, sticky=tk.W, padx=3, pady=3)
        
        # =================== ROW 2: Second row of labels ===================
        # Vehicle No - Column 0
        ttk.Label(form_inner, text="Vehicle No:").grid(row=2, column=0, sticky=tk.W, padx=3, pady=3)
        
        # Transfer Party Name - Column 1
        ttk.Label(form_inner, text="Transfer Party Name:").grid(row=2, column=1, sticky=tk.W, padx=3, pady=3)
        
        # Material Type - Column 2 
        ttk.Label(form_inner, text="Material Type:").grid(row=2, column=2, sticky=tk.W, padx=3, pady=3)
        
        # =================== ROW 3: Second row of entries ===================
        # Vehicle No Entry - Column 0
        self.vehicle_entry = ttk.Combobox(form_inner, textvariable=self.vehicle_var, width=config.STD_WIDTH)
        self.vehicle_entry.grid(row=3, column=0, sticky=tk.W, padx=3, pady=3)
        # Load initial vehicle numbers
        self.vehicle_entry['values'] = self.vehicle_autocomplete.get_vehicle_numbers()
        # Set up autocomplete
        self.vehicle_autocomplete.setup_vehicle_autocomplete()
        
        # Transfer Party Name Combobox - Column 1 (now a dropdown)
        self.tpt_combo = ttk.Combobox(form_inner, textvariable=self.tpt_var, state="readonly", width=config.STD_WIDTH)
        self.tpt_combo['values'] = ('Advitia Labs',)  # Default value, will be updated from settings
        self.tpt_combo.grid(row=3, column=1, sticky=tk.W, padx=3, pady=3)
        
        # Material Type Combo - Column 2
        material_type_combo = ttk.Combobox(form_inner, 
                                        textvariable=self.material_type_var, 
                                        state="readonly", 
                                        width=config.STD_WIDTH)
        material_type_combo['values'] = ('Legacy/MSW','Inert', 'Soil', 'Construction and Demolition', 
                                    'RDF(REFUSE DERIVED FUEL)')
        material_type_combo.grid(row=3, column=2, sticky=tk.W, padx=3, pady=3)
        
        # =================== WEIGHMENT PANEL (WITH CURRENT WEIGHT DISPLAY) ===================
        weighment_frame = ttk.LabelFrame(form_inner, text="Weighment Information")
        weighment_frame.grid(row=4, column=0, columnspan=3, sticky="ew", padx=3, pady=10)

        # Configure grid columns for weighment panel
        weighment_frame.columnconfigure(0, weight=1)  # Description
        weighment_frame.columnconfigure(1, weight=1)  # Weight value
        weighment_frame.columnconfigure(2, weight=1)  # Timestamp
        weighment_frame.columnconfigure(3, weight=1)  # Button

        # Current Weight Display (Prominent 6-digit display)
        ttk.Label(weighment_frame, text="Current Weight:", font=("Segoe UI", 10, "bold")).grid(
            row=0, column=0, sticky=tk.W, padx=5, pady=5)

        # Current Weight Display (large, prominent display for up to 6 digits)
        self.current_weight_display = ttk.Label(weighment_frame, 
                                               textvariable=self.current_weight_var,
                                               font=("Segoe UI", 16, "bold"),  
                                               foreground=config.COLORS["primary"],
                                               background=config.COLORS["background"],
                                               width=12)  
        self.current_weight_display.grid(row=0, column=1, sticky=tk.W, padx=5, pady=5)

        # Status label for current weight
        self.weight_status_label = ttk.Label(weighment_frame, 
                                           text="(Live from weighbridge)", 
                                           font=("Segoe UI", 8, "italic"),
                                           foreground="gray")
        self.weight_status_label.grid(row=0, column=2, sticky=tk.W, padx=5, pady=5)

        # Capture Weight Button
        self.capture_weight_btn = HoverButton(weighment_frame, text="Capture Weight", 
                                        bg=config.COLORS["primary"], 
                                        fg=config.COLORS["button_text"],
                                        font=("Segoe UI", 10, "bold"),
                                        padx=10, pady=10,
                                        command=self.weight_manager.capture_weight)
        self.capture_weight_btn.grid(row=1, column=2, rowspan=3, sticky="ns", padx=5, pady=5)

        # First Row - First Weighment
        ttk.Label(weighment_frame, text="First Weighment:", font=("Segoe UI", 9, "bold")).grid(
            row=1, column=0, sticky=tk.W, padx=5, pady=5)

        # First Weight Entry (read-only)
        self.first_weight_entry = ttk.Entry(weighment_frame, textvariable=self.first_weight_var, 
                                    width=12, style="Weight.TEntry", state="readonly")
        self.first_weight_entry.grid(row=1, column=1, sticky=tk.W, padx=5, pady=5)

        # Second Row - Second Weighment
        ttk.Label(weighment_frame, text="Second Weighment:", font=("Segoe UI", 9, "bold")).grid(
            row=2, column=0, sticky=tk.W, padx=5, pady=5)

        # Second Weight Entry (read-only)
        self.second_weight_entry = ttk.Entry(weighment_frame, textvariable=self.second_weight_var, 
                                        width=12, style="Weight.TEntry", state="readonly")
        self.second_weight_entry.grid(row=2, column=1, sticky=tk.W, padx=5, pady=5)

        # Third Row - Net Weight
        ttk.Label(weighment_frame, text="Net Weight:", font=("Segoe UI", 9, "bold")).grid(
            row=3, column=0, sticky=tk.W, padx=5, pady=5)

        # Net Weight Display (read-only)
        # Replace the existing net weight Entry with this enhanced Label
        net_weight_display = ttk.Label(weighment_frame, 
                                    textvariable=self.net_weight_var,
                                    font=("Segoe UI", 14, "bold"),
                                    foreground=config.COLORS["secondary"],
                                    background=config.COLORS["background"],
                                    width=12)
        net_weight_display.grid(row=3, column=1, sticky=tk.W, padx=5, pady=5)

        # Add kg unit label
        ttk.Label(weighment_frame, text="kg", 
                font=("Segoe UI", 10),
                foreground="gray").grid(row=3, column=1, sticky=tk.W, padx=(80, 5), pady=5)

        # Current weighment state indicator
        state_frame = ttk.Frame(weighment_frame)
        state_frame.grid(row=4, column=0, columnspan=4, sticky=tk.EW, padx=5, pady=(10,5))

        state_label = ttk.Label(state_frame, text="Current State: ", font=("Segoe UI", 9))
        state_label.pack(side=tk.LEFT)

        state_value_label = ttk.Label(state_frame, textvariable=self.weighment_state_var, 
                                    font=("Segoe UI", 9, "bold"), foreground=config.COLORS["primary"])
        state_value_label.pack(side=tk.LEFT)

        # Note about ticket increment behavior
        weight_note = ttk.Label(state_frame, 
                              text="💡 Ticket number increments only after BOTH weighments are completed", 
                              font=("Segoe UI", 8, "italic"), 
                              foreground="green")
        weight_note.pack(side=tk.RIGHT)


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
        self.after(2000, self.monitor_camera_status)  # Check every 2 seconds

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


    def restart_all_camera_feeds(self):
        """Restart both camera feeds with improved feedback"""
        try:
            if hasattr(self, 'front_camera'):
                self.front_camera.restart_feed()
            if hasattr(self, 'back_camera'):
                self.back_camera.restart_feed()
            
            # Update master button temporarily
            if hasattr(self, 'master_feed_btn'):
                self.master_feed_btn.config(text="🔄 Restarting...", state=tk.DISABLED)
                self.after(2000, lambda: self.master_feed_btn.config(text="🔄 Restart All Feeds", state=tk.NORMAL))
            
            print("Both camera feeds restarted")
            
        except Exception as e:
            print(f"Error restarting camera feeds: {e}")

    def stop_all_camera_feeds(self):
        """Stop all camera feeds - FIXED METHOD"""
        try:
            if hasattr(self, 'front_camera') and self.front_camera:
                if hasattr(self.front_camera, 'stop_continuous_feed'):
                    self.front_camera.stop_continuous_feed()
                elif hasattr(self.front_camera, 'stop_camera'):
                    self.front_camera.stop_camera()
                    
            if hasattr(self, 'back_camera') and self.back_camera:
                if hasattr(self.back_camera, 'stop_continuous_feed'):
                    self.back_camera.stop_continuous_feed()
                elif hasattr(self.back_camera, 'stop_camera'):
                    self.back_camera.stop_camera()
        except Exception as e:
            print(f"Error stopping cameras: {e}")


    def start_all_camera_feeds(self):
        """Start all camera feeds - FIXED METHOD"""
        try:
            if hasattr(self, 'front_camera') and self.front_camera:
                if hasattr(self.front_camera, 'start_continuous_feed'):
                    self.front_camera.start_continuous_feed()
                elif hasattr(self.front_camera, 'start_camera'):
                    self.front_camera.start_camera()
                    
            if hasattr(self, 'back_camera') and self.back_camera:
                if hasattr(self.back_camera, 'start_continuous_feed'):
                    self.back_camera.start_continuous_feed()
                elif hasattr(self.back_camera, 'start_camera'):
                    self.back_camera.start_camera()
        except Exception as e:
            print(f"Error starting cameras: {e}")


    def capture_both_cameras(self):
        """Capture current frame from both cameras simultaneously"""
        try:
            captured_count = 0
            
            # Capture front camera
            if hasattr(self, 'front_camera') and hasattr(self.front_camera, 'current_frame') and self.front_camera.current_frame is not None:
                if self.front_camera.capture_current_frame():
                    captured_count += 1
            
            # Capture back camera
            if hasattr(self, 'back_camera') and hasattr(self.back_camera, 'current_frame') and self.back_camera.current_frame is not None:
                if self.back_camera.capture_current_frame():
                    captured_count += 1
            
            if captured_count > 0:
                print(f"Successfully captured frames from {captured_count} camera(s)")
            else:
                print("No cameras available for capture")
                
        except Exception as e:
            print(f"Error capturing both cameras: {e}")


    def update_image_status_display(self):
        """Update the image status indicators based on captured images"""
        try:
            # Count images for each weighment
            first_count = 0
            second_count = 0
            
            # Check first weighment images
            if hasattr(self, 'first_front_image_path') and self.first_front_image_path:
                first_count += 1
            if hasattr(self, 'first_back_image_path') and self.first_back_image_path:
                first_count += 1
                
            # Check second weighment images  
            if hasattr(self, 'second_front_image_path') and self.second_front_image_path:
                second_count += 1
            if hasattr(self, 'second_back_image_path') and self.second_back_image_path:
                second_count += 1
            
            # Update first weighment status
            if hasattr(self, 'first_image_status_var'):
                self.first_image_status_var.set(f"1st: {first_count}/2")
                if hasattr(self, 'first_image_status'):
                    color = "green" if first_count == 2 else "orange" if first_count == 1 else "red"
                    self.first_image_status.config(foreground=color)
            
            # Update second weighment status
            if hasattr(self, 'second_image_status_var'):
                self.second_image_status_var.set(f"2nd: {second_count}/2")
                if hasattr(self, 'second_image_status'):
                    color = "green" if second_count == 2 else "orange" if second_count == 1 else "red"
                    self.second_image_status.config(foreground=color)
            
            # Update total status
            total_count = first_count + second_count
            if hasattr(self, 'total_image_status_var'):
                self.total_image_status_var.set(f"Total: {total_count}/4")
                
        except Exception as e:
            print(f"Error updating image status display: {e}")

    def get_weighment_image_count(self):
        """Get the count of images for the current weighment state
        
        Returns:
            tuple: (current_weighment_count, total_count)
        """
        try:
            current_weighment = getattr(self, 'current_weighment', 'first')
            
            if current_weighment == "first":
                count = 0
                if hasattr(self, 'first_front_image_path') and self.first_front_image_path:
                    count += 1
                if hasattr(self, 'first_back_image_path') and self.first_back_image_path:
                    count += 1
                return count, count
            else:
                first_count = 0
                if hasattr(self, 'first_front_image_path') and self.first_front_image_path:
                    first_count += 1
                if hasattr(self, 'first_back_image_path') and self.first_back_image_path:
                    first_count += 1
                    
                second_count = 0
                if hasattr(self, 'second_front_image_path') and self.second_front_image_path:
                    second_count += 1
                if hasattr(self, 'second_back_image_path') and self.second_back_image_path:
                    second_count += 1
                    
                return second_count, first_count + second_count
                
        except Exception as e:
            print(f"Error getting image count: {e}")
            return 0, 0

    def validate_cameras_for_capture(self):
        """Validate that cameras are ready for image capture
        
        Returns:
            tuple: (is_valid, message)
        """
        try:
            issues = []
            
            # Check if cameras exist
            if not hasattr(self, 'front_camera') or not self.front_camera:
                issues.append("Front camera not available")
            
            if not hasattr(self, 'back_camera') or not self.back_camera:
                issues.append("Back camera not available")
            
            # Check if cameras have capture capability
            if hasattr(self, 'front_camera') and self.front_camera:
                if not hasattr(self.front_camera, 'capture_image') and not hasattr(self, 'save_front_image'):
                    issues.append("Front camera has no capture method")
            
            if hasattr(self, 'back_camera') and self.back_camera:
                if not hasattr(self.back_camera, 'capture_image') and not hasattr(self, 'save_back_image'):
                    issues.append("Back camera has no capture method")
            
            if issues:
                return False, "; ".join(issues)
            else:
                return True, "Cameras ready for capture"
                
        except Exception as e:
            return False, f"Error validating cameras: {str(e)}"

    def reset_camera_display(self):
        """Reset camera displays to initial state"""
        try:
            if hasattr(self, 'front_camera') and self.front_camera:
                if hasattr(self.front_camera, 'reset_display'):
                    self.front_camera.reset_display()
                    
            if hasattr(self, 'back_camera') and self.back_camera:
                if hasattr(self.back_camera, 'reset_display'):
                    self.back_camera.reset_display()
                    
        except Exception as e:
            print(f"Error resetting camera display: {e}")

    def get_camera_status(self):
        """Get status of both cameras
        
        Returns:
            dict: Status information for both cameras
        """
        try:
            status = {
                'front_camera': {
                    'available': hasattr(self, 'front_camera') and self.front_camera is not None,
                    'type': 'unknown',
                    'status': 'unknown'
                },
                'back_camera': {
                    'available': hasattr(self, 'back_camera') and self.back_camera is not None,
                    'type': 'unknown', 
                    'status': 'unknown'
                }
            }
            
            # Get front camera details
            if status['front_camera']['available']:
                front_cam = self.front_camera
                status['front_camera']['type'] = getattr(front_cam, 'camera_type', 'USB')
                status['front_camera']['status'] = 'ready' if hasattr(front_cam, 'capture_image') else 'limited'
            
            # Get back camera details  
            if status['back_camera']['available']:
                back_cam = self.back_camera
                status['back_camera']['type'] = getattr(back_cam, 'camera_type', 'USB')
                status['back_camera']['status'] = 'ready' if hasattr(back_cam, 'capture_image') else 'limited'
                
            return status
            
        except Exception as e:
            print(f"Error getting camera status: {e}")
            return {
                'front_camera': {'available': False, 'type': 'error', 'status': str(e)},
                'back_camera': {'available': False, 'type': 'error', 'status': str(e)}
            }



# Add these methods to your MainForm class (copy into your MainForm class definition)

    def _get_tkinter_root(self):
        """Helper method to find a tkinter widget for scheduling"""
        # Try different ways to find a tkinter widget that supports .after()
        if hasattr(self, 'after'):
            return self
        elif hasattr(self, 'parent') and hasattr(self.parent, 'after'):
            return self.parent
        elif hasattr(self, 'master') and hasattr(self.master, 'after'):
            return self.master
        elif hasattr(self, 'root') and hasattr(self.root, 'after'):
            return self.root
        elif hasattr(self, 'tk') and hasattr(self.tk, 'after'):
            return self.tk
        else:
            # Look for any tkinter widget in our attributes
            for attr_name in dir(self):
                if not attr_name.startswith('_'):
                    attr = getattr(self, attr_name, None)
                    if attr and hasattr(attr, 'after'):
                        return attr
            return None

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
                from camera import RobustCameraView
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
            tk_widget = self._get_tkinter_root()
            if tk_widget:
                tk_widget.after(1000, self._restart_available_cameras)
            else:
                # Fallback - start immediately
                self._restart_available_cameras()
            
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
            if hasattr(self, 'front_camera') and hasattr(self.front_camera, 'camera_available') and self.front_camera.camera_available:
                self.front_camera.start_continuous_feed()
                
            if hasattr(self, 'back_camera') and hasattr(self.back_camera, 'camera_available') and self.back_camera.camera_available:
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
                self.master_feed_btn.config(text="🔄 Restarting...", state="disabled")
                
                # Schedule button reset
                tk_widget = self._get_tkinter_root()
                if tk_widget:
                    tk_widget.after(3000, lambda: self.master_feed_btn.config(text="🔄 Restart All Feeds", state="normal"))
                else:
                    # Fallback - reset immediately
                    import threading
                    def reset_button():
                        import time
                        time.sleep(3)
                        self.master_feed_btn.config(text="🔄 Restart All Feeds", state="normal")
                    threading.Thread(target=reset_button, daemon=True).start()
            
            print("Both camera feeds restarted with detection")
            
        except Exception as e:
            print(f"Error restarting camera feeds: {e}")

    def capture_both_cameras(self):
        """Capture current frame from both cameras simultaneously"""
        try:
            captured_count = 0
            
            # Capture front camera
            if hasattr(self, 'front_camera') and hasattr(self.front_camera, 'current_frame') and self.front_camera.current_frame is not None:
                if self.front_camera.capture_current_frame():
                    captured_count += 1
            
            # Capture back camera
            if hasattr(self, 'back_camera') and hasattr(self.back_camera, 'current_frame') and self.back_camera.current_frame is not None:
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
        tk_widget = self._get_tkinter_root()
        if tk_widget:
            tk_widget.after(2000, self.monitor_camera_status)  # Check every 2 seconds
        else:
            # Fallback - use threading
            import threading
            def delayed_monitor():
                import time
                time.sleep(2)
                self.monitor_camera_status()
            threading.Thread(target=delayed_monitor, daemon=True).start()

    def update_image_status_display(self):
        """Update the enhanced image status display"""
        if hasattr(self, 'image_handler') and hasattr(self, 'total_image_status_var'):
            try:
                # Get current image counts from the correct reference
                if hasattr(self, 'first_front_image_path'):
                    first_front = bool(self.first_front_image_path)
                    first_back = bool(self.first_back_image_path)
                    second_front = bool(self.second_front_image_path)
                    second_back = bool(self.second_back_image_path)
                else:
                    # Fallback if paths are in image_handler
                    first_front = bool(getattr(self.image_handler.main_form, 'first_front_image_path', None))
                    first_back = bool(getattr(self.image_handler.main_form, 'first_back_image_path', None))
                    second_front = bool(getattr(self.image_handler.main_form, 'second_front_image_path', None))
                    second_back = bool(getattr(self.image_handler.main_form, 'second_back_image_path', None))
                
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
                if hasattr(self, 'total_image_status_var'):
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
                if hasattr(self, 'front_camera'):
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
                if hasattr(self, 'back_camera'):
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
        # Check if we have settings_storage directly
        if hasattr(self, 'settings_storage'):
            return self.settings_storage
        
        # Try to traverse up widget hierarchy to find settings storage
        widget = self
        while widget:
            if hasattr(widget, 'settings_storage'):
                return widget.settings_storage
            if hasattr(widget, 'master'):
                widget = widget.master
            elif hasattr(widget, 'parent'):
                widget = widget.parent
            else:
                break
        
        # If not found in hierarchy, create a new instance
        try:
            from settings_storage import SettingsStorage
            return SettingsStorage()
        except Exception as e:
            print(f"Could not create SettingsStorage: {e}")
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
            if hasattr(self, 'front_camera'):
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
            if hasattr(self, 'back_camera'):
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
                if front_was_running and hasattr(self, 'front_camera'):
                    self.front_camera.start_continuous_feed()
                if back_was_running and hasattr(self, 'back_camera'):
                    self.back_camera.start_continuous_feed()
            
            # Schedule restart feeds after a brief delay
            tk_widget = self._get_tkinter_root()
            if tk_widget:
                tk_widget.after(1000, restart_feeds)
            else:
                # Fallback - use threading
                import threading
                def delayed_restart():
                    import time
                    time.sleep(1)
                    restart_feeds()
                threading.Thread(target=delayed_restart, daemon=True).start()
            
            print("Camera settings updated for robust feed system")
                    
        except Exception as e:
            print(f"Error updating camera settings: {e}")

    def create_cameras_panel(self, parent):
        """Create the cameras panel with cameras side by side and state-based image capture"""
        # Camera container with compact layout
        camera_frame = ttk.LabelFrame(parent, text="Camera Capture (Optional - Can save without images)")
        camera_frame.pack(fill=tk.X, padx=5, pady=5)
        
        # Container for both cameras side by side
        cameras_container = ttk.Frame(camera_frame, style="TFrame")
        cameras_container.pack(fill=tk.X, padx=5, pady=5)
        cameras_container.columnconfigure(0, weight=1)
        cameras_container.columnconfigure(1, weight=1)
        
        # Front camera
        front_panel = ttk.Frame(cameras_container, style="TFrame")
        front_panel.grid(row=0, column=0, padx=2, pady=2, sticky="nsew")
        
        # Front camera title
        ttk.Label(front_panel, text="Front Camera (Optional)").pack(anchor=tk.W, pady=2)
        
        # Create front camera with RTSP support
        try:
            self.front_camera = CameraView(front_panel)
            self.front_camera.save_function = self.image_handler.save_front_image
        except:
            # If camera fails to initialize, create a placeholder
            ttk.Label(front_panel, text="Camera not available\nRecords can still be saved").pack(pady=20)
            self.front_camera = None
        
        # Back camera
        back_panel = ttk.Frame(cameras_container, style="TFrame")
        back_panel.grid(row=0, column=1, padx=2, pady=2, sticky="nsew")
        
        # Back Camera title
        ttk.Label(back_panel, text="Back Camera (Optional)").pack(anchor=tk.W, pady=2)
        
        # Create back camera with RTSP support
        try:
            self.back_camera = CameraView(back_panel)
            self.back_camera.save_function = self.image_handler.save_back_image
        except:
            # If camera fails to initialize, create a placeholder
            ttk.Label(back_panel, text="Camera not available\nRecords can still be saved").pack(pady=20)
            self.back_camera = None
        
        # Load camera settings and configure cameras
        self.load_camera_settings()
        
        # Image status section
        status_frame = ttk.LabelFrame(camera_frame, text="Image Capture Status (Optional)")
        status_frame.pack(fill=tk.X, padx=5, pady=5)
        
        # Current weighment indicator
        current_weighment_frame = ttk.Frame(status_frame)
        current_weighment_frame.pack(fill=tk.X, padx=5, pady=2)
        
        ttk.Label(current_weighment_frame, text="Current State:", 
                 font=("Segoe UI", 9, "bold")).pack(side=tk.LEFT, padx=5)
        
        # This will show which weighment we're currently capturing images for
        weighment_status_label = ttk.Label(current_weighment_frame, 
                                          textvariable=self.weighment_state_var,
                                          font=("Segoe UI", 9, "bold"),
                                          foreground=config.COLORS["primary"])
        weighment_status_label.pack(side=tk.LEFT, padx=5)
        
        # Image count status
        image_status_frame = ttk.Frame(status_frame)
        image_status_frame.pack(fill=tk.X, padx=5, pady=2)
        
        ttk.Label(image_status_frame, text="Images Captured:").pack(side=tk.LEFT, padx=5)
        
        # First weighment image status
        self.first_image_status_var = tk.StringVar(value="1st: 0/2")
        self.first_image_status = ttk.Label(image_status_frame, 
                                           textvariable=self.first_image_status_var, 
                                           foreground="red",
                                           font=("Segoe UI", 8, "bold"))
        self.first_image_status.pack(side=tk.LEFT, padx=10)
        
        # Second weighment image status
        self.second_image_status_var = tk.StringVar(value="2nd: 0/2")
        self.second_image_status = ttk.Label(image_status_frame, 
                                            textvariable=self.second_image_status_var, 
                                            foreground="red",
                                            font=("Segoe UI", 8, "bold"))
        self.second_image_status.pack(side=tk.LEFT, padx=10)
        
        # Total image count
        self.total_image_status_var = tk.StringVar(value="Total: 0/4")
        total_image_status = ttk.Label(image_status_frame,
                                      textvariable=self.total_image_status_var,
                                      foreground="blue",
                                      font=("Segoe UI", 8, "bold"))
        total_image_status.pack(side=tk.LEFT, padx=10)
        
        # Instructions
        instruction_frame = ttk.Frame(status_frame)
        instruction_frame.pack(fill=tk.X, padx=5, pady=2)
        
        instruction_text = ("💡 Images are optional - records can be saved with or without images")
        instruction_label = ttk.Label(instruction_frame, text=instruction_text, 
                                     font=("Segoe UI", 8, "italic"), 
                                     foreground="green")
        instruction_label.pack(side=tk.LEFT, padx=5)
        
        # Add action buttons below the cameras
        action_buttons_frame = ttk.Frame(camera_frame, style="TFrame")
        action_buttons_frame.pack(fill=tk.X, padx=5, pady=(5, 8))
        
        # Create the buttons with callbacks to main application functions
        save_btn = HoverButton(action_buttons_frame, 
                            text="Save Record", 
                            font=("Segoe UI", 10, "bold"),
                            bg=config.COLORS["secondary"],
                            fg=config.COLORS["button_text"],
                            padx=8, pady=3,
                            command=self.trigger_save_callback)
        save_btn.pack(side=tk.LEFT, padx=5)
        
        view_btn = HoverButton(action_buttons_frame, 
                            text="View Records", 
                            font=("Segoe UI", 10),
                            bg=config.COLORS["primary"],
                            fg=config.COLORS["button_text"],
                            padx=8, pady=3,
                            command=self.trigger_view_callback)
        view_btn.pack(side=tk.LEFT, padx=5)
        
        clear_btn = HoverButton(action_buttons_frame, 
                            text="Clear", 
                            font=("Segoe UI", 10),
                            bg=config.COLORS["button_alt"],
                            fg=config.COLORS["button_text"],
                            padx=8, pady=3,
                            command=self.trigger_clear_callback)
        clear_btn.pack(side=tk.LEFT, padx=5)
        
        exit_btn = HoverButton(action_buttons_frame, 
                            text="Exit", 
                            font=("Segoe UI", 10),
                            bg=config.COLORS["error"],
                            fg=config.COLORS["button_text"],
                            padx=8, pady=3,
                            command=self.trigger_exit_callback)
        exit_btn.pack(side=tk.LEFT, padx=5)

    def trigger_save_callback(self):
        """Trigger the save callback - FIXED"""
        try:
            print("Save button clicked!")
            if self.save_callback:
                print("Calling save callback...")
                self.save_callback()
            else:
                print("No save callback set!")
                messagebox.showerror("Error", "Save function not available")
        except Exception as e:
            print(f"Error in save callback: {e}")
            messagebox.showerror("Error", f"Save failed: {str(e)}")

    def trigger_view_callback(self):
        """Trigger the view callback"""
        try:
            if self.view_callback:
                self.view_callback()
            else:
                messagebox.showinfo("Info", "View function not available")
        except Exception as e:
            print(f"Error in view callback: {e}")

    def trigger_clear_callback(self):
        """Trigger the clear callback"""
        try:
            if self.clear_callback:
                self.clear_callback()
            else:
                self.clear_form()
        except Exception as e:
            print(f"Error in clear callback: {e}")
            # Don't call exit callback on error - just clear the form
            self.clear_form()

    def trigger_exit_callback(self):
        """Trigger the exit callback"""
        try:
            if self.exit_callback:
                self.exit_callback()
            else:
                messagebox.showinfo("Info", "Exit function not available")
        except Exception as e:
            print(f"Error in exit callback: {e}")

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
        widget = self
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
            self.after(1000, restart_feeds)
            
            print("Camera settings updated for robust feed system")
                    
        except Exception as e:
            print(f"Error updating camera settings: {e}")




    def prepare_for_next_vehicle_after_first_weighment(self):
        """Prepare form for next vehicle AFTER first weighment is saved"""
        try:
            print(f"🎫 FORM DEBUG: Preparing for next vehicle after first weighment")
            
            # Reset form fields for next vehicle but keep site settings
            self.vehicle_var.set("")
            # Clear weighment data
            self.first_weight_var.set("")
            self.first_timestamp_var.set("")
            self.second_weight_var.set("")
            self.second_timestamp_var.set("")
            self.net_weight_var.set("")
            self.material_type_var.set("")  # Reset to default
            
            # Reset weighment state to first weighment
            self.current_weighment = "first"
            self.weighment_state_var.set("First Weighment")
            
            # Reset all 4 image paths for next vehicle
            self.first_front_image_path = None
            self.first_back_image_path = None
            self.second_front_image_path = None
            self.second_back_image_path = None
            
            # Reset images using image handler
            if hasattr(self, 'image_handler'):
                self.image_handler.reset_images()
            
            # Reserve the NEXT ticket number for the next vehicle
            self.reserve_next_ticket_number()
            new_ticket = self.rst_var.get()
            print(f"🎫 FORM DEBUG: New ticket number reserved: {new_ticket}")
            
            # Update image status display
            if hasattr(self, 'update_image_status_display'):
                self.update_image_status_display()
            
            print(f"🎫 FORM DEBUG: Form prepared for next vehicle - new ticket: {new_ticket}")
            
        except Exception as e:
            print(f"🎫 FORM DEBUG: Error preparing form for next vehicle: {e}")

    def find_main_app(self):
        """Find the main app instance to access data manager and pending vehicles panel"""
        # Start with the parent widget
        widget = self.parent
        while widget:
            # Check if this widget has the attributes we need (data_manager and pending_vehicles)
            if hasattr(widget, 'data_manager') and hasattr(widget, 'pending_vehicles'):
                return widget
            
            # Try to traverse up the widget hierarchy
            if hasattr(widget, 'master'):
                widget = widget.master
            elif hasattr(widget, 'parent'):
                widget = widget.parent
            elif hasattr(widget, 'tk'):
                # Sometimes we need to go through tk
                widget = widget.tk
            else:
                break
                
        # If we can't find through normal traversal, try a different approach
        # Look for any callback that might have the app reference
        if hasattr(self, 'save_callback'):
            # The save_callback is bound to the app's save_record method
            # Try to get the app instance from the callback
            try:
                if hasattr(self.save_callback, '__self__'):
                    callback_owner = self.save_callback.__self__
                    if hasattr(callback_owner, 'data_manager') and hasattr(callback_owner, 'pending_vehicles'):
                        return callback_owner
            except:
                pass
                
        return None


    # Import methods from modular files
    from form_ui import create_form
    from camera_ui import create_cameras_panel, load_camera_settings, get_settings_storage, update_camera_settings

    def find_main_app(self):
        """Find the main app instance to access data manager and pending vehicles panel"""
        widget = self.parent
        while widget:
            if hasattr(widget, 'data_manager') and hasattr(widget, 'pending_vehicles'):
                return widget
            if hasattr(widget, 'master'):
                widget = widget.master
            elif hasattr(widget, 'parent'):
                widget = widget.parent
            else:
                break
        return None

    def on_agency_change(self, *args):
        """Handle agency selection change - simplified for hardcoded mode"""
        if config.HARDCODED_MODE:
            # In hardcoded mode, context never changes
            return
        
        # Original logic for dynamic mode
        try:
            if hasattr(self, 'agency_var') and hasattr(self, 'site_var'):
                agency_name = self.agency_var.get()
                site_name = self.site_var.get()
                
                if agency_name and site_name:
                    if hasattr(self, 'data_manager') and self.data_manager:
                        self.data_manager.set_agency_site_context(agency_name, site_name)
                        print(f"Updated data context: {agency_name}_{site_name}")
                    elif hasattr(self, 'save_callback'):
                        app = self.find_main_app()
                        if app and hasattr(app, 'data_manager'):
                            app.data_manager.set_agency_site_context(agency_name, site_name)
                            print(f"Updated data context via app: {agency_name}_{site_name}")
                            
        except Exception as e:
            print(f"Error in on_agency_change: {e}")

    def on_site_change(self, *args):
        """Handle site selection change to update data file context"""
        self.on_agency_change()

    def reserve_next_ticket_number(self):
        """Reserve (peek at) the next ticket number WITHOUT incrementing counter"""
        try:
            print(f"🎫 FORM DEBUG: Reserving next ticket number...")
            
            # Use the new config function to reserve (not increment) ticket number
            next_ticket = config.reserve_next_ticket_number()
            self.rst_var.set(next_ticket)
            print(f"🎫 FORM DEBUG: Reserved ticket number: {next_ticket}")
            
            # Reset the form to first weighment state for new ticket
            self.current_weighment = "first"
            self.weighment_state_var.set("First Weighment")
            
        except Exception as e:
            print(f"🎫 FORM DEBUG: Error reserving ticket number: {e}")
            # Fallback to old method if new system fails
            self._generate_fallback_ticket()

    def generate_next_ticket_number(self):
        """Generate the next ticket number (for manual new ticket button)"""
        try:
            print(f"🎫 FORM DEBUG: Manually generating next ticket number...")
            
            # Use the new config function to reserve next ticket number
            next_ticket = config.reserve_next_ticket_number()
            self.rst_var.set(next_ticket)
            print(f"🎫 FORM DEBUG: Generated new ticket number: {next_ticket}")
            
            # Reset the form to first weighment state for new ticket
            self.current_weighment = "first"
            self.weighment_state_var.set("First Weighment")

        except Exception as e:
            print(f"🎫 FORM DEBUG: Error generating ticket number: {e}")
            # Fallback to old method if new system fails
            self._generate_fallback_ticket()


    
    def _generate_fallback_ticket(self):
        """Fallback ticket generation method (legacy support)"""
        if not hasattr(self, 'data_manager') or not self.data_manager:
            self.rst_var.set("T0001")
            return
            
        records = self.data_manager.get_all_records()
        highest_num = 0
        prefix = "T"
        
        for record in records:
            ticket = record.get('ticket_no', '')
            if ticket and ticket.startswith(prefix) and len(ticket) > 1:
                try:
                    num = int(ticket[1:])
                    highest_num = max(highest_num, num)
                except ValueError:
                    pass
        
        next_num = highest_num + 1
        next_ticket = f"{prefix}{next_num:04d}"
        self.rst_var.set(next_ticket)
    
    def get_current_ticket_info(self):
        """Get information about current ticket numbering"""
        try:
            current_ticket = config.get_current_ticket_number()
            
            # Get ticket settings for additional info
            if hasattr(self, 'data_manager'):
                app = self.find_main_app()
                if app and hasattr(app, 'settings_storage'):
                    ticket_settings = app.settings_storage.get_ticket_settings()
                    return {
                        "current_ticket": current_ticket,
                        "prefix": ticket_settings.get("ticket_prefix", "T"),
                        "digits": ticket_settings.get("ticket_digits", 4),
                        "next_number": ticket_settings.get("current_ticket_number", 1),
                        "last_reset": ticket_settings.get("last_reset_date", "Never")
                    }
            
            return {"current_ticket": current_ticket}
            
        except Exception as e:
            print(f"Error getting ticket info: {e}")
            return {"current_ticket": "T0001"}
    
    def load_pending_ticket(self, ticket_no):
        """Load a pending ticket for second weighment"""
        if hasattr(self, 'data_manager') and self.data_manager:
            records = self.data_manager.get_filtered_records(ticket_no)
            for record in records:
                if record.get('ticket_no') == ticket_no:
                    if record.get('second_weight') and record.get('second_timestamp'):
                        # Already completed
                        messagebox.showinfo("Completed Record", 
                                        "This ticket already has both weighments completed.")
                        self.load_record_data(record)
                        self.current_weighment = "second"
                        self.weighment_state_var.set("Weighment Complete")
                        return True
                    elif record.get('first_weight') and record.get('first_timestamp'):
                        # Ready for second weighment
                        self.load_record_data(record)
                        self.current_weighment = "second"
                        self.weighment_state_var.set("Second Weighment")
                        return True
        return False

    def init_variables(self):
        """Initialize form variables including 4 image paths"""
        # Create variables for form fields
        self.site_var = tk.StringVar(value="Guntur")
        self.agency_var = tk.StringVar()
        self.rst_var = tk.StringVar()
        self.vehicle_var = tk.StringVar()
        self.tpt_var = tk.StringVar()
        self.material_var = tk.StringVar()
        
        # User and site incharge variables
        self.user_name_var = tk.StringVar()
        self.site_incharge_var = tk.StringVar()
        
        # Weighment related variables
        self.first_weight_var = tk.StringVar()
        self.first_timestamp_var = tk.StringVar()
        self.second_weight_var = tk.StringVar()
        self.second_timestamp_var = tk.StringVar()
        self.net_weight_var = tk.StringVar()
        self.weighment_state_var = tk.StringVar(value="First Weighment")
        
        # Current weight display variable
        self.current_weight_var = tk.StringVar(value="0.00 kg")
        
        # Material type tracking
        self.material_type_var = tk.StringVar(value="Inert")
        
        # 4 separate image paths for first and second weighments
        self.first_front_image_path = None
        self.first_back_image_path = None
        self.second_front_image_path = None
        self.second_back_image_path = None
        
        # Weighment state
        self.current_weighment = "first"  # Can be "first" or "second"
        
        # Vehicle number autocomplete cache
        self.vehicle_numbers_cache = []
        
        # Bind the agency and site variables to update data context
        self.agency_var.trace_add("write", self.on_agency_change)
        self.site_var.trace_add("write", self.on_site_change)
        
        # Reserve next ticket number WITHOUT incrementing counter
        self.reserve_next_ticket_number()

    def update_net_weight_display(self):
        """Calculate and update net weight display when weights change"""
        try:
            first_weight_str = self.first_weight_var.get().strip()
            second_weight_str = self.second_weight_var.get().strip()
            
            if first_weight_str and second_weight_str:
                try:
                    first_weight = float(first_weight_str)
                    second_weight = float(second_weight_str)
                    net_weight = abs(first_weight - second_weight)
                    
                    # Update the net weight display
                    self.net_weight_var.set(f"{net_weight:.2f}")
                    
                    print(f"Net weight calculated and displayed: {net_weight:.2f}")
                    
                except (ValueError, TypeError) as e:
                    print(f"Error calculating net weight: {e}")
                    self.net_weight_var.set("")
            else:
                # Clear net weight if either weight is missing
                self.net_weight_var.set("")
        except Exception as e:
            print(f"Error updating net weight display: {e}")

    def setup_weight_variable_traces(self):
        """Set up trace callbacks to auto-update net weight when weights change"""
        try:
            # Add trace callbacks to first and second weight variables
            self.first_weight_var.trace_add("write", lambda *args: self.update_net_weight_display())
            self.second_weight_var.trace_add("write", lambda *args: self.update_net_weight_display())
            
            print("Weight variable traces set up for auto net weight calculation")
        except Exception as e:
            print(f"Error setting up weight traces: {e}")

    def commit_current_ticket_number(self):
        """Commit the current ticket number (increment the counter) - called after successful save"""
        try:
            current_ticket = self.rst_var.get()
            print(f"🎫 FORM DEBUG: Committing current ticket number: {current_ticket}")
            
            success = config.commit_next_ticket_number()
            if success:
                print(f"🎫 FORM DEBUG: ✅ Successfully committed ticket number: {current_ticket}")
            else:
                print(f"🎫 FORM DEBUG: ❌ Failed to commit ticket number: {current_ticket}")
            return success
        except Exception as e:
            print(f"🎫 FORM DEBUG: Error committing ticket number: {e}")
            return False

    def clear_form(self):
        """Reset form fields except site and Transfer Party Name - FIXED METHOD"""
        try:
            print(f"🎫 FORM DEBUG: Clearing form and generating new ticket...")
            
            # Reset variables
            self.vehicle_var.set("")
            self.first_weight_var.set("")
            self.first_timestamp_var.set("")
            self.second_weight_var.set("")
            self.second_timestamp_var.set("")
            self.net_weight_var.set("")
            self.material_type_var.set("")
            # Reset weighment state
            self.current_weighment = "first"
            self.weighment_state_var.set("First Weighment")
            
            # Reset all 4 image paths
            self.first_front_image_path = None
            self.first_back_image_path = None
            self.second_front_image_path = None
            self.second_back_image_path = None
            
            # Reset images using image handler
            if hasattr(self, 'image_handler'):
                self.image_handler.reset_images()
            
            # Reset cameras if they exist
            if hasattr(self, 'front_camera') and self.front_camera:
                try:
                    if hasattr(self.front_camera, 'stop_continuous_feed'):
                        self.front_camera.stop_continuous_feed()
                    elif hasattr(self.front_camera, 'stop_camera'):
                        self.front_camera.stop_camera()
                        
                    # Reset captured image and display
                    self.front_camera.captured_image = None
                    if hasattr(self.front_camera, 'canvas'):
                        self.front_camera.canvas.delete("all")
                        self.front_camera.show_status_message("Click 'Start Feed' to begin")
                    if hasattr(self.front_camera, 'save_button'):
                        self.front_camera.save_button.config(state=tk.DISABLED)
                except Exception as e:
                    print(f"🎫 FORM DEBUG: Error resetting front camera: {e}")
                    
            if hasattr(self, 'back_camera') and self.back_camera:
                try:
                    if hasattr(self.back_camera, 'stop_continuous_feed'):
                        self.back_camera.stop_continuous_feed()
                    elif hasattr(self.back_camera, 'stop_camera'):
                        self.back_camera.stop_camera()
                        
                    # Reset captured image and display
                    self.back_camera.captured_image = None
                    if hasattr(self.back_camera, 'canvas'):
                        self.back_camera.canvas.delete("all")
                        self.back_camera.show_status_message("Click 'Start Feed' to begin")
                    if hasattr(self.back_camera, 'save_button'):
                        self.back_camera.save_button.config(state=tk.DISABLED)
                except Exception as e:
                    print(f"🎫 FORM DEBUG: Error resetting back camera: {e}")
            
            # Reserve new ticket number when clearing form
            self.reserve_next_ticket_number()
            new_ticket = self.rst_var.get()
            print(f"🎫 FORM DEBUG: New ticket number after clear: {new_ticket}")
            
        except Exception as e:
            print(f"🎫 FORM DEBUG: Error in clear_form: {e}")


    def prepare_for_new_ticket_after_completion(self):
        """Prepare form for new ticket AFTER both weighments are complete and saved"""
        try:
            print(f"🎫 FORM DEBUG: Preparing for new ticket after completion")
            
            # Reset variables
            self.vehicle_var.set("")
            self.first_weight_var.set("")
            self.first_timestamp_var.set("")
            self.second_weight_var.set("")
            self.second_timestamp_var.set("")
            self.net_weight_var.set("")
            self.material_type_var.set("")
            
            # Reset weighment state
            self.current_weighment = "first"
            self.weighment_state_var.set("First Weighment")
            
            # Reset all 4 image paths
            self.first_front_image_path = None
            self.first_back_image_path = None
            self.second_front_image_path = None
            self.second_back_image_path = None
            
            # Reserve the next ticket number
            self.reserve_next_ticket_number()
            new_ticket = self.rst_var.get()
            print(f"🎫 FORM DEBUG: New ticket number reserved after completion: {new_ticket}")
            
            print(f"🎫 FORM DEBUG: Form prepared for new ticket after completion - ticket: {new_ticket}")
            
        except Exception as e:
            print(f"🎫 FORM DEBUG: Error preparing form for new ticket: {e}")


    def get_form_data(self):
        """Get form data as a dictionary with all 4 image fields"""
        now = datetime.datetime.now()
        
        # Get all image filenames using image handler
        image_filenames = self.image_handler.get_all_image_filenames()
        
        # Debug: Print current values to check what we're getting
        print(f"DEBUG - User name var: '{self.user_name_var.get()}'")
        print(f"DEBUG - Site incharge var: '{self.site_incharge_var.get()}'")
        print(f"DEBUG - Net weight var: '{self.net_weight_var.get()}'")
        
        data = {
            'date': now.strftime("%d-%m-%Y"),
            'time': now.strftime("%H:%M:%S"),
            'site_name': self.site_var.get(),
            'agency_name': self.agency_var.get(),
            'material': self.material_type_var.get(),
            'ticket_no': self.rst_var.get(),
            'vehicle_no': self.vehicle_var.get(),
            'transfer_party_name': self.tpt_var.get(),
            'first_weight': self.first_weight_var.get(),
            'first_timestamp': self.first_timestamp_var.get(),
            'second_weight': self.second_weight_var.get(),
            'second_timestamp': self.second_timestamp_var.get(),
            'net_weight': self.net_weight_var.get(),
            'material_type': self.material_type_var.get(),
            # All 4 image fields
            'first_front_image': image_filenames['first_front_image'],
            'first_back_image': image_filenames['first_back_image'],
            'second_front_image': image_filenames['second_front_image'],
            'second_back_image': image_filenames['second_back_image'],
            # Make sure these fields are properly set
            'site_incharge': self.site_incharge_var.get() if hasattr(self, 'site_incharge_var') else "",
            'user_name': self.user_name_var.get() if hasattr(self, 'user_name_var') else ""
        }
        
        # Ensure empty weight fields are saved as empty strings
        for field in ['first_weight', 'second_weight', 'first_timestamp', 'second_timestamp', 'net_weight']:
            if not data[field]:
                data[field] = ''
        
        # Debug: Print final data to verify
        print(f"DEBUG - Final data user_name: '{data['user_name']}'")
        print(f"DEBUG - Final data site_incharge: '{data['site_incharge']}'")
        print(f"DEBUG - Final data net_weight: '{data['net_weight']}'")
                
        return data

    def validate_vehicle_before_any_operation(self):
        """STRICT: Validate vehicle is not pending before ANY operation"""
        try:
            vehicle_no = self.vehicle_var.get().strip()
            
            if not vehicle_no:
                return True  # Empty vehicle will be caught by other validation
            
            # Use form validator to check
            if hasattr(self, 'form_validator'):
                return self.form_validator.validate_vehicle_not_in_pending()
            
            return True
            
        except Exception as e:
            print(f"Error in vehicle validation: {e}")
            messagebox.showerror("System Error", f"Cannot validate vehicle: {str(e)}")
            return False

    def setup_vehicle_validation(self):
        """Setup real-time vehicle validation"""
        # Bind validation to vehicle field changes
        self.vehicle_var.trace("w", self.on_vehicle_change)

    def on_vehicle_change(self, *args):
        """Called when vehicle number changes - validate immediately"""
        try:
            vehicle_no = self.vehicle_var.get().strip()
            
            if len(vehicle_no) >= 3:  # Only check when reasonable length
                # Small delay to avoid checking on every keystroke
                if hasattr(self, '_vehicle_check_after_id'):
                    self.after_cancel(self._vehicle_check_after_id)
                
                self._vehicle_check_after_id = self.after(500, self.delayed_vehicle_check)
                
        except Exception as e:
            print(f"Error in vehicle change handler: {e}")

    def delayed_vehicle_check(self):
        """Delayed vehicle check to avoid too many calls"""
        try:
            vehicle_no = self.vehicle_var.get().strip().upper()
            
            if not vehicle_no:
                return
            
            # Check if vehicle is pending and show immediate feedback
            app = self.find_main_app()
            if not app or not hasattr(app, 'data_manager'):
                return
            
            records = app.data_manager.get_all_records()
            
            for record in records:
                record_vehicle = record.get('vehicle_no', '').strip().upper()
                
                if record_vehicle == vehicle_no:
                    first_weight = record.get('first_weight', '').strip()
                    first_timestamp = record.get('first_timestamp', '').strip()
                    has_first = first_weight != '' and first_timestamp != ''
                    
                    second_weight = record.get('second_weight', '').strip()
                    second_timestamp = record.get('second_timestamp', '').strip()
                    missing_second = (second_weight == '' or second_timestamp == '')
                    
                    if has_first and missing_second:
                        # Show immediate warning
                        pending_ticket = record.get('ticket_no', 'Unknown')
                        
                        # Update vehicle field to show warning
                        self.vehicle_entry.config(style="Warning.TEntry")
                        
                        # Show tooltip or status
                        if hasattr(self, 'vehicle_status_label'):
                            self.vehicle_status_label.config(
                                text=f"⚠️ PENDING: Ticket {pending_ticket}",
                                foreground="red"
                            )
                        return
            
            # Vehicle not pending - clear warnings
            self.vehicle_entry.config(style="TEntry")
            if hasattr(self, 'vehicle_status_label'):
                self.vehicle_status_label.config(text="✅ Available", foreground="green")
                
        except Exception as e:
            print(f"Error in delayed vehicle check: {e}")

    def load_record_data(self, record):
        """Load record data into the form including all 4 images"""
        # Set basic fields
        self.rst_var.set(record.get('ticket_no', ''))
        self.vehicle_var.set(record.get('vehicle_no', ''))
        self.agency_var.set(record.get('agency_name', ''))
        material_data = record.get('material', '') or record.get('material_type', '')
        self.material_type_var.set(material_data) 
        self.tpt_var.set(record.get('transfer_party_name', ''))
        self.site_var.set(record.get('site_name', ''))
        # Set weighment data
        self.first_weight_var.set(record.get('first_weight', ''))
        self.first_timestamp_var.set(record.get('first_timestamp', ''))
        self.second_weight_var.set(record.get('second_weight', ''))
        self.second_timestamp_var.set(record.get('second_timestamp', ''))
        self.net_weight_var.set(record.get('net_weight', ''))
        
        # Handle all 4 images using image handler
        self.image_handler.load_images_from_record(record)

    def is_record_complete(self):
        """Check if record has both weighments complete"""
        first_weight = self.first_weight_var.get().strip()
        first_timestamp = self.first_timestamp_var.get().strip()
        second_weight = self.second_weight_var.get().strip()
        second_timestamp = self.second_timestamp_var.get().strip()
        
        return bool(first_weight and first_timestamp and second_weight and second_timestamp)

    def validate_form(self):
        """FIXED: Delegate form validation to FormValidator instance"""
        try:
            self.logger.info("Starting form validation - delegating to FormValidator")
            
            # Use the form_validator instance to validate
            if hasattr(self, 'form_validator') and self.form_validator:
                return self.form_validator.validate_form()
            else:
                self.logger.error("No form_validator available")
                messagebox.showerror("System Error", "Form validator not available. Please restart the application.")
                return False
            
        except Exception as e:
            self.logger.error(f"Error in form validation delegation: {e}")
            messagebox.showerror("Validation Error", f"Form validation failed: {str(e)}")
            return False


    def set_agency(self, agency_name):
        """Set the agency name"""
        if agency_name and hasattr(self, 'agency_var'):
            self.agency_var.set(agency_name)

    def set_site_incharge(self, incharge_name):
        """Set the site incharge name"""
        if incharge_name and hasattr(self, 'site_incharge_var'):
            self.site_incharge_var.set(incharge_name)

    def set_site(self, site_name):
        """Set the site name"""
        if site_name and hasattr(self, 'site_var'):
            self.site_var.set(site_name)

    def set_user_info(self, username=None, site_incharge=None):
        """Set the user and site incharge information"""
        if username and hasattr(self, 'user_name_var'):
            self.user_name_var.set(username)
            
        if site_incharge and hasattr(self, 'site_incharge_var'):
            self.site_incharge_var.set(site_incharge)

    def load_sites_and_agencies(self, settings_storage):
        """Load sites, agencies and transfer parties from settings storage or hardcoded values"""
        if config.HARDCODED_MODE:
            # Use hardcoded values
            sites = config.HARDCODED_SITES
            agencies = config.HARDCODED_AGENCIES
            transfer_parties = config.HARDCODED_TRANSFER_PARTIES
            
            self.logger.info("Using hardcoded dropdown values")
        else:
            # Original logic
            if not settings_storage:
                return
                
            sites_data = settings_storage.get_sites()
            sites = sites_data.get('sites', ['Guntur'])
            agencies = sites_data.get('agencies', ['Default Agency'])
            transfer_parties = sites_data.get('transfer_parties', ['Advitia Labs'])
        
        # Update dropdowns
        if hasattr(self, 'site_combo'):
            self.site_combo['values'] = sites
            if sites and not self.site_var.get():
                self.site_combo.current(0)
        
        if hasattr(self, 'agency_combo'):
            self.agency_combo['values'] = agencies
            if agencies and not self.agency_var.get():
                self.agency_combo.current(0)
        
        if hasattr(self, 'tpt_combo'):
            self.tpt_combo['values'] = transfer_parties
            if transfer_parties and not self.tpt_var.get():
                self.tpt_combo.current(0)

    def on_closing(self):
        """Handle cleanup when closing - FIXED METHOD"""
        try:
            if hasattr(self, 'front_camera') and self.front_camera:
                if hasattr(self.front_camera, 'stop_continuous_feed'):
                    self.front_camera.stop_continuous_feed()
                elif hasattr(self.front_camera, 'stop_camera'):
                    self.front_camera.stop_camera()
                    
            if hasattr(self, 'back_camera') and self.back_camera:
                if hasattr(self.back_camera, 'stop_continuous_feed'):
                    self.back_camera.stop_continuous_feed()
                elif hasattr(self.back_camera, 'stop_camera'):
                    self.back_camera.stop_camera()
        except Exception as e:
            print(f"Error in camera cleanup: {e}")

    # Legacy methods that delegate to component managers
    def handle_weighbridge_weight(self, weight):
        """Handle weight from weighbridge - delegates to weight manager"""
        return self.weight_manager.handle_weighbridge_weight(weight)
    
    def capture_weight(self):
        """Capture weight - delegates to weight manager"""
        return self.weight_manager.capture_weight()
    
    def save_front_image(self, captured_image=None):
        """Save front image - delegates to image handler"""
        return self.image_handler.save_front_image(captured_image)
    
    def save_back_image(self, captured_image=None):
        """Save back image - delegates to image handler"""
        return self.image_handler.save_back_image(captured_image)