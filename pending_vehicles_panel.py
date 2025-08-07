import tkinter as tk
from tkinter import ttk, messagebox
import datetime
import threading
import logging

import config
from ui_components import HoverButton

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
        """ENHANCED: Refresh pending list and prevent duplicates"""
        try:
            print(f"🚛 PENDING DEBUG: Refreshing pending vehicles list...")
            self.logger.info("Refreshing pending vehicles list")
            
            # Check if the tree widget still exists
            if not hasattr(self, 'tree') or not self.tree.winfo_exists():
                print(f"🚛 PENDING DEBUG: ❌ Tree widget no longer exists - skipping refresh")
                self.logger.warning("Tree widget no longer exists - skipping refresh")
                return
                
            # Clear existing items
            for item in self.tree.get_children():
                self.tree.delete(item)
                
            if not self.data_manager:
                print(f"🚛 PENDING DEBUG: ❌ No data manager available")
                self.logger.warning("No data manager available")
                return
                
            # Get all records
            records = self.data_manager.get_all_records()
            print(f"🚛 PENDING DEBUG: Retrieved {len(records)} total records")
            self.logger.info(f"Retrieved {len(records)} total records")
            
            # Filter for pending vehicles - only one record per vehicle
            pending_records = []
            seen_vehicle_numbers = set()  # Track vehicle numbers already added
            duplicate_count = 0
            
            for record in records:
                ticket_no = record.get('ticket_no', 'Unknown')
                vehicle_no = record.get('vehicle_no', '').strip().upper()  # Normalize
                
                # Check if record has first weighment but missing second
                first_weight = record.get('first_weight', '').strip()
                first_timestamp = record.get('first_timestamp', '').strip()
                has_first = first_weight != '' and first_timestamp != ''
                
                second_weight = record.get('second_weight', '').strip()
                second_timestamp = record.get('second_timestamp', '').strip()
                missing_second = (second_weight == '' or second_timestamp == '')
                
                # Debug print for each record
                print(f"🚛 PENDING DEBUG: Checking ticket {ticket_no}:")
                print(f"   - vehicle_no: '{vehicle_no}'")
                print(f"   - has_first: {has_first}, missing_second: {missing_second}")
                
                if has_first and missing_second:
                    if vehicle_no in seen_vehicle_numbers:
                        duplicate_count += 1
                        print(f"🚛 PENDING DEBUG: ⚠️  DUPLICATE VEHICLE: {vehicle_no} already in pending - skipping {ticket_no}")
                        self.logger.warning(f"Duplicate vehicle {vehicle_no} - skipping ticket {ticket_no}")
                        continue
                    
                    # Add to pending and mark vehicle as seen
                    pending_records.append(record)
                    seen_vehicle_numbers.add(vehicle_no)
                    print(f"🚛 PENDING DEBUG: ✅ Added to pending: {ticket_no} (vehicle: {vehicle_no})")
                    self.logger.info(f"Added to pending: {ticket_no} (vehicle: {vehicle_no})")
                else:
                    print(f"🚛 PENDING DEBUG: ⏭️  Skipped ticket {ticket_no} - not pending")
            
            print(f"🚛 PENDING DEBUG: Found {len(pending_records)} unique pending vehicles")
            print(f"🚛 PENDING DEBUG: Prevented {duplicate_count} duplicate vehicles from showing")
            self.logger.info(f"Found {len(pending_records)} unique pending vehicles, prevented {duplicate_count} duplicates")
            
            # Add to treeview, most recent first
            for record in reversed(pending_records):
                ticket_no = record.get('ticket_no', '')
                vehicle_no = record.get('vehicle_no', '')
                timestamp = record.get('first_timestamp', '')
                
                self.tree.insert("", tk.END, values=(
                    ticket_no,
                    vehicle_no,
                    self.format_timestamp(timestamp)
                ))
                print(f"🚛 PENDING DEBUG: Added to treeview: {ticket_no} - {vehicle_no}")
            
            # Apply alternating row colors
            self._apply_row_colors()
            
            print(f"🚛 PENDING DEBUG: ✅ Successfully refreshed pending list with {len(pending_records)} unique vehicles")
            self.logger.info(f"Successfully refreshed pending list with {len(pending_records)} unique vehicles")
            
        except Exception as e:
            print(f"🚛 PENDING DEBUG: ❌ Error refreshing pending vehicles list: {e}")
            self.logger.error(f"Error refreshing pending vehicles list: {e}")

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
                    print(f"🚛 PENDING DEBUG: ✅ Removed ticket {ticket_no} from pending list")
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