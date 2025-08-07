import tkinter as tk
from tkinter import ttk
import config

class HoverButton(tk.Button):
    """Button that changes color on hover"""
    def __init__(self, master, **kw):
        super().__init__(master, **kw)
        self.defaultBackground = self["background"]
        self.defaultForeground = self["foreground"]
        self.bind("<Enter>", self.on_enter)
        self.bind("<Leave>", self.on_leave)

    def on_enter(self, e):
        """Mouse enters button"""
        if self["state"] != "disabled":
            if self.defaultBackground == config.COLORS["primary"]:
                self["background"] = config.COLORS["button_hover"]
            elif self.defaultBackground == config.COLORS["secondary"]:
                self["background"] = "#00A896"  # Darker teal
            elif self.defaultBackground == config.COLORS["button_alt"]:
                self["background"] = config.COLORS["button_alt_hover"]
            elif self.defaultBackground == config.COLORS["error"]:
                self["background"] = "#D32F2F"  # Darker red

    def on_leave(self, e):
        """Mouse leaves button"""
        if self["state"] != "disabled":
            self["background"] = self.defaultBackground

# Add this to the create_styles() function in ui_components.py

def create_styles():
    """Create styles for widgets"""
    style = ttk.Style()
    
    # Configure theme
    style.theme_use('clam')
    
    # Label styles
    style.configure("TLabel", 
                    font=("Segoe UI", 9),
                    background=config.COLORS["background"],
                    foreground=config.COLORS["text"])
    
    # Title label style
    style.configure("Title.TLabel", 
                   font=("Segoe UI", 14, "bold"),
                   foreground=config.COLORS["primary"],
                   background=config.COLORS["background"])
    
    # Subtitle label style
    style.configure("Subtitle.TLabel", 
                   font=("Segoe UI", 11, "bold"),
                   foreground=config.COLORS["primary"],
                   background=config.COLORS["background"])
    
    # Entry style
    style.configure("TEntry", 
                   font=("Segoe UI", 9),
                   fieldbackground=config.COLORS["white"])
    style.map("TEntry",
             fieldbackground=[("readonly", config.COLORS["primary_light"])])
    
    # Special Weight Entry style with larger font and highlighted background
    style.configure("Weight.TEntry", 
                   font=("Segoe UI", 10, "bold"),
                   fieldbackground=config.COLORS["white"])
    style.map("Weight.TEntry",
             fieldbackground=[("readonly", "#E3F2FD")], # Light blue background
             foreground=[("readonly", config.COLORS["primary"])])
    
    # Combobox style
    style.configure("TCombobox", 
                   font=("Segoe UI", 9))
    
    # Button style
    style.configure("TButton", 
                   font=("Segoe UI", 9, "bold"),
                   background=config.COLORS["primary"],
                   foreground=config.COLORS["button_text"])
    style.map("TButton",
             background=[("active", config.COLORS["button_hover"])])
    
    # Frame style
    style.configure("TFrame", 
                   background=config.COLORS["background"])
    
    # LabelFrame style
    style.configure("TLabelframe", 
                   font=("Segoe UI", 9, "bold"),
                   background=config.COLORS["form_bg"])
    style.configure("TLabelframe.Label", 
                   font=("Segoe UI", 9, "bold"),
                   foreground=config.COLORS["primary"],
                   background=config.COLORS["background"])
                   
    # Notebook style
    style.configure("TNotebook", 
                  background=config.COLORS["background"],
                  tabmargins=[2, 5, 2, 0])
    style.configure("TNotebook.Tab", 
                  font=("Segoe UI", 9),
                  background=config.COLORS["primary_light"],
                  foreground=config.COLORS["text"],
                  padding=[8, 3])
    style.map("TNotebook.Tab",
            background=[("selected", config.COLORS["primary"])],
            foreground=[("selected", config.COLORS["white"])])
    
    # Treeview style
    style.configure("Treeview", 
                  font=("Segoe UI", 9),
                  background=config.COLORS["white"],
                  foreground=config.COLORS["text"],
                  fieldbackground=config.COLORS["white"])
    style.configure("Treeview.Heading", 
                  font=("Segoe UI", 9, "bold"),
                  background=config.COLORS["table_header_bg"],
                  foreground=config.COLORS["text"])
    style.map("Treeview",
            background=[("selected", config.COLORS["primary_light"])],
            foreground=[("selected", config.COLORS["primary"])])
    
    return style