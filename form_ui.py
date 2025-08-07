import tkinter as tk
from tkinter import ttk
import config
from ui_components import HoverButton

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
    
    # FIXED: New Ticket button now uses generate_next_ticket_number (manual reserve)
    auto_ticket_btn = HoverButton(form_inner, text="New", 
                                bg=config.COLORS["primary"], 
                                fg=config.COLORS["button_text"],
                                padx=4, pady=1,
                                command=self.generate_next_ticket_number)
    auto_ticket_btn.grid(row=1, column=0, sticky=tk.E, padx=(0, 5), pady=3)
    
    # Site Name Entry - Column 1
    self.site_combo = ttk.Combobox(form_inner, textvariable=self.site_var, state="readonly", width=config.STD_WIDTH)
    
    # Agency Name Combobox - Column 2 (now a dropdown)
    self.agency_combo = ttk.Combobox(form_inner, textvariable=self.agency_var, state="readonly", width=config.STD_WIDTH)
    
    # MODIFIED: Set dropdown values based on hardcoded mode
    if config.HARDCODED_MODE:
        # Use hardcoded values for comboboxes
        self.site_combo['values'] = config.HARDCODED_SITES
        self.agency_combo['values'] = config.HARDCODED_AGENCIES
        
        # Set default selections
        if config.HARDCODED_SITES:
            self.site_var.set(config.HARDCODED_SITES[0])
        if config.HARDCODED_AGENCIES:
            self.agency_var.set(config.HARDCODED_AGENCIES[0])
    else:
        # Original dynamic loading
        self.site_combo['values'] = ('Guntur',)
        self.agency_combo['values'] = ('Default Agency',)  # Default value, will be updated from settings
    
    self.site_combo.grid(row=1, column=1, sticky=tk.W, padx=3, pady=3)
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
    
    # MODIFIED: Set transfer party values based on hardcoded mode
    if config.HARDCODED_MODE:
        self.tpt_combo['values'] = config.HARDCODED_TRANSFER_PARTIES
        # Set default selection
        if config.HARDCODED_TRANSFER_PARTIES:
            self.tpt_var.set(config.HARDCODED_TRANSFER_PARTIES[0])
    else:
        self.tpt_combo['values'] = ('Advitia Labs',)  # Default value, will be updated from settings
    
    self.tpt_combo.grid(row=3, column=1, sticky=tk.W, padx=3, pady=3)
    
    # Material Type Combo - Column 2
    material_type_combo = ttk.Combobox(form_inner, 
                                    textvariable=self.material_type_var, 
                                    state="readonly", 
                                    width=config.STD_WIDTH)
    
    # MODIFIED: Set material values based on hardcoded mode
    if config.HARDCODED_MODE:
        material_type_combo['values'] = config.HARDCODED_MATERIALS
    else:
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

    # NEW ROW - Current Weight Display (Prominent 6-digit display)
    ttk.Label(weighment_frame, text="Current Weight:", font=("Segoe UI", 10, "bold")).grid(
        row=0, column=0, sticky=tk.W, padx=5, pady=5)

    # Current Weight Display (large, prominent display for up to 6 digits)
    self.current_weight_display = ttk.Label(weighment_frame, 
                                           textvariable=self.current_weight_var,
                                           font=("Segoe UI", 16, "bold"),  # Larger font for 6-digit visibility
                                           foreground=config.COLORS["primary"],
                                           background=config.COLORS["background"],
                                           width=12)  # Width to accommodate 6 digits + "kg"
    self.current_weight_display.grid(row=0, column=1, sticky=tk.W, padx=5, pady=5)

    # Status label for current weight
    self.weight_status_label = ttk.Label(weighment_frame, 
                                       text="(Showing you Live from weighbridge)", 
                                       font=("Segoe UI", 8, "italic"),
                                       foreground="gray")
    self.weight_status_label.grid(row=0, column=2, sticky=tk.W, padx=5, pady=5)

    # Capture Weight Button - spans across right side, positioned where user expects it
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

    # First Timestamp
    first_timestamp_label = ttk.Label(weighment_frame, textvariable=self.first_timestamp_var, 
                                    font=("Segoe UI", 8), foreground="blue")
    first_timestamp_label.grid(row=1, column=1, sticky=tk.E, padx=5, pady=5)

    # Second Row - Second Weighment
    ttk.Label(weighment_frame, text="Second Weighment:", font=("Segoe UI", 9, "bold")).grid(
        row=2, column=0, sticky=tk.W, padx=5, pady=5)

    # Second Weight Entry (read-only)
    self.second_weight_entry = ttk.Entry(weighment_frame, textvariable=self.second_weight_var, 
                                    width=12, style="Weight.TEntry", state="readonly")
    self.second_weight_entry.grid(row=2, column=1, sticky=tk.W, padx=5, pady=5)

    # Second Timestamp
    second_timestamp_label = ttk.Label(weighment_frame, textvariable=self.second_timestamp_var, 
                                     font=("Segoe UI", 8), foreground="blue")
    second_timestamp_label.grid(row=2, column=1, sticky=tk.E, padx=5, pady=5)

    # Third Row - Net Weight
    ttk.Label(weighment_frame, text="Net Weight:", font=("Segoe UI", 9, "bold")).grid(
        row=3, column=0, sticky=tk.W, padx=5, pady=5)

    # Net Weight Display (read-only)
    net_weight_display = ttk.Entry(weighment_frame, textvariable=self.net_weight_var, 
                                width=12, state="readonly", style="Weight.TEntry")
    net_weight_display.grid(row=3, column=1, sticky=tk.W, padx=5, pady=5)

    # Current weighment state indicator
    state_frame = ttk.Frame(weighment_frame)
    state_frame.grid(row=4, column=0, columnspan=4, sticky=tk.EW, padx=5, pady=(10,5))

    state_label = ttk.Label(state_frame, text="Current State: ", font=("Segoe UI", 9))
    state_label.pack(side=tk.LEFT)

    state_value_label = ttk.Label(state_frame, textvariable=self.weighment_state_var, 
                                font=("Segoe UI", 9, "bold"), foreground=config.COLORS["primary"])
    state_value_label.pack(side=tk.LEFT)

    # FIXED: Updated note about ticket increment behavior
    weight_note = ttk.Label(state_frame, 
                          text="💡 Ticket number increments only after BOTH weighments are completed", 
                          font=("Segoe UI", 8, "italic"), 
                          foreground="green")
    weight_note.pack(side=tk.RIGHT)
            
    # Image status indicators
    image_status_frame = ttk.Frame(form_inner)
    image_status_frame.grid(row=5, column=0, columnspan=3, sticky=tk.W, padx=3, pady=3)
    
    ttk.Label(image_status_frame, text="Images:").pack(side=tk.LEFT, padx=(0, 5))
    
    self.front_image_status_var = tk.StringVar(value="Front: ✗")
    self.front_image_status = ttk.Label(image_status_frame, textvariable=self.front_image_status_var, foreground="red")
    self.front_image_status.pack(side=tk.LEFT, padx=(0, 5))
    
    self.back_image_status_var = tk.StringVar(value="Back: ✗")
    self.back_image_status = ttk.Label(image_status_frame, textvariable=self.back_image_status_var, foreground="red")
    self.back_image_status.pack(side=tk.LEFT)