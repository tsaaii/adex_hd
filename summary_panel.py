import tkinter as tk
from tkinter import ttk, messagebox
import os
import datetime
from PIL import Image, ImageTk
import cv2

import config
from ui_components import HoverButton
from reports import ReportGenerator  # Import the new report generator

class SummaryPanel:
    """Panel for displaying summary of recent entries"""
    
    def __init__(self, parent, data_manager=None):
        """Initialize summary panel
        
        Args:
            parent: Parent widget
            data_manager: Data manager instance
        """
        self.parent = parent
        self.data_manager = data_manager
        
        # Create summary variables
        self.filter_var = tk.StringVar()
        
        # Create UI
        self.create_panel()
        
    def create_panel(self):
        """Create summary panel UI"""
        # Add recent transactions summary
        summary_label = ttk.Label(self.parent, text="Recent Transactions", style="Subtitle.TLabel")
        summary_label.pack(anchor=tk.W, padx=10, pady=(10, 5))
        
        # Top control frame
        control_frame = ttk.Frame(self.parent, style="TFrame")
        control_frame.pack(fill=tk.X, padx=10, pady=(0, 5))
        
        # Filter entry
        ttk.Label(control_frame, text="Filter:").pack(side=tk.LEFT, padx=(0, 5))
        ttk.Entry(control_frame, textvariable=self.filter_var, width=20).pack(side=tk.LEFT, padx=(0, 10))
        self.filter_var.trace_add("write", self.apply_filter)
        
        # Export options
        ttk.Label(control_frame, text="Export:").pack(side=tk.LEFT, padx=(20, 5))
        
        # Excel export button - now uses new report system
        excel_btn = HoverButton(control_frame, 
                              text="Excel", 
                              bg=config.COLORS["secondary"],
                              fg=config.COLORS["button_text"],
                              padx=5, pady=2,
                              command=self.export_to_excel)
        excel_btn.pack(side=tk.LEFT, padx=2)
        
        # PDF export button - now uses new report system
        pdf_btn = HoverButton(control_frame, 
                            text="PDF", 
                            bg=config.COLORS["primary"],
                            fg=config.COLORS["button_text"],
                            padx=5, pady=2,
                            command=self.export_to_pdf)
        pdf_btn.pack(side=tk.LEFT, padx=2)
        
        # Advanced Report button - opens full report dialog
        advanced_btn = HoverButton(control_frame, 
                                  text="Advanced Reports", 
                                  bg=config.COLORS["button_alt"],
                                  fg=config.COLORS["button_text"],
                                  padx=5, pady=2,
                                  command=self.show_advanced_reports)
        advanced_btn.pack(side=tk.LEFT, padx=2)
        
        # Summary frame with table
        summary_frame = ttk.LabelFrame(self.parent, text="Recent Entries")
        summary_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))
        
        # Create treeview for table
        columns = ("date", "vehicle", "ticket", "agency", "material", "first_weight", "second_weight", "net_weight", "images")
        self.summary_tree = ttk.Treeview(summary_frame, columns=columns, show="headings", height=10)
        
        # Define column headings
        self.summary_tree.heading("date", text="Date")
        self.summary_tree.heading("vehicle", text="Vehicle No")
        self.summary_tree.heading("ticket", text="Ticket No")
        self.summary_tree.heading("agency", text="Agency Name")
        self.summary_tree.heading("material", text="Material")
        self.summary_tree.heading("first_weight", text="First Weight")
        self.summary_tree.heading("second_weight", text="Second Weight")
        self.summary_tree.heading("net_weight", text="Net Weight")
        self.summary_tree.heading("images", text="Images")
        
        # Define column widths
        self.summary_tree.column("date", width=80)
        self.summary_tree.column("vehicle", width=90)
        self.summary_tree.column("ticket", width=70)
        self.summary_tree.column("agency", width=90)
        self.summary_tree.column("material", width=70)
        self.summary_tree.column("first_weight", width=80)
        self.summary_tree.column("second_weight", width=80)
        self.summary_tree.column("net_weight", width=70)
        self.summary_tree.column("images", width=50)
        
        # Add scrollbar
        summary_scrollbar = ttk.Scrollbar(summary_frame, orient=tk.VERTICAL, command=self.summary_tree.yview)
        self.summary_tree.configure(yscroll=summary_scrollbar.set)
        
        # Pack widgets
        summary_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.summary_tree.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Buttons frame
        buttons_frame = ttk.Frame(self.parent, style="TFrame")
        buttons_frame.pack(fill=tk.X, padx=10, pady=5)
        
        # Refresh button
        refresh_btn = HoverButton(buttons_frame, 
                                text="Refresh", 
                                bg=config.COLORS["primary"],
                                fg=config.COLORS["button_text"],
                                padx=8, pady=3,
                                command=self.update_summary)
        refresh_btn.pack(side=tk.LEFT, padx=5)
        
        # View details button
        details_btn = HoverButton(buttons_frame, 
                                text="View Details", 
                                bg=config.COLORS["primary"],
                                fg=config.COLORS["button_text"],
                                padx=8, pady=3,
                                command=self.view_entry_details)
        details_btn.pack(side=tk.LEFT, padx=5)
    
    def update_summary(self):
        """Update the summary tree with recent records"""
        # Clear existing items
        for item in self.summary_tree.get_children():
            self.summary_tree.delete(item)
            
        if not self.data_manager:
            return
            
        # Get records with filter applied
        filter_text = self.filter_var.get()
        records = self.data_manager.get_filtered_records(filter_text)
        
        # Show most recent first (limited to 300 for performance)
        for i, record in enumerate(reversed(records[-300:])):
            # Check for images
            image_info = "None"
            front_img = record.get('front_image', '')
            back_img = record.get('back_image', '')
            
            if front_img and back_img:
                image_info = "F & B"
            elif front_img:
                image_info = "Front"
            elif back_img:
                image_info = "Back"
            
            # Add to treeview
            self.summary_tree.insert("", tk.END, values=(
                record.get('date', ''),
                record.get('vehicle_no', ''),
                record.get('ticket_no', ''),
                record.get('agency_name', ''),
                record.get('material', ''),
                record.get('first_weight', ''),
                record.get('second_weight', ''),
                record.get('net_weight', ''),
                image_info
            ))
        
        # Alternate row colors
        self._apply_row_colors()
    
    def _apply_row_colors(self):
        """Apply alternating row colors to treeview"""
        for i, item in enumerate(self.summary_tree.get_children()):
            if i % 2 == 0:
                self.summary_tree.item(item, tags=("evenrow",))
            else:
                self.summary_tree.item(item, tags=("oddrow",))
        
        self.summary_tree.tag_configure("evenrow", background=config.COLORS["table_row_even"])
        self.summary_tree.tag_configure("oddrow", background=config.COLORS["table_row_odd"])
    
    def apply_filter(self, *args):
        """Apply filter to records"""
        self.update_summary()
    
    def export_to_excel(self):
        """Export records to Excel using new report system"""
        try:
            if not self.data_manager:
                messagebox.showerror("Error", "No data manager available")
                return
                
            # Get all records
            all_records = self.data_manager.get_all_records()
            
            if not all_records:
                messagebox.showwarning("No Records", "No records found to export.")
                return
            
            # Create report generator
            generator = ReportGenerator(self.parent, self.data_manager)
            
            # Set all records as selected for quick export
            generator.all_records = all_records
            generator.selected_records = [record.get('ticket_no', '') for record in all_records]
            
            # Export to Excel
            generator.export_selected_to_excel()
            
        except Exception as e:
            messagebox.showerror("Export Error", f"Failed to export to Excel:\n{str(e)}")
    
    def export_to_pdf(self):
        """Export records to PDF using new report system"""
        try:
            if not self.data_manager:
                messagebox.showerror("Error", "No data manager available")
                return
                
            # Get all records
            all_records = self.data_manager.get_all_records()
            
            if not all_records:
                messagebox.showwarning("No Records", "No records found to export.")
                return
            
            # Create report generator
            generator = ReportGenerator(self.parent, self.data_manager)
            
            # Set all records as selected for quick export
            generator.all_records = all_records
            generator.selected_records = [record.get('ticket_no', '') for record in all_records]
            
            # Export to PDF
            generator.export_selected_to_pdf()
            
        except Exception as e:
            messagebox.showerror("Export Error", f"Failed to export to PDF:\n{str(e)}")
    
    def show_advanced_reports(self):
        """Show the advanced report dialog with filtering and selection options"""
        try:
            if not self.data_manager:
                messagebox.showerror("Error", "No data manager available")
                return
                
            # Create and show the report generator dialog
            generator = ReportGenerator(self.parent, self.data_manager)
            generator.show_report_dialog()
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to open advanced reports:\n{str(e)}")
    
    def view_entry_details(self):
        """View details of selected entry"""
        selected_item = self.summary_tree.selection()
        if not selected_item:
            messagebox.showinfo("Selection", "Please select a record to view details.")
            return
        
        # Get vehicle number from selected item
        vehicle_no = self.summary_tree.item(selected_item, "values")[1]  # Vehicle No is index 1
        
        # Get record from data manager
        if self.data_manager:
            record = self.data_manager.get_record_by_vehicle(vehicle_no)
            if record:
                self.display_record_details(record)
            else:
                messagebox.showinfo("Not Found", f"Details for vehicle {vehicle_no} not found.")
    
    def display_record_details(self, record):
        """Display details of a record in a popup window"""
        details_window = tk.Toplevel(self.parent)
        details_window.title(f"Entry Details - {record.get('vehicle_no', '')}")
        details_window.geometry("650x500")
        details_window.configure(bg=config.COLORS["background"])
        
        # Details frame
        details_frame = ttk.LabelFrame(details_window, text="Entry Information")
        details_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Create two columns for details
        left_frame = ttk.Frame(details_frame)
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        right_frame = ttk.Frame(details_frame)
        right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Display all fields in two columns
        # Left column
        row = 0
        for label, value in [
            ("Date:", record.get('date', '')),
            ("Time:", record.get('time', '')),
            ("Site Name:", record.get('site_name', '')),
            ("Agency Name:", record.get('agency_name', '')),
            ("Input Material:", record.get('material', '')),
            ("Ticket No:", record.get('ticket_no', '')),
            ("Vehicle No:", record.get('vehicle_no', ''))
        ]:
            ttk.Label(left_frame, text=label, font=("Segoe UI", 9, "bold")).grid(row=row, column=0, sticky=tk.W, pady=2)
            ttk.Label(left_frame, text=value).grid(row=row, column=1, sticky=tk.W, pady=2, padx=5)
            row += 1
        
        # Right column
        row = 0
        for label, value in [
            ("Transfer Party:", record.get('transfer_party_name', '')),
            ("First Weight:", record.get('first_weight', '')),
            ("First Timestamp:", record.get('first_timestamp', '')),
            ("Second Weight:", record.get('second_weight', '')),
            ("Second Timestamp:", record.get('second_timestamp', '')),
            ("Net Weight:", record.get('net_weight', '')),
            ("Material Type:", record.get('material_type', ''))
        ]:
            ttk.Label(right_frame, text=label, font=("Segoe UI", 9, "bold")).grid(row=row, column=0, sticky=tk.W, pady=2)
            ttk.Label(right_frame, text=value).grid(row=row, column=1, sticky=tk.W, pady=2, padx=5)
            row += 1
        
        # Images frame
        images_frame = ttk.LabelFrame(details_window, text="Vehicle Images")
        images_frame.pack(fill=tk.X, padx=10, pady=(0, 10))
        
        # Display images in a row
        front_img_name = record.get('front_image', '')
        back_img_name = record.get('back_image', '')
        
        images_inner = ttk.Frame(images_frame)
        images_inner.pack(fill=tk.X, padx=5, pady=5)
        
        # Front image
        front_frame = ttk.LabelFrame(images_inner, text="Front")
        front_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=2)
        
        self.display_image_in_frame(front_frame, front_img_name, 200, 150)
        
        # Back image
        back_frame = ttk.LabelFrame(images_inner, text="Back")
        back_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=2)
        
        self.display_image_in_frame(back_frame, back_img_name, 200, 150)
        
        # Close button
        close_btn = HoverButton(details_window, 
                               text="Close", 
                               bg=config.COLORS["primary"],
                               fg=config.COLORS["button_text"],
                               padx=10, pady=3,
                               command=details_window.destroy)
        close_btn.pack(pady=5)
    
    def display_image_in_frame(self, parent, image_name, width, height):
        """Display an image in the given frame with specified size"""
        if image_name:
            image_path = os.path.join(config.IMAGES_FOLDER, image_name)
            if os.path.exists(image_path):
                try:
                    # Read image and resize
                    img = cv2.imread(image_path)
                    img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
                    img = cv2.resize(img, (width, height))
                    
                    # Convert to PhotoImage
                    photo = ImageTk.PhotoImage(image=Image.fromarray(img))
                    
                    # Display
                    label = tk.Label(parent, image=photo)
                    label.image = photo  # Keep reference
                    label.pack(fill=tk.BOTH, expand=True)
                except Exception as e:
                    ttk.Label(parent, text=f"Error: {str(e)}").pack(pady=20)
            else:
                ttk.Label(parent, text="Image not found").pack(pady=20)
        else:
            ttk.Label(parent, text="No image").pack(pady=20)