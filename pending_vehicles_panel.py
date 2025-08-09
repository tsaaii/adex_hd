import tkinter as tk
from tkinter import ttk, messagebox
import datetime
import threading
import logging

import config
from ui_components import HoverButton

import logging
import threading
import time
import contextlib
import os
import csv

# Global lock for file operations
_pending_file_lock = threading.RLock()

class SafeLogger:
    """Thread-safe logger that handles closed file scenarios gracefully"""
    
    def __init__(self, name, fallback_to_print=True):
        self.name = name
        self.fallback_to_print = fallback_to_print
        self._lock = threading.Lock()
        self._logger = None
        self._setup_logger()
    
    def _setup_logger(self):
        """Setup logger with safe file handling"""
        try:
            self._logger = logging.getLogger(self.name)
            # Don't add multiple handlers
            if not self._logger.handlers:
                handler = logging.StreamHandler()
                formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
                handler.setFormatter(formatter)
                self._logger.addHandler(handler)
                self._logger.setLevel(logging.INFO)
        except Exception as e:
            print(f"Logger setup failed for {self.name}: {e}")
            self._logger = None
    
    def _safe_log(self, level, message):
        """Thread-safe logging with fallback"""
        with self._lock:
            try:
                if self._logger:
                    getattr(self._logger, level)(message)
                    return True
            except (ValueError, OSError, AttributeError) as e:
                if "closed file" in str(e).lower():
                    if self.fallback_to_print:
                        print(f"[{self.name}-{level.upper()}] {message}")
                    return False
                else:
                    raise
            except Exception as e:
                if self.fallback_to_print:
                    print(f"[{self.name}-{level.upper()}] {message} (LOG_ERROR: {e})")
                return False
        return False
    
    def info(self, message):
        self._safe_log('info', message)
    
    def warning(self, message):
        self._safe_log('warning', message)
    
    def error(self, message):
        self._safe_log('error', message)
    
    def debug(self, message):
        self._safe_log('debug', message)

@contextlib.contextmanager
def safe_file_operation(retries=3, delay=0.1):
    """Context manager for safe file operations with retries"""
    for attempt in range(retries):
        try:
            with _pending_file_lock:
                yield
            break
        except (OSError, ValueError) as e:
            if "closed file" in str(e).lower() or "I/O operation" in str(e).lower():
                if attempt < retries - 1:
                    time.sleep(delay * (attempt + 1))
                    continue
                else:
                    print(f"File operation failed after {retries} attempts: {e}")
                    raise
            else:
                raise
        except Exception as e:
            print(f"Unexpected error in file operation: {e}")
            raise

def safe_csv_read(file_path, retries=3):
    """Safely read CSV file with retries and proper error handling"""
    if not os.path.exists(file_path):
        return []
    
    for attempt in range(retries):
        try:
            with safe_file_operation():
                with open(file_path, 'r', newline='', encoding='utf-8', errors='replace') as csv_file:
                    reader = csv.DictReader(csv_file)
                    records = list(reader)
                return records
        except (OSError, ValueError) as e:
            if "closed file" in str(e).lower() and attempt < retries - 1:
                print(f"CSV read attempt {attempt + 1} failed, retrying: {e}")
                time.sleep(0.2 * (attempt + 1))
                continue
            else:
                print(f"CSV read failed after {retries} attempts: {e}")
                return []
        except Exception as e:
            print(f"Unexpected CSV read error: {e}")
            return []
    
    return []

class PendingVehiclesPanel:
    """FIXED: Panel to display and manage vehicles waiting for second weighment with enhanced logging"""
    
    def __init__(self, parent, data_manager=None, on_vehicle_select=None):
        """Initialize the pending vehicles panel
        
        Args:
            parent: Parent widget
            data_manager: Data manager instance
            on_vehicle_select: Callback for when a vehicle is selected for second weighment
        """
        self.parent = parent
        self.data_manager = data_manager
        self.on_vehicle_select = on_vehicle_select
        
        # Set up logging
        self.logger = logging.getLogger('PendingVehiclesPanel')
        self.logger.info("PendingVehiclesPanel initialized")
        
        # Configure parent widget to handle resizing
        # This is critical for proper resize behavior
        if isinstance(parent, tk.Frame) or isinstance(parent, ttk.Frame):
            parent.columnconfigure(0, weight=1)
            parent.rowconfigure(0, weight=1)
        
        # Create panel
        self.create_panel()
    
    def create_panel(self):
        """Create the pending vehicles panel with proper resize support"""
        # Main frame - using grid instead of pack for better resize control
        main_frame = ttk.LabelFrame(self.parent, text="")  # Empty text, we'll add custom header
        main_frame.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        
        # Configure the main frame for resizing
        main_frame.columnconfigure(0, weight=1)
        main_frame.rowconfigure(1, weight=1)  # Row 1 is the treeview container
        
        # Create a custom header with logo and text
        header_frame = ttk.Frame(main_frame)
        header_frame.grid(row=0, column=0, sticky="ew", padx=2, pady=(2, 5))
        

        # Add the title text
        title_label = ttk.Label(header_frame, 
                               text="Pending Second Weighment", 
                               font=("Segoe UI", 10, "bold"),
                               foreground=config.COLORS["primary"])
        title_label.pack(side=tk.LEFT, padx=2)
        
        # Create a refresh button with just an icon on the right
        refresh_btn = HoverButton(header_frame, 
                               text="↻", 
                               font=("Segoe UI", 14, "bold"),
                               bg=config.COLORS["primary"],
                               fg=config.COLORS["button_text"],
                               width=2, height=1,
                               command=self.refresh_pending_list,
                               relief=tk.FLAT)
        refresh_btn.pack(side=tk.RIGHT, padx=5)
        
        # Create the inner frame that will hold the treeview
        inner_frame = ttk.Frame(main_frame)
        inner_frame.grid(row=1, column=0, sticky="nsew", padx=2, pady=2)
        
        # Configure the inner frame for resizing
        inner_frame.columnconfigure(0, weight=1)
        inner_frame.rowconfigure(0, weight=1)
        
        # Create treeview for pending vehicles
        columns = ("ticket", "vehicle", "timestamp")
        self.tree = ttk.Treeview(inner_frame, columns=columns, show="headings")
        
        # Define column headings with more compact labels
        self.tree.heading("ticket", text="Ticket#")
        self.tree.heading("vehicle", text="Vehicle#")
        self.tree.heading("timestamp", text="Time")
        
        # Define column widths - with weight distribution for dynamic resizing
        self.tree.column("ticket", width=60, minwidth=40)
        self.tree.column("vehicle", width=80, minwidth=60)
        self.tree.column("timestamp", width=60, minwidth=40)
        
        # Add scrollbar
        scrollbar = ttk.Scrollbar(inner_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscroll=scrollbar.set)
        
        # Use grid layout for proper resizing
        self.tree.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")
        
        # Bind double-click event
        self.tree.bind("<Double-1>", self.on_item_double_click)
        
        # Add Select button below the treeview
        select_btn = HoverButton(main_frame, 
                              text="Select for Weighment", 
                              bg=config.COLORS["primary"],
                              fg=config.COLORS["button_text"],
                              padx=5, pady=2,
                              command=self.select_vehicle)
        select_btn.grid(row=2, column=0, sticky="ew", padx=5, pady=5)
        
        # Populate the list initially
        self.refresh_pending_list()
    
    def select_vehicle(self):
        """Select the currently highlighted vehicle"""
        selected_items = self.tree.selection()
        if not selected_items:
            messagebox.showinfo("Selection", "Please select a vehicle from the list")
            return
            
        # Get ticket number from selected item
        ticket_no = self.tree.item(selected_items[0], "values")[0]
        
        self.logger.info(f"Vehicle selected: {ticket_no}")
        
        # Call callback with ticket number
        if self.on_vehicle_select and ticket_no:
            self.on_vehicle_select(ticket_no)



    def format_timestamp(self, timestamp):
        """Format timestamp to show just time if it's today"""
        if not timestamp:
            return ""
            
        try:
            # Parse the timestamp
            dt = datetime.datetime.strptime(timestamp, "%d-%m-%Y %H:%M:%S")
            
            # If it's today, just show the time in a more compact format
            if dt.date() == datetime.datetime.now().date():
                return dt.strftime("%H:%M")  # Removed seconds for compactness
            else:
                return dt.strftime("%d-%m %H:%M")  # Short date format
        except:
            return timestamp
    
    def _apply_row_colors(self):
        """Apply alternating row colors to treeview"""
        for i, item in enumerate(self.tree.get_children()):
            if i % 2 == 0:
                self.tree.item(item, tags=("evenrow",))
            else:
                self.tree.item(item, tags=("oddrow",))
        
        self.tree.tag_configure("evenrow", background=config.COLORS["table_row_even"])
        self.tree.tag_configure("oddrow", background=config.COLORS["table_row_odd"])
    
    def on_item_double_click(self, event):
        """Handle double-click on an item"""
        # Get the selected item
        selection = self.tree.selection()
        if not selection:
            return
            
        # Get the ticket number from the selected item
        ticket_no = self.tree.item(selection[0], "values")[0]
        
        self.logger.info(f"Double-clicked on ticket: {ticket_no}")
        
        # Call the callback if provided
        if self.on_vehicle_select and ticket_no:
            self.on_vehicle_select(ticket_no)
            
    def refresh_pending_list(self):
        """FIXED: Refresh pending vehicles list with comprehensive error handling"""
        # Use safe logger
        if not hasattr(self, 'safe_logger'):
            self.safe_logger = SafeLogger('PendingVehicles')
        
        try:
            self.safe_logger.info("Refreshing pending vehicles list")
            
            # Check if widget still exists
            if not hasattr(self, 'tree') or not self.tree.winfo_exists():
                self.safe_logger.warning("Tree widget no longer exists - skipping refresh")
                return
            
            # Check data manager availability
            if not self.data_manager:
                self.safe_logger.warning("No data manager available")
                return
            
            # Check shutdown status
            if hasattr(self.data_manager, 'is_shutting_down') and self.data_manager.is_shutting_down:
                self.safe_logger.info("Data manager is shutting down - skipping refresh")
                return
            
            # Clear existing items
            for item in self.tree.get_children():
                self.tree.delete(item)
            
            # Get records with safe operations
            records = safe_csv_read(self.data_manager.get_current_data_file())
            self.safe_logger.info(f"Retrieved {len(records)} total records")
            
            # Filter for pending vehicles
            pending_records = []
            seen_vehicles = set()
            
            for record in records:
                # Normalize field names
                ticket_no = record.get('Ticket No', record.get('ticket_no', 'Unknown'))
                vehicle_no = record.get('Vehicle No', record.get('vehicle_no', '')).strip().upper()
                
                # Check if has first but missing second weighment
                first_weight = record.get('First Weight', record.get('first_weight', '')).strip()
                first_timestamp = record.get('First Timestamp', record.get('first_timestamp', '')).strip()
                second_weight = record.get('Second Weight', record.get('second_weight', '')).strip()
                second_timestamp = record.get('Second Timestamp', record.get('second_timestamp', '')).strip()
                
                has_first = bool(first_weight and first_timestamp)
                missing_second = not bool(second_weight and second_timestamp)
                
                if has_first and missing_second and vehicle_no not in seen_vehicles:
                    pending_records.append(record)
                    seen_vehicles.add(vehicle_no)
                    self.safe_logger.info(f"Added to pending: {ticket_no} (vehicle: {vehicle_no})")
            
            # Add to treeview
            for record in reversed(pending_records):  # Most recent first
                ticket_no = record.get('Ticket No', record.get('ticket_no', ''))
                vehicle_no = record.get('Vehicle No', record.get('vehicle_no', ''))
                timestamp = record.get('First Timestamp', record.get('first_timestamp', ''))
                
                self.tree.insert("", tk.END, values=(
                    ticket_no,
                    vehicle_no,
                    self.format_timestamp(timestamp)
                ))
            
            # Apply row colors
            self._apply_row_colors()
            
            self.safe_logger.info(f"Successfully refreshed pending list with {len(pending_records)} unique vehicles")
            
        except Exception as e:
            error_str = str(e).lower()
            if "closed file" in error_str or "i/o operation" in error_str:
                self.safe_logger.error(f"File I/O error during refresh: {e}")
                # Schedule retry instead of crashing
                if hasattr(self, 'parent') and self.parent:
                    self.parent.after(30000, self.refresh_pending_list)  # Retry in 30 seconds
            else:
                self.safe_logger.error(f"Error refreshing pending vehicles list: {e}")


    def schedule_next_refresh(self):
        """Schedule the next automatic refresh with error handling"""
        try:
            # Only schedule if widget still exists and not shutting down
            if (hasattr(self, 'tree') and self.tree.winfo_exists() and 
                hasattr(self, 'parent') and self.parent):
                
                # Check if data manager is shutting down
                if (hasattr(self, 'data_manager') and 
                    hasattr(self.data_manager, 'is_shutting_down') and 
                    self.data_manager.is_shutting_down):
                    print("[SCHEDULE] Skipping refresh schedule - data manager shutting down")
                    return
                
                # Schedule next refresh in 60 seconds (60000 milliseconds)
                self.parent.after(60000, self.refresh_pending_list)
                print("[SCHEDULE] Next pending refresh scheduled in 60 seconds")
        except Exception as e:
            self.logger.error(f"Error scheduling next refresh: {e}")


    def shutdown(self):
        """Graceful shutdown of the pending vehicles panel"""
        try:
            print("🚛 PENDING DEBUG: Shutting down pending vehicles panel")
            self.logger.info("Shutting down pending vehicles panel")
            
            # Cancel any scheduled refreshes
            if hasattr(self, 'parent') and self.parent:
                # Try to cancel any pending after() calls
                try:
                    # This won't cancel all, but it's better than nothing
                    pass
                except:
                    pass
            
            print("🚛 PENDING DEBUG: Pending vehicles panel shutdown completed")
            
        except Exception as e:
            print(f"🚛 PENDING DEBUG: Error during shutdown: {e}")        

    def remove_saved_record(self, ticket_no):
        """FIXED: Remove a record from the pending list after it's saved with second weighment
        
        Args:
            ticket_no: Ticket number to remove
        """
        if not ticket_no:
            print(f"🚛 PENDING DEBUG: ❌ remove_saved_record called with empty ticket_no")
            self.logger.warning("remove_saved_record called with empty ticket_no")
            return
            
        print(f"🚛 PENDING DEBUG: Attempting to remove ticket {ticket_no} from pending list")
        self.logger.info(f"Attempting to remove ticket {ticket_no} from pending list")
        
        try:
            # Find and remove the record with this ticket number
            removed = False
            for item in self.tree.get_children():
                item_values = self.tree.item(item, "values")
                if len(item_values) > 0 and item_values[0] == ticket_no:
                    self.tree.delete(item)
                    removed = True
                    print(f"🚛 PENDING DEBUG:  Removed ticket {ticket_no} from pending list")
                    self.logger.info(f"Removed ticket {ticket_no} from pending list")
                    break
                    
            if not removed:
                print(f"🚛 PENDING DEBUG: ⚠️  Ticket {ticket_no} not found in pending list for removal")
                self.logger.warning(f"Ticket {ticket_no} not found in pending list for removal")
                # Refresh the entire list to ensure consistency
                print(f"🚛 PENDING DEBUG: Refreshing entire list to ensure consistency")
                self.refresh_pending_list()
            else:
                # Apply alternating row colors after removal
                self._apply_row_colors()
                
        except Exception as e:
            print(f"🚛 PENDING DEBUG: ❌ Error removing ticket {ticket_no} from pending list: {e}")
            self.logger.error(f"Error removing ticket {ticket_no} from pending list: {e}")
            # Refresh the entire list as fallback
            print(f"🚛 PENDING DEBUG: Refreshing entire list as fallback after error")
            self.refresh_pending_list()