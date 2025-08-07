import tkinter as tk
from tkinter import ttk, messagebox

import config
from ui_components import HoverButton

class LoginDialog:
    """Login dialog for application authentication"""
    
    def __init__(self, parent, settings_storage, show_select=False):
        """Initialize login dialog
        
        Args:
            parent: Parent window
            settings_storage: Settings storage instance
            show_select: Whether to show user/site selection dropdowns
        """
        self.parent = parent
        self.settings_storage = settings_storage
        self.show_select = show_select
        self.result = False  # Login success flag
        self.role = None  # User role
        self.username = None  # Username
        self.site = None  # Selected site
        self.incharge = None  # Selected site incharge
        
        # Create login window
        self.create_dialog()
    
    def create_dialog(self):
        """Create login dialog UI"""
        # Create top level window
        self.window = tk.Toplevel(self.parent)
        self.window.title("Login - Swaccha Andhra Corporation")
        self.window.geometry("450x450")  # Increased size for better visibility
        self.window.resizable(False, False)
        self.window.transient(self.parent)  # Make window modal
        self.window.grab_set()  # Make window modal
        
        # Center the dialog
        self.center_dialog()
        
        # Bind parent resizing to recenter dialog
        self.parent.bind("<Configure>", self.center_dialog)
        
        # Apply style
        main_frame = ttk.Frame(self.window, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Logo/Title frame
        logo_frame = ttk.Frame(main_frame)
        logo_frame.pack(fill=tk.X, pady=(0, 20))
        
        # Title
        title_label = ttk.Label(logo_frame, text="Swaccha Andhra Corporation", font=("Segoe UI", 22, "bold"))  # Increased font size
        title_label.pack(pady=5)
        
        # Subtitle
        subtitle_label = ttk.Label(logo_frame, text="Legacy monitor powered by Advitia Labs", font=("Segoe UI", 14))  # Increased font size
        subtitle_label.pack(pady=5)
        
        # Form fields
        form_frame = ttk.Frame(main_frame)
        form_frame.pack(fill=tk.X, pady=10)
        
        # User selection (only shown if show_select is True)
        if self.show_select:
            # User selection frame
            user_select_frame = ttk.Frame(form_frame)
            user_select_frame.pack(fill=tk.X, pady=8)  # Increased padding
            
            ttk.Label(user_select_frame, text="User:", font=("Segoe UI", 12)).pack(side=tk.LEFT, padx=5)  # Increased font size
            
            # Get users for dropdown
            users = self.settings_storage.get_users()
            usernames = list(users.keys())
            
            self.username_var = tk.StringVar()
            username_combo = ttk.Combobox(user_select_frame, textvariable=self.username_var, 
                                        values=usernames, font=("Segoe UI", 12), width=23)  # Increased font size
            username_combo.pack(side=tk.RIGHT, padx=5)
            if usernames:
                username_combo.current(0)
            
            # Site selection frame
            site_select_frame = ttk.Frame(form_frame)
            site_select_frame.pack(fill=tk.X, pady=8)  # Increased padding
            
            ttk.Label(site_select_frame, text="Site:", font=("Segoe UI", 12)).pack(side=tk.LEFT, padx=5)  # Increased font size
            
            # Get sites for dropdown
            sites_data = self.settings_storage.get_sites()
            sites = sites_data.get("sites", ["Guntur"])
            
            self.site_var = tk.StringVar()
            site_combo = ttk.Combobox(site_select_frame, textvariable=self.site_var, 
                                    values=sites, font=("Segoe UI", 12), width=23)  # Increased font size
            site_combo.pack(side=tk.RIGHT, padx=5)
            if sites:
                site_combo.current(0)
                
            # Site Incharge selection frame
            incharge_select_frame = ttk.Frame(form_frame)
            incharge_select_frame.pack(fill=tk.X, pady=8)  # Increased padding
            
            ttk.Label(incharge_select_frame, text="Incharge:", font=("Segoe UI", 12)).pack(side=tk.LEFT, padx=5)  # Increased font size
            
            # Get incharges for dropdown
            incharges = sites_data.get("incharges", ["Site Manager"])
            
            self.incharge_var = tk.StringVar()
            incharge_combo = ttk.Combobox(incharge_select_frame, textvariable=self.incharge_var, 
                                       values=incharges, font=("Segoe UI", 12), width=23)  # Increased font size
            incharge_combo.pack(side=tk.RIGHT, padx=5)
            if incharges:
                incharge_combo.current(0)
        else:
            # Username entry
            username_frame = ttk.Frame(form_frame)
            username_frame.pack(fill=tk.X, pady=8)  # Increased padding
            
            ttk.Label(username_frame, text="Username:", font=("Segoe UI", 12)).pack(side=tk.LEFT, padx=5)  # Increased font size
            self.username_var = tk.StringVar()
            username_entry = ttk.Entry(username_frame, textvariable=self.username_var, 
                                      width=25, font=("Segoe UI", 12))  # Increased font size
            username_entry.pack(side=tk.RIGHT, padx=5)
            username_entry.focus_set()  # Set focus to username
        
        # Password
        password_frame = ttk.Frame(form_frame)
        password_frame.pack(fill=tk.X, pady=8)  # Increased padding
        
        ttk.Label(password_frame, text="Password:", font=("Segoe UI", 12)).pack(side=tk.LEFT, padx=5)  # Increased font size
        self.password_var = tk.StringVar()
        password_entry = ttk.Entry(password_frame, textvariable=self.password_var, 
                                 show="*", width=25, font=("Segoe UI", 12))  # Increased font size
        password_entry.pack(side=tk.RIGHT, padx=5)
        
        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=(20, 0))
        
        login_btn = HoverButton(button_frame, text="Login", 
                              bg=config.COLORS["primary"],
                              fg=config.COLORS["button_text"],
                              font=("Segoe UI", 12, "bold"),  # Increased font size
                              padx=20, pady=7,  # Increased padding
                              command=self.login)
        login_btn.pack(side=tk.LEFT, padx=5)
        
        exit_btn = HoverButton(button_frame, text="Exit", 
                             bg=config.COLORS["error"],
                             fg=config.COLORS["button_text"],
                             font=("Segoe UI", 12),  # Increased font size
                             padx=20, pady=7,  # Increased padding
                             command=self.exit_app)
        exit_btn.pack(side=tk.RIGHT, padx=5)
        
        # Status message with increased size
        self.status_var = tk.StringVar()
        self.status_label = ttk.Label(main_frame, textvariable=self.status_var, 
                               foreground="green", font=("Segoe UI", 10, "bold"))  # Increased font size and made bold
        self.status_label.pack(pady=(15, 0))
        
        # Set default credentials hint
        self.status_var.set("For support, contact Advitia Labs at +91-6303 640 757")
        
        # Bind Enter key to login
        self.window.bind("<Return>", lambda event: self.login())
        
        # Wait for window to be destroyed
        self.parent.wait_window(self.window)
    
    def center_dialog(self, event=None):
        """Center the dialog on parent window, even after parent resize"""
        if not hasattr(self, 'window') or not self.window.winfo_exists():
            return
            
        # Get parent window dimensions and position
        parent_width = self.parent.winfo_width()
        parent_height = self.parent.winfo_height()
        parent_x = self.parent.winfo_rootx()
        parent_y = self.parent.winfo_rooty()
        
        # Get dialog dimensions
        dialog_width = self.window.winfo_width()
        dialog_height = self.window.winfo_height()
        
        # Calculate center position
        x = parent_x + (parent_width - dialog_width) // 2
        y = parent_y + (parent_height - dialog_height) // 2
        
        # Make sure the position is not off-screen
        if x < 0:
            x = 0
        if y < 0:
            y = 0
            
        # Set the dialog position
        self.window.geometry(f"+{x}+{y}")
    
    def login(self):
        """Handle login"""
        username = self.username_var.get().strip()
        password = self.password_var.get()
        
        if not username or not password:
            self.status_var.set("Please enter username and password")
            self.status_label.configure(foreground="red")
            return
        
        # Authenticate
        success, role = self.settings_storage.authenticate_user(username, password)
        
        if success:
            self.result = True
            self.role = role
            self.username = username
            if hasattr(self, 'site_var'):
                self.site = self.site_var.get()
            if hasattr(self, 'incharge_var'):
                self.incharge = self.incharge_var.get()
            self.window.destroy()
        else:
            # Show clear error message for wrong password
            self.status_var.set("Invalid username or password")
            self.status_label.configure(foreground="red")
    
    def exit_app(self):
        """Exit application"""
        self.result = False
        # Signal to exit application
        self.parent.quit()
        self.window.destroy()