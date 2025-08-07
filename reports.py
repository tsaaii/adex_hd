import os
import datetime
import csv
import pandas as pd
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import json
import config
import tkcalendar
import numpy as np  # Add this line to your imports


# Try to import optional dependencies
try:
    from tkcalendar import DateEntry
    CALENDAR_AVAILABLE = True
except ImportError:
    CALENDAR_AVAILABLE = False
    print("tkcalendar not available - using basic date entry")

try:
    from reportlab.lib.pagesizes import letter, A4, landscape  # Added landscape import
    from reportlab.lib import colors
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image as RLImage, PageBreak
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.pdfgen import canvas
    from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
    import cv2

    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False
    landscape = None  # Define fallback if import fails
    print("ReportLab not available - PDF generation will be limited")

class SimpleTimePicker(tk.Frame):
    """A simple time picker with dropdown selectors"""
    
    def __init__(self, parent, initial_time="00:00:00", **kwargs):
        super().__init__(parent, **kwargs)
        
        # Parse initial time
        try:
            time_parts = initial_time.split(':')
            hour = int(time_parts[0])
            minute = int(time_parts[1])
        except:
            hour, minute = 0, 0
        
        # Hour dropdown (00-23)
        self.hour_var = tk.StringVar(value=f"{hour:02d}")
        self.hour_combo = ttk.Combobox(self, textvariable=self.hour_var, width=3, state="readonly")
        self.hour_combo['values'] = [f"{i:02d}" for i in range(24)]
        self.hour_combo.pack(side=tk.LEFT)
        
        # Separator
        ttk.Label(self, text=":").pack(side=tk.LEFT)
        
        # Minute dropdown (00-59)
        self.minute_var = tk.StringVar(value=f"{minute:02d}")
        self.minute_combo = ttk.Combobox(self, textvariable=self.minute_var, width=3, state="readonly")
        self.minute_combo['values'] = [f"{i:02d}" for i in range(0, 60, 5)]  # 5-minute intervals
        self.minute_combo.pack(side=tk.LEFT)
        
        # Separator
        ttk.Label(self, text=":00").pack(side=tk.LEFT)  # Fixed seconds to 00
    
    def get_time(self):
        """Get the selected time as HH:MM:SS string"""
        hour = self.hour_var.get()
        minute = self.minute_var.get()
        return f"{hour}:{minute}:00"
    
    def set_time(self, time_string):
        """Set the time (HH:MM:SS format)"""
        try:
            time_parts = time_string.split(':')
            hour = int(time_parts[0])
            minute = int(time_parts[1])
            
            self.hour_var.set(f"{hour:02d}")
            # Round minute to nearest 5
            minute = (minute // 5) * 5
            self.minute_var.set(f"{minute:02d}")
        except:
            self.hour_var.set("00")
            self.minute_var.set("00")


class ReportGenerator:
    """Enhanced report generator with selection and filtering capabilities"""
    
    def __init__(self, parent, data_manager=None):
        """Initialize the report generator
        
        Args:
            parent: Parent widget (can be None for legacy functions)
            data_manager: Data manager instance
        """
        self.parent = parent
        self.data_manager = data_manager
        self.selected_records = []
        self.address_config = self.load_address_config()
        self.all_records = []
        self.report_window = None  # Initialize as None
        
        # Ensure reports folder exists
        self.reports_folder = config.REPORTS_FOLDER
        os.makedirs(self.reports_folder, exist_ok=True)
        
    def load_address_config(self):
        """Load address configuration from JSON file"""
        try:
            config_file = os.path.join(config.DATA_FOLDER, 'address_config.json')
            if os.path.exists(config_file):
                with open(config_file, 'r') as f:
                    return json.load(f)
            else:
                # Create default config
                default_config = {
                    "agencies": {
                        "Default Agency": {
                            "name": "Default Agency",
                            "address": "123 Main Street\nCity, State - 123456",
                            "contact": "+91-1234567890",
                            "email": "info@agency.com"
                        },
                        "Tharuni": {
                            "name": "Tharuni Environmental Services",
                            "address": "Environmental Complex\nGuntur, Andhra Pradesh - 522001",
                            "contact": "+91-9876543210",
                            "email": "info@tharuni.com"
                        }
                    },
                    "sites": {
                        "Guntur": {
                            "name": "Guntur Processing Site",
                            "address": "Industrial Area, Guntur\nAndhra Pradesh - 522001",
                            "contact": "+91-9876543210"
                        },
                        "Addanki": {
                            "name": "Addanki Collection Center",
                            "address": "Main Road, Addanki\nAndhra Pradesh - 523201",
                            "contact": "+91-9876543211"
                        }
                    }
                }
                
                # Save default config
                os.makedirs(config.DATA_FOLDER, exist_ok=True)
                with open(config_file, 'w') as f:
                    json.dump(default_config, f, indent=4)
                
                return default_config
        except Exception as e:
            print(f"Error loading address config: {e}")
            return {"agencies": {}, "sites": {}}
    
    def show_report_dialog(self):
        """Show the enhanced report selection dialog"""
        # Create report dialog window
        self.report_window = tk.Toplevel(self.parent)
        self.report_window.title("Generate Reports - Select Records")
        self.report_window.geometry("1000x750")
        self.report_window.resizable(True, True)
        
        # Configure grid weights
        self.report_window.columnconfigure(0, weight=1)
        self.report_window.rowconfigure(1, weight=1)
        
        # Create main frames
        self.create_filter_frame()
        self.create_selection_frame()
        self.create_action_frame()
        
        # Load initial data
        self.refresh_records()
    
    def create_filter_frame(self):
        """Create the filter frame with simple time picker dropdowns"""
        filter_frame = ttk.LabelFrame(self.report_window, text="Filter Records", padding=5)
        filter_frame.grid(row=0, column=0, sticky="ew", padx=10, pady=5)
        filter_frame.columnconfigure(1, weight=1)
        filter_frame.columnconfigure(3, weight=1)
        
        # Row 0: Date Range
        ttk.Label(filter_frame, text="From Date:").grid(row=0, column=0, sticky="w", padx=5, pady=5)
        
        if CALENDAR_AVAILABLE:
            self.from_date = DateEntry(filter_frame, width=12, background='darkblue',
                                    foreground='white', borderwidth=2,
                                    date_pattern='dd-mm-yyyy')
        else:
            self.from_date = ttk.Entry(filter_frame, width=15)
            self.from_date.insert(0, "DD-MM-YYYY")
        
        self.from_date.grid(row=0, column=1, sticky="w", padx=5, pady=5)
        
        ttk.Label(filter_frame, text="To Date:").grid(row=0, column=2, sticky="w", padx=5, pady=5)
        
        if CALENDAR_AVAILABLE:
            self.to_date = DateEntry(filter_frame, width=12, background='darkblue',
                                    foreground='white', borderwidth=2,
                                    date_pattern='dd-mm-yyyy')
            # Set default date range (last 30 days)
            end_date = datetime.datetime.now()
            start_date = end_date - datetime.timedelta(days=30)
            self.from_date.set_date(start_date.date())
            self.to_date.set_date(end_date.date())
        else:
            self.to_date = ttk.Entry(filter_frame, width=15)
            self.to_date.insert(0, "DD-MM-YYYY")
        
        self.to_date.grid(row=0, column=3, sticky="w", padx=5, pady=5)
        
        # Row 1: Time Range with Simple Time Pickers
        ttk.Label(filter_frame, text="From Time:").grid(row=1, column=0, sticky="w", padx=5, pady=5)
        
        # Simple time picker for from time
        self.from_time_picker = SimpleTimePicker(filter_frame, initial_time="00:00:00")
        self.from_time_picker.grid(row=1, column=1, sticky="w", padx=5, pady=5)
        
        ttk.Label(filter_frame, text="To Time:").grid(row=1, column=2, sticky="w", padx=5, pady=5)
        
        # Simple time picker for to time
        self.to_time_picker = SimpleTimePicker(filter_frame, initial_time="23:55:00")
        self.to_time_picker.grid(row=1, column=3, sticky="w", padx=5, pady=5)
        
        # Row 2: Vehicle Number filter
        ttk.Label(filter_frame, text="Vehicle No:").grid(row=2, column=0, sticky="w", padx=5, pady=5)
        self.vehicle_var = tk.StringVar()
        vehicle_entry = ttk.Entry(filter_frame, textvariable=self.vehicle_var)
        vehicle_entry.grid(row=2, column=1, sticky="ew", padx=5, pady=5)
        
        # Transfer Party filter
        ttk.Label(filter_frame, text="Transfer Party:").grid(row=2, column=2, sticky="w", padx=5, pady=5)
        self.transfer_party_var = tk.StringVar()
        self.transfer_party_combo = ttk.Combobox(filter_frame, textvariable=self.transfer_party_var)
        self.transfer_party_combo.grid(row=2, column=3, sticky="ew", padx=5, pady=5)
        
        # Row 3: Material filter
        ttk.Label(filter_frame, text="Material:").grid(row=3, column=0, sticky="w", padx=5, pady=5)
        self.material_var = tk.StringVar()
        self.material_combo = ttk.Combobox(filter_frame, textvariable=self.material_var)
        self.material_combo.grid(row=3, column=1, sticky="ew", padx=5, pady=5)
        
        # Record status filter
        ttk.Label(filter_frame, text="Status:").grid(row=3, column=2, sticky="w", padx=5, pady=5)
        self.status_var = tk.StringVar(value="All")
        status_combo = ttk.Combobox(filter_frame, textvariable=self.status_var, 
                                values=["All", "Complete", "Incomplete"], state="readonly")
        status_combo.grid(row=3, column=3, sticky="ew", padx=5, pady=5)
        
        # Buttons frame
        button_frame = ttk.Frame(filter_frame)
        button_frame.grid(row=4, column=0, columnspan=4, pady=15)
        
        # Apply filter button
        filter_btn = ttk.Button(button_frame, text="Apply Filters", command=self.apply_filters)
        filter_btn.pack(side=tk.LEFT, padx=5)
        
        # Clear filters button
        clear_btn = ttk.Button(button_frame, text="Clear Filters", command=self.clear_filters)
        clear_btn.pack(side=tk.LEFT, padx=5)
        
        # Refresh button
        refresh_btn = ttk.Button(button_frame, text="Refresh Data", command=self.refresh_records)
        refresh_btn.pack(side=tk.LEFT, padx=5)


    # Enhanced apply_filters method with time filtering
    def apply_filters(self):
        """Apply filters using simple time picker dropdowns"""
        filtered_records = []
        
        # Get filter values
        from_date_str = ""
        to_date_str = ""
        
        if CALENDAR_AVAILABLE:
            try:
                from_date_str = self.from_date.get_date().strftime("%d-%m-%Y")
                to_date_str = self.to_date.get_date().strftime("%d-%m-%Y")
            except:
                pass
        else:
            from_date_str = self.from_date.get().strip()
            to_date_str = self.to_date.get().strip()
        
        # Get time values from simple time pickers
        from_time_str = self.from_time_picker.get_time()
        to_time_str = self.to_time_picker.get_time()
        
        vehicle_filter = self.vehicle_var.get().strip().lower()
        transfer_party_filter = self.transfer_party_var.get().strip().lower()
        material_filter = self.material_var.get().strip().lower()
        status_filter = self.status_var.get()
        
        for record in self.all_records:
            # Date and Time filter
            if from_date_str and to_date_str:
                try:
                    record_date = datetime.datetime.strptime(record.get('date', ''), "%d-%m-%Y")
                    from_date = datetime.datetime.strptime(from_date_str, "%d-%m-%Y")
                    to_date = datetime.datetime.strptime(to_date_str, "%d-%m-%Y")
                    
                    # Check date range first
                    if not (from_date.date() <= record_date.date() <= to_date.date()):
                        continue
                    
                    # Time filtering logic
                    record_time_str = record.get('time', '00:00:00').strip()
                    if record_time_str:
                        try:
                            # Combine date and time for accurate comparison
                            record_datetime_str = f"{record.get('date', '')} {record_time_str}"
                            record_datetime = datetime.datetime.strptime(record_datetime_str, "%d-%m-%Y %H:%M:%S")
                            
                            # Create from and to datetime objects
                            from_datetime_str = f"{from_date_str} {from_time_str}"
                            to_datetime_str = f"{to_date_str} {to_time_str}"
                            
                            from_datetime = datetime.datetime.strptime(from_datetime_str, "%d-%m-%Y %H:%M:%S")
                            to_datetime = datetime.datetime.strptime(to_datetime_str, "%d-%m-%Y %H:%M:%S")
                            
                            # Check if record falls within the datetime range
                            if not (from_datetime <= record_datetime <= to_datetime):
                                continue
                                
                        except ValueError:
                            # If time parsing fails, fall back to date-only comparison
                            pass
                            
                except ValueError:
                    # If date parsing fails, skip this record
                    pass
            
            # Apply other filters
            if vehicle_filter:
                vehicle_no = record.get('vehicle_no', '').lower()
                if vehicle_filter not in vehicle_no:
                    continue
            
            if transfer_party_filter:
                transfer_party = record.get('transfer_party_name', '').lower()
                if transfer_party_filter not in transfer_party:
                    continue
            
            if material_filter:
                material = record.get('material', '').lower()
                if material_filter not in material:
                    continue
            
            if status_filter != "All":
                first_weight = record.get('first_weight', '').strip()
                second_weight = record.get('second_weight', '').strip()
                is_complete = bool(first_weight and second_weight)
                
                if status_filter == "Complete" and not is_complete:
                    continue
                elif status_filter == "Incomplete" and is_complete:
                    continue
            
            filtered_records.append(record)
        
        # Update the treeview
        self.update_records_display(filtered_records)

    # Helper method to validate time format
    def validate_time_format(self, time_str):
        """Validate time format HH:MM:SS"""
        try:
            datetime.datetime.strptime(time_str, "%H:%M:%S")
            return True
        except ValueError:
            return False


    # Enhanced clear_filters method
    def clear_filters(self):
        """Clear all filters including simple time pickers"""
        if CALENDAR_AVAILABLE:
            # Reset date range
            end_date = datetime.datetime.now()
            start_date = end_date - datetime.timedelta(days=30)
            self.from_date.set_date(start_date.date())
            self.to_date.set_date(end_date.date())
        else:
            self.from_date.delete(0, tk.END)
            self.to_date.delete(0, tk.END)
            self.from_date.insert(0, "DD-MM-YYYY")
            self.to_date.insert(0, "DD-MM-YYYY")
        
        # Reset simple time pickers
        self.from_time_picker.set_time("00:00:00")
        self.to_time_picker.set_time("23:55:00")
        
        self.vehicle_var.set("")
        self.transfer_party_var.set("")
        self.material_var.set("")
        self.status_var.set("All")
        
        # Refresh display
        self.apply_filters()


    # Enhanced record selection methods
    def create_selection_frame(self):
        """Create the record selection frame with enhanced functionality"""
        selection_frame = ttk.LabelFrame(self.report_window, text="Select Records for Export", padding=5)
        selection_frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=5)
        selection_frame.columnconfigure(0, weight=1)
        selection_frame.rowconfigure(1, weight=1)
        
        # Selection controls
        control_frame = ttk.Frame(selection_frame)
        control_frame.grid(row=0, column=0, sticky="ew", pady=5)
        
        # Select all/none buttons
        select_all_btn = ttk.Button(control_frame, text="Select All", command=self.select_all_records)
        select_all_btn.pack(side=tk.LEFT, padx=5)
        
        select_none_btn = ttk.Button(control_frame, text="Select None", command=self.select_no_records)
        select_none_btn.pack(side=tk.LEFT, padx=5)
        
        # NEW: Toggle selection mode info
        info_label = ttk.Label(control_frame, text="Double-click any record to toggle selection", 
                            font=("Arial", 9, "italic"))
        info_label.pack(side=tk.LEFT, padx=20)
        
        # Records count label
        self.records_count_var = tk.StringVar(value="Records: 0 | Selected: 0")
        count_label = ttk.Label(control_frame, textvariable=self.records_count_var)
        count_label.pack(side=tk.RIGHT, padx=5)
        
        # Create treeview for record selection
        tree_frame = ttk.Frame(selection_frame)
        tree_frame.grid(row=1, column=0, sticky="nsew", pady=5)
        tree_frame.columnconfigure(0, weight=1)
        tree_frame.rowconfigure(0, weight=1)
        
        # Define columns including time
        columns = ("select", "ticket", "date", "time", "vehicle", "agency", "material", "first_weight", "second_weight", "status")
        self.records_tree = ttk.Treeview(tree_frame, columns=columns, show="headings", height=15)
        
        # Define headings
        self.records_tree.heading("select", text="☐")
        self.records_tree.heading("ticket", text="Ticket No")
        self.records_tree.heading("date", text="Date")
        self.records_tree.heading("time", text="Time")  # NEW COLUMN
        self.records_tree.heading("vehicle", text="Vehicle No")
        self.records_tree.heading("agency", text="Agency")
        self.records_tree.heading("material", text="Material")
        self.records_tree.heading("first_weight", text="First Weight")
        self.records_tree.heading("second_weight", text="Second Weight")
        self.records_tree.heading("status", text="Status")
        
        # Define column widths
        self.records_tree.column("select", width=30, minwidth=30)
        self.records_tree.column("ticket", width=80, minwidth=80)
        self.records_tree.column("date", width=80, minwidth=80)
        self.records_tree.column("time", width=70, minwidth=70)  # NEW COLUMN
        self.records_tree.column("vehicle", width=100, minwidth=100)
        self.records_tree.column("agency", width=120, minwidth=120)
        self.records_tree.column("material", width=80, minwidth=80)
        self.records_tree.column("first_weight", width=80, minwidth=80)
        self.records_tree.column("second_weight", width=80, minwidth=80)
        self.records_tree.column("status", width=80, minwidth=80)
        
        # Add scrollbars
        v_scrollbar = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self.records_tree.yview)
        h_scrollbar = ttk.Scrollbar(tree_frame, orient=tk.HORIZONTAL, command=self.records_tree.xview)
        self.records_tree.configure(yscrollcommand=v_scrollbar.set, xscrollcommand=h_scrollbar.set)
        
        # Pack treeview and scrollbars
        self.records_tree.grid(row=0, column=0, sticky="nsew")
        v_scrollbar.grid(row=0, column=1, sticky="ns")
        h_scrollbar.grid(row=1, column=0, sticky="ew")
        
        # ENHANCED: Multiple event bindings for better record selection
        self.records_tree.bind("<Double-1>", self.toggle_record_selection)
        self.records_tree.bind("<Button-1>", self.on_tree_click)  # Single click support
        self.records_tree.bind("<Return>", self.toggle_record_selection)  # Enter key support
        self.records_tree.bind("<space>", self.toggle_record_selection)  # Spacebar support


    # Enhanced update_records_display method
    def update_records_display(self, records):
        """Update the treeview with filtered records including time column"""
        # Clear existing items
        for item in self.records_tree.get_children():
            self.records_tree.delete(item)
        
        # Add records
        for record in records:
            ticket_no = record.get('ticket_no', '')
            date = record.get('date', '')
            time = record.get('time', '')  # NEW: Include time field
            vehicle_no = record.get('vehicle_no', '')
            agency = record.get('agency_name', '')
            material = record.get('material', '')
            first_weight = record.get('first_weight', '')
            second_weight = record.get('second_weight', '')
            
            # Determine status
            status = "Complete" if (first_weight and second_weight) else "Incomplete"
            
            # Check if record is already selected
            select_symbol = "☑" if ticket_no in self.selected_records else "☐"
            
            self.records_tree.insert("", "end", values=(
                select_symbol, ticket_no, date, time, vehicle_no, agency, material, 
                first_weight, second_weight, status
            ), tags=(ticket_no,))
        
        # Update count
        self.update_selection_count()


    # Enhanced toggle_record_selection method
    def toggle_record_selection(self, event):
        """Enhanced toggle selection of a record with better error handling"""
        # Get the item that was clicked/selected
        if event.type == '4':  # Button-1 (single click)
            item = self.records_tree.identify('item', event.x, event.y)
            column = self.records_tree.identify('column', event.x, event.y)
            # Only toggle if clicking on the select column or if double-clicking anywhere
            if column != '#1':  # Not clicking on select column
                return
        else:  # Double-click, Enter, or Space
            selection = self.records_tree.selection()
            item = selection[0] if selection else None
        
        if not item:
            return
        
        try:
            values = list(self.records_tree.item(item, 'values'))
            if len(values) < 2:  # Ensure we have enough columns
                return
                
            ticket_no = values[1]  # Ticket number is at index 1
            
            if values[0] == "☐":  # Not selected
                values[0] = "☑"
                if ticket_no not in self.selected_records:
                    self.selected_records.append(ticket_no)
            else:  # Selected
                values[0] = "☐"
                if ticket_no in self.selected_records:
                    self.selected_records.remove(ticket_no)
            
            self.records_tree.item(item, values=values)
            self.update_selection_count()
            
            # Optional: Provide visual feedback
            self.records_tree.selection_set(item)  # Keep item selected for visual feedback
            
        except Exception as e:
            print(f"Error toggling record selection: {e}")


    # Enhanced on_tree_click method
    def on_tree_click(self, event):
        """Handle tree click events with improved detection"""
        item = self.records_tree.identify('item', event.x, event.y)
        column = self.records_tree.identify('column', event.x, event.y)
        
        if item and column == '#1':  # Click on select column
            # Select the item first
            self.records_tree.selection_set(item)
            # Then toggle selection
            self.toggle_record_selection(event)


    # Enhanced get_detailed_filter_info method
    def get_detailed_filter_info(self):
        """Get detailed filter information including date ranges with times - FIXED for legacy usage"""
        try:
            filter_info = {}
            
            # Date range information with times
            if (CALENDAR_AVAILABLE and 
                hasattr(self, 'from_date') and hasattr(self, 'to_date') and 
                self.from_date and self.to_date):
                try:
                    from_date = self.from_date.get_date()
                    to_date = self.to_date.get_date()
                    
                    # EASY FIX: Add these 4 lines to get actual time picker values
                    start_time = "00:00:00"
                    end_time = "23:59:59"
                    if hasattr(self, 'from_time_picker'): start_time = self.from_time_picker.get_time()
                    if hasattr(self, 'to_time_picker'): end_time = self.to_time_picker.get_time()
                    
                    filter_info['date_range'] = {
                        'start_date': from_date.strftime("%d-%m-%Y"),
                        'start_time': start_time,  # This will now use actual time
                        'end_date': to_date.strftime("%d-%m-%Y"),
                        'end_time': end_time       # This will now use actual time
                    }
                except:
                    filter_info['date_range'] = None
            
            # Rest of your existing code stays exactly the same...
            # Vehicle filter
            if hasattr(self, 'vehicle_var') and self.vehicle_var:
                vehicle_filter = self.vehicle_var.get().strip()
                if vehicle_filter:
                    filter_info['vehicle_filter'] = vehicle_filter
            
            # Material filter
            if hasattr(self, 'material_var') and self.material_var:
                material_filter = self.material_var.get().strip()
                if material_filter:
                    filter_info['material_filter'] = material_filter
            
            # Status filter
            if hasattr(self, 'status_var') and self.status_var:
                status_filter = self.status_var.get().strip()
                if status_filter and status_filter != 'All':
                    filter_info['status_filter'] = status_filter
            
            # Transfer party filter
            if hasattr(self, 'transfer_party_var') and self.transfer_party_var:
                transfer_party_filter = self.transfer_party_var.get().strip()
                if transfer_party_filter:
                    filter_info['transfer_party_filter'] = transfer_party_filter
            
            return filter_info
            
        except Exception as e:
            print(f"Error getting detailed filter info: {e}")
            return {}

    def create_action_frame(self):
        """Create the action buttons frame"""
        action_frame = ttk.LabelFrame(self.report_window, text="Export Options", padding=10)
        action_frame.grid(row=2, column=0, sticky="ew", padx=10, pady=5)
        
        # Export buttons
        excel_btn = ttk.Button(action_frame, text="📊 Export to Excel", 
                              command=self.export_selected_to_excel)
        excel_btn.pack(side=tk.LEFT, padx=10, pady=5)
        
        pdf_btn = ttk.Button(action_frame, text="📄 Export to PDF", 
                            command=self.export_selected_to_pdf)
        pdf_btn.pack(side=tk.LEFT, padx=10, pady=5)
        
        # Address config button
        config_btn = ttk.Button(action_frame, text="⚙️ Configure Address", 
                               command=self.show_address_config)
        config_btn.pack(side=tk.LEFT, padx=10, pady=5)
        
        # Close button
        close_btn = ttk.Button(action_frame, text="Close", command=self.report_window.destroy)
        close_btn.pack(side=tk.RIGHT, padx=10, pady=5)
    
    def refresh_records(self):
        """Refresh the records from data manager"""
        if not self.data_manager:
            return
        
        # Get all records
        self.all_records = self.data_manager.get_all_records()
        
        # Populate filter dropdowns
        self.populate_filter_dropdowns()
        
        # Apply current filters
        self.apply_filters()
    
    def populate_filter_dropdowns(self):
        """Populate the filter dropdown options"""
        if not self.all_records:
            return
        
        # Get unique values for dropdowns
        transfer_parties = set()
        materials = set()
        
        for record in self.all_records:
            transfer_party = record.get('transfer_party_name', '').strip()
            material = record.get('material', '').strip()
            
            if transfer_party:
                transfer_parties.add(transfer_party)
            if material:
                materials.add(material)
        
        # Update combobox values
        self.transfer_party_combo['values'] = [''] + sorted(list(transfer_parties))
        self.material_combo['values'] = [''] + sorted(list(materials))
    
    
    def select_all_records(self):
        """Select all visible records"""
        self.selected_records = []
        for item in self.records_tree.get_children():
            values = list(self.records_tree.item(item, 'values'))
            values[0] = "☑"
            ticket_no = values[1]
            self.selected_records.append(ticket_no)
            self.records_tree.item(item, values=values)
        
        self.update_selection_count()
    
    def select_no_records(self):
        """Deselect all records"""
        self.selected_records = []
        for item in self.records_tree.get_children():
            values = list(self.records_tree.item(item, 'values'))
            values[0] = "☐"
            self.records_tree.item(item, values=values)
        
        self.update_selection_count()
    
    def update_selection_count(self):
        """Update the selection count display"""
        total_records = len(self.records_tree.get_children())
        selected_count = len(self.selected_records)
        self.records_count_var.set(f"Records: {total_records} | Selected: {selected_count}")
    
    def get_selected_record_data(self):
        """Get the full data for selected records"""
        if not self.selected_records:
            return []
        
        selected_data = []
        for record in self.all_records:
            if record.get('ticket_no', '') in self.selected_records:
                selected_data.append(record)
        
        return selected_data
    
    def export_selected_to_excel(self):
        """Export selected records to Excel with summary format"""
        selected_data = self.get_selected_record_data()
        
        if not selected_data:
            messagebox.showwarning("No Selection", "Please select at least one record to export.")
            return
        
        try:
            # Generate filename based on applied filters
            filename = self.generate_filtered_filename(selected_data, "xlsx")
            
            # Save to reports folder
            save_path = os.path.join(self.reports_folder, filename)
            
            # Calculate summary data
            total_trips = len(selected_data)
            total_net_weight = 0
            date_range = self.get_date_range_info(selected_data)
            applied_filters = self.get_applied_filters_info()
            
            for record in selected_data:
                try:
                    net_weight = float(record.get('net_weight', 0) or 0)
                    total_net_weight += net_weight
                except (ValueError, TypeError):
                    pass
            
            # Create DataFrame with summary information
            df = pd.DataFrame(selected_data)
            
            # Export to Excel with enhanced formatting and summary
            with pd.ExcelWriter(save_path, engine='openpyxl') as writer:
                # Create summary sheet
                summary_data = {
                    'Metric': ['Total Number of Trips', 'Total Net Weight (kg)', 'Date Range', 'Applied Filters', 'Export Date'],
                    'Value': [total_trips, f"{total_net_weight:.2f}", date_range, applied_filters, datetime.datetime.now().strftime('%d-%m-%Y %H:%M:%S')]
                }
                summary_df = pd.DataFrame(summary_data)
                summary_df.to_excel(writer, sheet_name='Summary', index=False)
                
                # Add detailed records
                df.to_excel(writer, sheet_name='Detailed Records', index=False)
                
                # Get the workbook and format summary sheet
                workbook = writer.book
                summary_ws = writer.sheets['Summary']
                
                # Add title to summary sheet
                summary_ws.insert_rows(1, 3)
                summary_ws['A1'] = "SWACCHA ANDHRA CORPORATION - FILTERED REPORT SUMMARY"
                summary_ws['A2'] = f"Generated on: {datetime.datetime.now().strftime('%d-%m-%Y %H:%M:%S')}"
                summary_ws['A3'] = ""  # Empty row for spacing
            
            messagebox.showinfo("Export Successful", 
                              f"Excel summary report saved successfully!\n\n"
                              f"File: {filename}\n"
                              f"Records: {total_trips}\n"
                              f"Total Weight: {total_net_weight:.2f} kg\n"
                              f"Location: {self.reports_folder}")
            
            # FIXED: Only close window if it exists
            if hasattr(self, 'report_window') and self.report_window:
                self.report_window.destroy()
            
        except Exception as e:
            messagebox.showerror("Export Error", f"Failed to export to Excel:\n{str(e)}")
    
    def export_selected_to_pdf(self):
        """FIXED: Always export to PDF summary format regardless of filters applied"""
        if not REPORTLAB_AVAILABLE:
            messagebox.showerror("PDF Export Error", 
                            "ReportLab library is not installed.\n"
                            "Please install it using: pip install reportlab")
            return
        
        selected_data = self.get_selected_record_data()
        
        if not selected_data:
            messagebox.showwarning("No Selection", "Please select at least one record to export.")
            return
        
        try:
            # ALWAYS use summary format for advanced reports (FIXED LOGIC)
            if len(selected_data) == 1:
                # Single record - use individual format
                filename = self.generate_filename(selected_data, "pdf")
                save_path = os.path.join(self.reports_folder, filename)
                
                self.create_pdf_report(selected_data, save_path)
                messagebox.showinfo("Export Successful", 
                                f"Individual PDF report saved successfully!\n\n"
                                f"File: {filename}\n"
                                f"Location: {self.reports_folder}")
            else:
                # Multiple records - ALWAYS use summary format
                filename = self.generate_filtered_filename(selected_data, "pdf")
                save_path = os.path.join(self.reports_folder, filename)
                
                print(f"📄 EXPORT DEBUG: Creating summary PDF for {len(selected_data)} records with applied filters")
                self.create_summary_pdf_report(selected_data, save_path)
                
                messagebox.showinfo("Export Successful", 
                                f"Summary PDF Report saved successfully!\n\n"
                                f"File: {filename}\n"
                                f"Records: {len(selected_data)}\n"
                                f"Location: {self.reports_folder}")
            
            # FIXED: Only close window if it exists
            if hasattr(self, 'report_window') and self.report_window:
                self.report_window.destroy()
            
        except Exception as e:
            messagebox.showerror("Export Error", f"Failed to export to PDF:\n{str(e)}")



    def generate_filtered_filename(self, selected_data, extension="pdf"):
        """Generate intelligent filename based on applied filters and data - FIXED for legacy usage"""
        try:
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            
            # Ensure selected_data is a list of dictionaries
            if not selected_data or not isinstance(selected_data, list):
                return f"Enhanced_Report_{timestamp}.{extension}"
            
            # For single record, create specific filename
            if len(selected_data) == 1:
                record = selected_data[0]
                if isinstance(record, dict):
                    agency_name = record.get('agency_name', 'Unknown').replace(' ', '_').replace('/', '_')
                    site_name = record.get('site_name', 'Unknown').replace(' ', '_').replace('/', '_')
                    ticket_no = record.get('ticket_no', 'Unknown').replace(' ', '_').replace('/', '_')
                    vehicle_no = record.get('vehicle_no', 'Unknown').replace(' ', '_').replace('/', '_')
                    return f"{agency_name}_{site_name}_{ticket_no}_{vehicle_no}_{timestamp}.{extension}"
                else:
                    return f"Single_Record_{timestamp}.{extension}"
            else:
                # For multiple records, use agency/site info if available
                filename_parts = []
                
                # Add agency info if consistent across records
                agencies = set()
                sites = set()
                for record in selected_data:
                    if isinstance(record, dict):
                        agencies.add(record.get('agency_name', 'Unknown'))
                        sites.add(record.get('site_name', 'Unknown'))
                
                if len(agencies) == 1:
                    agency_part = list(agencies)[0].replace(' ', '_').replace('/', '_')
                    filename_parts.append(agency_part)
                
                if len(sites) == 1:
                    site_part = list(sites)[0].replace(' ', '_').replace('/', '_')
                    filename_parts.append(site_part)
                
                # Get date range from data
                dates = []
                for record in selected_data:
                    if isinstance(record, dict):
                        date_str = record.get('date', '')
                        if date_str:
                            dates.append(date_str)
                
                if dates:
                    unique_dates = sorted(set(dates))
                    if len(unique_dates) == 1:
                        filename_parts.append(unique_dates[0].replace('-', ''))
                    elif len(unique_dates) > 1:
                        start_date = unique_dates[0].replace('-', '')
                        end_date = unique_dates[-1].replace('-', '')
                        filename_parts.append(f"{start_date}_to_{end_date}")
                
                # Construct final filename
                if filename_parts:
                    base_filename = "_".join(filename_parts)
                    date_stamp = datetime.datetime.now().strftime("%d-%m-%Y")
                    return f"{date_stamp}_Summary_{base_filename}.{extension}"
                else:
                    return f"Summary_Report_{len(selected_data)}records_{timestamp}.{extension}"
                
        except Exception as e:
            print(f"Error generating filtered filename: {e}")
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            return f"Enhanced_Report_{len(selected_data) if selected_data else 0}records_{timestamp}.{extension}"

    def create_summary_pdf_report(self, records_data, save_path):
        """Create an enhanced summary PDF report with expanded columns and proper naming"""
        if not REPORTLAB_AVAILABLE:
            return False
            
        try:
            # Ensure output directory exists
            os.makedirs(os.path.dirname(save_path), exist_ok=True)
            
            # Use landscape orientation for all tables in summary
            if landscape:
                doc = SimpleDocTemplate(save_path, pagesize=landscape(A4),
                                        rightMargin=20, leftMargin=20, topMargin=30, bottomMargin=30)
            else:
                doc = SimpleDocTemplate(save_path, pagesize=A4,
                                        rightMargin=20, leftMargin=20, topMargin=30, bottomMargin=30)
            
            styles = getSampleStyleSheet()
            elements = []

            # Create enhanced styles (same as before)
            header_style = ParagraphStyle(
                name='HeaderStyle',
                fontSize=16,
                alignment=TA_CENTER,
                fontName='Helvetica-Bold',
                textColor=colors.black,
                spaceAfter=8,
                spaceBefore=4
            )
            
            subheader_style = ParagraphStyle(
                name='SubHeaderStyle',
                fontSize=10,
                alignment=TA_CENTER,
                fontName='Helvetica',
                textColor=colors.black,
                spaceAfter=6
            )
            
            summary_header_style = ParagraphStyle(
                name='SummaryHeaderStyle',
                fontSize=12,
                alignment=TA_CENTER,
                fontName='Helvetica-Bold',
                textColor=colors.darkblue,
                spaceAfter=8,
                spaceBefore=12
            )
            
            material_header_style = ParagraphStyle(
                name='MaterialHeaderStyle',
                fontSize=11,
                alignment=TA_CENTER,
                fontName='Helvetica-Bold',
                textColor=colors.darkgreen,
                spaceAfter=6,
                spaceBefore=10
            )
            
            attribution_style = ParagraphStyle(
                name='AttributionStyle',
                fontSize=10,
                alignment=TA_CENTER,
                fontName='Helvetica',
                textColor=colors.darkgrey,
                spaceAfter=4
            )

            # ENHANCED: Header section using agency information from address.json
            # Get agency and site information from first record
            first_record = records_data[0] if records_data else {}
            agency_name = first_record.get('agency_name', 'Default Agency')
            site_name = first_record.get('site_name', 'Unknown Site')
            
            # Get agency info from address config
            agency_info = self.address_config.get('agencies', {}).get(agency_name, {})
            site_info = self.address_config.get('sites', {}).get(site_name, {})
            
            # ENHANCED: Create agency header table with proper information
            agency_info_data = []
            
            # Agency name row (main header)
            agency_info_data.append([agency_info.get('name', agency_name)])
            
            # Agency address if available
            if agency_info.get('address'):
                agency_address = agency_info.get('address', '').replace('\n', '<br/>')
                agency_info_data.append([agency_address])
            
            # Contact information row
            contact_info = []
            if agency_info.get('contact'):
                contact_info.append(f"Phone: {agency_info.get('contact')}")
            if agency_info.get('email'):
                contact_info.append(f"Email: {agency_info.get('email')}")
            if site_info.get('contact') and site_info.get('contact') != agency_info.get('contact'):
                contact_info.append(f"Site Phone: {site_info.get('contact')}")
            
            if contact_info:
                agency_info_data.append([" | ".join(contact_info)])
            
            # Create the agency header table
            if agency_info_data:
                agency_table = Table(agency_info_data, colWidths=[500])
                agency_table.setStyle(TableStyle([
                    # Black outline only, no background fills
                    ('BOX', (0, 0), (-1, -1), 2, colors.black),
                    # Text alignment and formatting
                    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                    ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                    # Font styling - first row (agency name) bold and larger
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, 0), 16),
                    # Remaining rows normal font
                    ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
                    ('FONTSIZE', (0, 1), (-1, -1), 14),
                    # Padding
                    ('TOPPADDING', (0, 0), (-1, -1), 8),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
                    ('LEFTPADDING', (0, 0), (-1, -1), 12),
                    ('RIGHTPADDING', (0, 0), (-1, -1), 12),
                ]))
                
                elements.append(agency_table)
            else:
                # Fallback to default headers if no agency info
                elements.append(Paragraph("Default Agency", header_style))
                elements.append(Paragraph("Swaccha Andhra Monitor - Advitia Labs", subheader_style))
            
            # Group records by material type and calculate statistics
            material_stats = self.calculate_material_statistics(records_data)
            total_trips = len(records_data)
            total_net_weight = sum(stats['total_weight'] for stats in material_stats.values())
            total_weight_tonnes = total_net_weight / 1000
            
            # Filter information section
            filter_details = self.get_detailed_filter_info()
            
            if filter_details and filter_details.get('date_range'):
                date_range = filter_details['date_range']
                start_date = date_range.get('start_date', 'N/A')
                start_time = date_range.get('start_time', '00:00:00')
                end_date = date_range.get('end_date', 'N/A')
                end_time = date_range.get('end_time', '23:59:59')
                elements.append(Paragraph(f"<b>Date Range:</b> {start_date} {start_time} to {end_date} {end_time}", subheader_style))
            else:
                elements.append(Paragraph("<b>Date Range:</b> All records", subheader_style))
            
            # Add other filters if any
            other_filters = []
            if filter_details.get('vehicle_filter'):
                other_filters.append(f"Vehicle: {filter_details['vehicle_filter']}")
            if filter_details.get('material_filter'):
                other_filters.append(f"Material: {filter_details['material_filter']}")
            if filter_details.get('status_filter') and filter_details['status_filter'] != 'All':
                other_filters.append(f"Status: {filter_details['status_filter']}")
            if filter_details.get('transfer_party_filter'):
                other_filters.append(f"Transfer Party: {filter_details['transfer_party_filter']}")
            
            if other_filters:
                elements.append(Paragraph(f"<b>Additional Filters:</b> {' | '.join(other_filters)}", subheader_style))
            
            elements.append(Spacer(1, 12))
            
            # Summary Statistics Table with Material Type breakdown (same as before)
            elements.append(Paragraph("SUMMARY STATISTICS", summary_header_style))
            
            # Overall summary
            summary_table_data = [
                ['Summary Type', 'Count'],
                ['Total Number of Trips', f"{total_trips:,}"]
            ]
            
            # Add material-wise breakdown
            summary_table_data.append(['', ''])  # Empty row for spacing
            summary_table_data.append(['BREAKDOWN BY MATERIAL TYPE', ''])
            
            for material, stats in sorted(material_stats.items()):
                material_tonnes = stats['total_weight'] / 1000
                percentage = (stats['total_weight'] / total_net_weight * 100) if total_net_weight > 0 else 0
                
                summary_table_data.append([
                    f"{material} - Trips", 
                    f"{stats['trip_count']:,} trips"
                ])
                summary_table_data.append([
                    f"{material} - Weight", 
                    f"{material_tonnes:.3f} MT ({percentage:.1f}%)"
                ])
            
            summary_table = Table(summary_table_data, colWidths=[300, 200])
            summary_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.lightblue),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 11),
                ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 1), (-1, -1), 10),
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('TOPPADDING', (0, 0), (-1, -1), 6),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
                # Highlight material type headers
                ('BACKGROUND', (0, 3), (-1, 3), colors.lightgreen),
                ('FONTNAME', (0, 3), (-1, 3), 'Helvetica-Bold'),
                # Alternate colors for material rows
                ('ROWBACKGROUNDS', (0, 5), (-1, -1), [colors.white, colors.beige]),
            ]))
            
            elements.append(summary_table)
            
            # Attribution line
            timestamp = datetime.datetime.now().strftime('%d-%m-%Y %H:%M:%S')
            attribution_text = f"Report generated by Swaccha Andhra Monitor by Advitia Labs at {timestamp}"
            elements.append(Paragraph("─" * 40, attribution_style))
            elements.append(Paragraph(attribution_text, attribution_style))
            
            elements.append(Spacer(1, 12))
            
            # ENHANCED: Create separate detailed tables for each material type with NEW COLUMNS
            elements.append(Paragraph("DETAILED RECORDS BY MATERIAL TYPE", summary_header_style))
            
            # Group records by material type
            grouped_records = self.group_records_by_material(records_data)
            
            for i, (material, material_records) in enumerate(sorted(grouped_records.items())):
                if i > 0:
                    elements.append(Spacer(1, 20))  # Space between material tables
                
                # Material type header
                material_count = len(material_records)
                material_weight = sum(float(record.get('net_weight', 0) or 0) for record in material_records)
                material_tonnes = material_weight / 1000
                
                material_header_text = f"MATERIAL TYPE: {material.upper()} ({material_count} trips, {material_tonnes:.3f} MT)"
                elements.append(Paragraph(material_header_text, material_header_style))
                
                # ENHANCED: Create table with NEW COLUMN STRUCTURE and PROPER NAMING
                # Final headers: S.NO, DATE, SLIP NO, VEHICLE NO, GROSS, IN_TIME, TARE, OUT_TIME, NET WT
                table_data = [['S.NO', 'DATE', 'SLIP NO', 'VEHICLE NO', 'GROSS', 'IN_TIME', 'TARE', 'OUT_TIME', 'NET WT']]
                
                for j, record in enumerate(material_records, 1):
                    # Extract data with proper formatting
                    date = record.get('date', 'N/A')
                    slip_no = record.get('ticket_no', 'N/A')  # Renamed from Ticket
                    vehicle_no = record.get('vehicle_no', 'N/A')
                    
                    # NEW COLUMNS: Extract Gross (First Weight) and Tare (Second Weight) with kg units
                    gross_weight = record.get('first_weight', '').strip()
                    try:
                        # CHANGE: Add "kg" to the gross weight display
                        gross_display = f"{float(gross_weight):.1f} kg" if gross_weight else "0.0 kg"
                    except:
                        gross_display = "0.0 kg"
                    
                    tare_weight = record.get('second_weight', '').strip()
                    try:
                        # CHANGE: Add "kg" to the tare weight display
                        tare_display = f"{float(tare_weight):.1f} kg" if tare_weight else "0.0 kg"
                    except:
                        tare_display = "0.0 kg"
                    
                    # NEW COLUMNS: Extract time from datetime timestamp (21-06-2025 10:04:58 → 10:04:58)
                    in_time = record.get('first_timestamp', '').strip()
                    in_time_display = in_time.split(' ')[1] if ' ' in in_time else "N/A"
                    
                    out_time = record.get('second_timestamp', '').strip()
                    out_time_display = out_time.split(' ')[1] if ' ' in out_time else "N/A"
                    
                    # Net weight with kg units
                    net_weight = record.get('net_weight', '').strip()
                    try:
                        # CHANGE: Add "kg" to the net weight display
                        net_weight_display = f"{float(net_weight):.1f} kg" if net_weight else "0.0 kg"
                    except:
                        net_weight_display = "0.0 kg"
                    
                    
                    table_data.append([
                        str(j),                    # S.NO
                        date,                      # DATE
                        slip_no,                   # SLIP NO (renamed from Ticket)
                        vehicle_no,                # VEHICLE NO
                        gross_display,             # GROSS (First Weight) with kg
                        in_time_display,           # IN_TIME (First Timestamp)
                        tare_display,              # TARE (Second Weight) with kg
                        out_time_display,          # OUT_TIME (Second Timestamp)
                        net_weight_display        # NET WT with kg
                    ])
                
                # ENHANCED: Adjusted column widths for expanded table (9 columns total)
                # Landscape A4 provides ~800 points width, distribute across 9 columns
                # Increased widths to accommodate larger font sizes
                col_widths = [40, 75, 70, 85, 70, 65, 70, 65, 70]  # Total ~610 points, adjusted for larger fonts
                
                table = Table(table_data, repeatRows=1, colWidths=col_widths)
                table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
                    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, 0), 11),  # Increased header font size to 14
                    ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
                    ('FONTSIZE', (0, 1), (-1, -1), 10),  # Increased data font size to 12
                    ('BOTTOMPADDING', (0, 0), (-1, 0), 4),
                    ('TOPPADDING', (0, 0), (-1, -1), 2),
                    ('BOTTOMPADDING', (0, 1), (-1, -1), 2),
                    ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
                    ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                    # Alternating row colors for better readability
                    ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.beige]),
                ]))
                
                elements.append(table)
                
                # Add material summary at the end of each table
                material_summary = Table([
                    [f"SUBTOTAL FOR {material.upper()}: {material_count} trips, {material_tonnes:.3f} MT"]
                ], colWidths=[sum(col_widths)])
                material_summary.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, -1), colors.lightgreen),
                    ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, -1), 11),
                    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                    ('GRID', (0, 0), (-1, -1), 1, colors.black),
                    ('TOPPADDING', (0, 0), (-1, -1), 3),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
                ]))
                elements.append(material_summary)
            
            # Build PDF
            doc.build(elements)
            
            print(f"📄 ENHANCED PDF EXPORT: Successfully created EXPANDED COLUMNS summary PDF with kg units")
            print(f"   - Total Records: {total_trips}")
            print(f"   - Total Net Weight: {total_weight_tonnes:.3f} MT ({total_net_weight:.2f} kg)")
            print(f"   - Material Types: {len(material_stats)}")
            print(f"   - UPDATED: Added kg units to all weight columns (Gross, Tare, Net WT)")
            print(f"   - UPDATED: Increased font sizes - Headers: 14pt, Data: 12pt")
            print(f"   - NEW COLUMNS: Added Gross, In_Time, Tare, Out_Time")
            print(f"   - RENAMED COLUMNS: Ticket → Slip No, etc.")
            for material, stats in material_stats.items():
                material_tonnes = stats['total_weight'] / 1000
                print(f"     • {material}: {stats['trip_count']} trips, {material_tonnes:.3f} MT")
            print(f"   - ORIENTATION: Landscape for 9-column table visibility")
            
            return True
            
        except Exception as e:
            print(f"Error creating enhanced summary PDF report: {e}")
            import traceback
            print(f"Detailed error: {traceback.format_exc()}")
            return False


    def calculate_material_statistics(self, records_data):
        """Calculate statistics grouped by material type
        
        Args:
            records_data: List of record dictionaries
            
        Returns:
            dict: Statistics by material type
        """
        try:
            material_stats = {}
            
            for record in records_data:
                # Get material type - check multiple possible field names
                material = (
                    record.get('material', '') or 
                    record.get('material', '') or 
                    record.get('transfer_party', '') or 
                    'Unknown Material'
                ).strip()
                
                if not material:
                    material = 'Unknown Material'
                
                # Initialize material stats if not exists
                if material not in material_stats:
                    material_stats[material] = {
                        'trip_count': 0,
                        'total_weight': 0.0,
                        'records': []
                    }
                
                # Add to statistics
                material_stats[material]['trip_count'] += 1
                material_stats[material]['records'].append(record)
                
                # Add weight if available
                try:
                    net_weight = float(record.get('net_weight', 0) or 0)
                    material_stats[material]['total_weight'] += net_weight
                except (ValueError, TypeError):
                    pass
            
            print(f"📊 MATERIAL STATS: Calculated statistics for {len(material_stats)} material types")
            for material, stats in material_stats.items():
                print(f"   • {material}: {stats['trip_count']} trips, {stats['total_weight']:.2f} kg")
            
            return material_stats
            
        except Exception as e:
            print(f"Error calculating material statistics: {e}")
            return {}

    def group_records_by_material(self, records_data):
        """Group records by material type for table generation
        
        Args:
            records_data: List of record dictionaries
            
        Returns:
            dict: Records grouped by material type
        """
        try:
            grouped_records = {}
            
            for record in records_data:
                # Get material type - check multiple possible field names
                material = (
                    record.get('material', '') or 
                    record.get('material', '') or 
                    record.get('transfer_party', '') or 
                    'Unknown Material'
                ).strip()
                
                if not material:
                    material = 'Unknown Material'
                
                # Group records
                if material not in grouped_records:
                    grouped_records[material] = []
                
                grouped_records[material].append(record)
            
            # Sort records within each material group by date and time
            for material in grouped_records:
                grouped_records[material].sort(key=lambda r: (
                    r.get('date', ''), 
                    r.get('time', ''),
                    r.get('ticket_no', '')
                ))
            
            print(f"📋 RECORD GROUPING: Grouped {len(records_data)} records into {len(grouped_records)} material types")
            
            return grouped_records
            
        except Exception as e:
            print(f"Error grouping records by material: {e}")
            return {'Unknown Material': records_data}  # Fallback

    def export_selected_to_pdf(self):
        """ENHANCED: Export to PDF with material type grouping"""
        if not REPORTLAB_AVAILABLE:
            messagebox.showerror("PDF Export Error", 
                            "ReportLab library is not installed.\n"
                            "Please install it using: pip install reportlab")
            return
        
        selected_data = self.get_selected_record_data()
        
        if not selected_data:
            messagebox.showwarning("No Selection", "Please select at least one record to export.")
            return
        
        try:
            if len(selected_data) == 1:
                # Single record - use individual format
                filename = self.generate_filename(selected_data, "pdf")
                save_path = os.path.join(self.reports_folder, filename)
                
                self.create_pdf_report(selected_data, save_path)
                messagebox.showinfo("Export Successful", 
                                f"Individual PDF report saved successfully!\n\n"
                                f"File: {filename}\n"
                                f"Location: {self.reports_folder}")
            else:
                # Multiple records - ENHANCED with material grouping
                filename = self.generate_filtered_filename(selected_data, "pdf")
                save_path = os.path.join(self.reports_folder, filename)
                
                print(f"📄 EXPORT DEBUG: Creating MATERIAL-GROUPED summary PDF for {len(selected_data)} records")
                
                # Count material types for user info
                materials = set()
                for record in selected_data:
                    material = (
                        record.get('material', '') or 
                        record.get('material', '') or 
                        'Unknown'
                    ).strip() or 'Unknown'
                    materials.add(material)
                
                self.create_summary_pdf_report(selected_data, save_path)
                
                messagebox.showinfo("Export Successful", 
                                f"ENHANCED Summary PDF Report saved successfully!\n\n"
                                f"File: {filename}\n"
                                f"Records: {len(selected_data)}\n"
                                f"Material Types: {len(materials)} ({', '.join(sorted(materials))})\n"
                                f"Features: Material grouping, weight breakdown, separate tables\n"
                                f"Location: {self.reports_folder}")
            
            # Close window if it exists
            if hasattr(self, 'report_window') and self.report_window:
                self.report_window.destroy()
            
        except Exception as e:
            messagebox.showerror("Export Error", f"Failed to export to PDF:\n{str(e)}")
            import traceback
            print(f"PDF export error: {traceback.format_exc()}")


        
    def get_date_range_info(self, records_data):
        """Get human-readable date range from records"""
        try:
            if not records_data:
                return "Unknown"
                
            dates = []
            for record in records_data:
                date_str = record.get('date', '')
                if date_str:
                    try:
                        date_obj = datetime.datetime.strptime(date_str, "%d-%m-%Y")
                        dates.append(date_obj)
                    except:
                        pass
            
            if not dates:
                return "Unknown"
                
            min_date = min(dates)
            max_date = max(dates)
            
            if min_date.date() == max_date.date():
                return min_date.strftime("%d-%m-%Y")
            else:
                return f"{min_date.strftime('%d-%m-%Y')} to {max_date.strftime('%d-%m-%Y')}"
                
        except Exception as e:
            print(f"Error getting date range info: {e}")
            return "Unknown"

    def generate_filename(self, selected_data, extension):
        """Generate filename based on Agency_Site_Ticket format (for single records)"""
        try:
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            
            if len(selected_data) == 1:
                # Single record: Agency_Site_Ticket.extension
                record = selected_data[0]
                ticket_no = record.get('ticket_no', 'Unknown').replace('/', '_')
                site_name = record.get('site_name', 'Unknown').replace(' ', '_').replace('/', '_')
                agency_name = record.get('agency_name', 'Unknown').replace(' ', '_').replace('/', '_')
                return f"{agency_name}_{site_name}_{ticket_no}.{extension}"
            else:
                # This shouldn't be used for multiple records anymore
                return f"Report_{len(selected_data)}records_{timestamp}.{extension}"
                
        except Exception as e:
            print(f"Error generating filename: {e}")
            # Fallback filename
            return f"Report_{len(selected_data)}records_{timestamp}.{extension}"
    
    def create_pdf_report(self, records_data, save_path):
        """Create PDF report with 4-image grid for complete records (used only for single records)"""
        doc = SimpleDocTemplate(save_path, pagesize=A4,
                                rightMargin=20, leftMargin=20, topMargin=20, bottomMargin=20)
        
        styles = getSampleStyleSheet()
        elements = []

        # Ink-friendly styles with increased font sizes
        header_style = ParagraphStyle(
            name='HeaderStyle',
            fontSize=18,
            alignment=TA_CENTER,
            fontName='Helvetica-Bold',
            textColor=colors.black,
            spaceAfter=6,
            spaceBefore=6
        )
        
        subheader_style = ParagraphStyle(
            name='SubHeaderStyle',
            fontSize=12,
            alignment=TA_CENTER,
            fontName='Helvetica',
            textColor=colors.black,
            spaceAfter=12
        )
        
        section_header_style = ParagraphStyle(
            name='SectionHeader',
            fontSize=13,
            alignment=TA_CENTER,
            fontName='Helvetica-Bold',
            textColor=colors.black,
            spaceAfter=6,
            spaceBefore=6
        )

        label_style = ParagraphStyle(
            name='LabelStyle',
            fontSize=11,
            fontName='Helvetica-Bold',
            textColor=colors.black
        )

        value_style = ParagraphStyle(
            name='ValueStyle',
            fontSize=11,
            fontName='Helvetica',
            textColor=colors.black
        )

        for i, record in enumerate(records_data):
            if i > 0:
                elements.append(PageBreak())

            # Get agency information from address config
            agency_name = record.get('agency_name', 'Unknown Agency')
            agency_info = self.address_config.get('agencies', {}).get(agency_name, {})
            
            # Header Section with Agency Info
            elements.append(Paragraph(agency_info.get('name', agency_name), header_style))
            
            if agency_info.get('address'):
                address_text = agency_info.get('address', '').replace('\n', '<br/>')
                elements.append(Paragraph(address_text, subheader_style))
            
            # Contact information
            contact_info = []
            if agency_info.get('contact'):
                contact_info.append(f"Phone: {agency_info.get('contact')}")
            if agency_info.get('email'):
                contact_info.append(f"Email: {agency_info.get('email')}")
            
            if contact_info:
                elements.append(Paragraph(" | ".join(contact_info), subheader_style))
            
            elements.append(Spacer(1, 0.2*inch))

            # Print date and ticket information
            print_date = datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S")
            ticket_no = record.get('ticket_no', '000')
            
            elements.append(Paragraph(f"Print Date: {print_date}", value_style))
            elements.append(Paragraph(f"Ticket No: {ticket_no}", header_style))
            elements.append(Spacer(1, 0.15*inch))

            # Vehicle Information
            elements.append(Paragraph("VEHICLE INFORMATION", section_header_style))
            
            # Get material from material field if material is empty
            material_value = record.get('material', '') or record.get('material', '')
            user_name_value = record.get('user_name', '') or "Not specified"
            site_incharge_value = record.get('site_incharge', '') or "Not specified"
            
            vehicle_data = [
                [Paragraph("<b>Vehicle No:</b>", label_style), Paragraph(record.get('vehicle_no', ''), value_style), 
                Paragraph("<b>Date:</b>", label_style), Paragraph(record.get('date', ''), value_style), 
                Paragraph("<b>Time:</b>", label_style), Paragraph(record.get('time', ''), value_style)],
                [Paragraph("<b>Material:</b>", label_style), Paragraph(material_value, value_style), 
                Paragraph("<b>Site Name:</b>", label_style), Paragraph(record.get('site_name', ''), value_style), 
                Paragraph("<b>Transfer Party:</b>", label_style), Paragraph(record.get('transfer_party_name', ''), value_style)],
                [Paragraph("<b>Agency Name:</b>", label_style), Paragraph(record.get('agency_name', ''), value_style), 
                Paragraph("<b>User Name:</b>", label_style), Paragraph(user_name_value, value_style), 
                Paragraph("<b>Site Incharge:</b>", label_style), Paragraph(site_incharge_value, value_style)]
            ]
            
            vehicle_inner_table = Table(vehicle_data, colWidths=[1.2*inch, 1.3*inch, 1.0*inch, 1.3*inch, 1.2*inch, 1.5*inch])
            vehicle_inner_table.setStyle(TableStyle([
                ('FONTNAME', (0,0), (-1,-1), 'Helvetica'),
                ('FONTSIZE', (0,0), (-1,-1), 12),
                ('ALIGN', (0,0), (-1,-1), 'LEFT'),
                ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
                ('LEFTPADDING', (0,0), (-1,-1), 2),
                ('RIGHTPADDING', (0,0), (-1,-1), 2),
                ('TOPPADDING', (0,0), (-1,-1), 4),
                ('BOTTOMPADDING', (0,0), (-1,-1), 4),
            ]))
            
            vehicle_table = Table([[vehicle_inner_table]], colWidths=[7.5*inch])
            vehicle_table.setStyle(TableStyle([
                ('GRID', (0,0), (-1,-1), 1, colors.black),
                ('LEFTPADDING', (0,0), (-1,-1), 12),
                ('RIGHTPADDING', (0,0), (-1,-1), 12),
                ('TOPPADDING', (0,0), (-1,-1), 8),
                ('BOTTOMPADDING', (0,0), (-1,-1), 8),
                ('VALIGN', (0,0), (-1,-1), 'TOP'),
            ]))
            elements.append(vehicle_table)
            elements.append(Spacer(1, 0.15*inch))

            # Weighment Information
            elements.append(Paragraph("WEIGHMENT DETAILS", section_header_style))
            first_weight_str = record.get('first_weight', '').strip()
            second_weight_str = record.get('second_weight', '').strip()
            net_weight_str = record.get('net_weight', '').strip()

            if not net_weight_str and first_weight_str and second_weight_str:
                try:
                    first_weight = float(first_weight_str)
                    second_weight = float(second_weight_str)
                    calculated_net = abs(first_weight - second_weight)
                    net_weight_str = f"{calculated_net:.2f}"
                except (ValueError, TypeError):
                    net_weight_str = "Calculation Error"

            # If we still don't have net weight, try to calculate from available data
            if not net_weight_str or net_weight_str == "Calculation Error":
                if first_weight_str and second_weight_str:
                    try:
                        first_weight = float(first_weight_str)
                        second_weight = float(second_weight_str)
                        calculated_net = abs(first_weight - second_weight)
                        net_weight_str = f"{calculated_net:.2f}"
                    except (ValueError, TypeError):
                        net_weight_str = "Unable to calculate"
                else:
                    net_weight_str = "Not Available"

            # Format display weights
            first_weight_display = f"{first_weight_str} kg" if first_weight_str else "Not captured"
            second_weight_display = f"{second_weight_str} kg" if second_weight_str else "Not captured"
            net_weight_display = f"{net_weight_str} kg" if net_weight_str and net_weight_str not in ["Not Available", "Unable to calculate", "Calculation Error"] else net_weight_str
            weighment_data = [
                [Paragraph("<b>First Weight:</b>", label_style), Paragraph(first_weight_display, value_style), 
                Paragraph("<b>First Time:</b>", label_style), Paragraph(record.get('first_timestamp', '') or "Not captured", value_style)],
                [Paragraph("<b>Second Weight:</b>", label_style), Paragraph(second_weight_display, value_style), 
                Paragraph("<b>Second Time:</b>", label_style), Paragraph(record.get('second_timestamp', '') or "Not captured", value_style)],
                [Paragraph("<b>Net Weight:</b>", label_style), Paragraph(net_weight_display, value_style)]
            ]
            
            weighment_inner_table = Table(weighment_data, colWidths=[1.5*inch, 1.5*inch, 1.2*inch, 2.8*inch])
            weighment_inner_table.setStyle(TableStyle([
                ('FONTNAME', (0,0), (-1,-1), 'Helvetica'),
                ('FONTSIZE', (0,0), (-1,-1), 12),
                ('ALIGN', (0,0), (-1,-1), 'LEFT'),
                ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
                ('LEFTPADDING', (0,0), (-1,-1), 2),
                ('RIGHTPADDING', (0,0), (-1,-1), 2),
                ('TOPPADDING', (0,0), (-1,-1), 4),
                ('BOTTOMPADDING', (0,0), (-1,-1), 4),
                ('SPAN', (2,2), (3,2)),
                ('ALIGN', (2,2), (3,2), 'RIGHT'),
            ]))
            
            weighment_table = Table([[weighment_inner_table]], colWidths=[7.5*inch])
            weighment_table.setStyle(TableStyle([
                ('GRID', (0,0), (-1,-1), 1, colors.black),
                ('LEFTPADDING', (0,0), (-1,-1), 12),
                ('RIGHTPADDING', (0,0), (-1,-1), 12),
                ('TOPPADDING', (0,0), (-1,-1), 8),
                ('BOTTOMPADDING', (0,0), (-1,-1), 8),
                ('VALIGN', (0,0), (-1,-1), 'TOP'),
            ]))
            elements.append(weighment_table)
            elements.append(Spacer(1, 0.15*inch))

            # NEW: 4-Image Grid Section
            elements.append(Paragraph("VEHICLE IMAGES (4-Image System)", section_header_style))
            
            # Get all 4 image paths
            first_front_img_path = os.path.join(config.IMAGES_FOLDER, record.get('first_front_image', ''))
            first_back_img_path = os.path.join(config.IMAGES_FOLDER, record.get('first_back_image', ''))
            second_front_img_path = os.path.join(config.IMAGES_FOLDER, record.get('second_front_image', ''))
            second_back_img_path = os.path.join(config.IMAGES_FOLDER, record.get('second_back_image', ''))

            # Create 2x2 image grid with headers (unchanged)
            img_data = [
                ["1ST WEIGHMENT - FRONT", "1ST WEIGHMENT - BACK"],
                [None, None],  # Will be filled with first weighment images
                ["2ND WEIGHMENT - FRONT", "2ND WEIGHMENT - BACK"], 
                [None, None]   # Will be filled with second weighment images
            ]

            # Calculate image dimensions to maintain aspect ratio
            IMG_WIDTH = 6.0*inch
            IMG_HEIGHT = 4.5*inch

            # Process images with the new high-quality method
            first_front_img = self.process_image_for_grid(first_front_img_path, f"Ticket: {ticket_no} - 1st Front", IMG_WIDTH, IMG_HEIGHT)
            first_back_img = self.process_image_for_grid(first_back_img_path, f"Ticket: {ticket_no} - 1st Back", IMG_WIDTH, IMG_HEIGHT)
            second_front_img = self.process_image_for_grid(second_front_img_path, f"Ticket: {ticket_no} - 2nd Front", IMG_WIDTH, IMG_HEIGHT)
            second_back_img = self.process_image_for_grid(second_back_img_path, f"Ticket: {ticket_no} - 2nd Back", IMG_WIDTH, IMG_HEIGHT)

            # Fill the image grid
            img_data[1] = [first_front_img or "1st Front\nImage not available", 
                        first_back_img or "1st Back\nImage not available"]
            img_data[3] = [second_front_img or "2nd Front\nImage not available", 
                        second_back_img or "2nd Back\nImage not available"]

            # Create images table with the larger dimensions
            img_table = Table(img_data, 
                            colWidths=[IMG_WIDTH, IMG_WIDTH],
                            rowHeights=[0.4*inch, IMG_HEIGHT, 0.4*inch, IMG_HEIGHT])
            img_table.setStyle(TableStyle([
                            ('GRID', (0,0), (-1,-1), 0.5, colors.black),
                            ('FONTNAME', (0,0), (-1,-1), 'Helvetica-Bold'),
                            ('FONTSIZE', (0,0), (1,0), 12),  # Increased header font size
                            ('FONTSIZE', (0,2), (1,2), 12),  # Increased header font size
                            ('ALIGN', (0,0), (-1,-1), 'CENTER'),
                            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
                            ('LEFTPADDING', (0,0), (-1,-1), 6),    # Increased padding
                            ('RIGHTPADDING', (0,0), (-1,-1), 6),   # Increased padding
                            ('TOPPADDING', (0,0), (-1,-1), 6),     # Increased padding
                            ('BOTTOMPADDING', (0,0), (-1,-1), 6),  # Increased padding
                            # Header background
                            ('BACKGROUND', (0,0), (1,0), colors.lightgrey),
                            ('BACKGROUND', (0,2), (1,2), colors.lightgrey),
                        ]))
            elements.append(img_table)
                        
                        # Add Agency signature line at bottom right
            elements.append(Spacer(1, 0.3*inch))
                        
            signature_table = Table([["", "Operator's Signature"]], colWidths=[5*inch, 2.5*inch])
            signature_table.setStyle(TableStyle([
                            ('FONTNAME', (0,0), (-1,-1), 'Helvetica'),
                            ('FONTSIZE', (0,0), (-1,-1), 11),
                            ('ALIGN', (1,0), (1,0), 'RIGHT'),
                            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
                            ('LEFTPADDING', (0,0), (-1,-1), 0),
                            ('RIGHTPADDING', (0,0), (-1,-1), 0),
                            ('TOPPADDING', (0,0), (-1,-1), 0),
                            ('BOTTOMPADDING', (0,0), (-1,-1), 0),
                        ]))
            elements.append(signature_table)

                    # Build the PDF
            doc.build(elements)

    def process_image_for_grid(self, image_path, watermark_text, width, height):
        """Process image for grid display with high quality"""
        if not image_path or not os.path.exists(image_path):
            return None
            
        try:
            # Use our high-quality preparation method
            temp_path = self.prepare_image_for_pdf(image_path, watermark_text)
            if temp_path:
                img = RLImage(temp_path, width=width, height=height)
                os.remove(temp_path)
                return img
        except Exception as e:
            print(f"Error processing image for grid: {e}")
            return None
        return None


    def prepare_image_for_pdf(self, image_path, watermark_text):
        """Prepare image for PDF with high quality and watermark"""
        try:
            # Read image
            img = cv2.imread(image_path)
            if img is None:
                return None
            
            # Get original dimensions
            height, width = img.shape[:2]
            
            # Calculate new dimensions while maintaining aspect ratio
            # We'll use larger dimensions for better quality
            max_width = 1200  # Increased from 400
            max_height = 900  # Increased from 300
            
            # Calculate scaling factor
            scale_w = max_width / width
            scale_h = max_height / height
            scale = min(scale_w, scale_h)
            
            new_width = int(width * scale)
            new_height = int(height * scale)
            
            # Use high-quality interpolation
            img_resized = cv2.resize(img, (new_width, new_height), interpolation=cv2.INTER_LANCZOS4)
            
            # Add watermark
            from camera import add_watermark  # Import the watermark function
            watermarked_img = add_watermark(img_resized, watermark_text)
            
            # Save temporary file with high quality
            temp_filename = f"temp_pdf_image_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S_%f')}.jpg"
            temp_path = os.path.join(config.IMAGES_FOLDER, temp_filename)
            
            # Save with high quality (100% JPEG quality)
            cv2.imwrite(temp_path, watermarked_img, [int(cv2.IMWRITE_JPEG_QUALITY), 100])
            
            return temp_path
            
        except Exception as e:
            print(f"Error preparing image for PDF: {e}")
            import traceback
            print(traceback.format_exc())
            return None
    
    def show_address_config(self):
        """Show address configuration dialog"""
        config_window = tk.Toplevel(self.report_window)
        config_window.title("Address Configuration")
        config_window.geometry("600x500")
        config_window.resizable(True, True)
        
        # Create notebook for different sections
        notebook = ttk.Notebook(config_window)
        notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Agencies tab
        agencies_frame = ttk.Frame(notebook)
        notebook.add(agencies_frame, text="Agencies")
        self.create_agencies_config(agencies_frame)
        
        # Sites tab
        sites_frame = ttk.Frame(notebook)
        notebook.add(sites_frame, text="Sites")
        self.create_sites_config(sites_frame)
        
        # Buttons frame
        buttons_frame = ttk.Frame(config_window)
        buttons_frame.pack(fill=tk.X, padx=10, pady=10)
        
        save_btn = ttk.Button(buttons_frame, text="Save Configuration", 
                             command=self.save_address_config)
        save_btn.pack(side=tk.LEFT, padx=5)
        
        close_btn = ttk.Button(buttons_frame, text="Close", 
                              command=config_window.destroy)
        close_btn.pack(side=tk.RIGHT, padx=5)
    
    def create_agencies_config(self, parent):
        """Create agencies configuration interface"""
        # Agencies listbox
        list_frame = ttk.Frame(parent)
        list_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        ttk.Label(list_frame, text="Select Agency:").pack(anchor=tk.W)
        
        self.agencies_listbox = tk.Listbox(list_frame, height=8)
        self.agencies_listbox.pack(fill=tk.BOTH, expand=True, pady=5)
        self.agencies_listbox.bind('<<ListboxSelect>>', self.on_agency_select)
        
        # Agency details frame
        details_frame = ttk.LabelFrame(parent, text="Agency Details", padding=10)
        details_frame.pack(fill=tk.X, padx=10, pady=10)
        
        # Agency name
        ttk.Label(details_frame, text="Agency Name:").grid(row=0, column=0, sticky=tk.W, pady=2)
        self.agency_name_var = tk.StringVar()
        ttk.Entry(details_frame, textvariable=self.agency_name_var, width=40).grid(row=0, column=1, sticky=tk.EW, pady=2)
        
        # Address
        ttk.Label(details_frame, text="Address:").grid(row=1, column=0, sticky=tk.W, pady=2)
        self.agency_address_text = tk.Text(details_frame, height=3, width=40)
        self.agency_address_text.grid(row=1, column=1, sticky=tk.EW, pady=2)
        
        # Contact
        ttk.Label(details_frame, text="Contact:").grid(row=2, column=0, sticky=tk.W, pady=2)
        self.agency_contact_var = tk.StringVar()
        ttk.Entry(details_frame, textvariable=self.agency_contact_var, width=40).grid(row=2, column=1, sticky=tk.EW, pady=2)
        
        # Email
        ttk.Label(details_frame, text="Email:").grid(row=3, column=0, sticky=tk.W, pady=2)
        self.agency_email_var = tk.StringVar()
        ttk.Entry(details_frame, textvariable=self.agency_email_var, width=40).grid(row=3, column=1, sticky=tk.EW, pady=2)
        
        details_frame.columnconfigure(1, weight=1)
        
        # Buttons
        btn_frame = ttk.Frame(details_frame)
        btn_frame.grid(row=4, column=0, columnspan=2, pady=10)
        
        ttk.Button(btn_frame, text="Add Agency", command=self.add_agency).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Update Agency", command=self.update_agency).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Delete Agency", command=self.delete_agency).pack(side=tk.LEFT, padx=5)
        
        # Load agencies
        self.load_agencies_list()
    
    def create_sites_config(self, parent):
        """Create sites configuration interface"""
        # Similar structure for sites
        list_frame = ttk.Frame(parent)
        list_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        ttk.Label(list_frame, text="Select Site:").pack(anchor=tk.W)
        
        self.sites_listbox = tk.Listbox(list_frame, height=8)
        self.sites_listbox.pack(fill=tk.BOTH, expand=True, pady=5)
        self.sites_listbox.bind('<<ListboxSelect>>', self.on_site_select)
        
        # Site details frame
        details_frame = ttk.LabelFrame(parent, text="Site Details", padding=10)
        details_frame.pack(fill=tk.X, padx=10, pady=10)
        
        # Site name
        ttk.Label(details_frame, text="Site Name:").grid(row=0, column=0, sticky=tk.W, pady=2)
        self.site_name_var = tk.StringVar()
        ttk.Entry(details_frame, textvariable=self.site_name_var, width=40).grid(row=0, column=1, sticky=tk.EW, pady=2)
        
        # Address
        ttk.Label(details_frame, text="Address:").grid(row=1, column=0, sticky=tk.W, pady=2)
        self.site_address_text = tk.Text(details_frame, height=3, width=40)
        self.site_address_text.grid(row=1, column=1, sticky=tk.EW, pady=2)
        
        # Contact
        ttk.Label(details_frame, text="Contact:").grid(row=2, column=0, sticky=tk.W, pady=2)
        self.site_contact_var = tk.StringVar()
        ttk.Entry(details_frame, textvariable=self.site_contact_var, width=40).grid(row=2, column=1, sticky=tk.EW, pady=2)
        
        details_frame.columnconfigure(1, weight=1)
        
        # Buttons
        btn_frame = ttk.Frame(details_frame)
        btn_frame.grid(row=3, column=0, columnspan=2, pady=10)
        
        ttk.Button(btn_frame, text="Add Site", command=self.add_site).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Update Site", command=self.update_site).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Delete Site", command=self.delete_site).pack(side=tk.LEFT, padx=5)
        
        # Load sites
        self.load_sites_list()
    
    def load_agencies_list(self):
        """Load agencies into listbox"""
        self.agencies_listbox.delete(0, tk.END)
        for agency_name in self.address_config.get('agencies', {}):
            self.agencies_listbox.insert(tk.END, agency_name)
    
    def load_sites_list(self):
        """Load sites into listbox"""
        self.sites_listbox.delete(0, tk.END)
        for site_name in self.address_config.get('sites', {}):
            self.sites_listbox.insert(tk.END, site_name)
    
    def on_agency_select(self, event):
        """Handle agency selection"""
        selection = self.agencies_listbox.curselection()
        if selection:
            agency_name = self.agencies_listbox.get(selection[0])
            agency_data = self.address_config.get('agencies', {}).get(agency_name, {})
            
            self.agency_name_var.set(agency_data.get('name', agency_name))
            self.agency_address_text.delete(1.0, tk.END)
            self.agency_address_text.insert(1.0, agency_data.get('address', ''))
            self.agency_contact_var.set(agency_data.get('contact', ''))
            self.agency_email_var.set(agency_data.get('email', ''))
    
    def on_site_select(self, event):
        """Handle site selection"""
        selection = self.sites_listbox.curselection()
        if selection:
            site_name = self.sites_listbox.get(selection[0])
            site_data = self.address_config.get('sites', {}).get(site_name, {})
            
            self.site_name_var.set(site_data.get('name', site_name))
            self.site_address_text.delete(1.0, tk.END)
            self.site_address_text.insert(1.0, site_data.get('address', ''))
            self.site_contact_var.set(site_data.get('contact', ''))
    
    def add_agency(self):
        """Add new agency"""
        name = self.agency_name_var.get().strip()
        if not name:
            messagebox.showerror("Error", "Please enter agency name")
            return
        
        agency_data = {
            'name': name,
            'address': self.agency_address_text.get(1.0, tk.END).strip(),
            'contact': self.agency_contact_var.get().strip(),
            'email': self.agency_email_var.get().strip()
        }
        
        if 'agencies' not in self.address_config:
            self.address_config['agencies'] = {}
        
        self.address_config['agencies'][name] = agency_data
        self.load_agencies_list()
        messagebox.showinfo("Success", "Agency added successfully")
    
    def update_agency(self):
        """Update selected agency"""
        selection = self.agencies_listbox.curselection()
        if not selection:
            messagebox.showerror("Error", "Please select an agency to update")
            return
        
        old_name = self.agencies_listbox.get(selection[0])
        new_name = self.agency_name_var.get().strip()
        
        if not new_name:
            messagebox.showerror("Error", "Please enter agency name")
            return
        
        agency_data = {
            'name': new_name,
            'address': self.agency_address_text.get(1.0, tk.END).strip(),
            'contact': self.agency_contact_var.get().strip(),
            'email': self.agency_email_var.get().strip()
        }
        
        # Remove old entry if name changed
        if old_name != new_name and old_name in self.address_config.get('agencies', {}):
            del self.address_config['agencies'][old_name]
        
        self.address_config['agencies'][new_name] = agency_data
        self.load_agencies_list()
        messagebox.showinfo("Success", "Agency updated successfully")
    
    def delete_agency(self):
        """Delete selected agency"""
        selection = self.agencies_listbox.curselection()
        if not selection:
            messagebox.showerror("Error", "Please select an agency to delete")
            return
        
        agency_name = self.agencies_listbox.get(selection[0])
        
        if messagebox.askyesno("Confirm", f"Delete agency '{agency_name}'?"):
            if agency_name in self.address_config.get('agencies', {}):
                del self.address_config['agencies'][agency_name]
                self.load_agencies_list()
                # Clear form
                self.agency_name_var.set('')
                self.agency_address_text.delete(1.0, tk.END)
                self.agency_contact_var.set('')
                self.agency_email_var.set('')
                messagebox.showinfo("Success", "Agency deleted successfully")
    
    def add_site(self):
        """Add new site"""
        name = self.site_name_var.get().strip()
        if not name:
            messagebox.showerror("Error", "Please enter site name")
            return
        
        site_data = {
            'name': name,
            'address': self.site_address_text.get(1.0, tk.END).strip(),
            'contact': self.site_contact_var.get().strip()
        }
        
        if 'sites' not in self.address_config:
            self.address_config['sites'] = {}
        
        self.address_config['sites'][name] = site_data
        self.load_sites_list()
        messagebox.showinfo("Success", "Site added successfully")
    
    def update_site(self):
        """Update selected site"""
        selection = self.sites_listbox.curselection()
        if not selection:
            messagebox.showerror("Error", "Please select a site to update")
            return
        
        old_name = self.sites_listbox.get(selection[0])
        new_name = self.site_name_var.get().strip()
        
        if not new_name:
            messagebox.showerror("Error", "Please enter site name")
            return
        
        site_data = {
            'name': new_name,
            'address': self.site_address_text.get(1.0, tk.END).strip(),
            'contact': self.site_contact_var.get().strip()
        }
        
        # Remove old entry if name changed
        if old_name != new_name and old_name in self.address_config.get('sites', {}):
            del self.address_config['sites'][old_name]
        
        self.address_config['sites'][new_name] = site_data
        self.load_sites_list()
        messagebox.showinfo("Success", "Site updated successfully")
    
    def delete_site(self):
        """Delete selected site"""
        selection = self.sites_listbox.curselection()
        if not selection:
            messagebox.showerror("Error", "Please select a site to delete")
            return
        
        site_name = self.sites_listbox.get(selection[0])
        
        if messagebox.askyesno("Confirm", f"Delete site '{site_name}'?"):
            if site_name in self.address_config.get('sites', {}):
                del self.address_config['sites'][site_name]
                self.load_sites_list()
                # Clear form
                self.site_name_var.set('')
                self.site_address_text.delete(1.0, tk.END)
                self.site_contact_var.set('')
                messagebox.showinfo("Success", "Site deleted successfully")
    
    def save_address_config(self):
        """Save address configuration to file"""
        try:
            config_file = os.path.join(config.DATA_FOLDER, 'address_config.json')
            with open(config_file, 'w') as f:
                json.dump(self.address_config, f, indent=4)
            messagebox.showinfo("Success", "Configuration saved successfully")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save configuration: {str(e)}")


# Legacy export functions for backward compatibility
def export_to_excel(filename=None, data_manager=None):
    """Export records to Excel - now saves to reports folder with proper naming"""
    if not data_manager:
        messagebox.showerror("Error", "Data manager not available")
        return False
        
    try:
        generator = ReportGenerator(None, data_manager)  # None parent for legacy usage
        
        # Auto-select all records for quick export
        generator.all_records = data_manager.get_all_records()
        if not generator.all_records:
            messagebox.showwarning("No Records", "No records found to export.")
            return False
            
        generator.selected_records = [record.get('ticket_no', '') for record in generator.all_records if record.get('ticket_no', '')]
        
        if generator.selected_records:
            generator.export_selected_to_excel()
            return True
        else:
            messagebox.showwarning("No Valid Records", "No valid records with ticket numbers found to export.")
            return False
            
    except Exception as e:
        messagebox.showerror("Export Error", f"Failed to export to Excel:\n{str(e)}")
        print(f"Excel export error: {e}")
        return False

def export_to_pdf(filename=None, data_manager=None):
    """Export records to PDF - now saves to reports folder with proper naming"""
    if not data_manager:
        messagebox.showerror("Error", "Data manager not available")
        return False
        
    try:
        generator = ReportGenerator(None, data_manager)  # None parent for legacy usage
        
        # Auto-select all records for quick export
        generator.all_records = data_manager.get_all_records()
        if not generator.all_records:
            messagebox.showwarning("No Records", "No records found to export.")
            return False
            
        generator.selected_records = [record.get('ticket_no', '') for record in generator.all_records if record.get('ticket_no', '')]
        
        if generator.selected_records:
            generator.export_selected_to_pdf()
            return True
        else:
            messagebox.showwarning("No Valid Records", "No valid records with ticket numbers found to export.")
            return False
            
    except Exception as e:
        messagebox.showerror("Export Error", f"Failed to export to PDF:\n{str(e)}")
        print(f"PDF export error: {e}")
        return False