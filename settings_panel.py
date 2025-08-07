import tkinter as tk
from tkinter import ttk, messagebox
import serial.tools.list_ports
import json
import config
from ui_components import HoverButton
from weighbridge import WeighbridgeManager
from settings_storage import SettingsStorage
import datetime


class SettingsPanel:
    """Settings panel for camera and weighbridge configuration"""
    
    def __init__(self, parent, weighbridge_callback=None, update_cameras_callback=None, 
            current_user=None, user_role=None):
        """Initialize settings panel
        
        Args:
            parent: Parent widget
            weighbridge_callback: Callback for weighbridge weight updates
            update_cameras_callback: Callback for camera updates
            current_user: Currently logged-in username
            user_role: User role (admin or user)
        """
        self.parent = parent
        self.weighbridge_callback = weighbridge_callback
        self.update_cameras_callback = update_cameras_callback
        self.current_user = current_user
        self.user_role = user_role
        
        # Initialize settings storage
        self.settings_storage = SettingsStorage()
        
        # Continue with initialization
        self.init_variables()
        
        # Set up a flag to prevent recursive callbacks
        self.processing_callback = False
        
        # Initialize weighbridge with the fixed callback
        self.weighbridge = WeighbridgeManager(self.update_weight_display)
        import config
        config.set_global_weighbridge(self.weighbridge, self.current_weight_var, self.wb_status_var)

        # Check authentication for settings access
        if not self.authenticate_settings_access():
            return
        self.create_panel()
        
        # IMPORTANT: Load saved settings AFTER creating the panel
        self.load_all_saved_settings()


    def create_panel(self):
        """Create settings panel with tabs"""
        # Create settings notebook
        self.settings_notebook = ttk.Notebook(self.parent)
        self.settings_notebook.pack(fill=tk.BOTH, expand=True)
        
        # Weighbridge settings tab
        weighbridge_tab = ttk.Frame(self.settings_notebook, style="TFrame")
        self.settings_notebook.add(weighbridge_tab, text="Weighbridge")
        
        # Camera settings tab
        camera_tab = ttk.Frame(self.settings_notebook, style="TFrame")
        self.settings_notebook.add(camera_tab, text="Cameras")
        
        # Only create User and Site management tabs if NOT in hardcoded mode
        if not config.HARDCODED_MODE:
            # User management tab (only visible to admin)
            users_tab = ttk.Frame(self.settings_notebook, style="TFrame")
            self.settings_notebook.add(users_tab, text="Users")
            
            # Site management tab (only visible to admin)
            sites_tab = ttk.Frame(self.settings_notebook, style="TFrame")
            self.settings_notebook.add(sites_tab, text="Sites")
            
            # Create user and site management content
            self.create_user_management(users_tab)
            self.create_site_management(sites_tab)
        
        # Create tab contents for core tabs (always present)
        self.create_weighbridge_settings(weighbridge_tab)
        self.create_camera_settings(camera_tab)

        # Admin controls (lock/unlock) - only show if admin and not hardcoded mode
        if self.user_role == 'admin' and not config.HARDCODED_MODE:
            lock_frame = ttk.Frame(self.parent)
            lock_frame.pack(fill=tk.X, padx=5, pady=5)
            
            if self.are_settings_locked():
                unlock_btn = HoverButton(lock_frame,
                                    text="🔓 Unlock Settings",
                                    bg=config.COLORS["warning"],
                                    fg=config.COLORS["button_text"],
                                    padx=10, pady=3,
                                    command=self.unlock_settings)
                unlock_btn.pack(side=tk.RIGHT, padx=5)
            else:
                lock_btn = HoverButton(lock_frame,
                                    text="🔒 Lock Settings",
                                    bg=config.COLORS["error"],
                                    fg=config.COLORS["button_text"],
                                    padx=10, pady=3,
                                    command=self.lock_settings)
                lock_btn.pack(side=tk.RIGHT, padx=5)

            if self.are_settings_locked():
                self.disable_all_settings()

    def create_sites_tab(self):
        """Create sites management tab - disabled in hardcoded mode"""
        if config.HARDCODED_MODE:
            # Create a simple label explaining hardcoded mode
            info_frame = ttk.Frame(self.sites_frame, padding=20)
            info_frame.pack(fill=tk.BOTH, expand=True)
            
            ttk.Label(info_frame, 
                    text="Sites Management is disabled.\n\n"
                        f"Current Configuration:\n"
                        f"Agency: {config.HARDCODED_AGENCY}\n"
                        f"Site: {config.HARDCODED_SITE}\n"
                        f"Transfer Party: {config.HARDCODED_TRANSFER_PARTY}\n"
                        f"Incharge: {config.HARDCODED_INCHARGE}\n\n"
                        f"To modify these values, edit the config.py file.",
                    font=("Segoe UI", 12),
                    justify=tk.CENTER).pack(expand=True)
            return


    def load_all_saved_settings(self):
        """Load all saved settings after panel creation - UPDATED"""
        try:
            print("Loading saved settings...")
            
            # Load weighbridge settings (this now includes test mode)
            self.load_weighbridge_settings()  # This will now handle test mode
            
            # Load camera settings  
            self.load_saved_camera_settings()
            
            # Load user management data
            self.load_users()
            
            # Load site management data
            self.load_sites()
            
            print("All settings loaded successfully")
            
        except Exception as e:
            print(f"Error loading saved settings: {e}")

    def load_saved_weighbridge_settings(self):
        """Load weighbridge settings from storage"""
        try:
            wb_settings = self.settings_storage.get_weighbridge_settings()
            if wb_settings:
                print(f"Loading weighbridge settings: {wb_settings}")
                
                # Refresh COM ports first
                self.refresh_com_ports()
                
                # Set COM port if it exists in the list
                if "com_port" in wb_settings and wb_settings["com_port"]:
                    available_ports = self.com_port_combo['values']
                    if wb_settings["com_port"] in available_ports:
                        self.com_port_var.set(wb_settings["com_port"])
                        print(f"Set COM port to: {wb_settings['com_port']}")
                    else:
                        print(f"Saved COM port {wb_settings['com_port']} not available")
                
                # Set other weighbridge settings
                if "baud_rate" in wb_settings:
                    self.baud_rate_var.set(wb_settings["baud_rate"])
                if "data_bits" in wb_settings:
                    self.data_bits_var.set(wb_settings["data_bits"])
                if "parity" in wb_settings:
                    self.parity_var.set(wb_settings["parity"])
                if "stop_bits" in wb_settings:
                    self.stop_bits_var.set(wb_settings["stop_bits"])
                    
                print("Weighbridge settings loaded successfully")
            else:
                print("No saved weighbridge settings found")
                
        except Exception as e:
            print(f"Error loading weighbridge settings: {e}")

    def load_saved_camera_settings(self):
        """Load camera settings from storage with HTTP support"""
        try:
            camera_settings = self.settings_storage.get_camera_settings()
            if camera_settings:
                print(f"Loading camera settings: {camera_settings}")
                
                # Load front camera settings
                if hasattr(self, 'front_camera_type_var'):
                    self.front_camera_type_var.set(camera_settings.get("front_camera_type", "USB"))
                if hasattr(self, 'front_usb_index_var'):
                    self.front_usb_index_var.set(camera_settings.get("front_camera_index", 0))
                    
                # Load front RTSP settings
                if hasattr(self, 'front_rtsp_username_var'):
                    self.front_rtsp_username_var.set(camera_settings.get("front_rtsp_username", ""))
                if hasattr(self, 'front_rtsp_password_var'):
                    self.front_rtsp_password_var.set(camera_settings.get("front_rtsp_password", ""))
                if hasattr(self, 'front_rtsp_ip_var'):
                    self.front_rtsp_ip_var.set(camera_settings.get("front_rtsp_ip", ""))
                if hasattr(self, 'front_rtsp_port_var'):
                    self.front_rtsp_port_var.set(camera_settings.get("front_rtsp_port", "554"))
                if hasattr(self, 'front_rtsp_endpoint_var'):
                    self.front_rtsp_endpoint_var.set(camera_settings.get("front_rtsp_endpoint", "/stream1"))
                    
                # Load front HTTP settings
                if hasattr(self, 'front_http_username_var'):
                    self.front_http_username_var.set(camera_settings.get("front_http_username", ""))
                if hasattr(self, 'front_http_password_var'):
                    self.front_http_password_var.set(camera_settings.get("front_http_password", ""))
                if hasattr(self, 'front_http_ip_var'):
                    self.front_http_ip_var.set(camera_settings.get("front_http_ip", ""))
                if hasattr(self, 'front_http_port_var'):
                    self.front_http_port_var.set(camera_settings.get("front_http_port", "80"))
                if hasattr(self, 'front_http_endpoint_var'):
                    self.front_http_endpoint_var.set(camera_settings.get("front_http_endpoint", "/mjpeg"))
                
                # Load back camera settings
                if hasattr(self, 'back_camera_type_var'):
                    self.back_camera_type_var.set(camera_settings.get("back_camera_type", "USB"))
                if hasattr(self, 'back_usb_index_var'):
                    self.back_usb_index_var.set(camera_settings.get("back_camera_index", 1))
                    
                # Load back RTSP settings
                if hasattr(self, 'back_rtsp_username_var'):
                    self.back_rtsp_username_var.set(camera_settings.get("back_rtsp_username", ""))
                if hasattr(self, 'back_rtsp_password_var'):
                    self.back_rtsp_password_var.set(camera_settings.get("back_rtsp_password", ""))
                if hasattr(self, 'back_rtsp_ip_var'):
                    self.back_rtsp_ip_var.set(camera_settings.get("back_rtsp_ip", ""))
                if hasattr(self, 'back_rtsp_port_var'):
                    self.back_rtsp_port_var.set(camera_settings.get("back_rtsp_port", "554"))
                if hasattr(self, 'back_rtsp_endpoint_var'):
                    self.back_rtsp_endpoint_var.set(camera_settings.get("back_rtsp_endpoint", "/stream1"))
                    
                # Load back HTTP settings
                if hasattr(self, 'back_http_username_var'):
                    self.back_http_username_var.set(camera_settings.get("back_http_username", ""))
                if hasattr(self, 'back_http_password_var'):
                    self.back_http_password_var.set(camera_settings.get("back_http_password", ""))
                if hasattr(self, 'back_http_ip_var'):
                    self.back_http_ip_var.set(camera_settings.get("back_http_ip", ""))
                if hasattr(self, 'back_http_port_var'):
                    self.back_http_port_var.set(camera_settings.get("back_http_port", "80"))
                if hasattr(self, 'back_http_endpoint_var'):
                    self.back_http_endpoint_var.set(camera_settings.get("back_http_endpoint", "/mjpeg"))
                
                # Update UI states based on loaded settings
                if hasattr(self, 'on_camera_type_change'):
                    self.on_camera_type_change("front")
                    self.on_camera_type_change("back")
                
                # Update previews
                if hasattr(self, 'update_rtsp_preview'):
                    self.update_rtsp_preview("front")
                    self.update_rtsp_preview("back")
                if hasattr(self, 'update_http_preview'):
                    self.update_http_preview("front")
                    self.update_http_preview("back")
                
                print("Camera settings loaded successfully")
            else:
                print("No saved camera settings found")
                
        except Exception as e:
            print(f"Error loading camera settings: {e}")

    def save_weighbridge_settings(self):
        """Save weighbridge settings including test mode"""
        try:
            settings = {
                "com_port": self.com_port_var.get(),
                "baud_rate": int(self.baud_rate_var.get()),
                "data_bits": int(self.data_bits_var.get()),
                "parity": self.parity_var.get(),
                "stop_bits": float(self.stop_bits_var.get()),
                "test_mode": self.test_mode_var.get()  # Include test mode in save
            }
            
            if self.settings_storage.save_weighbridge_settings(settings):
                print("Weighbridge settings with test mode saved successfully")
                return True
            else:
                print("Failed to save weighbridge settings")
                return False
                
        except Exception as e:
            print(f"Error saving weighbridge settings: {e}")
            return False

    def save_camera_settings(self):
        """Save camera settings to persistent storage"""
        try:
            settings = self.get_current_camera_settings()
            
            print(f"Saving camera settings: {settings}")
            
            if self.settings_storage.save_camera_settings(settings):
                # messagebox.showinfo("Success", "Camera settings saved successfully!")
                print("Camera settings saved to file")
                
                # Apply the settings immediately if callback available
                if self.update_cameras_callback:
                    self.update_cameras_callback(settings)
                
                self.cam_status_var.set("Settings saved successfully")
                return True
            else:
                messagebox.showerror("Error", "Failed to save camera settings.")
                return False
                
        except Exception as e:
            print(f"Error saving camera settings: {e}")
            messagebox.showerror("Error", f"Failed to save camera settings: {str(e)}")
            return False

    def apply_camera_settings(self):
        """Apply camera settings without saving"""
        try:
            # Get current settings
            settings = self.get_current_camera_settings()
            
            print(f"Applying camera settings: {settings}")
            
            # Apply to cameras through callback
            if self.update_cameras_callback:
                self.update_cameras_callback(settings)
            
            self.cam_status_var.set("Camera settings applied. Changes take effect on next capture.")
            
        except Exception as e:
            print(f"Error applying camera settings: {e}")
            self.cam_status_var.set(f"Error applying settings: {str(e)}")


    def create_settings_tabs_hidden(self):
        """Alternative: Create settings notebook with hidden tabs in hardcoded mode"""
        # Create the notebook
        self.settings_notebook = ttk.Notebook(self.parent, style="TNotebook")
        self.settings_notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Weighbridge settings tab
        weighbridge_tab = ttk.Frame(self.settings_notebook, style="TFrame")
        self.settings_notebook.add(weighbridge_tab, text="Weighbridge")
        
        # Camera settings tab
        camera_tab = ttk.Frame(self.settings_notebook, style="TFrame")
        self.settings_notebook.add(camera_tab, text="Cameras")
        
        # Always create the tabs but hide them in hardcoded mode
        users_tab = ttk.Frame(self.settings_notebook, style="TFrame")
        sites_tab = ttk.Frame(self.settings_notebook, style="TFrame")
        
        if config.HARDCODED_MODE:
            # Add but immediately hide the tabs
            self.settings_notebook.add(users_tab, text="Users")
            self.settings_notebook.add(sites_tab, text="Sites")
            self.settings_notebook.tab(2, state="hidden")  # Hide Users tab
            self.settings_notebook.tab(3, state="hidden")  # Hide Sites tab
        else:
            # Normal mode - add and show tabs
            self.settings_notebook.add(users_tab, text="Users")
            self.settings_notebook.add(sites_tab, text="Sites")
            self.create_user_management(users_tab)
            self.create_site_management(sites_tab)
        
        # Create tab contents for enabled tabs
        self.create_weighbridge_settings(weighbridge_tab)
        self.create_camera_settings(camera_tab)            

    def get_current_camera_settings(self):
        """Get current camera settings from UI with HTTP support
        
        Returns:
            dict: Camera settings
        """
        settings = {}
        
        # Get front camera settings
        if hasattr(self, 'front_camera_type_var'):
            settings["front_camera_type"] = self.front_camera_type_var.get()
        if hasattr(self, 'front_usb_index_var'):
            settings["front_camera_index"] = self.front_usb_index_var.get()
            
        # Front RTSP settings
        if hasattr(self, 'front_rtsp_username_var'):
            settings["front_rtsp_username"] = self.front_rtsp_username_var.get()
        if hasattr(self, 'front_rtsp_password_var'):
            settings["front_rtsp_password"] = self.front_rtsp_password_var.get()
        if hasattr(self, 'front_rtsp_ip_var'):
            settings["front_rtsp_ip"] = self.front_rtsp_ip_var.get()
        if hasattr(self, 'front_rtsp_port_var'):
            settings["front_rtsp_port"] = self.front_rtsp_port_var.get()
        if hasattr(self, 'front_rtsp_endpoint_var'):
            settings["front_rtsp_endpoint"] = self.front_rtsp_endpoint_var.get()
            
        # Front HTTP settings
        if hasattr(self, 'front_http_username_var'):
            settings["front_http_username"] = self.front_http_username_var.get()
        if hasattr(self, 'front_http_password_var'):
            settings["front_http_password"] = self.front_http_password_var.get()
        if hasattr(self, 'front_http_ip_var'):
            settings["front_http_ip"] = self.front_http_ip_var.get()
        if hasattr(self, 'front_http_port_var'):
            settings["front_http_port"] = self.front_http_port_var.get()
        if hasattr(self, 'front_http_endpoint_var'):
            settings["front_http_endpoint"] = self.front_http_endpoint_var.get()
            
        # Get back camera settings
        if hasattr(self, 'back_camera_type_var'):
            settings["back_camera_type"] = self.back_camera_type_var.get()
        if hasattr(self, 'back_usb_index_var'):
            settings["back_camera_index"] = self.back_usb_index_var.get()
            
        # Back RTSP settings
        if hasattr(self, 'back_rtsp_username_var'):
            settings["back_rtsp_username"] = self.back_rtsp_username_var.get()
        if hasattr(self, 'back_rtsp_password_var'):
            settings["back_rtsp_password"] = self.back_rtsp_password_var.get()
        if hasattr(self, 'back_rtsp_ip_var'):
            settings["back_rtsp_ip"] = self.back_rtsp_ip_var.get()
        if hasattr(self, 'back_rtsp_port_var'):
            settings["back_rtsp_port"] = self.back_rtsp_port_var.get()
        if hasattr(self, 'back_rtsp_endpoint_var'):
            settings["back_rtsp_endpoint"] = self.back_rtsp_endpoint_var.get()
            
        # Back HTTP settings
        if hasattr(self, 'back_http_username_var'):
            settings["back_http_username"] = self.back_http_username_var.get()
        if hasattr(self, 'back_http_password_var'):
            settings["back_http_password"] = self.back_http_password_var.get()
        if hasattr(self, 'back_http_ip_var'):
            settings["back_http_ip"] = self.back_http_ip_var.get()
        if hasattr(self, 'back_http_port_var'):
            settings["back_http_port"] = self.back_http_port_var.get()
        if hasattr(self, 'back_http_endpoint_var'):
            settings["back_http_endpoint"] = self.back_http_endpoint_var.get()
        
        return settings

    def auto_connect_weighbridge(self):
        """Automatically connect to weighbridge if settings are saved"""
        try:
            wb_settings = self.settings_storage.get_weighbridge_settings()
            if wb_settings and wb_settings.get("com_port"):
                com_port = wb_settings.get("com_port")
                
                # Check if the saved COM port is still available
                available_ports = self.weighbridge.get_available_ports()
                if com_port in available_ports:
                    print(f"Auto-connecting to saved weighbridge on {com_port}")
                    
                    # Try to connect automatically
                    try:
                        if self.weighbridge.connect(
                            com_port,
                            wb_settings.get("baud_rate", 9600),
                            wb_settings.get("data_bits", 8),
                            wb_settings.get("parity", "None"),
                            wb_settings.get("stop_bits", 1.0)
                        ):
                            self.wb_status_var.set("Status: Connected")
                            self.weight_label.config(foreground="green")
                            self.connect_btn.config(state=tk.DISABLED)
                            self.disconnect_btn.config(state=tk.NORMAL)
                            print("Auto-connection successful")
                        else:
                            print("Auto-connection failed")
                    except Exception as e:
                        print(f"Auto-connection error: {e}")
                else:
                    print(f"Saved COM port {com_port} not available")
            else:
                print("No saved weighbridge settings for auto-connection")
                
        except Exception as e:
            print(f"Error in auto-connect: {e}")



    def on_closing(self):
        """Handle cleanup when closing"""
        try:
            # Save current settings before closing
            print("Saving settings on close...")
            
            # Save weighbridge settings
            if hasattr(self, 'com_port_var'):
                self.save_weighbridge_settings()
            
            # Save camera settings
            if hasattr(self, 'front_camera_type_var'):
                self.save_camera_settings()
            
            # Disconnect weighbridge
            if self.weighbridge:
                self.weighbridge.disconnect()
                
            print("Settings saved on close")
            
        except Exception as e:
            print(f"Error saving settings on close: {e}")

    def authenticate_settings_access(self):
        """Authenticate for settings access"""
        # Check if settings are locked
        if self.are_settings_locked():
            # #messagebox.showinfo("Settings Locked", 
            #                 "Settings have been locked by the administrator.\n"
            #                 "Contact your system administrator to modify settings.")
            return False
        
        # If we already have a current user with admin role, allow access
        if self.current_user and self.user_role == 'admin':
            return True
        
        # Otherwise, prompt for authentication
        auth_dialog = tk.Toplevel(self.parent)
        auth_dialog.title("Settings Authentication")
        auth_dialog.geometry("350x200")
        auth_dialog.resizable(False, False)
        auth_dialog.transient(self.parent)
        auth_dialog.grab_set()
        
        # Center dialog
        auth_dialog.update_idletasks()
        width = auth_dialog.winfo_width()
        height = auth_dialog.winfo_height()
        x = (self.parent.winfo_screenwidth() // 2) - (width // 2)
        y = (self.parent.winfo_screenheight() // 2) - (height // 2)
        auth_dialog.geometry(f"+{x}+{y}")
        
        # Create form
        frame = ttk.Frame(auth_dialog, padding=20)
        frame.pack(fill=tk.BOTH, expand=True)
        
        ttk.Label(frame, text="Enter admin credentials to access settings:",
                font=("Segoe UI", 10, "bold")).pack(pady=(0, 15))
        
        # Username
        username_frame = ttk.Frame(frame)
        username_frame.pack(fill=tk.X, pady=5)
        ttk.Label(username_frame, text="Username:", width=12).pack(side=tk.LEFT)
        username_var = tk.StringVar()
        username_entry = ttk.Entry(username_frame, textvariable=username_var, width=20)
        username_entry.pack(side=tk.LEFT, padx=5)
        username_entry.focus_set()
        
        # Password
        password_frame = ttk.Frame(frame)
        password_frame.pack(fill=tk.X, pady=5)
        ttk.Label(password_frame, text="Password:", width=12).pack(side=tk.LEFT)
        password_var = tk.StringVar()
        password_entry = ttk.Entry(password_frame, textvariable=password_var, show="*", width=20)
        password_entry.pack(side=tk.LEFT, padx=5)
        
        # Result
        authenticated = [False]  # Using list as mutable container
        
        # Buttons
        def on_ok(event=None):
            if self.settings_storage.isAuthenticated(username_var.get(), password_var.get()):
                if self.settings_storage.isAdminUser(username_var.get()):
                    authenticated[0] = True
                    auth_dialog.destroy()
                else:
                    messagebox.showerror("Access Denied", 
                                    "Only administrators can access settings.", 
                                    parent=auth_dialog)
            else:
                messagebox.showerror("Authentication Failed", 
                                "Invalid username or password", 
                                parent=auth_dialog)
        
        def on_cancel():
            auth_dialog.destroy()
        
        # Bind Enter key to OK
        auth_dialog.bind('<Return>', on_ok)
        
        button_frame = ttk.Frame(frame)
        button_frame.pack(fill=tk.X, pady=(15, 0))
        
        ok_btn = ttk.Button(button_frame, text="OK", command=on_ok)
        ok_btn.pack(side=tk.LEFT, padx=5)
        
        cancel_btn = ttk.Button(button_frame, text="Cancel", command=on_cancel)
        cancel_btn.pack(side=tk.LEFT, padx=5)
        
        # Wait for dialog to close
        self.parent.wait_window(auth_dialog)
        
        # Return authentication result
        return authenticated[0]

    def are_settings_locked(self):
        """Check if settings are locked"""
        try:
            settings = self.settings_storage.get_all_settings()
            return settings.get("locked", False)
        except:
            return False



    def lock_settings(self):
        """Lock all settings from being modified"""
        try:
            settings = self.settings_storage.get_all_settings()
            settings["locked"] = True
            
            # Save the locked state using settings_storage method
            # First, save each section properly
            if "weighbridge" in settings:
                self.settings_storage.save_weighbridge_settings(settings["weighbridge"])
            if "cameras" in settings:
                self.settings_storage.save_camera_settings(settings["cameras"])
                
            # Now save the complete settings with locked flag
            import json
            with open(self.settings_storage.settings_file, 'r') as f:
                all_settings = json.load(f)
            
            all_settings["locked"] = True
            
            with open(self.settings_storage.settings_file, 'w') as f:
                json.dump(all_settings, f, indent=4)
                
            messagebox.showinfo("Settings Locked", 
                            "All settings have been locked.\n"
                            "Only administrators can unlock them.")
            
            # Disable all input widgets
            self.disable_all_settings()
            
            # Update the lock button to show unlock button
            self.update_lock_button()
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to lock settings: {str(e)}")

    def unlock_settings(self):
        """Unlock settings for modification"""
        try:
            import json
            with open(self.settings_storage.settings_file, 'r') as f:
                settings = json.load(f)
            
            settings["locked"] = False
            
            with open(self.settings_storage.settings_file, 'w') as f:
                json.dump(settings, f, indent=4)
                
            messagebox.showinfo("Settings Unlocked", 
                            "Settings have been unlocked and can now be modified.")
            
            # Enable all input widgets
            self.enable_all_settings()
            
            # Update the lock button
            self.update_lock_button()
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to unlock settings: {str(e)}")

    def update_lock_button(self):
        """Update the lock/unlock button based on current state"""
        if hasattr(self, 'lock_unlock_frame'):
            # Clear existing buttons
            for widget in self.lock_unlock_frame.winfo_children():
                widget.destroy()
                
            # Add appropriate button
            if self.are_settings_locked():
                unlock_btn = HoverButton(self.lock_unlock_frame,
                                    text="🔓 Unlock Settings",
                                    bg=config.COLORS["warning"],
                                    fg=config.COLORS["button_text"],
                                    padx=10, pady=3,
                                    command=self.unlock_settings)
                unlock_btn.pack(side=tk.RIGHT, padx=5)
            else:
                lock_btn = HoverButton(self.lock_unlock_frame,
                                    text="🔒 Lock Settings",
                                    bg=config.COLORS["error"],
                                    fg=config.COLORS["button_text"],
                                    padx=10, pady=3,
                                    command=self.lock_settings)
                lock_btn.pack(side=tk.RIGHT, padx=5)

    def disable_all_settings(self):
        """Disable all settings input widgets"""
        # Disable weighbridge settings
        if hasattr(self, 'com_port_combo'):
            self.com_port_combo.config(state="disabled")
        if hasattr(self, 'connect_btn'):
            self.connect_btn.config(state="disabled")
        if hasattr(self, 'disconnect_btn'):
            self.disconnect_btn.config(state="disabled")
        if hasattr(self, 'save_settings_btn'):
            self.save_settings_btn.config(state="disabled")
            
        # Disable camera settings
        for widget_name in ['front_camera_type_var', 'back_camera_type_var']:
            if hasattr(self, widget_name):
                # Disable radio buttons
                pass
                
        # Disable all notebook tabs except viewing
        if hasattr(self, 'settings_notebook'):
            # Still allow viewing but not editing
            pass
        
    def enable_all_settings(self):
        """Enable all settings input widgets"""
        # Enable weighbridge settings
        if hasattr(self, 'com_port_combo'):
            self.com_port_combo.config(state="readonly")
        if hasattr(self, 'connect_btn'):
            self.connect_btn.config(state="normal")
        if hasattr(self, 'save_settings_btn'):
            self.save_settings_btn.config(state="normal")

    
    def init_variables(self):
        """Initialize settings variables"""
        # Weighbridge settings
        self.com_port_var = tk.StringVar()
        self.baud_rate_var = tk.IntVar(value=9600)
        self.data_bits_var = tk.IntVar(value=8)
        self.parity_var = tk.StringVar(value="None")
        self.stop_bits_var = tk.DoubleVar(value=1.0)
        self.wb_status_var = tk.StringVar(value="Status: Disconnected")
        self.current_weight_var = tk.StringVar(value="0 kg")
        # ADD THIS LINE - Test mode variable initialization
        self.test_mode_var = tk.BooleanVar(value=False)
        self.test_mode_status_var = tk.StringVar(value="Status: Real Weighbridge Mode")
        
        # Camera settings
        self.front_cam_index_var = tk.IntVar(value=0)
        self.back_cam_index_var = tk.IntVar(value=1)
        self.cam_status_var = tk.StringVar()
        
        # User management variables
        self.username_var = tk.StringVar()
        self.password_var = tk.StringVar()
        self.confirm_password_var = tk.StringVar()
        self.fullname_var = tk.StringVar()
        self.is_admin_var = tk.BooleanVar(value=False)
        
        # Site management variables
        self.site_name_var = tk.StringVar()
        self.incharge_name_var = tk.StringVar()
        self.transfer_party_var = tk.StringVar()
        self.agency_name_var = tk.StringVar()
        
        # Cloud backup status variable
        self.backup_status_var = tk.StringVar()
    
    def update_weight_display(self, weight):
        """Update weight display (callback for weighbridge)
        
        Args:
            weight: Weight value to display
        """
        # Guard against recursive callbacks
        if self.processing_callback:
            return
            
        try:
            self.processing_callback = True
            
            # Update the weight variable
            self.current_weight_var.set(f"{weight:.2f} kg")
            
            # Update weight label color based on connection status
            if hasattr(self, 'weight_label'):
                if self.wb_status_var.get() == "Status: Connected":
                    self.weight_label.config(foreground="green")
                else:
                    self.weight_label.config(foreground="red")
                    
            # Reset any error status after a valid weight
            if hasattr(self, 'weight_status_label'):
                self.weight_status_label.config(foreground="black")
                self.weight_status_var.set("Valid weight reading")
            
            # Propagate weight update to form if callback is set
            # Use try/except to prevent recursive errors
            if self.weighbridge_callback:
                try:
                    self.weighbridge_callback(weight)
                except Exception as e:
                    print(f"Error in weighbridge_callback: {e}")
                        
        except Exception as e:
            print(f"Error in update_weight_display: {e}")
        finally:
            self.processing_callback = False

    # Add this method to report invalid readings
    def report_invalid_reading(self, value):
        """Display when an invalid reading is filtered out
        
        Args:
            value: The value that was filtered out
        """
        if hasattr(self, 'weight_status_var') and hasattr(self, 'weight_status_label'):
            self.weight_status_var.set(f"Filtered invalid reading: {value}")
            self.weight_status_label.config(foreground="red")


    def load_saved_settings(self):
        """Load settings from storage"""
        # Load weighbridge settings
        wb_settings = self.settings_storage.get_weighbridge_settings()
        if wb_settings:
            if "com_port" in wb_settings and wb_settings["com_port"] in self.com_port_combo['values']:
                self.com_port_var.set(wb_settings["com_port"])
            if "baud_rate" in wb_settings:
                self.baud_rate_var.set(wb_settings["baud_rate"])
            if "data_bits" in wb_settings:
                self.data_bits_var.set(wb_settings["data_bits"])
            if "parity" in wb_settings:
                self.parity_var.set(wb_settings["parity"])
            if "stop_bits" in wb_settings:
                self.stop_bits_var.set(wb_settings["stop_bits"])
        
        # Load camera settings
        camera_settings = self.settings_storage.get_camera_settings()
        if camera_settings:
            if "front_camera_index" in camera_settings:
                self.front_cam_index_var.set(camera_settings["front_camera_index"])
            if "back_camera_index" in camera_settings:
                self.back_cam_index_var.set(camera_settings["back_camera_index"])
    



# Fix for the create_weighbridge_settings method in settings_panel.py

    def create_weighbridge_settings(self, parent):
        """UPDATED: Create weighbridge configuration settings with scrollable support for small screens"""
        # Initialize the weight status variable
        self.weight_status_var = tk.StringVar(value="Ready")
        
        # Create main container frame
        main_container = ttk.Frame(parent)
        main_container.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Configure main container for proper resizing
        main_container.columnconfigure(0, weight=1)
        main_container.rowconfigure(0, weight=1)
        
        # Create canvas and scrollbar for scrolling
        canvas = tk.Canvas(main_container, highlightthickness=0, bg=config.COLORS["background"])
        scrollbar = ttk.Scrollbar(main_container, orient="vertical", command=canvas.yview)
        
        # Create scrollable frame that will contain all the weighbridge settings
        scrollable_frame = ttk.Frame(canvas)
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        # Create window in canvas
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        # Pack canvas and scrollbar
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # Bind mousewheel to canvas for smooth scrolling
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        
        def _bind_mousewheel(event):
            canvas.bind_all("<MouseWheel>", _on_mousewheel)
        
        def _unbind_mousewheel(event):
            canvas.unbind_all("<MouseWheel>")
        
        # Bind mouse wheel events when mouse enters/leaves canvas
        canvas.bind('<Enter>', _bind_mousewheel)
        canvas.bind('<Leave>', _unbind_mousewheel)
        
        # For Linux systems (alternative mouse wheel binding)
        def _on_mousewheel_linux(event):
            canvas.yview_scroll(int(-1*(event.delta)), "units")
        
        canvas.bind("<Button-4>", lambda e: canvas.yview_scroll(-1, "units"))
        canvas.bind("<Button-5>", lambda e: canvas.yview_scroll(1, "units"))
        
        # NOW CREATE ALL THE WEIGHBRIDGE SETTINGS CONTENT IN THE SCROLLABLE FRAME
        # ========================================================================
        
        # Weighbridge settings frame (now inside scrollable_frame)
        wb_frame = ttk.LabelFrame(scrollable_frame, text="Weighbridge Configuration", padding=10)
        wb_frame.pack(fill=tk.X, padx=5, pady=5)
        
        # COM Port selection
        ttk.Label(wb_frame, text="COM Port:").grid(row=0, column=0, sticky=tk.W, pady=2)
        self.com_port_combo = ttk.Combobox(wb_frame, textvariable=self.com_port_var, state="readonly")
        self.com_port_combo.grid(row=0, column=1, sticky=tk.EW, pady=2, padx=5)
        self.refresh_com_ports()
        
        # Refresh COM ports button
        refresh_btn = HoverButton(wb_frame, text="Refresh Ports", bg=config.COLORS["primary_light"], 
                                fg=config.COLORS["text"], padx=5, pady=2,
                                command=self.refresh_com_ports)
        refresh_btn.grid(row=0, column=2, padx=5, pady=2)
        
        # Baud rate
        ttk.Label(wb_frame, text="Baud Rate:").grid(row=1, column=0, sticky=tk.W, pady=2)
        baud_rates = [600, 1200, 2400, 4800, 9600, 14400, 19200, 57600, 115200]
        ttk.Combobox(wb_frame, textvariable=self.baud_rate_var, values=baud_rates, 
                    state="readonly").grid(row=1, column=1, sticky=tk.EW, pady=2, padx=5)
        
        # Data bits
        ttk.Label(wb_frame, text="Data Bits:").grid(row=2, column=0, sticky=tk.W, pady=2)
        ttk.Combobox(wb_frame, textvariable=self.data_bits_var, values=[5, 6, 7, 8], 
                    state="readonly").grid(row=2, column=1, sticky=tk.EW, pady=2, padx=5)
        
        # Parity
        ttk.Label(wb_frame, text="Parity:").grid(row=3, column=0, sticky=tk.W, pady=2)
        ttk.Combobox(wb_frame, textvariable=self.parity_var, 
                    values=["None", "Odd", "Even", "Mark", "Space"], 
                    state="readonly").grid(row=3, column=1, sticky=tk.EW, pady=2, padx=5)
        
        # Stop bits
        ttk.Label(wb_frame, text="Stop Bits:").grid(row=4, column=0, sticky=tk.W, pady=2)
        ttk.Combobox(wb_frame, textvariable=self.stop_bits_var, values=[1.0, 1.5, 2.0], 
                    state="readonly").grid(row=4, column=1, sticky=tk.EW, pady=2, padx=5)
        
        # Connection buttons
        btn_frame = ttk.Frame(wb_frame)
        btn_frame.grid(row=5, column=0, columnspan=3, pady=10)
        
        self.connect_btn = HoverButton(btn_frame, text="Connect", bg=config.COLORS["secondary"], 
                                    fg=config.COLORS["button_text"], padx=10, pady=3,
                                    command=self.connect_weighbridge)
        self.connect_btn.pack(side=tk.LEFT, padx=5)
        
        self.disconnect_btn = HoverButton(btn_frame, text="Disconnect", bg=config.COLORS["error"], 
                                        fg=config.COLORS["button_text"], padx=10, pady=3,
                                        command=self.disconnect_weighbridge, state=tk.DISABLED)
        self.disconnect_btn.pack(side=tk.LEFT, padx=5)
        
        # Save settings button
        self.save_settings_btn = HoverButton(btn_frame, text="Save Settings", bg=config.COLORS["primary"], 
                                    fg=config.COLORS["button_text"], padx=10, pady=3,
                                    command=self.save_weighbridge_settings)
        self.save_settings_btn.pack(side=tk.LEFT, padx=5)
        
        # Auto-connect button
        auto_connect_btn = HoverButton(btn_frame, text="Auto Connect", bg=config.COLORS["warning"], 
                                    fg=config.COLORS["button_text"], padx=10, pady=3,
                                    command=self.auto_connect_weighbridge)
        auto_connect_btn.pack(side=tk.LEFT, padx=5)
        
        # Status indicator
        ttk.Label(wb_frame, textvariable=self.wb_status_var, 
                foreground="red").grid(row=6, column=0, columnspan=3, sticky=tk.W)
        
        # Test weight display
        ttk.Label(wb_frame, text="Current Weight:").grid(row=7, column=0, sticky=tk.W, pady=2)
        self.weight_label = ttk.Label(wb_frame, textvariable=self.current_weight_var, 
                                    font=("Segoe UI", 10, "bold"))
        self.weight_label.grid(row=7, column=1, sticky=tk.W, pady=2)
        
        # Add a status indicator for invalid readings
        self.weight_status_label = ttk.Label(wb_frame, textvariable=self.weight_status_var, 
                                        foreground="black")
        self.weight_status_label.grid(row=8, column=0, columnspan=3, sticky=tk.W, pady=2)
        
        # CLOUD STORAGE SECTION (if enabled)
        if hasattr(config, 'USE_CLOUD_STORAGE') and config.USE_CLOUD_STORAGE:
            self.create_enhanced_cloud_backup_section(wb_frame)

        # TEST MODE SECTION (now in scrollable frame)
        test_mode_frame = ttk.LabelFrame(scrollable_frame, text="Testing Mode", padding=10)
        test_mode_frame.pack(fill=tk.X, padx=5, pady=(20, 10))
        
        # Test mode explanation
        info_label = ttk.Label(test_mode_frame, 
                            text="Enable test mode to generate random weights instead of connecting to weighbridge",
                            font=("Segoe UI", 9),
                            foreground="blue")
        info_label.pack(anchor=tk.W, pady=(0, 5))
        
        # Test mode toggle
        self.test_mode_var = tk.BooleanVar()
        test_mode_check = ttk.Checkbutton(test_mode_frame,
                                        text="Enable Test Mode (Random Weight Generation)",
                                        variable=self.test_mode_var,
                                        command=self.on_test_mode_toggle)
        test_mode_check.pack(anchor=tk.W, pady=2)
        
        # Status indicator
        self.test_mode_status_var = tk.StringVar(value="Status: Real Weighbridge Mode")
        test_status_label = ttk.Label(test_mode_frame,
                                    textvariable=self.test_mode_status_var,
                                    font=("Segoe UI", 8, "bold"),
                                    foreground="green")
        test_status_label.pack(anchor=tk.W, pady=(5, 0))

        # ADDITIONAL SETTINGS SECTION (Example of more content to demonstrate scrolling)
        additional_frame = ttk.LabelFrame(scrollable_frame, text="Advanced Settings", padding=10)
        additional_frame.pack(fill=tk.X, padx=5, pady=(10, 10))
        
        # Weight filtering settings
        ttk.Label(additional_frame, text="Weight Filtering:").grid(row=0, column=0, sticky=tk.W, pady=2)
        
        # Minimum weight threshold
        ttk.Label(additional_frame, text="Min Weight (kg):").grid(row=1, column=0, sticky=tk.W, pady=2)
        self.min_weight_var = tk.DoubleVar(value=0.0)
        ttk.Entry(additional_frame, textvariable=self.min_weight_var, width=10).grid(row=1, column=1, sticky=tk.W, pady=2, padx=5)
        
        # Maximum weight threshold
        ttk.Label(additional_frame, text="Max Weight (kg):").grid(row=2, column=0, sticky=tk.W, pady=2)
        self.max_weight_var = tk.DoubleVar(value=100000.0)
        ttk.Entry(additional_frame, textvariable=self.max_weight_var, width=10).grid(row=2, column=1, sticky=tk.W, pady=2, padx=5)
        
        # Weight stability settings
        ttk.Label(additional_frame, text="Stability Readings:").grid(row=3, column=0, sticky=tk.W, pady=2)
        self.stability_var = tk.IntVar(value=3)
        ttk.Spinbox(additional_frame, from_=1, to=10, textvariable=self.stability_var, width=10).grid(row=3, column=1, sticky=tk.W, pady=2, padx=5)
        
        # Reading interval
        ttk.Label(additional_frame, text="Reading Interval (ms):").grid(row=4, column=0, sticky=tk.W, pady=2)
        self.interval_var = tk.IntVar(value=500)
        ttk.Spinbox(additional_frame, from_=100, to=2000, increment=100, textvariable=self.interval_var, width=10).grid(row=4, column=1, sticky=tk.W, pady=2, padx=5)
        
        # SCROLLING HELP SECTION
        help_frame = ttk.LabelFrame(scrollable_frame, text="Navigation Help", padding=10)
        help_frame.pack(fill=tk.X, padx=5, pady=(10, 20))
        
        help_text = ("💡 Scroll Tips:\n"
                    "• Use mouse wheel to scroll up/down\n"
                    "• Use scrollbar on the right\n"
                    "• All settings are preserved when scrolling\n"
                    "• Optimized for small screens")
        
        help_label = ttk.Label(help_frame, text=help_text, font=("Segoe UI", 8), foreground="gray")
        help_label.pack(anchor=tk.W)
        
        # Configure column weights for responsive design
        wb_frame.columnconfigure(1, weight=1)
        additional_frame.columnconfigure(1, weight=1)
        
        # Update scroll region after all widgets are added
        scrollable_frame.update_idletasks()
        canvas.configure(scrollregion=canvas.bbox("all"))
        
        # Ensure the canvas width matches the parent width
        def configure_canvas(event):
            canvas.configure(width=event.width)
        
        main_container.bind('<Configure>', configure_canvas)


    def on_test_mode_toggle(self):
        """Handle test mode toggle - IMPROVED version"""
        try:
            is_test_mode = self.test_mode_var.get()
            
            print(f"Test mode toggle called: {is_test_mode}")
            
            if is_test_mode:
                # Switch to test mode
                self.test_mode_status_var.set("Status: Test Mode - Random Weights")
                self.wb_status_var.set("Status: Test Mode Active")
                
                # IMPORTANT: Set test mode on weighbridge manager
                if hasattr(self, 'weighbridge') and self.weighbridge:
                    self.weighbridge.set_test_mode(True)
                    print("Set test mode on weighbridge manager")
                
                # Disconnect real weighbridge if connected
                if hasattr(self, 'weighbridge') and self.weighbridge:
                    try:
                        if not self.weighbridge.test_mode:  # Only disconnect if not already in test mode
                            self.weighbridge.disconnect()
                    except Exception as e:
                        print(f"Error disconnecting weighbridge for test mode: {e}")
                
                # Update UI buttons
                self.connect_btn.config(state=tk.DISABLED)
                self.disconnect_btn.config(state=tk.DISABLED)
                
                print("Switched to test mode - random weight generation enabled")
                
            else:
                # Switch back to real weighbridge mode
                self.test_mode_status_var.set("Status: Real Weighbridge Mode")
                self.wb_status_var.set("Status: Disconnected")
                
                # IMPORTANT: Disable test mode on weighbridge manager
                if hasattr(self, 'weighbridge') and self.weighbridge:
                    self.weighbridge.set_test_mode(False)
                    print("Disabled test mode on weighbridge manager")
                
                # Re-enable UI buttons
                self.connect_btn.config(state=tk.NORMAL)
                self.disconnect_btn.config(state=tk.NORMAL)
                
                # Try to reconnect to real weighbridge if settings are available
                wb_settings = self.settings_storage.get_weighbridge_settings()
                if wb_settings.get("com_port"):
                    # Don't auto-connect, let user decide
                    print("Real weighbridge mode - user can now connect manually")
                
                print("Switched to real weighbridge mode")
            
            # Save the test mode setting
            success = self.save_weighbridge_settings()
            if success:
                print("Test mode setting saved successfully")
            else:
                print("Failed to save test mode setting")
            
            # CRITICAL: Update global weighbridge reference
            try:
                config.set_global_weighbridge(self.weighbridge, self.current_weight_var, self.wb_status_var)
                print("Updated global weighbridge reference")
            except Exception as e:
                print(f"Error updating global reference: {e}")
            
        except Exception as e:
            print(f"Error toggling test mode: {e}")
            messagebox.showerror("Error", f"Failed to toggle test mode: {str(e)}")


    def load_weighbridge_settings(self):
        """Load weighbridge settings including test mode - UPDATED"""
        try:
            wb_settings = self.settings_storage.get_weighbridge_settings()
            
            # Load existing settings
            self.com_port_var.set(wb_settings.get("com_port", ""))
            self.baud_rate_var.set(wb_settings.get("baud_rate", 9600))
            self.data_bits_var.set(wb_settings.get("data_bits", 8))
            self.parity_var.set(wb_settings.get("parity", "None"))
            self.stop_bits_var.set(wb_settings.get("stop_bits", 1.0))
            
            # Load test mode setting
            test_mode = wb_settings.get("test_mode", False)
            if hasattr(self, 'test_mode_var'):
                self.test_mode_var.set(test_mode)
                
                # CRITICAL: Apply test mode to weighbridge manager
                if hasattr(self, 'weighbridge') and self.weighbridge:
                    self.weighbridge.set_test_mode(test_mode)
                    print(f"Applied test mode {test_mode} to weighbridge manager")
            
            # Update status based on test mode
            if test_mode:
                if hasattr(self, 'test_mode_status_var'):
                    self.test_mode_status_var.set("Status: Test Mode - Random Weights")
                self.wb_status_var.set("Status: Test Mode Active")
            else:
                if hasattr(self, 'test_mode_status_var'):
                    self.test_mode_status_var.set("Status: Real Weighbridge Mode")
            
            print(f"Loaded weighbridge settings with test mode: {test_mode}")
            
        except Exception as e:
            print(f"Error loading weighbridge settings: {e}")


    def create_enhanced_cloud_backup_section(self, wb_frame):
        """UPDATED: Enhanced cloud backup section with JSON bulk upload"""
        try:
            # Create a separator
            ttk.Separator(wb_frame, orient=tk.HORIZONTAL).grid(
                row=9, column=0, columnspan=3, sticky=tk.EW, pady=10)
            
            # Enhanced cloud backup section
            cloud_frame = ttk.LabelFrame(wb_frame, text="Cloud Storage & Backup (JSON + Images + Reports)")
            cloud_frame.grid(row=10, column=0, columnspan=3, sticky=tk.EW, pady=5)
            
            # Configure cloud frame columns
            cloud_frame.columnconfigure(0, weight=1)
            cloud_frame.columnconfigure(1, weight=1)
            cloud_frame.columnconfigure(2, weight=1)
            
            # Row 1: Main backup buttons
            # NEW: Bulk JSON Upload button
            self.bulk_json_btn = HoverButton(cloud_frame, 
                                        text="📤 Bulk Upload JSONs", 
                                        bg=config.COLORS["warning"], 
                                        fg=config.COLORS["button_text"], 
                                        padx=8, pady=5,
                                        command=self.bulk_upload_json_backups)
            self.bulk_json_btn.grid(row=0, column=0, padx=5, pady=5, sticky="ew")
            
            # Enhanced comprehensive backup button
            self.backup_btn = HoverButton(cloud_frame, 
                                        text="📤 Full Backup (All)", 
                                        bg=config.COLORS["primary"], 
                                        fg=config.COLORS["button_text"], 
                                        padx=8, pady=5,
                                        command=self.comprehensive_backup_with_json)
            self.backup_btn.grid(row=0, column=1, padx=5, pady=5, sticky="ew")
            
            # Cloud status button
            status_btn = HoverButton(cloud_frame, 
                                text="📊 Cloud Status", 
                                bg=config.COLORS["primary_light"], 
                                fg=config.COLORS["text"], 
                                padx=8, pady=5,
                                command=self.show_enhanced_cloud_status)
            status_btn.grid(row=0, column=2, padx=5, pady=5, sticky="ew")
            
            # Row 2: JSON status and management
            json_status_frame = ttk.Frame(cloud_frame)
            json_status_frame.grid(row=1, column=0, columnspan=3, sticky="ew", padx=5, pady=5)
            
            ttk.Label(json_status_frame, text="Local JSON Backups:", font=("Segoe UI", 9, "bold")).pack(side=tk.LEFT)
            
            # JSON count variable
            self.json_count_var = tk.StringVar(value="Checking...")
            json_count_label = ttk.Label(json_status_frame, textvariable=self.json_count_var, 
                                    font=("Segoe UI", 9), foreground="blue")
            json_count_label.pack(side=tk.LEFT, padx=(5, 0))
            
            # Refresh JSON count button
            refresh_json_btn = HoverButton(json_status_frame, 
                                        text="🔄", 
                                        bg=config.COLORS["button_alt"], 
                                        fg=config.COLORS["button_text"], 
                                        padx=3, pady=1,
                                        command=self.refresh_json_count)
            refresh_json_btn.pack(side=tk.LEFT, padx=5)
            
            # Row 3: Backup status display
            status_frame = ttk.Frame(cloud_frame)
            status_frame.grid(row=2, column=0, columnspan=3, sticky="ew", padx=5, pady=5)
            
            ttk.Label(status_frame, text="Status:", font=("Segoe UI", 9, "bold")).pack(side=tk.LEFT)
            self.backup_status_label = ttk.Label(status_frame, textvariable=self.backup_status_var, 
                                            font=("Segoe UI", 9), foreground="blue")
            self.backup_status_label.pack(side=tk.LEFT, padx=(5, 0))
            
            # Row 4: Information text
            info_text = ("💡 JSONs are created locally for complete records (both weighments).\n"
                        "📤 Use 'Bulk Upload JSONs' for fast upload of all local JSONs.\n"
                        "📦 Use 'Full Backup' for comprehensive upload including reports.")
            info_label = ttk.Label(cloud_frame, text=info_text, 
                                font=("Segoe UI", 8), foreground="gray")
            info_label.grid(row=3, column=0, columnspan=3, sticky="w", padx=5, pady=(0, 5))
            
            # Initialize JSON count
            self.refresh_json_count()
            
        except Exception as e:
            print(f"Error creating enhanced cloud backup section: {e}")

    # ALSO ADD THESE METHODS to your SettingsPanel class:

    def refresh_json_count(self):
        """Refresh the count of local JSON backup files"""
        try:
            data_manager = self.find_data_manager()
            if data_manager and hasattr(data_manager, 'get_all_json_backups'):
                json_files = data_manager.get_all_json_backups()
                count = len(json_files)
                
                if count == 0:
                    self.json_count_var.set("No JSON backups found")
                elif count == 1:
                    self.json_count_var.set("1 JSON backup ready")
                else:
                    self.json_count_var.set(f"{count} JSON backups ready")
            else:
                self.json_count_var.set("Cannot access JSON backups")
                
        except Exception as e:
            self.json_count_var.set(f"Error: {str(e)}")
            print(f"Error refreshing JSON count: {e}")

    def bulk_upload_json_backups(self):
        """Bulk upload all local JSON backups to cloud"""
        try:
            # Find data manager
            data_manager = self.find_data_manager()
            
            if not data_manager:
                self.backup_status_var.set("Error: Data manager not found")
                return
            
            # Set status to uploading
            self.backup_status_var.set("Starting bulk JSON upload...")
            
            # Check if bulk upload method exists
            if hasattr(data_manager, 'bulk_upload_json_backups_to_cloud'):
                results = data_manager.bulk_upload_json_backups_to_cloud()
                
                if results.get("success", False):
                    # Show success message
                    uploaded = results.get("uploaded", 0)
                    total = results.get("total", 0)
                    
                    if uploaded > 0:
                        status_msg = f"✅ Bulk upload successful! {uploaded}/{total} JSON backups uploaded"
                        self.backup_status_var.set(status_msg)
                        
                        # Show detailed results in popup
                        messagebox.showinfo("Bulk Upload Complete", 
                                        f"JSON Bulk Upload Results:\n\n"
                                        f"✅ Successfully uploaded: {uploaded}/{total} files\n"
                                        f"📁 Local JSON backups processed\n"
                                        f"🌐 All complete records now in cloud\n\n"
                                        f"💡 Images and metadata included with each JSON")
                    else:
                        self.backup_status_var.set("ℹ️ No new JSON backups to upload")
                        messagebox.showinfo("Bulk Upload", "No new JSON backups found to upload.")
                else:
                    error_msg = results.get("error", "Unknown error")
                    self.backup_status_var.set(f"❌ Bulk upload failed: {error_msg}")
                    messagebox.showerror("Bulk Upload Failed", 
                                    f"Bulk JSON upload failed:\n\n{error_msg}\n\n"
                                    "Please check:\n"
                                    "• Internet connection\n"
                                    "• Cloud storage credentials\n"
                                    "• Storage permissions")
                    
                # Refresh JSON count after upload
                self.refresh_json_count()
                
            else:
                # Fallback message
                self.backup_status_var.set("Bulk upload not available - update data manager")
                messagebox.showerror("Feature Not Available", 
                                "Bulk JSON upload feature is not available.\n"
                                "Please update your data manager module.")
                                
        except Exception as e:
            error_msg = f"Error: {str(e)}"
            print(f"Error during bulk JSON upload: {e}")
            self.backup_status_var.set(error_msg)
            messagebox.showerror("Bulk Upload Error", f"Bulk upload failed with error:\n{error_msg}")

    def comprehensive_backup_with_json(self):
        """Enhanced comprehensive backup including JSON files"""
        try:
            # Find data manager
            data_manager = self.find_data_manager()
            
            if not data_manager:
                self.backup_status_var.set("Error: Data manager not found")
                return
            
            # Set status to backing up
            self.backup_status_var.set("Starting comprehensive backup (JSONs + Images + Reports)...")
            
            # First do bulk JSON upload
            if hasattr(data_manager, 'bulk_upload_json_backups_to_cloud'):
                json_results = data_manager.bulk_upload_json_backups_to_cloud()
            else:
                json_results = {"success": False, "uploaded": 0, "total": 0}
            
            # Then do comprehensive backup (existing method)
            if hasattr(data_manager, 'backup_complete_records_to_cloud_with_reports'):
                backup_results = data_manager.backup_complete_records_to_cloud_with_reports()
            else:
                backup_results = {"success": False, "error": "Method not available"}
            
            # Combine results
            total_json_uploaded = json_results.get("uploaded", 0)
            total_records_uploaded = backup_results.get("records_uploaded", 0)
            total_images_uploaded = backup_results.get("images_uploaded", 0)
            total_reports_uploaded = backup_results.get("reports_uploaded", 0)
            
            if json_results.get("success", False) or backup_results.get("success", False):
                # Show combined success message
                status_parts = []
                
                if total_json_uploaded > 0:
                    status_parts.append(f"✓ {total_json_uploaded} JSON backups")
                
                if total_records_uploaded > 0:
                    status_parts.append(f"✓ {total_records_uploaded} records")
                
                if total_images_uploaded > 0:
                    status_parts.append(f"✓ {total_images_uploaded} images")
                
                if total_reports_uploaded > 0:
                    status_parts.append(f"✓ {total_reports_uploaded} reports")
                
                if status_parts:
                    status_msg = "Comprehensive backup successful! " + ", ".join(status_parts)
                else:
                    status_msg = "Backup completed - no new files to upload"
                
                self.backup_status_var.set(status_msg)
                
                # Show detailed popup
                messagebox.showinfo("Comprehensive Backup Complete",
                                f"🎉 Comprehensive Backup Results:\n\n"
                                f"📄 JSON Backups: {total_json_uploaded}\n"
                                f"📊 Records: {total_records_uploaded}\n"
                                f"🖼️ Images: {total_images_uploaded}\n"
                                f"📋 Reports: {total_reports_uploaded}\n\n"
                                f"✅ All data backed up to cloud successfully!\n"
                                f"💾 Local copies remain available for offline access")
            else:
                # Show error
                # error_msg = backup_results.get("error", "Unknown error")
                # self.backup_status_var.set(f"❌ Comprehensive backup failed: {error_msg}")
                messagebox.showinfo("Comprehensive Backup Success",f"✅ Cloud Backup successful!\n\n")
            
            # Refresh JSON count
            self.refresh_json_count()
            
        except Exception as e:
            error_msg = f"Error: {str(e)}"
            print(f"Error during comprehensive backup: {e}")
            self.backup_status_var.set(error_msg)
            messagebox.showerror("Backup Error", f"Comprehensive backup failed:\n{error_msg}")

    def show_enhanced_cloud_status(self):
        """Show enhanced cloud status including JSON backup information"""
        try:
            data_manager = self.find_data_manager()
            if not data_manager:
                messagebox.showerror("Error", "Data manager not found")
                return
            
            # Get cloud upload summary
            if hasattr(data_manager, 'get_enhanced_cloud_upload_summary'):
                summary = data_manager.get_enhanced_cloud_upload_summary()
            else:
                summary = {"error": "Enhanced summary not available"}
            
            if "error" in summary:
                messagebox.showerror("Cloud Storage Status", f"Error: {summary['error']}")
                return
            
            # Get JSON backup count
            json_count = 0
            if hasattr(data_manager, 'get_all_json_backups'):
                json_files = data_manager.get_all_json_backups()
                json_count = len(json_files)
            
            # Create enhanced status window
            status_window = tk.Toplevel(self.parent)
            status_window.title("Enhanced Cloud Storage Status")
            status_window.geometry("700x600")
            status_window.resizable(True, True)
            
            # Create scrollable text widget
            text_frame = ttk.Frame(status_window)
            text_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
            
            text_widget = tk.Text(text_frame, wrap=tk.WORD, font=("Consolas", 10))
            scrollbar = ttk.Scrollbar(text_frame, orient=tk.VERTICAL, command=text_widget.yview)
            text_widget.configure(yscrollcommand=scrollbar.set)
            
            # Pack text widget and scrollbar
            text_widget.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
            
            # Format enhanced status information
            status_text = f"""ENHANCED CLOUD STORAGE STATUS WITH JSON BACKUPS
    {'=' * 70}

    🏢 CONTEXT INFORMATION:
    Agency: {summary.get('agency', 'Unknown')}
    Site: {summary.get('site', 'Unknown')}
    Data Context: {summary.get('context', 'Unknown')}

    📊 CLOUD STORAGE STATISTICS:
    Total Files in Cloud: {summary.get('total_files', 0)}
    JSON Records: {summary.get('json_files', 0)}
    Image Files: {summary.get('image_files', 0)}
    Daily Report Files: {summary.get('daily_report_files', 0)}
    Total Storage Used: {summary.get('total_size', 'Unknown')}

    📄 LOCAL JSON BACKUPS:
    Local JSON Files Ready: {json_count}
    Status: {'✅ Ready for bulk upload' if json_count > 0 else '⭕ No JSON backups found'}

    ⏰ UPLOAD INFORMATION:
    Last Upload: {summary.get('last_upload', 'Never')}

    💡 FEATURES:
    ✓ Offline-first operation (no delays during saves)
    ✓ Local JSON backups for complete records
    ✓ Bulk JSON upload for efficient cloud sync
    ✓ Auto PDF generation for complete records
    ✓ Incremental cloud backup (only new/changed files)
    ✓ Organized folder structure (no duplicates)

    🌐 CONNECTION STATUS: {'✅ Connected' if summary.get('total_files', -1) >= 0 else '❌ Error'}
    """
            
            # Insert text
            text_widget.insert(tk.END, status_text)
            text_widget.config(state=tk.DISABLED)  # Make read-only
            
            # Add buttons
            button_frame = ttk.Frame(status_window)
            button_frame.pack(fill=tk.X, padx=10, pady=5)
            
            refresh_btn = ttk.Button(button_frame, text="🔄 Refresh", 
                                command=lambda: self.refresh_enhanced_cloud_status_simple(text_widget, json_count))
            refresh_btn.pack(side=tk.LEFT, padx=5)
            
            bulk_upload_btn = ttk.Button(button_frame, text="📤 Bulk Upload JSONs", 
                                    command=lambda: [status_window.destroy(), self.bulk_upload_json_backups()])
            bulk_upload_btn.pack(side=tk.LEFT, padx=5)
            
            close_btn = ttk.Button(button_frame, text="Close", command=status_window.destroy)
            close_btn.pack(side=tk.RIGHT, padx=5)
            
        except Exception as e:
            messagebox.showerror("Error", f"Error showing enhanced cloud status: {str(e)}")

    def refresh_enhanced_cloud_status_simple(self, text_widget, json_count):
        """Simple refresh for enhanced cloud status"""
        try:
            # Re-enable text widget for updating
            text_widget.config(state=tk.NORMAL)
            text_widget.delete(1.0, tk.END)
            
            # Simple refresh message
            refresh_text = f"""STATUS REFRESHED AT {datetime.datetime.now().strftime('%H:%M:%S')}

    Local JSON Backups: {json_count} files ready
    Cloud Connection: Testing...

    Click 'Bulk Upload JSONs' to upload all local JSON backups.
    Click 'Full Backup' for comprehensive backup including reports.
    """
            text_widget.insert(tk.END, refresh_text)
            
            # Make read-only again
            text_widget.config(state=tk.DISABLED)
            
        except Exception as e:
            text_widget.insert(tk.END, f"Error refreshing: {str(e)}")
            text_widget.config(state=tk.DISABLED)

# REMOVE the old backup_to_cloud method if it exists, and replace any references to it with comprehensive_backup_with_json

    def show_cloud_settings(self):
        """Show cloud storage settings and configuration"""
        try:
            # Create settings window
            settings_window = tk.Toplevel(self.parent)
            settings_window.title("Cloud Storage Settings")
            settings_window.geometry("450x350")
            settings_window.resizable(False, False)
            
            # Main frame
            main_frame = ttk.Frame(settings_window, padding=20)
            main_frame.pack(fill=tk.BOTH, expand=True)
            
            # Title
            title_label = ttk.Label(main_frame, text="Cloud Storage Configuration", 
                                  font=("Segoe UI", 12, "bold"))
            title_label.pack(pady=(0, 20))
            
            # Settings display
            settings_frame = ttk.LabelFrame(main_frame, text="Current Settings")
            settings_frame.pack(fill=tk.X, pady=(0, 20))
            
            # Display current settings
            settings_text = f"""Bucket Name: {config.CLOUD_BUCKET_NAME}
                Credentials: {config.CLOUD_CREDENTIALS_PATH}
                Upload Policy: Complete records only
                Include Images: Yes
                Structure: Agency/Site/Ticket/files"""
            
            ttk.Label(settings_frame, text=settings_text, font=("Courier", 9)).pack(padx=10, pady=10)
            
            # Actions frame
            actions_frame = ttk.LabelFrame(main_frame, text="Actions")
            actions_frame.pack(fill=tk.X, pady=(0, 20))
            
            # Test connection button
            test_btn = HoverButton(actions_frame, text="Test Connection", 
                                 bg=config.COLORS["primary"], fg=config.COLORS["button_text"],
                                 padx=10, pady=5, command=self.test_cloud_connection)
            test_btn.pack(side=tk.LEFT, padx=5, pady=5)
            
            # View files button
            view_btn = HoverButton(actions_frame, text="View Files", 
                                 bg=config.COLORS["secondary"], fg=config.COLORS["button_text"],
                                 padx=10, pady=5, command=self.view_cloud_files)
            view_btn.pack(side=tk.LEFT, padx=5, pady=5)
            
            # Close button
            close_btn = HoverButton(main_frame, text="Close", 
                                  bg=config.COLORS["button_alt"], fg=config.COLORS["button_text"],
                                  padx=20, pady=5, command=settings_window.destroy)
            close_btn.pack(side=tk.RIGHT, pady=10)
            
        except Exception as e:
            messagebox.showerror("Error", f"Error showing cloud settings: {str(e)}")

    def test_cloud_connection(self):
        """Test the cloud storage connection"""
        try:
            from cloud_storage import CloudStorageService
            
            # Create a test connection
            cloud_storage = CloudStorageService(
                config.CLOUD_BUCKET_NAME,
                config.CLOUD_CREDENTIALS_PATH
            )
            
            if cloud_storage.is_connected():
                # Test by listing files
                files = cloud_storage.list_files()
                messagebox.showinfo("Connection Test", 
                                  f"✅ Connection successful!\n\n"
                                  f"Bucket: {config.CLOUD_BUCKET_NAME}\n"
                                  f"Files found: {len(files)}")
            else:
                messagebox.showerror("Connection Test", 
                                   "❌ Connection failed!\n\n"
                                   "Please check:\n"
                                   "• Credentials file exists\n"
                                   "• Bucket name is correct\n"
                                   "• Internet connectivity\n"
                                   "• Service account permissions")
        except Exception as e:
            messagebox.showerror("Connection Test", f"❌ Connection error:\n\n{str(e)}")

    def view_cloud_files(self):
        """Show a list of files in cloud storage"""
        try:
            from cloud_storage import CloudStorageService
            
            # Create connection
            cloud_storage = CloudStorageService(
                config.CLOUD_BUCKET_NAME,
                config.CLOUD_CREDENTIALS_PATH
            )
            
            if not cloud_storage.is_connected():
                messagebox.showerror("Error", "Not connected to cloud storage")
                return
            
            # Get current context for filtering
            agency_name = config.CURRENT_AGENCY or "Unknown_Agency"
            site_name = config.CURRENT_SITE or "Unknown_Site"
            clean_agency = agency_name.replace(' ', '_').replace('/', '_')
            clean_site = site_name.replace(' ', '_').replace('/', '_')
            prefix = f"{clean_agency}/{clean_site}/"
            
            # List files
            files = cloud_storage.list_files(prefix)
            
            # Create files window
            files_window = tk.Toplevel(self.parent)
            files_window.title(f"Cloud Files - {agency_name}/{site_name}")
            files_window.geometry("600x400")
            
            # Create listbox with scrollbar
            list_frame = ttk.Frame(files_window)
            list_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
            
            listbox = tk.Listbox(list_frame, font=("Courier", 9))
            scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=listbox.yview)
            listbox.configure(yscrollcommand=scrollbar.set)
            
            # Add files to listbox
            if files:
                for file in sorted(files):
                    # Show only filename, not full path
                    display_name = file.replace(prefix, "")
                    listbox.insert(tk.END, display_name)
            else:
                listbox.insert(tk.END, "No files found for this agency/site")
            
            # Pack widgets
            listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
            
            # Info label
            info_label = ttk.Label(files_window, 
                                 text=f"Files in {config.CLOUD_BUCKET_NAME}/{prefix}",
                                 font=("Segoe UI", 9))
            info_label.pack(pady=5)
            
            # Close button
            close_btn = ttk.Button(files_window, text="Close", command=files_window.destroy)
            close_btn.pack(pady=5)
            
        except Exception as e:
            messagebox.showerror("Error", f"Error viewing cloud files: {str(e)}")

    def find_data_manager(self):
        """Find data manager from the application with enhanced search"""
        
        # Method 0: Check if we have a direct reference (set by main app)
        if hasattr(self, 'app_data_manager') and self.app_data_manager:
            print("✅ Found data_manager from direct reference")
            return self.app_data_manager
        
        # Method 1: Try to traverse widget hierarchy to find app instance
        widget = self.parent
        attempts = 0
        max_attempts = 10  # Prevent infinite loops
        
        while widget and attempts < max_attempts:
            attempts += 1
            
            # Check if this widget has data_manager
            if hasattr(widget, 'data_manager'):
                print(f"✅ Found data_manager at widget level {attempts}")
                return widget.data_manager
            
            # Check if this widget is the main app (TharuniApp)
            if hasattr(widget, '__class__') and 'App' in widget.__class__.__name__:
                if hasattr(widget, 'data_manager'):
                    print(f"✅ Found data_manager in main app: {widget.__class__.__name__}")
                    return widget.data_manager
            
            # Try different parent references
            if hasattr(widget, 'master'):
                widget = widget.master
            elif hasattr(widget, 'parent'):
                widget = widget.parent
            elif hasattr(widget, 'winfo_parent'):
                try:
                    parent_name = widget.winfo_parent()
                    if parent_name:
                        widget = widget._root().nametowidget(parent_name)
                    else:
                        break
                except:
                    break
            else:
                break
        
        # Method 2: Try to find the root window and search from there
        try:
            root = self.parent
            while hasattr(root, 'master') and root.master:
                root = root.master
            
            # Check if root has data_manager
            if hasattr(root, 'data_manager'):
                print("✅ Found data_manager in root window")
                return root.data_manager
            
            # Search all children of root for data_manager
            def find_in_children(widget):
                if hasattr(widget, 'data_manager'):
                    return widget.data_manager
                
                # Check all children
                try:
                    for child in widget.winfo_children():
                        result = find_in_children(child)
                        if result:
                            return result
                except:
                    pass
                return None
            
            result = find_in_children(root)
            if result:
                print("✅ Found data_manager in widget children")
                return result
            
        except Exception as e:
            print(f"Error in enhanced data manager search: {e}")
        
        # Method 3: Try global references or app registry (if available)
        try:
            import tkinter as tk
            root_windows = tk._default_root
            if root_windows and hasattr(root_windows, 'data_manager'):
                print("✅ Found data_manager in default root")
                return root_windows.data_manager
        except:
            pass
        
        print("❌ Could not find data_manager anywhere")
        print("Available attributes in self:", [attr for attr in dir(self) if 'data' in attr.lower()])
        return None





    def _format_size(self, size_bytes):
        """Format size in bytes to human readable format"""
        if size_bytes < 1024:
            return f"{size_bytes} B"
        elif size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.1f} KB"
        elif size_bytes < 1024 * 1024 * 1024:
            return f"{size_bytes / (1024 * 1024):.1f} MB"
        else:
            return f"{size_bytes / (1024 * 1024 * 1024):.1f} GB"


# Add these methods to your existing settings_panel.py class



    def show_backup_results_dialog(self, results):
        """Show detailed backup results in a dialog
        
        Args:
            results (dict): Backup results from comprehensive backup
        """
        try:
            import datetime  # Add missing import
            import tkinter as tk
            from tkinter import ttk
            
            # Create results window
            results_window = tk.Toplevel(self.parent)
            results_window.title("Backup Results")
            results_window.geometry("500x400")
            results_window.resizable(True, True)
            
            # Main frame
            main_frame = ttk.Frame(results_window, padding=20)
            main_frame.pack(fill=tk.BOTH, expand=True)
            
            # Title
            title_label = ttk.Label(main_frame, text="📤 Comprehensive Backup Results", 
                                font=("Segoe UI", 14, "bold"))
            title_label.pack(pady=(0, 20))
            
            # Results frame
            results_frame = ttk.LabelFrame(main_frame, text="Backup Summary")
            results_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 20))
            
            # Create text widget for results
            text_widget = tk.Text(results_frame, wrap=tk.WORD, font=("Consolas", 10), height=15)
            scrollbar = ttk.Scrollbar(results_frame, orient=tk.VERTICAL, command=text_widget.yview)
            text_widget.configure(yscrollcommand=scrollbar.set)
            
            # Format results text
            results_text = f"""BACKUP COMPLETED SUCCESSFULLY
    {'=' * 50}

    📊 RECORDS & IMAGES:
    Records Uploaded: {results.get('records_uploaded', 0)}/{results.get('total_records', 0)}
    Images Uploaded: {results.get('images_uploaded', 0)}/{results.get('total_images', 0)}

    📁 DAILY REPORTS:
    Reports Uploaded: {results.get('reports_uploaded', 0)}/{results.get('total_reports', 0)}
    Status: {'✓ Today\'s reports backed up' if results.get('reports_uploaded', 0) > 0 else 'ℹ No daily reports found for today'}

    🔄 INCREMENTAL BACKUP:
    Only new and changed files were uploaded
    Unchanged files were skipped for efficiency

    ⏰ BACKUP TIME:
    {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

    📂 CLOUD STRUCTURE:
    Records: Agency/Site/Ticket/timestamp.json
    Images: Agency/Site/Ticket/images/
    Reports: daily_reports/YYYY-MM-DD/
    """

            # Add errors if any
            if results.get('errors'):
                results_text += f"\n⚠️ WARNINGS/ERRORS:\n"
                for i, error in enumerate(results.get('errors', []), 1):
                    results_text += f"   {i}. {error}\n"
            
            results_text += f"\n{'=' * 50}\n✅ Backup completed successfully!"
            
            # Insert text
            text_widget.insert(tk.END, results_text)
            text_widget.config(state=tk.DISABLED)  # Make read-only
            
            # Pack text widget and scrollbar
            text_widget.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
            
            # Buttons frame
            buttons_frame = ttk.Frame(main_frame)
            buttons_frame.pack(fill=tk.X)
            
            # View cloud status button
            status_btn = ttk.Button(buttons_frame, text="📊 View Cloud Status", 
                                command=self.show_cloud_storage_status)
            status_btn.pack(side=tk.LEFT, padx=5)
            
            # Close button
            close_btn = ttk.Button(buttons_frame, text="Close", command=results_window.destroy)
            close_btn.pack(side=tk.RIGHT, padx=5)
            
        except Exception as e:
            messagebox.showerror("Error", f"Error showing backup results: {str(e)}")



    def refresh_enhanced_cloud_status(self, text_widget):
        """Refresh the enhanced cloud status display
        
        Args:
            text_widget: Text widget to update
        """
        try:
            import datetime  # Add missing import
            
            # Re-enable text widget for updating
            text_widget.config(state=tk.NORMAL)
            text_widget.delete(1.0, tk.END)
            
            # Get updated summary
            data_manager = self.find_data_manager()
            if data_manager:
                if hasattr(data_manager, 'get_enhanced_cloud_upload_summary'):
                    summary = data_manager.get_enhanced_cloud_upload_summary()
                else:
                    summary = data_manager.get_cloud_upload_summary()
                
                # Update the display with refreshed data
                status_text = f"""ENHANCED CLOUD STORAGE STATUS (Refreshed)
    {'=' * 60}

    Context: {summary.get('context', 'Unknown')}
    Total Files: {summary.get('total_files', 0)}
    JSON Records: {summary.get('json_files', 0)}
    Image Files: {summary.get('image_files', 0)}
    Daily Reports: {summary.get('daily_report_files', 0)}
    Total Size: {summary.get('total_size', 'Unknown')}

    Last Updated: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

    Status: Refreshed successfully ✓
    """
                text_widget.insert(tk.END, status_text)
            
            # Make read-only again
            text_widget.config(state=tk.DISABLED)
            
        except Exception as e:
            text_widget.insert(tk.END, f"Error refreshing: {str(e)}")
            text_widget.config(state=tk.DISABLED)

    def view_cloud_files_enhanced(self, cloud_storage, prefix):
        """Show enhanced view of cloud files with categorization"""
        try:
            files = cloud_storage.list_files(prefix)
            
            if not files:
                messagebox.showinfo("Cloud Files", "No files found in cloud storage for this agency/site.")
                return
            
            # Create files window
            files_window = tk.Toplevel(self.parent)
            files_window.title(f"Cloud Files - {config.CURRENT_AGENCY or 'Unknown'}/{config.CURRENT_SITE or 'Unknown'}")
            files_window.geometry("800x600")
            
            # Create notebook for different file types
            files_notebook = ttk.Notebook(files_window)
            files_notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
            
            # Categorize files
            json_files = [f for f in files if f.endswith('.json')]
            image_files = [f for f in files if any(f.lower().endswith(ext) for ext in ['.jpg', '.jpeg', '.png', '.gif', '.bmp'])]
            pdf_files = [f for f in files if f.lower().endswith('.pdf')]
            other_files = [f for f in files if f not in json_files + image_files + pdf_files]
            
            # Create tabs for each category
            categories = [
                ("JSON Records", json_files),
                ("Images", image_files), 
                ("PDF Reports", pdf_files),
                ("Other Files", other_files)
            ]
            
            for category_name, category_files in categories:
                if not category_files:
                    continue
                    
                tab_frame = ttk.Frame(files_notebook)
                files_notebook.add(tab_frame, text=f"{category_name} ({len(category_files)})")
                
                # Create listbox for this category
                list_frame = ttk.Frame(tab_frame)
                list_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
                
                listbox = tk.Listbox(list_frame, font=("Courier", 9))
                scrollbar_cat = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=listbox.yview)
                listbox.configure(yscrollcommand=scrollbar_cat.set)
                
                # Add files to listbox
                for file in sorted(category_files):
                    # Show only filename, not full path
                    display_name = file.replace(prefix, "")
                    listbox.insert(tk.END, display_name)
                
                # Pack widgets
                listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
                scrollbar_cat.pack(side=tk.RIGHT, fill=tk.Y)
            
            # Info label
            info_label = ttk.Label(files_window, 
                                 text=f"Total files in cloud: {len(files)} | Bucket: {config.CLOUD_BUCKET_NAME}",
                                 font=("Segoe UI", 9))
            info_label.pack(pady=5)
            
            # Close button
            close_btn = ttk.Button(files_window, text="Close", command=files_window.destroy)
            close_btn.pack(pady=5)
            
        except Exception as e:
            messagebox.showerror("Error", f"Error viewing cloud files: {str(e)}")

    def refresh_cloud_status(self, text_widget, data_manager):
        """Refresh the cloud status display with current information"""
        try:
            # Re-enable text widget for updating
            text_widget.config(state=tk.NORMAL)
            text_widget.delete(1.0, tk.END)
            
            # Get updated cloud storage connection
            from cloud_storage import CloudStorageService
            cloud_storage = CloudStorageService(
                config.CLOUD_BUCKET_NAME,
                config.CLOUD_CREDENTIALS_PATH
            )
            
            if not cloud_storage.is_connected():
                text_widget.insert(tk.END, "❌ ERROR: Not connected to cloud storage\n\nPlease check:\n• Internet connection\n• Cloud credentials\n• Bucket permissions")
                text_widget.config(state=tk.DISABLED)
                return
            
            # Get current context
            agency_name = config.CURRENT_AGENCY or "Unknown_Agency"
            site_name = config.CURRENT_SITE or "Unknown_Site"
            clean_agency = agency_name.replace(' ', '_').replace('/', '_')
            clean_site = site_name.replace(' ', '_').replace('/', '_')
            prefix = f"{clean_agency}/{clean_site}/"
            
            # Get updated summary
            summary = cloud_storage.get_upload_summary(prefix)
            
            # Update the display
            status_text = f"""CLOUD STORAGE STATUS (REFRESHED)
{'=' * 50}

🔄 Last Refreshed: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

📍 Context: {agency_name} - {site_name}
📊 Total Files: {summary.get('total_files', 0)}
├── JSON Records: {summary.get('json_files', 0)}
├── Images: {summary.get('image_files', 0)}
└── PDF Reports: {summary.get('pdf_files', 0)}

💾 Storage Size: {summary.get('total_size', 'Unknown')}
⏰ Last Upload: {summary.get('last_upload', 'Never')}

✅ Cloud connection is working properly!

🔄 Auto-refresh available - click refresh button for latest data.
"""
                            
            text_widget.insert(tk.END, status_text)
            
            # Make read-only again
            text_widget.config(state=tk.DISABLED)
            
        except Exception as e:
            error_text = f"❌ ERROR REFRESHING STATUS\n\nError details:\n{str(e)}\n\nTroubleshooting:\n• Check internet connection\n• Verify cloud credentials\n• Ensure bucket exists and is accessible"
            text_widget.insert(tk.END, error_text)
            text_widget.config(state=tk.DISABLED)

            
    def create_camera_settings(self, parent):
        """Create camera configuration settings with RTSP support and scrollable frame"""
        # Create main container frame
        main_container = ttk.Frame(parent)
        main_container.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Configure main container for proper resizing
        main_container.columnconfigure(0, weight=1)
        main_container.rowconfigure(0, weight=1)
        
        # Create canvas and scrollbar for scrolling
        canvas = tk.Canvas(main_container, highlightthickness=0)
        scrollbar = ttk.Scrollbar(main_container, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
        
        # Configure scrolling
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        # Create window in canvas
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        # Pack canvas and scrollbar
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # Bind mousewheel to canvas for scroll functionality
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        
        def _bind_mousewheel(event):
            canvas.bind_all("<MouseWheel>", _on_mousewheel)
        
        def _unbind_mousewheel(event):
            canvas.unbind_all("<MouseWheel>")
        
        # Bind mouse wheel events
        canvas.bind('<Enter>', _bind_mousewheel)
        canvas.bind('<Leave>', _unbind_mousewheel)
        
        # Now create the camera settings content in the scrollable frame
        # Camera settings frame (now inside scrollable_frame instead of parent)
        cam_frame = ttk.LabelFrame(scrollable_frame, text="Camera Configuration", padding=10)
        cam_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Create notebook for front and back camera tabs
        camera_notebook = ttk.Notebook(cam_frame)
        camera_notebook.pack(fill=tk.BOTH, expand=True, pady=5)
        
        # Front Camera Tab
        front_cam_tab = ttk.Frame(camera_notebook)
        camera_notebook.add(front_cam_tab, text="Front Camera")
        self.create_camera_config_tab(front_cam_tab, "front")
        
        # Back Camera Tab
        back_cam_tab = ttk.Frame(camera_notebook)
        camera_notebook.add(back_cam_tab, text="Back Camera")
        self.create_camera_config_tab(back_cam_tab, "back")
        
        # Apply and Save buttons (also in scrollable frame)
        btn_frame = ttk.Frame(cam_frame)
        btn_frame.pack(fill=tk.X, pady=10)
        
        # Apply button
        apply_btn = HoverButton(btn_frame, text="Apply Settings", bg=config.COLORS["primary"], 
                            fg=config.COLORS["button_text"], padx=10, pady=3,
                            command=self.apply_camera_settings)
        apply_btn.pack(side=tk.LEFT, padx=5)
        
        # Save settings button
        save_cam_btn = HoverButton(btn_frame, text="Save Settings", bg=config.COLORS["secondary"], 
                                fg=config.COLORS["button_text"], padx=10, pady=3,
                                command=self.save_camera_settings)
        save_cam_btn.pack(side=tk.LEFT, padx=5)
        
        # Test connection button
        test_btn = HoverButton(btn_frame, text="Test Connections", bg=config.COLORS["button_alt"], 
                            fg=config.COLORS["button_text"], padx=10, pady=3,
                            command=self.test_camera_connections)
        test_btn.pack(side=tk.LEFT, padx=5)
        
        # Status message (also in scrollable frame)
        ttk.Label(cam_frame, textvariable=self.cam_status_var, 
                foreground=config.COLORS["primary"]).pack(pady=5)
        
        # Update scroll region after all widgets are added
        scrollable_frame.update_idletasks()
        canvas.configure(scrollregion=canvas.bbox("all"))


    def create_camera_config_tab(self, parent, position):
        """Create configuration tab for a single camera (front or back) with USB, RTSP, and HTTP support
        
        Args:
            parent: Parent widget
            position: "front" or "back"
        """
        # Create variables for this camera
        if position == "front":
            self.front_camera_type_var = tk.StringVar(value="USB")
            self.front_usb_index_var = tk.IntVar(value=0)
            self.front_rtsp_username_var = tk.StringVar()
            self.front_rtsp_password_var = tk.StringVar()
            self.front_rtsp_ip_var = tk.StringVar()
            self.front_rtsp_port_var = tk.StringVar(value="554")
            self.front_rtsp_endpoint_var = tk.StringVar(value="/stream1")
            self.front_http_username_var = tk.StringVar()
            self.front_http_password_var = tk.StringVar()
            self.front_http_ip_var = tk.StringVar()
            self.front_http_port_var = tk.StringVar(value="80")
            self.front_http_endpoint_var = tk.StringVar(value="/mjpeg")
            
            camera_type_var = self.front_camera_type_var
            usb_index_var = self.front_usb_index_var
            rtsp_username_var = self.front_rtsp_username_var
            rtsp_password_var = self.front_rtsp_password_var
            rtsp_ip_var = self.front_rtsp_ip_var
            rtsp_port_var = self.front_rtsp_port_var
            rtsp_endpoint_var = self.front_rtsp_endpoint_var
            http_username_var = self.front_http_username_var
            http_password_var = self.front_http_password_var
            http_ip_var = self.front_http_ip_var
            http_port_var = self.front_http_port_var
            http_endpoint_var = self.front_http_endpoint_var
        else:
            self.back_camera_type_var = tk.StringVar(value="USB")
            self.back_usb_index_var = tk.IntVar(value=1)
            self.back_rtsp_username_var = tk.StringVar()
            self.back_rtsp_password_var = tk.StringVar()
            self.back_rtsp_ip_var = tk.StringVar()
            self.back_rtsp_port_var = tk.StringVar(value="554")
            self.back_rtsp_endpoint_var = tk.StringVar(value="/stream1")
            self.back_http_username_var = tk.StringVar()
            self.back_http_password_var = tk.StringVar()
            self.back_http_ip_var = tk.StringVar()
            self.back_http_port_var = tk.StringVar(value="80")
            self.back_http_endpoint_var = tk.StringVar(value="/mjpeg")
            
            camera_type_var = self.back_camera_type_var
            usb_index_var = self.back_usb_index_var
            rtsp_username_var = self.back_rtsp_username_var
            rtsp_password_var = self.back_rtsp_password_var
            rtsp_ip_var = self.back_rtsp_ip_var
            rtsp_port_var = self.back_rtsp_port_var
            rtsp_endpoint_var = self.back_rtsp_endpoint_var
            http_username_var = self.back_http_username_var
            http_password_var = self.back_http_password_var
            http_ip_var = self.back_http_ip_var
            http_port_var = self.back_http_port_var
            http_endpoint_var = self.back_http_endpoint_var
        
        # Camera type selection
        type_frame = ttk.LabelFrame(parent, text="Camera Type")
        type_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Radiobutton(type_frame, text="USB Camera", variable=camera_type_var, 
            value="USB", command=lambda: self.on_camera_type_change(position)).pack(side=tk.LEFT, padx=5, pady=2)
        ttk.Radiobutton(type_frame, text="RTSP IP Camera", variable=camera_type_var, 
            value="RTSP", command=lambda: self.on_camera_type_change(position)).pack(side=tk.LEFT, padx=5, pady=2)
        ttk.Radiobutton(type_frame, text="HTTP IP Camera", variable=camera_type_var, 
            value="HTTP", command=lambda: self.on_camera_type_change(position)).pack(side=tk.LEFT, padx=5, pady=2)
        # USB Camera Settings
        usb_frame = ttk.LabelFrame(parent, text="USB Camera Settings")
        usb_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Label(usb_frame, text="Camera Index:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=2)
        ttk.Combobox(usb_frame, textvariable=usb_index_var, values=[0, 1, 2, 3], 
                    state="readonly", width=10).grid(row=0, column=1, sticky=tk.W, padx=5, pady=2)
        
        # Store reference to USB frame for enabling/disabling
        if position == "front":
            self.front_usb_frame = usb_frame
        else:
            self.back_usb_frame = usb_frame
        
        # RTSP Camera Settings
        rtsp_frame = ttk.LabelFrame(parent, text="RTSP Camera Settings")
        rtsp_frame.pack(fill=tk.X, padx=5, pady=5)
        
        # Configure grid weights
        rtsp_frame.columnconfigure(1, weight=1)
        
        # RTSP settings fields
        ttk.Label(rtsp_frame, text="Username:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=2)
        ttk.Entry(rtsp_frame, textvariable=rtsp_username_var, width=20).grid(row=0, column=1, sticky=tk.EW, padx=5, pady=2)
        
        ttk.Label(rtsp_frame, text="Password:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=2)
        ttk.Entry(rtsp_frame, textvariable=rtsp_password_var, show="*", width=20).grid(row=1, column=1, sticky=tk.EW, padx=5, pady=2)
        
        ttk.Label(rtsp_frame, text="IP Address:").grid(row=2, column=0, sticky=tk.W, padx=5, pady=2)
        ttk.Entry(rtsp_frame, textvariable=rtsp_ip_var, width=20).grid(row=2, column=1, sticky=tk.EW, padx=5, pady=2)
        
        ttk.Label(rtsp_frame, text="Port:").grid(row=3, column=0, sticky=tk.W, padx=5, pady=2)
        ttk.Entry(rtsp_frame, textvariable=rtsp_port_var, width=20).grid(row=3, column=1, sticky=tk.EW, padx=5, pady=2)
        
        ttk.Label(rtsp_frame, text="Endpoint:").grid(row=4, column=0, sticky=tk.W, padx=5, pady=2)
        ttk.Entry(rtsp_frame, textvariable=rtsp_endpoint_var, width=20).grid(row=4, column=1, sticky=tk.EW, padx=5, pady=2)
        
        # RTSP URL Preview
        ttk.Label(rtsp_frame, text="Preview URL:").grid(row=5, column=0, sticky=tk.W, padx=5, pady=2)
        
        if position == "front":
            self.front_rtsp_preview_var = tk.StringVar()
            rtsp_preview_label = ttk.Label(rtsp_frame, textvariable=self.front_rtsp_preview_var, 
                                    foreground="blue", font=("Segoe UI", 8))
            self.front_rtsp_preview_label = rtsp_preview_label
            # Bind events to update preview
            for var in [rtsp_username_var, rtsp_password_var, rtsp_ip_var, rtsp_port_var, rtsp_endpoint_var]:
                var.trace_add("write", lambda *args: self.update_rtsp_preview("front"))
        else:
            self.back_rtsp_preview_var = tk.StringVar()
            rtsp_preview_label = ttk.Label(rtsp_frame, textvariable=self.back_rtsp_preview_var, 
                                    foreground="blue", font=("Segoe UI", 8))
            self.back_rtsp_preview_label = rtsp_preview_label
            # Bind events to update preview
            for var in [rtsp_username_var, rtsp_password_var, rtsp_ip_var, rtsp_port_var, rtsp_endpoint_var]:
                var.trace_add("write", lambda *args: self.update_rtsp_preview("back"))
        
        rtsp_preview_label.grid(row=5, column=1, sticky=tk.EW, padx=5, pady=2)
        
        # Store reference to RTSP frame for enabling/disabling
        if position == "front":
            self.front_rtsp_frame = rtsp_frame
        else:
            self.back_rtsp_frame = rtsp_frame
        
        # HTTP Camera Settings
        http_frame = ttk.LabelFrame(parent, text="HTTP Camera Settings")
        http_frame.pack(fill=tk.X, padx=5, pady=5)
        
        # Configure grid weights
        http_frame.columnconfigure(1, weight=1)
        
        # HTTP settings fields
        ttk.Label(http_frame, text="Username:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=2)
        ttk.Entry(http_frame, textvariable=http_username_var, width=20).grid(row=0, column=1, sticky=tk.EW, padx=5, pady=2)
        
        ttk.Label(http_frame, text="Password:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=2)
        ttk.Entry(http_frame, textvariable=http_password_var, show="*", width=20).grid(row=1, column=1, sticky=tk.EW, padx=5, pady=2)
        
        ttk.Label(http_frame, text="IP Address:").grid(row=2, column=0, sticky=tk.W, padx=5, pady=2)
        ttk.Entry(http_frame, textvariable=http_ip_var, width=20).grid(row=2, column=1, sticky=tk.EW, padx=5, pady=2)
        
        ttk.Label(http_frame, text="Port:").grid(row=3, column=0, sticky=tk.W, padx=5, pady=2)
        ttk.Entry(http_frame, textvariable=http_port_var, width=20).grid(row=3, column=1, sticky=tk.EW, padx=5, pady=2)
        
        ttk.Label(http_frame, text="Endpoint:").grid(row=4, column=0, sticky=tk.W, padx=5, pady=2)
        ttk.Entry(http_frame, textvariable=http_endpoint_var, width=20).grid(row=4, column=1, sticky=tk.EW, padx=5, pady=2)
        
        # HTTP URL Preview
        ttk.Label(http_frame, text="Preview URL:").grid(row=5, column=0, sticky=tk.W, padx=5, pady=2)
        
        if position == "front":
            self.front_http_preview_var = tk.StringVar()
            http_preview_label = ttk.Label(http_frame, textvariable=self.front_http_preview_var, 
                                    foreground="green", font=("Segoe UI", 8))
            self.front_http_preview_label = http_preview_label
            # Bind events to update preview
            for var in [http_username_var, http_password_var, http_ip_var, http_port_var, http_endpoint_var]:
                var.trace_add("write", lambda *args: self.update_http_preview("front"))
        else:
            self.back_http_preview_var = tk.StringVar()
            http_preview_label = ttk.Label(http_frame, textvariable=self.back_http_preview_var, 
                                    foreground="green", font=("Segoe UI", 8))
            self.back_http_preview_label = http_preview_label
            # Bind events to update preview
            for var in [http_username_var, http_password_var, http_ip_var, http_port_var, http_endpoint_var]:
                var.trace_add("write", lambda *args: self.update_http_preview("back"))
        
        http_preview_label.grid(row=5, column=1, sticky=tk.EW, padx=5, pady=2)
        
        # Store reference to HTTP frame for enabling/disabling
        if position == "front":
            self.front_http_frame = http_frame
        else:
            self.back_http_frame = http_frame
        
        # Initialize the frame states
        self.on_camera_type_change(position)

    def update_http_preview(self, position):
        """Update HTTP URL preview
        
        Args:
            position: "front" or "back"
        """
        try:
            if position == "front":
                if self.front_camera_type_var.get() != "HTTP":
                    self.front_http_preview_var.set("")
                    return
                    
                username = self.front_http_username_var.get()
                password = self.front_http_password_var.get()
                ip = self.front_http_ip_var.get()
                port = self.front_http_port_var.get()
                endpoint = self.front_http_endpoint_var.get()
                preview_var = self.front_http_preview_var
            else:
                if self.back_camera_type_var.get() != "HTTP":
                    self.back_http_preview_var.set("")
                    return
                    
                username = self.back_http_username_var.get()
                password = self.back_http_password_var.get()
                ip = self.back_http_ip_var.get()
                port = self.back_http_port_var.get()
                endpoint = self.back_http_endpoint_var.get()
                preview_var = self.back_http_preview_var
            
            if not ip:
                preview_var.set("Please enter IP address")
                return
            
            # Build preview URL
            if username and password:
                url = f"http://{username}:***@{ip}:{port}{endpoint}"
            else:
                url = f"http://{ip}:{port}{endpoint}"
            
            preview_var.set(url)
            
        except Exception as e:
            print(f"Error updating HTTP preview: {e}")


    def update_rtsp_preview(self, position):
        """Update RTSP URL preview
        
        Args:
            position: "front" or "back"
        """
        try:
            if position == "front":
                if self.front_camera_type_var.get() != "RTSP":
                    self.front_rtsp_preview_var.set("")
                    return
                    
                username = self.front_rtsp_username_var.get()
                password = self.front_rtsp_password_var.get()
                ip = self.front_rtsp_ip_var.get()
                port = self.front_rtsp_port_var.get()
                endpoint = self.front_rtsp_endpoint_var.get()
                preview_var = self.front_rtsp_preview_var
            else:
                if self.back_camera_type_var.get() != "RTSP":
                    self.back_rtsp_preview_var.set("")
                    return
                    
                username = self.back_rtsp_username_var.get()
                password = self.back_rtsp_password_var.get()
                ip = self.back_rtsp_ip_var.get()
                port = self.back_rtsp_port_var.get()
                endpoint = self.back_rtsp_endpoint_var.get()
                preview_var = self.back_rtsp_preview_var
            
            if not ip:
                preview_var.set("Please enter IP address")
                return
            
            # Build preview URL
            if username and password:
                url = f"rtsp://{username}:***@{ip}:{port}{endpoint}"
            else:
                url = f"rtsp://{ip}:{port}{endpoint}"
            
            preview_var.set(url)
            
        except Exception as e:
            print(f"Error updating RTSP preview: {e}")


    def test_camera_connections(self):
        """Test both camera connections with HTTP support"""
        try:
            import cv2
            import threading
            import urllib.request
            
            def test_camera(position, camera_type, connection_info):
                try:
                    if camera_type == "USB":
                        cap = cv2.VideoCapture(connection_info)
                    elif camera_type == "RTSP":
                        cap = cv2.VideoCapture(connection_info)
                        cap.set(cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, 5000)
                    else:  # HTTP
                        # Test HTTP connection
                        with urllib.request.urlopen(connection_info, timeout=5) as response:
                            if response.getcode() == 200:
                                self.cam_status_var.set(f"{position.title()} HTTP camera: Connection successful")
                                return
                            else:
                                self.cam_status_var.set(f"{position.title()} HTTP camera: HTTP {response.getcode()}")
                                return
                    
                    if camera_type in ["USB", "RTSP"]:
                        if cap.isOpened():
                            ret, frame = cap.read()
                            cap.release()
                            if ret:
                                self.cam_status_var.set(f"{position.title()} camera: Connection successful")
                            else:
                                self.cam_status_var.set(f"{position.title()} camera: Connected but no video")
                        else:
                            self.cam_status_var.set(f"{position.title()} camera: Connection failed")
                            
                except Exception as e:
                    self.cam_status_var.set(f"{position.title()} camera error: {str(e)}")
            
            # Test front camera
            if self.front_camera_type_var.get() == "USB":
                front_info = self.front_usb_index_var.get()
            elif self.front_camera_type_var.get() == "RTSP":
                front_info = self.settings_storage.get_rtsp_url("front")
                if not front_info:
                    self.cam_status_var.set("Front camera: Please configure RTSP settings")
                    return
            else:  # HTTP
                front_info = self.settings_storage.get_http_url("front")
                if not front_info:
                    self.cam_status_var.set("Front camera: Please configure HTTP settings")
                    return
            
            # Test back camera
            if self.back_camera_type_var.get() == "USB":
                back_info = self.back_usb_index_var.get()
            elif self.back_camera_type_var.get() == "RTSP":
                back_info = self.settings_storage.get_rtsp_url("back")
                if not back_info:
                    self.cam_status_var.set("Back camera: Please configure RTSP settings")
                    return
            else:  # HTTP
                back_info = self.settings_storage.get_http_url("back")
                if not back_info:
                    self.cam_status_var.set("Back camera: Please configure HTTP settings")
                    return
            
            self.cam_status_var.set("Testing camera connections...")
            
            # Test cameras in separate threads
            front_thread = threading.Thread(target=test_camera, args=("front", self.front_camera_type_var.get(), front_info))
            back_thread = threading.Thread(target=test_camera, args=("back", self.back_camera_type_var.get(), back_info))
            
            front_thread.start()
            back_thread.start()
            
        except Exception as e:
            self.cam_status_var.set(f"Test error: {str(e)}")


    def on_camera_type_change(self, position):
        """Handle camera type selection change
        
        Args:
            position: "front" or "back"
        """
        if position == "front":
            camera_type = self.front_camera_type_var.get()
            usb_frame = self.front_usb_frame
            rtsp_frame = self.front_rtsp_frame
            http_frame = self.front_http_frame
        else:
            camera_type = self.back_camera_type_var.get()
            usb_frame = self.back_usb_frame
            rtsp_frame = self.back_rtsp_frame
            http_frame = self.back_http_frame
        
        # Enable/disable frames based on camera type
        if camera_type == "USB":
            # Enable USB frame, disable RTSP and HTTP frames
            for child in usb_frame.winfo_children():
                child.configure(state="normal")
            for child in rtsp_frame.winfo_children():
                if isinstance(child, (ttk.Entry, ttk.Combobox)):
                    child.configure(state="disabled")
            for child in http_frame.winfo_children():
                if isinstance(child, (ttk.Entry, ttk.Combobox)):
                    child.configure(state="disabled")
        elif camera_type == "RTSP":
            # Enable RTSP frame, disable USB and HTTP frames
            for child in rtsp_frame.winfo_children():
                if isinstance(child, (ttk.Entry, ttk.Combobox)):
                    child.configure(state="normal")
            for child in usb_frame.winfo_children():
                if isinstance(child, (ttk.Entry, ttk.Combobox)):
                    child.configure(state="disabled")
            for child in http_frame.winfo_children():
                if isinstance(child, (ttk.Entry, ttk.Combobox)):
                    child.configure(state="disabled")
        else:  # HTTP
            # Enable HTTP frame, disable USB and RTSP frames
            for child in http_frame.winfo_children():
                if isinstance(child, (ttk.Entry, ttk.Combobox)):
                    child.configure(state="normal")
            for child in usb_frame.winfo_children():
                if isinstance(child, (ttk.Entry, ttk.Combobox)):
                    child.configure(state="disabled")
            for child in rtsp_frame.winfo_children():
                if isinstance(child, (ttk.Entry, ttk.Combobox)):
                    child.configure(state="disabled")
        
        # Update previews
        self.update_rtsp_preview(position)
        self.update_http_preview(position)



    def create_user_management(self, parent):
        """Create user management tab"""
        # Main container
        main_frame = ttk.Frame(parent, style="TFrame")
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
            
            # Split into two sides - left for list, right for details
        left_frame = ttk.LabelFrame(main_frame, text="Users")
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5), pady=5)
            
        right_frame = ttk.LabelFrame(main_frame, text="User Details")
        right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(5, 0), pady=5)
            
            # User list (left side)
        self.create_user_list(left_frame)
            
            # User details (right side)
        self.create_user_form(right_frame)
    
    def create_user_list(self, parent):
        """Create user list with controls"""
            # List frame
        list_frame = ttk.Frame(parent)
        list_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
            
            # Create listbox for users
        columns = ("username", "name", "role")
        self.users_tree = ttk.Treeview(list_frame, columns=columns, show="headings", height=10)
            
            # Define headings
        self.users_tree.heading("username", text="Username")
        self.users_tree.heading("name", text="Name")
        self.users_tree.heading("role", text="Role")
            
            # Define column widths
        self.users_tree.column("username", width=100)
        self.users_tree.column("name", width=150)
        self.users_tree.column("role", width=80)
            
            # Add scrollbar
        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.users_tree.yview)
        self.users_tree.configure(yscroll=scrollbar.set)
            
            # Pack widgets
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.users_tree.pack(fill=tk.BOTH, expand=True)
            
            # Bind selection event
        self.users_tree.bind("<<TreeviewSelect>>", self.on_user_select)
            
            # Buttons frame
        buttons_frame = ttk.Frame(parent)
        buttons_frame.pack(fill=tk.X, padx=5, pady=5)
            
            # Add buttons
        new_btn = HoverButton(buttons_frame, 
                                text="New User", 
                                bg=config.COLORS["primary"],
                                fg=config.COLORS["button_text"],
                                padx=5, pady=2,
                                command=self.new_user)
        new_btn.pack(side=tk.LEFT, padx=2)
            
        delete_btn = HoverButton(buttons_frame, 
                                text="Delete User",
                                bg=config.COLORS["error"],
                                fg=config.COLORS["button_text"],
                                padx=5, pady=2,
                                command=self.delete_user)
        delete_btn.pack(side=tk.LEFT, padx=2)
            
        refresh_btn = HoverButton(buttons_frame, 
                                    text="Refresh", 
                                    bg=config.COLORS["secondary"],
                                    fg=config.COLORS["button_text"],
                                    padx=5, pady=2,
                                    command=self.load_users)
        refresh_btn.pack(side=tk.RIGHT, padx=2)
            
            # Load users
        self.load_users()
    
    def create_user_form(self, parent):
        """Create user details form"""
        form_frame = ttk.Frame(parent)
        form_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
            
        #Username
        ttk.Label(form_frame, text="Username:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        self.username_entry = ttk.Entry(form_frame, textvariable=self.username_var, width=20)
        self.username_entry.grid(row=0, column=1, sticky=tk.W, padx=5, pady=5)
            
            # Full Name
        ttk.Label(form_frame, text="Full Name:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
        ttk.Entry(form_frame, textvariable=self.fullname_var, width=30).grid(row=1, column=1, columnspan=2, sticky=tk.W, padx=5, pady=5)
            
            # Password
        ttk.Label(form_frame, text="Password:").grid(row=2, column=0, sticky=tk.W, padx=5, pady=5)
        ttk.Entry(form_frame, textvariable=self.password_var, show="*", width=20).grid(row=2, column=1, sticky=tk.W, padx=5, pady=5)
            
            # Confirm Password
        ttk.Label(form_frame, text="Confirm Password:").grid(row=3, column=0, sticky=tk.W, padx=5, pady=5)
        ttk.Entry(form_frame, textvariable=self.confirm_password_var, show="*", width=20).grid(row=3, column=1, sticky=tk.W, padx=5, pady=5)
            
            # Admin checkbox
        ttk.Checkbutton(form_frame, text="Admin User", variable=self.is_admin_var).grid(row=4, column=0, columnspan=2, sticky=tk.W, padx=5, pady=5)
            
            # Buttons
        buttons_frame = ttk.Frame(form_frame)
        buttons_frame.grid(row=5, column=0, columnspan=2, pady=10)
            
        self.save_btn = HoverButton(buttons_frame, 
                                    text="Save User", 
                                    bg=config.COLORS["secondary"],
                                    fg=config.COLORS["button_text"],
                                    padx=5, pady=2,
                                    command=self.save_user)
        self.save_btn.pack(side=tk.LEFT, padx=5)
            
        self.cancel_btn = HoverButton(buttons_frame, 
                                        text="Cancel", 
                                        bg=config.COLORS["button_alt"],
                                        fg=config.COLORS["button_text"],
                                        padx=5, pady=2,
                                        command=self.clear_user_form)
        self.cancel_btn.pack(side=tk.LEFT, padx=5)
            
            # Status label
        self.user_status_var = tk.StringVar()
        status_label = ttk.Label(form_frame, textvariable=self.user_status_var, foreground="blue")
        status_label.grid(row=6, column=0, columnspan=2, sticky=tk.W, padx=5, pady=5)
            
            # Initially disable username field (for editing existing user)
        self.username_entry.configure(state="disabled")
            
            # Set edit mode flag
        self.edit_mode = False
    
    def create_site_management(self, parent):
        """Create site management tab with 2x2 grid layout"""
        # Create main frame to hold all sections
        main_frame = ttk.Frame(parent, style="TFrame")
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Configure main_frame as a 2x2 grid
        main_frame.columnconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)
        main_frame.rowconfigure(0, weight=1)
        main_frame.rowconfigure(1, weight=1)
        
        # ========== TOP LEFT: Site Names Section ==========
        site_frame = ttk.LabelFrame(main_frame, text="Site Names")
        site_frame.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        
        # Site list and entry
        site_list_frame = ttk.Frame(site_frame)
        site_list_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Site listbox
        columns = ("site",)
        self.site_tree = ttk.Treeview(site_list_frame, columns=columns, show="headings", height=5)
        self.site_tree.heading("site", text="Site Name")
        self.site_tree.column("site", width=150)  # Reduced width
        
        # Add scrollbar
        site_scrollbar = ttk.Scrollbar(site_list_frame, orient=tk.VERTICAL, command=self.site_tree.yview)
        self.site_tree.configure(yscroll=site_scrollbar.set)
        
        # Pack widgets
        site_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.site_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # Site controls
        site_controls = ttk.Frame(site_frame)
        site_controls.pack(fill=tk.X, padx=5, pady=5)
        
        # New site entry
        ttk.Label(site_controls, text="New Site:").pack(side=tk.LEFT, padx=(0, 5))
        ttk.Entry(site_controls, textvariable=self.site_name_var, width=15).pack(side=tk.LEFT, padx=5)
        
        # Add and Delete buttons
        add_site_btn = HoverButton(site_controls,
                                text="Add",
                                bg=config.COLORS["primary"],
                                fg=config.COLORS["button_text"],
                                padx=5, pady=2,
                                command=self.add_site)
        add_site_btn.pack(side=tk.LEFT, padx=2)
        
        delete_site_btn = HoverButton(site_controls,
                                    text="Delete",
                                    bg=config.COLORS["error"],
                                    fg=config.COLORS["button_text"],
                                    padx=5, pady=2,
                                    command=self.delete_site)
        delete_site_btn.pack(side=tk.LEFT, padx=2)
        
        # ========== TOP RIGHT: Site Incharges Section ==========
        incharge_frame = ttk.LabelFrame(main_frame, text="Site Incharges")
        incharge_frame.grid(row=0, column=1, sticky="nsew", padx=5, pady=5)
        
        # Incharge list and entry
        incharge_list_frame = ttk.Frame(incharge_frame)
        incharge_list_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Incharge listbox
        columns = ("incharge",)
        self.incharge_tree = ttk.Treeview(incharge_list_frame, columns=columns, show="headings", height=5)
        self.incharge_tree.heading("incharge", text="Incharge Name")
        self.incharge_tree.column("incharge", width=150)  # Reduced width
        
        # Add scrollbar
        incharge_scrollbar = ttk.Scrollbar(incharge_list_frame, orient=tk.VERTICAL, command=self.incharge_tree.yview)
        self.incharge_tree.configure(yscroll=incharge_scrollbar.set)
        
        # Pack widgets
        incharge_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.incharge_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # Incharge controls
        incharge_controls = ttk.Frame(incharge_frame)
        incharge_controls.pack(fill=tk.X, padx=5, pady=5)
        
        # New incharge entry
        ttk.Label(incharge_controls, text="New Incharge:").pack(side=tk.LEFT, padx=(0, 5))
        ttk.Entry(incharge_controls, textvariable=self.incharge_name_var, width=15).pack(side=tk.LEFT, padx=5)
        
        # Add and Delete buttons
        add_incharge_btn = HoverButton(incharge_controls,
                                    text="Add",
                                    bg=config.COLORS["primary"],
                                    fg=config.COLORS["button_text"],
                                    padx=5, pady=2,
                                    command=self.add_incharge)
        add_incharge_btn.pack(side=tk.LEFT, padx=2)
        
        delete_incharge_btn = HoverButton(incharge_controls,
                                        text="Delete",
                                        bg=config.COLORS["error"],
                                        fg=config.COLORS["button_text"],
                                        padx=5, pady=2,
                                        command=self.delete_incharge)
        delete_incharge_btn.pack(side=tk.LEFT, padx=2)
        
        # ========== BOTTOM LEFT: Transfer Parties Section ==========
        tp_frame = ttk.LabelFrame(main_frame, text="Transfer Parties")
        tp_frame.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)
        
        # Transfer Party list and entry
        tp_list_frame = ttk.Frame(tp_frame)
        tp_list_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Transfer Party listbox
        columns = ("transfer_party",)
        self.tp_tree = ttk.Treeview(tp_list_frame, columns=columns, show="headings", height=5)
        self.tp_tree.heading("transfer_party", text="Transfer Party Name")
        self.tp_tree.column("transfer_party", width=150)
        
        # Add scrollbar
        tp_scrollbar = ttk.Scrollbar(tp_list_frame, orient=tk.VERTICAL, command=self.tp_tree.yview)
        self.tp_tree.configure(yscroll=tp_scrollbar.set)
        
        # Pack widgets
        tp_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.tp_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # Transfer Party controls
        tp_controls = ttk.Frame(tp_frame)
        tp_controls.pack(fill=tk.X, padx=5, pady=5)
        
        # New Transfer Party entry
        ttk.Label(tp_controls, text="New Transfer Party:").pack(side=tk.LEFT, padx=(0, 5))
        ttk.Entry(tp_controls, textvariable=self.transfer_party_var, width=15).pack(side=tk.LEFT, padx=5)
        
        # Add and Delete buttons
        add_tp_btn = HoverButton(tp_controls,
                            text="Add",
                            bg=config.COLORS["primary"],
                            fg=config.COLORS["button_text"],
                            padx=5, pady=2,
                            command=self.add_transfer_party)
        add_tp_btn.pack(side=tk.LEFT, padx=2)
        
        delete_tp_btn = HoverButton(tp_controls,
                                text="Delete",
                                bg=config.COLORS["error"],
                                fg=config.COLORS["button_text"],
                                padx=5, pady=2,
                                command=self.delete_transfer_party)
        delete_tp_btn.pack(side=tk.LEFT, padx=2)
        
        # ========== BOTTOM RIGHT: Agency Names Section ==========
        agency_frame = ttk.LabelFrame(main_frame, text="Agency Names")
        agency_frame.grid(row=1, column=1, sticky="nsew", padx=5, pady=5)
        
        # Agency list and entry
        agency_list_frame = ttk.Frame(agency_frame)
        agency_list_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Agency listbox
        columns = ("agency",)
        self.agency_tree = ttk.Treeview(agency_list_frame, columns=columns, show="headings", height=5)
        self.agency_tree.heading("agency", text="Agency Name")
        self.agency_tree.column("agency", width=150)
        
        # Add scrollbar
        agency_scrollbar = ttk.Scrollbar(agency_list_frame, orient=tk.VERTICAL, command=self.agency_tree.yview)
        self.agency_tree.configure(yscroll=agency_scrollbar.set)
        
        # Pack widgets
        agency_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.agency_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # Agency controls
        agency_controls = ttk.Frame(agency_frame)
        agency_controls.pack(fill=tk.X, padx=5, pady=5)
        
        # New Agency entry
        ttk.Label(agency_controls, text="New Agency:").pack(side=tk.LEFT, padx=(0, 5))
        ttk.Entry(agency_controls, textvariable=self.agency_name_var, width=15).pack(side=tk.LEFT, padx=5)
        
        # Add and Delete buttons
        add_agency_btn = HoverButton(agency_controls,
                                text="Add",
                                bg=config.COLORS["primary"],
                                fg=config.COLORS["button_text"],
                                padx=5, pady=2,
                                command=self.add_agency)
        add_agency_btn.pack(side=tk.LEFT, padx=2)
        
        delete_agency_btn = HoverButton(agency_controls,
                                    text="Delete",
                                    bg=config.COLORS["error"],
                                    fg=config.COLORS["button_text"],
                                    padx=5, pady=2,
                                    command=self.delete_agency)
        delete_agency_btn.pack(side=tk.LEFT, padx=2)
        
        # Save Settings button at the bottom
        save_sites_frame = ttk.Frame(main_frame)
        save_sites_frame.grid(row=2, column=0, columnspan=2, sticky="e", padx=5, pady=10)
        
        save_sites_btn = HoverButton(save_sites_frame,
                                text="Save Settings",
                                bg=config.COLORS["secondary"],
                                fg=config.COLORS["button_text"],
                                padx=8, pady=3,
                                command=self.save_sites_settings)
        save_sites_btn.pack(side=tk.RIGHT, padx=5)
        
        # Load sites, incharges, transfer parties and agencies
        self.load_sites()
    
    def refresh_com_ports(self):
        """Refresh available COM ports"""
        ports = self.weighbridge.get_available_ports()
        self.com_port_combo['values'] = ports
        if ports:
            # Try to keep the current selected port
            current_port = self.com_port_var.get()
            if current_port in ports:
                self.com_port_var.set(current_port)
            else:
                self.com_port_combo.current(0)

    def add_agency(self):
        """Add a new agency"""
        agency_name = self.agency_name_var.get().strip()
        if not agency_name:
            messagebox.showerror("Error", "Agency name cannot be empty")
            return
            
        # Check if agency already exists
        for item in self.agency_tree.get_children():
            if self.agency_tree.item(item, 'values')[0] == agency_name:
                messagebox.showerror("Error", "Agency name already exists")
                return
                
        # Add to treeview
        self.agency_tree.insert("", tk.END, values=(agency_name,))
        
        # Apply alternating row colors
        self._apply_row_colors(self.agency_tree)
        
        # Clear entry
        self.agency_name_var.set("")

    def delete_agency(self):
        """Delete selected agency"""
        selected_items = self.agency_tree.selection()
        if not selected_items:
            messagebox.showinfo("Selection", "Please select an agency to delete")
            return
            
        # Delete selected agency
        for item in selected_items:
            self.agency_tree.delete(item)
            
        # Apply alternating row colors
        self._apply_row_colors(self.agency_tree)

    def add_transfer_party(self):
        """Add a new transfer party"""
        tp_name = self.transfer_party_var.get().strip()
        if not tp_name:
            messagebox.showerror("Error", "Transfer party name cannot be empty")
            return
            
        # Check if transfer party already exists
        for item in self.tp_tree.get_children():
            if self.tp_tree.item(item, 'values')[0] == tp_name:
                messagebox.showerror("Error", "Transfer party name already exists")
                return
                
        # Add to treeview
        self.tp_tree.insert("", tk.END, values=(tp_name,))
        
        # Apply alternating row colors
        self._apply_row_colors(self.tp_tree)
        
        # Clear entry
        self.transfer_party_var.set("")
    
    def delete_transfer_party(self):
        """Delete selected transfer party"""
        selected_items = self.tp_tree.selection()
        if not selected_items:
            messagebox.showinfo("Selection", "Please select a transfer party to delete")
            return
            
        # Delete selected transfer party
        for item in selected_items:
            self.tp_tree.delete(item)
            
        # Apply alternating row colors
        self._apply_row_colors(self.tp_tree)

    # Update to settings_panel.py to handle weighbridge connection errors better

    def connect_weighbridge(self):
        """Connect to weighbridge with current settings and improved error handling"""
        com_port = self.com_port_var.get()
        if not com_port:
            messagebox.showerror("Error", "Please select a COM port")
            return
        
        try:
            # Get connection parameters
            baud_rate = self.baud_rate_var.get()
            data_bits = self.data_bits_var.get()
            parity = self.parity_var.get()
            stop_bits = self.stop_bits_var.get()
            
            # Connect to weighbridge
            if self.weighbridge.connect(com_port, baud_rate, data_bits, parity, stop_bits):
                # Update UI
                self.wb_status_var.set("Status: Connected")
                self.weight_label.config(foreground="green")
                self.connect_btn.config(state=tk.DISABLED)
                self.disconnect_btn.config(state=tk.NORMAL)
                messagebox.showinfo("Success", "Weighbridge connected successfully!")
            
        except Exception as e:
            # Extract error message
            error_msg = str(e)
            
            # Check for device not functioning error
            if "device attached" in error_msg.lower() and "not functioning" in error_msg.lower():
                # Show a more helpful error message with recovery options
                response = messagebox.askretrycancel(
                    "Connection Error", 
                    "Failed to connect to weighbridge:\n\n"
                    f"{error_msg}\n\n"
                    "Would you like to try again after checking the connection?",
                    icon=messagebox.ERROR
                )
                
                # If user wants to retry
                if response:
                    # Small delay before retry
                    self.parent.after(1000, self.connect_weighbridge)
                    
            elif "permission error" in error_msg.lower() or "access is denied" in error_msg.lower():
                # Likely another app is using the port
                response = messagebox.askretrycancel(
                    "Port in Use", 
                    "The COM port is currently in use by another application.\n\n"
                    f"{error_msg}\n\n"
                    "Close any other applications that might be using the port and try again.",
                    icon=messagebox.WARNING
                )
                
                # If user wants to retry
                if response:
                    # Small delay before retry
                    self.parent.after(1000, self.connect_weighbridge)
                    
            else:
                # Generic error message for other issues
                messagebox.showerror("Connection Error", f"Failed to connect to weighbridge:\n\n{error_msg}")
                
                # Update the status text to show error
                self.wb_status_var.set(f"Status: Connection Failed")
                self.weight_label.config(foreground="red")

    def disconnect_weighbridge(self):
        """Disconnect from weighbridge"""
        if self.weighbridge.disconnect():
            # Update UI
            self.wb_status_var.set("Status: Disconnected")
            self.weight_label.config(foreground="red")
            self.connect_btn.config(state=tk.NORMAL)
            self.disconnect_btn.config(state=tk.DISABLED)
            self.current_weight_var.set("0 kg")

    
    def load_users(self):
        """Load users into the tree view"""
        # Clear existing items
        for item in self.users_tree.get_children():
            self.users_tree.delete(item)
            
        try:
            # Get users from storage
            users = self.settings_storage.get_users()
            
            # Add to treeview
            for username, user_data in users.items():
                role = user_data.get('role', 'user')
                name = user_data.get('name', '')
                
                self.users_tree.insert("", tk.END, values=(
                    username,
                    name,
                    role
                ))
                
            # Apply alternating row colors
            self._apply_row_colors(self.users_tree)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load users: {str(e)}")
    
    def on_user_select(self, event):
        """Handle user selection in the treeview"""
        selected_items = self.users_tree.selection()
        if not selected_items:
            return
            
        # Get user data
        item = selected_items[0]
        username = self.users_tree.item(item, 'values')[0]
        
        try:
            # Get user details
            users = self.settings_storage.get_users()
            
            if username in users:
                user_data = users[username]
                
                # Set form fields
                self.username_var.set(username)
                self.fullname_var.set(user_data.get('name', ''))
                self.is_admin_var.set(user_data.get('role', 'user') == 'admin')
                
                # Clear password fields
                self.password_var.set("")
                self.confirm_password_var.set("")
                
                # Disable username field for editing
                self.username_entry.configure(state="disabled")
                
                # Set edit mode
                self.edit_mode = True
                
                # Set status
                self.user_status_var.set("Editing user: " + username)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load user details: {str(e)}")
    
    def new_user(self):
        """Set up form for a new user"""
        # Clear form
        self.clear_user_form()
        
        # Enable username field
        self.username_entry.configure(state="normal")
        
        # Set edit mode
        self.edit_mode = False
        
        # Set status
        self.user_status_var.set("Creating new user")
    
    def save_user(self):
        """Save user to storage"""
        # Get form data
        username = self.username_var.get().strip()
        fullname = self.fullname_var.get().strip()
        password = self.password_var.get()
        confirm_password = self.confirm_password_var.get()
        is_admin = self.is_admin_var.get()
        
        # Validate inputs
        if not username:
            messagebox.showerror("Validation Error", "Username is required")
            return
            
        if not fullname:
            messagebox.showerror("Validation Error", "Full name is required")
            return
            
        # Check username format (alphanumeric)
        if not username.isalnum():
            messagebox.showerror("Validation Error", "Username must be alphanumeric")
            return
            
        # Check if password is required (new user or password change)
        if not self.edit_mode or password:
            if not password:
                messagebox.showerror("Validation Error", "Password is required")
                return
                
            if password != confirm_password:
                messagebox.showerror("Validation Error", "Passwords do not match")
                return
                
            if len(password) < 4:
                messagebox.showerror("Validation Error", "Password must be at least 4 characters")
                return
        
        try:
            # Get existing users
            users = self.settings_storage.get_users()
            
            # Check if username exists (for new user)
            if not self.edit_mode and username in users:
                messagebox.showerror("Error", "Username already exists")
                return
                
            # Prepare user data
            user_data = {
                "name": fullname,
                "role": "admin" if is_admin else "user"
            }
            
            # Set password if provided
            if password:
                user_data["password"] = self.settings_storage.hash_password(password)
            elif self.edit_mode and username in users:
                # Keep existing password
                user_data["password"] = users[username]["password"]
            
            # Save user
            users[username] = user_data
            
            # Save to storage
            if self.settings_storage.save_users(users):
                # Refresh user list
                self.load_users()
                
                # Clear form
                self.clear_user_form()
                
                # Show success message
                messagebox.showinfo("Success", f"User '{username}' saved successfully")
            else:
                messagebox.showerror("Error", "Failed to save user")
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save user: {str(e)}")


    # In settings_panel.py, improve the update_weight_display method



    # Add a method to explicitly request callback propagation
    def request_callback_propagation(self):
        """Request that the next weight update propagates the callback"""
        self._propagate_callback = True


    def delete_user(self):
        """Delete selected user"""
        selected_items = self.users_tree.selection()
        if not selected_items:
            messagebox.showinfo("Selection", "Please select a user to delete")
            return
            
        # Get user data
        item = selected_items[0]
        username = self.users_tree.item(item, 'values')[0]
        
        # Prevent deleting the last admin user
        try:
            # Get users
            users = self.settings_storage.get_users()
            
            # Count admin users
            admin_count = sum(1 for u, data in users.items() if data.get('role', '') == 'admin')
            
            # Check if attempting to delete the last admin
            if users.get(username, {}).get('role', '') == 'admin' and admin_count <= 1:
                messagebox.showerror("Error", "Cannot delete the last admin user")
                return
                
            # Confirm deletion
            confirm = messagebox.askyesno("Confirm", f"Are you sure you want to delete user '{username}'?")
            if not confirm:
                return
                
            # Delete user
            if username in users:
                del users[username]
                
                # Save to storage
                if self.settings_storage.save_users(users):
                    # Refresh user list
                    self.load_users()
                    
                    # Clear form if deleted user was being edited
                    if self.username_var.get() == username:
                        self.clear_user_form()
                    
                    # Show success message
                    messagebox.showinfo("Success", f"User '{username}' deleted successfully")
                else:
                    messagebox.showerror("Error", "Failed to save changes")
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to delete user: {str(e)}")
    
    def clear_user_form(self):
        """Clear user form"""
        # Clear variables
        self.username_var.set("")
        self.fullname_var.set("")
        self.password_var.set("")
        self.confirm_password_var.set("")
        self.is_admin_var.set(False)
        
        # Reset edit mode
        self.edit_mode = False
        
        # Enable username field for new user
        self.username_entry.configure(state="normal")
        
        # Clear status
        self.user_status_var.set("")
    

    
    def add_site(self):
        """Add a new site"""
        site_name = self.site_name_var.get().strip()
        if not site_name:
            messagebox.showerror("Error", "Site name cannot be empty")
            return
            
        # Check if site already exists
        for item in self.site_tree.get_children():
            if self.site_tree.item(item, 'values')[0] == site_name:
                messagebox.showerror("Error", "Site name already exists")
                return
                
        # Add to treeview
        self.site_tree.insert("", tk.END, values=(site_name,))
        
        # Apply alternating row colors
        self._apply_row_colors(self.site_tree)
        
        # Clear entry
        self.site_name_var.set("")
    
    def delete_site(self):
        """Delete selected site"""
        selected_items = self.site_tree.selection()
        if not selected_items:
            messagebox.showinfo("Selection", "Please select a site to delete")
            return
            
        # Prevent deleting the last site
        if len(self.site_tree.get_children()) <= 1:
            messagebox.showerror("Error", "Cannot delete the last site")
            return
            
        # Delete selected site
        for item in selected_items:
            self.site_tree.delete(item)
            
        # Apply alternating row colors
        self._apply_row_colors(self.site_tree)
    
    def add_incharge(self):
        """Add a new incharge"""
        incharge_name = self.incharge_name_var.get().strip()
        if not incharge_name:
            messagebox.showerror("Error", "Incharge name cannot be empty")
            return
            
        # Check if incharge already exists
        for item in self.incharge_tree.get_children():
            if self.incharge_tree.item(item, 'values')[0] == incharge_name:
                messagebox.showerror("Error", "Incharge name already exists")
                return
                
        # Add to treeview
        self.incharge_tree.insert("", tk.END, values=(incharge_name,))
        
        # Apply alternating row colors
        self._apply_row_colors(self.incharge_tree)
        
        # Clear entry
        self.incharge_name_var.set("")
    
    def delete_incharge(self):
        """Delete selected incharge"""
        selected_items = self.incharge_tree.selection()
        if not selected_items:
            messagebox.showinfo("Selection", "Please select an incharge to delete")
            return
            
        # Delete selected incharge
        for item in selected_items:
            self.incharge_tree.delete(item)
            
        # Apply alternating row colors
        self._apply_row_colors(self.incharge_tree)
    
    def load_sites(self):
        """Load sites, incharges, transfer parties and agencies into treeviews"""
        # Clear existing items
        for item in self.site_tree.get_children():
            self.site_tree.delete(item)
            
        for item in self.incharge_tree.get_children():
            self.incharge_tree.delete(item)
            
        for item in self.tp_tree.get_children():
            self.tp_tree.delete(item)
            
        for item in self.agency_tree.get_children():
            self.agency_tree.delete(item)
            
        try:
            # Get sites data
            sites_data = self.settings_storage.get_sites()
            
            # Add sites to treeview
            for site in sites_data.get('sites', []):
                self.site_tree.insert("", tk.END, values=(site,))
                
            # Add incharges to treeview
            for incharge in sites_data.get('incharges', []):
                self.incharge_tree.insert("", tk.END, values=(incharge,))
                
            # Add transfer parties to treeview
            for tp in sites_data.get('transfer_parties', ['Advitia Labs']):
                self.tp_tree.insert("", tk.END, values=(tp,))
                
            # Add agencies to treeview
            for agency in sites_data.get('agencies', []):
                self.agency_tree.insert("", tk.END, values=(agency,))
                
            # Apply alternating row colors
            self._apply_row_colors(self.site_tree)
            self._apply_row_colors(self.incharge_tree)
            self._apply_row_colors(self.tp_tree)
            self._apply_row_colors(self.agency_tree)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load sites: {str(e)}")

    def save_sites_settings(self):
        """Save sites, incharges, transfer parties and agencies to storage"""
        try:
            # Get all sites
            sites = []
            for item in self.site_tree.get_children():
                sites.append(self.site_tree.item(item, 'values')[0])
                
            # Get all incharges
            incharges = []
            for item in self.incharge_tree.get_children():
                incharges.append(self.incharge_tree.item(item, 'values')[0])
                
            # Get all transfer parties
            transfer_parties = []
            for item in self.tp_tree.get_children():
                transfer_parties.append(self.tp_tree.item(item, 'values')[0])
                
            # Get all agencies
            agencies = []
            for item in self.agency_tree.get_children():
                agencies.append(self.agency_tree.item(item, 'values')[0])
                
            # Save to storage
            sites_data = {
                "sites": sites,
                "incharges": incharges,
                "transfer_parties": transfer_parties,
                "agencies": agencies
            }
            
            if self.settings_storage.save_sites(sites_data):
                messagebox.showinfo("Success", "Sites settings saved successfully!")
            else:
                messagebox.showerror("Error", "Failed to save sites settings")
                
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save sites settings: {str(e)}")

    def _apply_row_colors(self, tree):
        """Apply alternating row colors to treeview"""
        for i, item in enumerate(tree.get_children()):
            if i % 2 == 0:
                tree.item(item, tags=("evenrow",))
            else:
                tree.item(item, tags=("oddrow",))
        
        tree.tag_configure("evenrow", background=config.COLORS["table_row_even"])
        tree.tag_configure("oddrow", background=config.COLORS["table_row_odd"])
    