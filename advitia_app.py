#pyinstaller --onedir --windowed --add-data "data;data" --collect-all=cv2 --collect-all=pandas --collect-all=PIL --hidden-import=serial --hidden-import=google.cloud --hidden-import=psutil --optimize=2 --strip --noupx --name="Swaccha_Andhra2.0" --icon=right.ico advitia_app.py
# pyinstaller ^
#   --onedir ^
#   --windowed ^
#   --name="SAC_monitor_Chilakaluripeta" ^
#   --icon=right.ico ^
#   --add-data "data;data" ^
#   --add-data "assets/logo.png;assets" ^
#   --hidden-import=serial ^
#   --hidden-import=serial.tools.list_ports ^
#   --hidden-import=google.cloud.storage ^
#   --hidden-import=google.api_core.exceptions ^
#   --hidden-import=google.auth ^
#   --hidden-import=PIL._tkinter_finder ^
#   --hidden-import=PIL.Image ^
#   --hidden-import=PIL.ImageTk ^
#   --hidden-import=pandas._libs.testing ^
#   --hidden-import=cv2 ^
#   --hidden-import=reportlab.pdfgen.canvas ^
#   --hidden-import=reportlab.lib.pagesizes ^
#   --hidden-import=reportlab.platypus ^
#   --hidden-import=psutil ^
#   --hidden-import=tkinter.filedialog ^
#   --hidden-import=tkinter.messagebox ^
#   --exclude-module=matplotlib ^
#   --exclude-module=scipy ^
#   --exclude-module=jupyter ^
#   --exclude-module=cv2.aruco ^
#   --exclude-module=cv2.face ^
#   --exclude-module=cv2.tracking ^
#   --optimize=2 ^
#   --str
#   advitia_app.py

import tkinter as tk
import os
import datetime
import threading
import logging
from tkinter import ttk, messagebox
from pending_vehicles_panel import PendingVehiclesPanel
import config
from ui_components import HoverButton, create_styles
from camera import CameraView
from main_form import MainForm
from summary_panel import SummaryPanel
from settings_panel import SettingsPanel
from data_management import DataManager  # This now includes auto PDF generation
from reports import export_to_excel, export_to_pdf
from settings_storage import SettingsStorage
from login_dialog import LoginDialog
import pandas._libs.testing
from unified_logging import setup_unified_logging
try:
    from simple_connectivity import add_connectivity_to_app, add_to_queue_if_available, cleanup_connectivity
    CONNECTIVITY_AVAILABLE = True
except ImportError:
    CONNECTIVITY_AVAILABLE = False
if config.HARDCODED_MODE:
    from hardcoded_settings import HardcodedSettingsStorage
else:
    from settings_storage import SettingsStorage

def setup_app_logging():
    """FIXED: Set up application-wide logging with better error handling"""
    try:
        logs_dir = config.LOGS_FOLDER
        os.makedirs(logs_dir, exist_ok=True)
        
        # Create log filename with current date
        log_filename = os.path.join(logs_dir, f"app_{datetime.datetime.now().strftime('%Y-%m-%d')}.log")
        
        # Configure logging with safer file handler
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_filename, encoding='utf-8'),
                logging.StreamHandler()
            ]
        )
        
        return logging.getLogger('TharuniApp')
        
    except Exception as e:
        print(f"⚠️ Could not setup app logging: {e}")
        # Return a fallback logger
        class FallbackLogger:
            def info(self, msg): print(f"INFO: {msg}")
            def warning(self, msg): print(f"WARNING: {msg}")
            def error(self, msg): print(f"ERROR: {msg}")
            def debug(self, msg): print(f"DEBUG: {msg}")
            def critical(self, msg): print(f"CRITICAL: {msg}")
        
        return FallbackLogger()

class TharuniApp:
    """FIXED: Main application class with enhanced logging and error handling"""
    
    def __init__(self, root):
        """Initialize the application with authentication and logging
        
        Args:
            root: Root Tkinter window
        """
        self.root = root
        self.root.title("Swaccha Andhra Corporation powered by Advitia Labs")
        self.root.geometry("900x580")
        self.root.minsize(900, 580)

        # FIXED: Setup unified logging with better error handling
        try:
            unified_logger = setup_unified_logging("combined", "logs")  # FIXED: typo "coimbined" -> "combined"
        except Exception as e:
            print(f"⚠️ Could not setup unified logging: {e}")
            unified_logger = None
        
        # FIXED: Set up logging with fallback
        try:
            self.logger = setup_app_logging()
            self.logger.info("="*60)
            self.logger.info("APPLICATION STARTUP")
            self.logger.info("="*60)
        except Exception as e:
            print(f"⚠️ Could not setup app logging: {e}")
            # Create a fallback logger that just prints
            class FallbackLogger:
                def info(self, msg): print(f"INFO: {msg}")
                def warning(self, msg): print(f"WARNING: {msg}")
                def error(self, msg): print(f"ERROR: {msg}")
                def debug(self, msg): print(f"DEBUG: {msg}")
                def critical(self, msg): print(f"CRITICAL: {msg}")
            self.logger = FallbackLogger()
        
        try:
            # Set up initial configuration
            config.setup()
            self.logger.info("Configuration setup completed")
            
            # Initialize data manager with auto PDF generation
            self.data_manager = DataManager()
            self.logger.info("Data manager initialized")
            
            # MODIFIED: Initialize settings storage based on mode
            if config.HARDCODED_MODE:
                from hardcoded_settings import HardcodedSettingsStorage
                self.settings_storage = HardcodedSettingsStorage()
                self.logger.info("Using hardcoded settings storage")
            else:
                self.settings_storage = SettingsStorage()
                self.logger.info("Using file-based settings storage")
            
            # IMPORTANT: Verify settings integrity at startup (only for non-hardcoded mode)
            if not config.HARDCODED_MODE:
                if not self.settings_storage.verify_settings_integrity():
                    self.logger.warning("Settings integrity check failed - reinitializing settings files")
                    self.settings_storage.initialize_files()
            
            # Initialize UI styles
            self.style = create_styles()
            self.logger.info("UI styles initialized")
            
            # Show login dialog before creating UI
            self.logged_in_user = None
            self.user_role = None
            self.selected_site = None
            self.selected_incharge = None
            self.authenticate_user()
            
            # Initialize UI components if login successful
            if self.logged_in_user:
                self.logger.info(f"User logged in: {self.logged_in_user} (Role: {self.user_role})")
                
                # IMPORTANT: Set the data context based on login selections
                self.setup_data_context()
                
                self.create_widgets()

                # Start time update
                self.update_datetime()
                
                # Start periodic refresh for pending vehicles
                self.periodic_refresh()
                if CONNECTIVITY_AVAILABLE:
                    add_connectivity_to_app(self)                
                # Add window close handler with settings persistence
                self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
                
                self.logger.info("Application initialization completed successfully")
            else:
                self.logger.info("User authentication failed or canceled - exiting")
                self.root.destroy()
                return
                
        except Exception as e:
            self.logger.error(f"Critical error during application initialization: {e}")
            messagebox.showerror("Initialization Error", 
                               f"Failed to initialize application:\n{str(e)}\n\nCheck logs for details.")
            self.root.quit()





    def authenticate_user(self):
        """Enhanced authentication with logo, site display, and better UI"""
        try:
            self.logger.info("Starting user authentication")
            
            if config.HARDCODED_MODE:
                if config.REQUIRE_PASSWORD:
                    # Enhanced password dialog with logo and site info
                    result = self.show_enhanced_login_dialog()
                    
                    if result and result == config.HARDCODED_PASSWORD:
                        self.logged_in_user = config.HARDCODED_USER
                        self.user_role = "admin"
                        self.selected_site = config.HARDCODED_SITE
                        self.selected_incharge = config.HARDCODED_INCHARGE
                        self.logger.info(f"Hardcoded authentication successful: {self.logged_in_user}")
                    else:
                        self.logger.info("Authentication canceled - exiting application")
                        self.root.destroy()
                        return
                else:
                    # Show welcome dialog even without password requirement
                    self.show_welcome_dialog()
                    
                    # No authentication required
                    self.logged_in_user = config.HARDCODED_USER
                    self.user_role = "admin"
                    self.selected_site = config.HARDCODED_SITE
                    self.selected_incharge = config.HARDCODED_INCHARGE
                    self.logger.info(f"Auto-login: {self.logged_in_user}")
            else:
                # Original login dialog for non-hardcoded mode
                from login_dialog import LoginDialog
                login = LoginDialog(self.root, self.settings_storage, show_select=True)
                
                if login.result:
                    self.logged_in_user = login.username
                    self.user_role = login.role
                    self.selected_site = login.site
                    self.selected_incharge = login.incharge
                    self.logger.info(f"Authentication successful: {self.logged_in_user}")
                else:
                    self.logger.info("Authentication canceled - exiting application")
                    self.root.destroy()
        
        except Exception as e:
            self.logger.error(f"Authentication error: {e}")
            self.root.quit()


    def resource_path(relative_path):
        """ Get absolute path to resource, works for dev and for PyInstaller """
        try:
            # PyInstaller creates a temp folder and stores path in _MEIPASS
            base_path = sys._MEIPASS
        except Exception:
            base_path = os.path.abspath(".")
        
        return os.path.join(base_path, relative_path)

    def show_enhanced_login_dialog(self):
        """Show enhanced login dialog with logo and site information"""
        try:
            import tkinter as tk
            from tkinter import ttk
            from PIL import Image, ImageTk
            import os
            
            # Create modal dialog
            dialog = tk.Toplevel(self.root)
            dialog.title("Swaccha Andhra Monitor - Login")
            dialog.transient(self.root)
            dialog.grab_set()
            
            # Center the dialog and make it larger
            dialog_width = 450
            dialog_height = 550
            
            # Get main window position and size
            self.root.update_idletasks()
            main_x = self.root.winfo_x()
            main_y = self.root.winfo_y()
            main_width = self.root.winfo_width()
            main_height = self.root.winfo_height()
            
            # Calculate center position relative to main window
            x = main_x + (main_width - dialog_width) // 2
            y = main_y + (main_height - dialog_height) // 2
            
            dialog.geometry(f"{dialog_width}x{dialog_height}+{x}+{y}")
            dialog.resizable(False, False)
            
            # Configure dialog colors
            dialog.configure(bg=config.COLORS.get("background", "#f0f0f0"))
            
            # Main frame with padding
            main_frame = ttk.Frame(dialog)
            main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
            
            # Logo section
            logo_frame = ttk.Frame(main_frame)
            logo_frame.pack(fill=tk.X, pady=(0, 20))
            
            # Try to load logo
            logo_loaded = False
            try:
                # Look for logo in multiple locations
                possible_logo_paths = [
                    os.path.join("assets", "logo.png"),
                    os.path.join("assets", "logo.jpg"),
                    os.path.join("images", "logo.png"),
                    os.path.join("images", "logo.jpg"),
                    "logo.png",
                    "logo.jpg"
                ]
                
                for logo_path in possible_logo_paths:
                    if os.path.exists(logo_path):
                        try:
                            # Load and resize logo
                            logo_image = Image.open(logo_path)
                            # Resize logo to fit nicely (max 150x100)
                            logo_image.thumbnail((150, 100), Image.Resampling.LANCZOS)
                            logo_photo = ImageTk.PhotoImage(logo_image)
                            
                            logo_label = ttk.Label(logo_frame, image=logo_photo)
                            logo_label.image = logo_photo  # Keep reference
                            logo_label.pack(pady=(0, 10))
                            logo_loaded = True
                            break
                        except Exception as e:
                            self.logger.warning(f"Could not load logo from {logo_path}: {e}")
                            continue
                            
            except Exception as e:
                self.logger.warning(f"Logo loading error: {e}")
            
            # If no logo loaded, show company name
            if not logo_loaded:
                company_label = ttk.Label(logo_frame, 
                                        text="Weight Management System",
                                        font=("Segoe UI", 16, "bold"),
                                        foreground=config.COLORS.get("primary", "#2E86AB"))
                company_label.pack(pady=(0, 10))
            
            # Site information section
            site_frame = ttk.LabelFrame(main_frame, text="Site Information", padding=15)
            site_frame.pack(fill=tk.X, pady=(0, 20))
            
            # Site name
            site_name_label = ttk.Label(site_frame, 
                                    text=f"Site: {config.HARDCODED_SITE}",
                                    font=("Segoe UI", 12, "bold"),
                                    foreground=config.COLORS.get("success", "#28a745"))
            site_name_label.pack(anchor=tk.W, pady=(0, 5))
            
            # Incharge
            incharge_label = ttk.Label(site_frame, 
                                    text=f"Site Incharge: {config.HARDCODED_INCHARGE}",
                                    font=("Segoe UI", 10))
            incharge_label.pack(anchor=tk.W, pady=(0, 5))
            
            # User info
            user_label = ttk.Label(site_frame, 
                                text=f"User: {config.HARDCODED_USER}",
                                font=("Segoe UI", 10))
            user_label.pack(anchor=tk.W)
            
            # Login section
            login_frame = ttk.LabelFrame(main_frame, text="Authentication", padding=15)
            login_frame.pack(fill=tk.X, pady=(0, 20))
            
            # Password label
            password_label = ttk.Label(login_frame, 
                                    text="Enter Password to Continue:",
                                    font=("Segoe UI", 10))
            password_label.pack(anchor=tk.W, pady=(0, 10))
            
            # Password entry
            self.password_var = tk.StringVar()
            password_entry = ttk.Entry(login_frame, 
                                    textvariable=self.password_var,
                                    show='*', 
                                    font=("Segoe UI", 11),
                                    width=30)
            password_entry.pack(fill=tk.X, pady=(0, 10))
            
            # Error message label (initially hidden) - using tk.Label for better color control
            self.error_var = tk.StringVar()
            error_label = tk.Label(login_frame, 
                                textvariable=self.error_var,
                                font=("Segoe UI", 9, "bold"),
                                fg="red",
                                bg=dialog.cget("bg"),
                                wraplength=400,
                                justify=tk.LEFT)
            error_label.pack(fill=tk.X, pady=(0, 15))
            
            # Focus on password entry
            password_entry.focus_set()
            
            # Buttons frame
            button_frame = ttk.Frame(main_frame)
            button_frame.pack(fill=tk.X)
            
            # Result storage
            self.dialog_result = None
            
            def clear_error():
                """Clear error message when user starts typing"""
                self.error_var.set("")
                # Reset password entry style
                try:
                    password_entry.configure(style="TEntry")
                except:
                    try:
                        password_entry.configure(background="white")
                    except:
                        pass
            
            def show_error(message):
                """Show error message and highlight password field"""
                self.error_var.set(message)
                
                # Make sure error label is visible and red
                error_label.configure(fg="red", bg=dialog.cget("bg"))
                
                # Create a custom style for error state
                try:
                    style = ttk.Style()
                    style.configure("Error.TEntry", 
                                fieldbackground="#ffe6e6", 
                                bordercolor="red",
                                focuscolor="red")
                    password_entry.configure(style="Error.TEntry")
                except Exception as e:
                    # Fallback: try to change the background directly
                    try:
                        password_entry.configure(background="#ffe6e6")
                    except:
                        pass
                
                # Clear password field
                self.password_var.set("")
                password_entry.focus_set()
                
                # Flash the error message for attention
                flash_count = 0
                def flash_error():
                    nonlocal flash_count
                    if flash_count < 6:  # Flash 3 times
                        current_color = error_label.cget("fg")
                        new_color = "#ff0000" if current_color == "#990000" else "#990000"
                        error_label.configure(fg=new_color)
                        flash_count += 1
                        if hasattr(dialog, 'winfo_exists') and dialog.winfo_exists():
                            dialog.after(200, flash_error)
                    else:
                        # End with red color
                        error_label.configure(fg="red")
                
                flash_error()
            
            def validate_password():
                """Validate the entered password"""
                entered_password = self.password_var.get().strip()
                
                if not entered_password:
                    show_error("⚠️ Password cannot be empty!")
                    return False
                
                if entered_password == config.HARDCODED_PASSWORD:
                    return True
                else:
                    show_error("❌ Invalid password! Please try again.")
                    return False
            
            def on_login():
                """Handle login button click"""
                if validate_password():
                    self.dialog_result = self.password_var.get()
                    dialog.destroy()
            
            def on_cancel():
                self.dialog_result = None
                dialog.destroy()
            
            # Bind password field events
            self.password_var.trace('w', lambda *args: clear_error())  # Clear error when typing
            
            # Login button
            login_btn = ttk.Button(button_frame, 
                                text="🔐 Login", 
                                command=on_login,
                                style="Accent.TButton")
            login_btn.pack(side=tk.RIGHT, padx=(10, 0))
            
            # Cancel button
            cancel_btn = ttk.Button(button_frame, 
                                text="❌ Cancel", 
                                command=on_cancel)
            cancel_btn.pack(side=tk.RIGHT)
            
            # Bind Enter key to login with validation
            def on_enter(event):
                on_login()
            
            dialog.bind('<Return>', on_enter)
            password_entry.bind('<Return>', on_enter)
            
            # Bind Escape key to cancel
            dialog.bind('<Escape>', lambda e: on_cancel())
            
            # Status bar
            status_frame = ttk.Frame(main_frame)
            status_frame.pack(fill=tk.X, pady=(15, 0))
            
            timestamp_label = ttk.Label(status_frame, 
                                    text=f"Login Time: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                                    font=("Segoe UI", 8),
                                    foreground="gray")
            timestamp_label.pack(anchor=tk.W)
            
            # Wait for dialog to close
            dialog.wait_window()
            
            return self.dialog_result
            
        except Exception as e:
            self.logger.error(f"Enhanced login dialog error: {e}")
            # Fallback to simple dialog
            import tkinter.simpledialog as simpledialog
            return simpledialog.askstring("Login", "Enter password:", show='*')

    def show_welcome_dialog(self):
        """Show welcome dialog for auto-login mode"""
        try:
            import tkinter as tk
            from tkinter import ttk
            from PIL import Image, ImageTk
            import os
            
            # Create modal dialog
            dialog = tk.Toplevel(self.root)
            dialog.title("Weight Management System - Welcome")
            dialog.transient(self.root)
            dialog.grab_set()
            
            # Smaller dialog for welcome
            dialog_width = 400
            dialog_height = 450
            
            # Get main window position and size
            self.root.update_idletasks()
            main_x = self.root.winfo_x()
            main_y = self.root.winfo_y()
            main_width = self.root.winfo_width()
            main_height = self.root.winfo_height()
            
            # Calculate center position relative to main window
            x = main_x + (main_width - dialog_width) // 2
            y = main_y + (main_height - dialog_height) // 2
            
            dialog.geometry(f"{dialog_width}x{dialog_height}+{x}+{y}")
            dialog.resizable(False, False)
            
            # Configure dialog colors
            dialog.configure(bg=config.COLORS.get("background", "#f0f0f0"))
            
            # Main frame with padding
            main_frame = ttk.Frame(dialog)
            main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
            
            # Logo section (same as login dialog)
            logo_frame = ttk.Frame(main_frame)
            logo_frame.pack(fill=tk.X, pady=(0, 20))
            
            # Try to load logo (same logic as login dialog)
            logo_loaded = False
            try:
                possible_logo_paths = [
                    os.path.join("assets", "logo.png"),
                    os.path.join("assets", "logo.jpg"),
                    os.path.join("images", "logo.png"),
                    os.path.join("images", "logo.jpg"),
                    "logo.png",
                    "logo.jpg"
                ]
                
                for logo_path in possible_logo_paths:
                    if os.path.exists(logo_path):
                        try:
                            logo_image = Image.open(logo_path)
                            logo_image.thumbnail((150, 100), Image.Resampling.LANCZOS)
                            logo_photo = ImageTk.PhotoImage(logo_image)
                            
                            logo_label = ttk.Label(logo_frame, image=logo_photo)
                            logo_label.image = logo_photo
                            logo_label.pack(pady=(0, 10))
                            logo_loaded = True
                            break
                        except Exception:
                            continue
                            
            except Exception as e:
                self.logger.warning(f"Logo loading error: {e}")
            
            if not logo_loaded:
                company_label = ttk.Label(logo_frame, 
                                        text="Weight Management System",
                                        font=("Segoe UI", 16, "bold"),
                                        foreground=config.COLORS.get("primary", "#2E86AB"))
                company_label.pack(pady=(0, 10))
            
            # Welcome message
            welcome_label = ttk.Label(main_frame,
                                    text="Welcome!",
                                    font=("Segoe UI", 14, "bold"))
            welcome_label.pack(pady=(0, 20))
            
            # Site information section
            site_frame = ttk.LabelFrame(main_frame, text="Site Information", padding=15)
            site_frame.pack(fill=tk.X, pady=(0, 20))
            
            # Site details
            site_info = [
                ("Site", config.HARDCODED_SITE),
                ("Incharge", config.HARDCODED_INCHARGE),
                ("User", config.HARDCODED_USER),
                ("Login Time", datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
            ]
            
            for label_text, value_text in site_info:
                info_frame = ttk.Frame(site_frame)
                info_frame.pack(fill=tk.X, pady=2)
                
                label = ttk.Label(info_frame, 
                                text=f"{label_text}:",
                                font=("Segoe UI", 10, "bold"),
                                width=12)
                label.pack(side=tk.LEFT)
                
                value = ttk.Label(info_frame, 
                                text=value_text,
                                font=("Segoe UI", 10))
                value.pack(side=tk.LEFT)
            
            # Continue button
            continue_btn = ttk.Button(main_frame, 
                                    text="Continue to Application", 
                                    command=lambda: dialog.destroy(),
                                    style="Accent.TButton")
            continue_btn.pack(pady=20)
            
            # Auto-close after 3 seconds
            def auto_close():
                try:
                    dialog.destroy()
                except:
                    pass
            
            dialog.after(3000, auto_close)  # Auto-close after 3 seconds
            
            # Bind Enter key and Escape key
            dialog.bind('<Return>', lambda e: dialog.destroy())
            dialog.bind('<Escape>', lambda e: dialog.destroy())
            
            # Focus on continue button
            continue_btn.focus_set()
            
            # Wait for dialog to close
            dialog.wait_window()
            
        except Exception as e:
            self.logger.error(f"Welcome dialog error: {e}")
            # If welcome dialog fails, just continue
            pass

    def setup_data_context(self):
        """Set up data context with hardcoded values when in hardcoded mode"""
        try:
            self.logger.info("Setting up data context")
            
            if config.HARDCODED_MODE:
                # Use hardcoded values
                agency_name = config.HARDCODED_AGENCY
                site_name = config.HARDCODED_SITE
                self.logger.info("Using hardcoded agency and site values")
            else:
                # Original logic for dynamic selection
                sites_data = self.settings_storage.get_sites()
                agencies = sites_data.get('agencies', ['Default Agency'])
                agency_name = agencies[0] if agencies else 'Default Agency'
                site_name = self.selected_site if self.selected_site else 'Guntur'
            
            self.data_manager.set_agency_site_context(agency_name, site_name)
            
            self.current_agency = agency_name
            self.current_site = site_name
            
            self.logger.info(f"Data context initialized: Agency='{agency_name}', Site='{site_name}'")
            self.logger.info(f"Data will be saved to: {self.data_manager.get_current_data_file()}")
            self.logger.info(f"PDFs will be saved to: {self.data_manager.get_daily_folder('pdf')}")
            
        except Exception as e:
            self.logger.error(f"Error setting up data context: {e}")
            raise

    def create_widgets(self):
        """Create all widgets and layout for the application"""
        try:
            self.logger.info("Creating application widgets")
            
            # Create main container frame
            main_container = ttk.Frame(self.root, padding="5", style="TFrame")
            main_container.pack(fill=tk.BOTH, expand=True)
            
            # Title and header section with user and site info plus PDF status
            self.create_header(main_container)
            
            # Create notebook for tabs
            self.notebook = ttk.Notebook(main_container)
            self.notebook.pack(fill=tk.BOTH, expand=True, pady=(5, 0))
            
            # Create tabs
            main_tab = ttk.Frame(self.notebook, style="TFrame")
            self.notebook.add(main_tab, text="Vehicle Entry")
            
            summary_tab = ttk.Frame(self.notebook, style="TFrame")
            self.notebook.add(summary_tab, text="Recent Entries")
            
            settings_tab = ttk.Frame(self.notebook, style="TFrame")
            self.notebook.add(settings_tab, text="Settings")
            
            # Main panel with scrollable frame for small screens
            self.create_main_panel(main_tab)
            
            # Create summary panel
            self.summary_panel = SummaryPanel(summary_tab, self.data_manager)
            self.logger.info("Summary panel created")
            
            # Create settings panel with user info, weighbridge callback, and data manager reference
            self.settings_panel = SettingsPanel(
                settings_tab, 
                weighbridge_callback=self.update_weight_from_weighbridge,  # This is the key callback
                update_cameras_callback=self.update_camera_indices,
                current_user=self.logged_in_user,
                user_role=self.user_role
            )
            
            # IMPORTANT: Set data manager reference in settings panel for cloud backup
            if hasattr(self.settings_panel, '__dict__'):
                self.settings_panel.app_data_manager = self.data_manager
                self.logger.info("✅ Data manager reference set in settings panel")
            
            # Also store reference in parent widget for widget hierarchy search
            settings_tab.data_manager = self.data_manager
            
            # Handle role-based access to settings tabs - with error handling
            try:
                if self.user_role != 'admin' and hasattr(self.settings_panel, 'settings_notebook'):
                    # Hide user and site management tabs for non-admin users
                    self.settings_panel.settings_notebook.tab(2, state=tk.HIDDEN)  # Users tab
                    self.settings_panel.settings_notebook.tab(3, state=tk.HIDDEN)  # Sites tab
                    self.logger.info("Non-admin user - hid admin-only tabs")
            except (AttributeError, tk.TclError) as e:
                self.logger.error(f"Error setting tab visibility: {e}")
            
            # IMPORTANT: Ensure settings persistence after all widgets are created
            self.root.after(1000, self.ensure_settings_persistence)
            
            self.logger.info("Widget creation completed successfully")
            
        except Exception as e:
            self.logger.error(f"Error creating widgets: {e}")
            raise

    def create_main_panel(self, parent):
        """Create main panel with form and pending vehicles list"""
        try:
            self.logger.info("Creating main panel")
            
            # Main panel to hold everything with scrollable frame for small screens
            main_panel = ttk.Frame(parent, style="TFrame")
            main_panel.pack(fill=tk.BOTH, expand=True)
            
            # Configure main_panel for proper resizing
            main_panel.columnconfigure(0, weight=3)  # Left panel gets 3x the weight
            main_panel.columnconfigure(1, weight=1)  # Right panel gets 1x the weight
            main_panel.rowconfigure(0, weight=1)     # Single row gets all the weight
            
            # Split the main panel into two parts: form and pending vehicles
            # Use grid instead of pack for better resize control
            left_panel = ttk.Frame(main_panel, style="TFrame")
            left_panel.grid(row=0, column=0, sticky="nsew", padx=(0, 5))
            
            right_panel = ttk.Frame(main_panel, style="TFrame")
            right_panel.grid(row=0, column=1, sticky="nsew", padx=(5, 0))
            
            # Add a canvas with scrollbar for small screens on the left panel
            canvas = tk.Canvas(left_panel, bg=config.COLORS["background"], highlightthickness=0)
            scrollbar = ttk.Scrollbar(left_panel, orient="vertical", command=canvas.yview)
            
            # Configure left_panel for proper resizing
            left_panel.columnconfigure(0, weight=1)
            left_panel.rowconfigure(0, weight=1)
            
            # Create a frame that will contain the form and cameras
            scrollable_frame = ttk.Frame(canvas, style="TFrame")
            scrollable_frame.bind(
                "<Configure>",
                lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
            )
            
            # Add the frame to the canvas
            canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
            canvas.configure(yscrollcommand=scrollbar.set)
            
            # Pack the canvas and scrollbar
            canvas.pack(side="left", fill="both", expand=True)
            scrollbar.pack(side="right", fill="y")
            
            # Create the main form - pass data manager for ticket lookup
            self.main_form = MainForm(
                scrollable_frame, 
                notebook=self.notebook,
                summary_update_callback=self.update_summary,
                data_manager=self.data_manager,
                save_callback=self.save_record,
                view_callback=self.view_records,
                clear_callback=self.clear_form,
                exit_callback=self.confirm_exit
            )
            self.logger.info("Main form created")

            # Load sites and agencies for dropdowns in the main form
            self.main_form.load_sites_and_agencies(self.settings_storage)

            # Set the site name based on login selection if available
            if self.selected_site:
                self.main_form.set_site(self.selected_site)

            # UPDATED: Properly set agency and site incharge
            # Set the agency based on current context
            if hasattr(self, 'current_agency'):
                self.main_form.set_agency(self.current_agency)

            # Set the site incharge (separate from agency)
            if self.selected_incharge:
                self.main_form.set_site_incharge(self.selected_incharge)
            
            # Set user information
            self.main_form.set_user_info(
                username=self.logged_in_user,
                site_incharge=self.selected_incharge
            )

            # Create the pending vehicles panel on the right
            self.pending_vehicles = PendingVehiclesPanel(
                right_panel,
                data_manager=self.data_manager,
                on_vehicle_select=self.load_pending_vehicle
            )
            self.logger.info("Pending vehicles panel created")
            
            # Configure scroll region after adding content
            scrollable_frame.update_idletasks()
            canvas.configure(scrollregion=canvas.bbox("all"))
            
            self.logger.info("Main panel creation completed")
            
        except Exception as e:
            self.logger.error(f"Error creating main panel: {e}")
            raise
    def confirm_exit(self):
        """Ask for confirmation before exiting"""
        try:
            result = messagebox.askyesno("Exit Application", 
                                        "Are you sure you want to exit the application?")
            if result:
                self.on_closing()
        except Exception as e:
            self.logger.error(f"Error in confirm_exit: {e}")
            self.on_closing()

    def save_record(self):
        """FIXED: Save current record - smart ticket increment logic"""
        try:
            self.logger.info("="*50)
            self.logger.info("SAVE RECORD OPERATION STARTED WITH SMART TICKET FLOW")
            
            # Validate form first
            if not self.main_form.validate_form():
                self.logger.warning("Form validation failed - aborting save")
                return
            
            # Get form data
            record_data = self.main_form.get_form_data()
            ticket_no = record_data.get('ticket_no', '')
            
            print(f"🎫 TICKET FLOW DEBUG: Starting save for ticket: {ticket_no}")
            self.logger.info(f"Saving record for ticket: {ticket_no}")
            
            # Check if this is a new ticket or updating existing pending ticket
            is_update = False
            existing_record = None
            
            if ticket_no:
                # Check if record with this ticket number exists
                records = self.data_manager.get_filtered_records(ticket_no)
                for record in records:
                    if record.get('ticket_no') == ticket_no:
                        is_update = True
                        existing_record = record
                        print(f"🎫 TICKET FLOW DEBUG: This is an UPDATE to existing ticket: {ticket_no}")
                        self.logger.info(f"Updating existing record: {ticket_no}")
                        break
            
            if not is_update:
                print(f"🎫 TICKET FLOW DEBUG: This is a NEW record: {ticket_no}")
                self.logger.info(f"Adding new record: {ticket_no}")
            
            # Save to database
            self.logger.info(f"Calling data_manager.save_record for {ticket_no}")
            save_result = self.data_manager.save_record(record_data)
            
            # Handle the save result
            if isinstance(save_result, dict) and save_result.get('success', False):
                self.logger.info(f"✅ Record {ticket_no} saved successfully")
                
                # Extract weighment analysis from save result
                is_complete_record = save_result.get('is_complete_record', False)
                is_first_weighment_save = save_result.get('is_first_weighment_save', False)
                pdf_generated = save_result.get('pdf_generated', False)
                pdf_path = save_result.get('pdf_path', '')
                if CONNECTIVITY_AVAILABLE:
                    add_to_queue_if_available(self, record_data, pdf_path)
                todays_reports_folder = save_result.get('todays_reports_folder', '')
                
                print(f"🎫 TICKET FLOW DEBUG: Save result analysis:")
                print(f"   - is_complete_record: {is_complete_record}")
                print(f"   - is_first_weighment_save: {is_first_weighment_save}")
                print(f"   - is_update: {is_update}")
                
                # SMART TICKET LOGIC: Only increment counter when we actually "consume" a ticket number
                should_increment_counter = False
                
                if not is_update:
                    # This is a brand new record using a fresh ticket number
                    should_increment_counter = True
                    print(f"🎫 TICKET FLOW DEBUG: NEW record - will increment counter")
                elif is_update and is_complete_record:
                    # This is completing an existing pending record - the ticket was already "consumed"
                    # when the first weighment was saved, so don't increment again
                    should_increment_counter = False
                    print(f"🎫 TICKET FLOW DEBUG: Completing existing record - will NOT increment counter")
                elif is_update and is_first_weighment_save:
                    # This is adding first weighment to an existing record (edge case)
                    # Check if the existing record was empty before
                    if existing_record:
                        existing_first_weight = existing_record.get('first_weight', '').strip()
                        existing_first_timestamp = existing_record.get('first_timestamp', '').strip()
                        was_empty_before = not (existing_first_weight and existing_first_timestamp)
                        
                        if was_empty_before:
                            # This existing record was empty, so now we're actually using the ticket
                            should_increment_counter = True
                            print(f"🎫 TICKET FLOW DEBUG: Adding first weighment to empty record - will increment counter")
                        else:
                            # This existing record already had data, so ticket was already consumed
                            should_increment_counter = False
                            print(f"🎫 TICKET FLOW DEBUG: Updating existing record with data - will NOT increment counter")
                    else:
                        # Fallback - treat as new
                        should_increment_counter = True
                        print(f"🎫 TICKET FLOW DEBUG: Fallback for first weighment - will increment counter")
                
                # Apply the increment logic
                ticket_incremented = False
                if should_increment_counter:
                    print(f"🎫 TICKET FLOW DEBUG: INCREMENTING ticket counter after save of {ticket_no}")
                    commit_success = self.main_form.commit_current_ticket_number()
                    if commit_success:
                        print(f"🎫 TICKET FLOW DEBUG: ✅ Ticket counter incremented from {ticket_no}")
                        ticket_incremented = True
                    else:
                        print(f"🎫 TICKET FLOW DEBUG: ❌ Failed to increment ticket counter")
                        self.logger.warning(f"Failed to commit ticket number {ticket_no}")
                else:
                    print(f"🎫 TICKET FLOW DEBUG: NOT incrementing counter - ticket {ticket_no} was already consumed")
                
                # Handle different scenarios for UI updates and user feedback
                if is_first_weighment_save and not is_update:
                    # NEW first-only weighment record
                    print(f"🎫 TICKET FLOW DEBUG: First weighment saved for NEW ticket {ticket_no}")
                    
                    # Generate new ticket for next vehicle
                    self.main_form.prepare_for_next_vehicle_after_first_weighment()
                    new_ticket = self.main_form.rst_var.get()
                    print(f"🎫 TICKET FLOW DEBUG: Generated next ticket number: {new_ticket}")
                    
                    # Show success message
                    try:
                        messagebox.showinfo("First Weighment Saved", 
                                        f"✅ First weighment saved for ticket {ticket_no}!\n"
                                        f"🚛 Vehicle added to pending queue\n"
                                        f"🎫 New ticket number: {new_ticket}\n\n"
                                        f"💡 Vehicle can return later for second weighment")
                    except Exception as msg_error:
                        self.logger.warning(f"Could not show messagebox: {msg_error}")
                        
                elif is_complete_record and not is_update:
                    # NEW complete record (both weighments at once)
                    print(f"🎫 TICKET FLOW DEBUG: Complete record saved for NEW ticket {ticket_no}")
                    
                    # Generate new ticket for next vehicle
                    self.main_form.prepare_for_new_ticket_after_completion()
                    new_ticket = self.main_form.rst_var.get()
                    print(f"🎫 TICKET FLOW DEBUG: Generated next ticket number: {new_ticket}")
                    
                    # Switch to summary tab
                    self.notebook.select(1)
                    
                    # Show completion message
                    try:
                        if pdf_generated and pdf_path:
                            relative_folder = os.path.relpath(todays_reports_folder, os.getcwd()) if todays_reports_folder else "reports"
                            messagebox.showinfo("Complete Record Saved + PDF Generated", 
                                            f"✅ Complete weighment saved for ticket {ticket_no}!\n"
                                            f"✅ PDF generated: {os.path.basename(pdf_path)}\n"
                                            f"🎫 New ticket number: {new_ticket}\n\n"
                                            f"📂 PDF Location: {relative_folder}")
                        else:
                            messagebox.showinfo("Complete Record Saved", 
                                            f"✅ Complete weighment saved for ticket {ticket_no}!\n"
                                            f"🎫 New ticket number: {new_ticket}")
                    except Exception as msg_error:
                        self.logger.warning(f"Could not show messagebox: {msg_error}")
                        
                elif is_update and is_complete_record:
                    # UPDATE: Completing second weighment for existing pending record
                    print(f"🎫 TICKET FLOW DEBUG: Second weighment completed for existing ticket {ticket_no}")
                    
                    # Remove from pending vehicles list AFTER successful save
                    self.logger.info(f"Removing {ticket_no} from pending vehicles list")
                    if hasattr(self, 'pending_vehicles'):
                        self.pending_vehicles.remove_saved_record(ticket_no)
                    
                    # Generate new ticket for next vehicle (always show next available ticket)
                    self.main_form.prepare_for_new_ticket_after_completion()
                    new_ticket = self.main_form.rst_var.get()
                    print(f"🎫 TICKET FLOW DEBUG: Generated next ticket number after completing {ticket_no}: {new_ticket}")
                    
                    # Switch to summary tab
                    self.notebook.select(1)
                    
                    # Show completion message
                    try:
                        if pdf_generated and pdf_path:
                            relative_folder = os.path.relpath(todays_reports_folder, os.getcwd()) if todays_reports_folder else "reports"
                            messagebox.showinfo("Second Weighment Completed + PDF Generated", 
                                            f"✅ Second weighment completed for ticket {ticket_no}!\n"
                                            f"✅ PDF generated: {os.path.basename(pdf_path)}\n"
                                            f"🎫 Ready for next vehicle: {new_ticket}\n\n"
                                            f"📂 PDF Location: {relative_folder}")
                        else:
                            messagebox.showinfo("Second Weighment Completed", 
                                            f"✅ Second weighment completed for ticket {ticket_no}!\n"
                                            f"🎫 Ready for next vehicle: {new_ticket}")
                    except Exception as msg_error:
                        self.logger.warning(f"Could not show messagebox: {msg_error}")
                        
                elif is_update and is_first_weighment_save:
                    # UPDATE: Adding first weighment to existing record
                    print(f"🎫 TICKET FLOW DEBUG: First weighment added to existing ticket {ticket_no}")
                    
                    # Generate new ticket for next vehicle (only if we incremented)
                    if ticket_incremented:
                        self.main_form.prepare_for_next_vehicle_after_first_weighment()
                        new_ticket = self.main_form.rst_var.get()
                        print(f"🎫 TICKET FLOW DEBUG: Generated next ticket number: {new_ticket}")
                    else:
                        # Don't change the current ticket display
                        new_ticket = self.main_form.rst_var.get()
                        print(f"🎫 TICKET FLOW DEBUG: Keeping current ticket number: {new_ticket}")
                    
                    try:
                        messagebox.showinfo("First Weighment Updated", 
                                        f"✅ First weighment updated for ticket {ticket_no}!\n"
                                        f"🎫 Current ticket: {new_ticket}")
                    except Exception as msg_error:
                        self.logger.warning(f"Could not show messagebox: {msg_error}")
                
                else:
                    # Catch-all: Any other successful save
                    print(f"🎫 TICKET FLOW DEBUG: Other successful save scenario for ticket {ticket_no}")
                    
                    # Generate new ticket for next vehicle (only if we incremented)
                    if ticket_incremented:
                        self.main_form.prepare_for_new_ticket_after_completion()
                        new_ticket = self.main_form.rst_var.get()
                        print(f"🎫 TICKET FLOW DEBUG: Generated next ticket number: {new_ticket}")
                    else:
                        new_ticket = self.main_form.rst_var.get()
                        print(f"🎫 TICKET FLOW DEBUG: Keeping current ticket number: {new_ticket}")
                    
                    try:
                        messagebox.showinfo("Record Saved", 
                                        f"✅ Record saved for ticket {ticket_no}!\n"
                                        f"🎫 Current ticket: {new_ticket}")
                    except Exception as msg_error:
                        self.logger.warning(f"Could not show messagebox: {msg_error}")
                
                # Always update the summary and pending vehicles list when saving
                self.update_summary()
                self.update_pending_vehicles()
                
                print(f"🎫 TICKET FLOW DEBUG: Save operation completed successfully")
                self.logger.info("SAVE RECORD OPERATION COMPLETED SUCCESSFULLY WITH SMART TICKET FLOW")
                
            else:
                # Handle error case
                error_msg = save_result.get('error', 'Unknown error') if isinstance(save_result, dict) else 'Save operation failed'
                print(f"🎫 TICKET FLOW DEBUG: ❌ Save failed: {error_msg}")
                self.logger.error(f"❌ Failed to save record {ticket_no}: {error_msg}")
                messagebox.showerror("Error", f"Failed to save record: {error_msg}")
                
        except Exception as e:
            print(f"🎫 TICKET FLOW DEBUG: ❌ Critical error in save_record: {e}")
            self.logger.error(f"❌ Critical error in save_record: {e}")
            messagebox.showerror("Save Error", f"Critical error saving record:\n{str(e)}\n\nCheck logs for details.")
        finally:
            print("🎫 TICKET FLOW DEBUG: " + "="*50)
            self.logger.info("="*50)

    def prepare_for_next_vehicle_after_first_weighment(self):
        """Prepare form for next vehicle AFTER first weighment is saved and ticket is committed"""
        try:
            # Reset form fields for next vehicle but keep site settings
            self.vehicle_var.set("")
            self.agency_var.set("")  # Reset agency for next vehicle
            
            # Clear weighment data
            self.first_weight_var.set("")
            self.first_timestamp_var.set("")
            self.second_weight_var.set("")
            self.second_timestamp_var.set("")
            self.net_weight_var.set("")
            self.material_type_var.set("Inert")  # Reset to default
            
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
            # This is critical - the counter was already incremented, so this gets the next number
            self.reserve_next_ticket_number()
            
            # Update image status display
            if hasattr(self, 'update_image_status_display'):
                self.update_image_status_display()
            
            print(f"Form prepared for next vehicle - new ticket: {self.rst_var.get()}")
            
        except Exception as e:
            print(f"Error preparing form for next vehicle: {e}")

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

    def update_pending_vehicles(self):
        """FIXED: Update the pending vehicles panel with error handling"""
        try:
            self.logger.debug("Updating pending vehicles list")
            if hasattr(self, 'pending_vehicles') and self.pending_vehicles:
                # Check if the widget still exists before refreshing
                if hasattr(self.pending_vehicles, 'tree') and self.pending_vehicles.tree.winfo_exists():
                    self.pending_vehicles.refresh_pending_list()
                    self.logger.debug("Pending vehicles list updated successfully")
                else:
                    self.logger.warning("Pending vehicles tree widget no longer exists")
        except Exception as e:
            self.logger.error(f"Error updating pending vehicles: {e}")


    def load_pending_vehicle(self, ticket_no):
        """FIXED: Load a pending vehicle when selected from the pending vehicles panel"""
        try:
            self.logger.info(f"Loading pending vehicle: {ticket_no}")
            
            if hasattr(self, 'main_form'):
                # Switch to main tab
                self.notebook.select(0)
                
                # Load the pending ticket data into the form
                success = self.main_form.load_pending_ticket(ticket_no)
                
                if success:
                    self.logger.info(f"Successfully loaded pending ticket: {ticket_no}")
                    # Inform the user they need to capture weight manually
                    if self.is_weighbridge_connected():
                        messagebox.showinfo("Vehicle Selected", 
                                        f"Ticket {ticket_no} loaded for second weighment.\n"
                                        "Press 'Capture Weight' button when the vehicle is on the weighbridge.")
                    else:
                        messagebox.showinfo("Vehicle Selected", 
                                        f"Ticket {ticket_no} loaded for second weighment.\n"
                                        "Please connect weighbridge and capture weight when ready.")
                else:
                    self.logger.error(f"Failed to load pending ticket: {ticket_no}")
                    messagebox.showerror("Error", f"Could not load ticket {ticket_no}")
            else:
                self.logger.error("Main form not available")
                
        except Exception as e:
            self.logger.error(f"Error loading pending vehicle {ticket_no}: {e}")
            messagebox.showerror("Error", f"Error loading vehicle: {str(e)}")

    def create_header(self, parent):
            """Create compressed header with all info in single line"""
            # Main header frame
            header_frame = ttk.Frame(parent, style="TFrame")
            header_frame.pack(fill=tk.X, pady=(0, 3))
            
            # Single styled header bar with all elements in one line
            self.title_box = tk.Frame(header_frame, bg=config.COLORS["header_bg"], padx=8, pady=3)
            self.title_box.pack(fill=tk.X)
            
            # Left side - Title - FIXED: changed title_box to self.title_box
            title_label = tk.Label(self.title_box, 
                                text="Swaccha Andhra Corporation - RealTime Tracker", 
                                font=("Segoe UI", 12, "bold"),
                                fg=config.COLORS["white"],
                                bg=config.COLORS["header_bg"])
            title_label.pack(side=tk.LEFT)
            
            # Center - All info in single line with separators - FIXED: changed title_box to self.title_box
            info_frame = tk.Frame(self.title_box, bg=config.COLORS["header_bg"])
            info_frame.pack(side=tk.LEFT, expand=True, padx=15)
            
            # Build info text parts
            info_parts = []
            # Site info
            if self.selected_site:
                info_parts.append(f"Site: {self.selected_site}")
            
            # Incharge info
            if self.selected_incharge:
                info_parts.append(f"Incharge: {self.selected_incharge}")
            
            # Join all info with separators
            info_text = " • ".join(info_parts)
            
            # Single info label with all details
            info_label = tk.Label(info_frame, 
                                text=info_text,
                                font=("Segoe UI", 8),
                                fg=config.COLORS["primary_light"],
                                bg=config.COLORS["header_bg"],
                                anchor="center")
            info_label.pack(expand=True)
            
            # Right side - Date, Time and Logout - FIXED: changed title_box to self.title_box
            right_frame = tk.Frame(self.title_box, bg=config.COLORS["header_bg"])
            right_frame.pack(side=tk.RIGHT)
            
            # Date and time variables
            self.date_var = tk.StringVar()
            self.time_var = tk.StringVar()
            
            # Date and time in single line
            datetime_label = tk.Label(right_frame, 
                                    text="",  # Will be updated by update_datetime
                                    font=("Segoe UI", 8, "bold"),
                                    fg=config.COLORS["white"],
                                    bg=config.COLORS["header_bg"])
            datetime_label.pack(side=tk.LEFT, padx=(0, 10))
            
            # Store reference for datetime updates
            self.datetime_label = datetime_label
            
            # Logout button (smaller)
            logout_btn = HoverButton(right_frame, 
                                text="Logout", 
                                font=("Segoe UI", 8),
                                bg=config.COLORS["button_alt"],
                                fg=config.COLORS["white"],
                                padx=8, pady=2,
                                command=self.logout)
            logout_btn.pack(side=tk.RIGHT)

    def update_datetime(self):
        """Update date and time display in compressed format"""
        try:
            now = datetime.datetime.now()
            
            # Format: DD-MM-YYYY • HH:MM:SS
            date_str = now.strftime("%d-%m-%Y")
            time_str = now.strftime("%H:%M:%S")
            datetime_str = f"{date_str} • {time_str}"
            
            # Update individual variables if they exist (for compatibility)
            if hasattr(self, 'date_var'):
                self.date_var.set(date_str)
            if hasattr(self, 'time_var'):
                self.time_var.set(time_str)
            
            # Update combined datetime label
            if hasattr(self, 'datetime_label'):
                self.datetime_label.config(text=datetime_str)
            
            # Schedule next update
            if hasattr(self, 'root'):
                self.root.after(1000, self.update_datetime)
                
        except Exception as e:
            print(f"Error updating datetime: {e}")


    def logout(self):
        """Logout and close application"""
        try:
            self.logger.info("User logging out...")
            
            # Clean up resources
            if hasattr(self, 'main_form'):
                self.main_form.on_closing()
            
            if hasattr(self, 'settings_panel'):
                self.settings_panel.on_closing()
            
            # Reset user info
            self.logged_in_user = None
            self.user_role = None
            self.selected_site = None
            self.selected_incharge = None
            
            self.logger.info("Logout completed - closing application")
            
            # Simply close the application
            self.root.destroy()
            
        except Exception as e:
            self.logger.error(f"Error during logout: {e}")
            self.root.destroy()



    def periodic_refresh(self):
        """Periodically refresh data displays with error handling"""
        try:
            # Update pending vehicles list if it exists
            self.update_pending_vehicles()
            
            # Check if we need to update the daily PDF folder (date changed)
            if hasattr(self, 'data_manager'):
                self.data_manager.get_daily_pdf_folder()  # This will create new folder if date changed
            
        except Exception as e:
            self.logger.error(f"Error in periodic refresh: {e}")
        finally:
            # Schedule next refresh and store the job ID so we can cancel it if needed
            self._refresh_job = self.root.after(60000, self.periodic_refresh)  # Refresh every minute

    def update_weight_from_weighbridge(self, weight):
        """Update weight from weighbridge with error handling"""
        try:
            # Guard against recursive calls
            if hasattr(self, '_processing_weight_update') and self._processing_weight_update:
                return
            
            # Set processing flag
            self._processing_weight_update = True
            
            # Make the weight available to the main form
            if hasattr(self, 'settings_panel'):
                self.settings_panel.current_weight_var.set(f"{weight} kg")
                
            # Only update UI, don't perform automatic actions
            if self.notebook.index("current") == 0 and hasattr(self, 'main_form'):
                # Update the weight display
                if hasattr(self.main_form, 'current_weight_var'):
                    self.main_form.current_weight_var.set(f"{weight:.2f} kg")
                    
        except Exception as e:
            self.logger.error(f"Error updating weight from weighbridge: {e}")
        finally:
            # Clear processing flag
            self._processing_weight_update = False

    def is_weighbridge_connected(self):
        """Check if weighbridge is connected"""
        try:
            if hasattr(self, 'settings_panel') and hasattr(self.settings_panel, 'wb_status_var'):
                return self.settings_panel.wb_status_var.get() == "Status: Connected"
            return False
        except Exception as e:
            self.logger.error(f"Error checking weighbridge connection: {e}")
            return False

    def ensure_settings_persistence(self):
        """Ensure settings are properly loaded and persisted"""
        try:
            self.logger.info("Ensuring settings persistence...")
            
            # Verify settings integrity
            if not self.settings_storage.verify_settings_integrity():
                self.logger.warning("Settings integrity check failed - reinitializing")
                self.settings_storage.initialize_files()
            
            # Load and apply weighbridge settings if available
            wb_settings = self.settings_storage.get_weighbridge_settings()
            if wb_settings and wb_settings.get("com_port"):
                self.logger.info(f"Found saved weighbridge settings: {wb_settings}")
                
                # Try to auto-connect if settings are complete
                if hasattr(self, 'settings_panel'):
                    self.root.after(2000, self.settings_panel.auto_connect_weighbridge)
            
            self.logger.info("Settings persistence check completed")
            
        except Exception as e:
            self.logger.error(f"Error ensuring settings persistence: {e}")

    def update_camera_indices(self, settings):
        """Update camera settings with error handling"""
        try:
            self.logger.info(f"Updating camera settings: {settings}")
            
            if hasattr(self, 'main_form'):
                # Stop cameras if running
                if hasattr(self.main_form, 'front_camera'):
                    self.main_form.front_camera.stop_camera()
                    
                if hasattr(self.main_form, 'back_camera'):
                    self.main_form.back_camera.stop_camera()
                
                # Update camera settings
                if hasattr(self.main_form, 'update_camera_settings'):
                    self.main_form.update_camera_settings(settings)
            
            # Save settings to ensure persistence
            if hasattr(self, 'settings_storage'):
                self.settings_storage.save_camera_settings(settings)
                self.logger.info("Camera settings saved for persistence")
                
        except Exception as e:
            self.logger.error(f"Error updating camera settings: {e}")

    def update_summary(self):
        """Update the summary view with error handling"""
        try:
            if hasattr(self, 'summary_panel'):
                self.summary_panel.update_summary()
        except Exception as e:
            self.logger.error(f"Error updating summary: {e}")

    def view_records(self):
        """View all records in a separate window"""
        try:
            # Switch to the summary tab
            self.notebook.select(1)
            
            # Refresh the summary
            self.update_summary()
        except Exception as e:
            self.logger.error(f"Error viewing records: {e}")

    def clear_form(self):
        """Clear the main form with error handling"""
        try:
            if hasattr(self, 'main_form'):
                self.main_form.clear_form()
        except Exception as e:
            self.logger.error(f"Error clearing form: {e}")

    def on_closing(self):
        """Handle application closing with enhanced logging"""
        try:
            self.logger.info("Application closing - saving settings...")
            
            # Cancel any pending periodic refresh
            if hasattr(self, '_refresh_job'):
                try:
                    self.root.after_cancel(self._refresh_job)
                except:
                    pass
            
            # Save settings through settings panel
            if hasattr(self, 'settings_panel'):
                self.settings_panel.on_closing()
            
            # Clean up resources
            if hasattr(self, 'main_form'):
                self.main_form.on_closing()
            
            # Clean up connectivity if available
            if CONNECTIVITY_AVAILABLE:
                try:
                    cleanup_connectivity(self)
                except:
                    pass
            
            self.logger.info("="*60)
            self.logger.info("APPLICATION SHUTDOWN COMPLETED")
            self.logger.info("="*60)
            
            # Close the application
            self.root.destroy()
            
        except Exception as e:
            self.logger.error(f"Error during shutdown: {e}")
            self.root.destroy()

# Main entry point
if __name__ == "__main__":
    # Create root window
    root = tk.Tk()
    app = None
    
    try:
        # Create application instance
        app = TharuniApp(root)
        
        # Only start mainloop if user successfully logged in
        if app and app.logged_in_user:
            root.mainloop()
        else:
            # Authentication failed or canceled - close gracefully
            root.destroy()
            
    except Exception as e:
        # Log any critical startup errors
        print(f"Critical application error: {e}")
        import traceback
        traceback.print_exc()
        
        # Show error dialog
        try:
            from tkinter import messagebox
            messagebox.showerror("Critical Error", 
                               f"Application failed to start:\n{str(e)}\n\nCheck logs for details.")
        except:
            pass
    finally:
        try:
            if app and hasattr(app, 'on_closing'):
                app.on_closing()
            root.destroy()
        except:
            pass
        
        # Ensure clean exit
        import sys
        sys.exit(0)