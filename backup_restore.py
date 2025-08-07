import os
import shutil
import datetime
import zipfile
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

import config
from ui_components import HoverButton

class BackupRestore:
    """Class for managing backup and restore of application data"""
    
    def __init__(self, parent):
        """Initialize the backup restore module
        
        Args:
            parent: Parent widget
        """
        self.parent = parent
        self.backup_folder = os.path.join(config.DATA_FOLDER, 'backups')
        self.ensure_backup_folder()
        
    def ensure_backup_folder(self):
        """Ensure the backup folder exists"""
        if not os.path.exists(self.backup_folder):
            os.makedirs(self.backup_folder)
            
    def create_backup_panel(self):
        """Create the backup and restore panel"""
        # Main frame
        backup_frame = ttk.LabelFrame(self.parent, text="Backup and Restore")
        backup_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Info text
        info_label = ttk.Label(backup_frame, 
                              text="Create backup files of your data or restore from previous backups.",
                              wraplength=450)
        info_label.pack(pady=10)
        
        # Buttons frame
        buttons_frame = ttk.Frame(backup_frame)
        buttons_frame.pack(pady=10)
        
        # Create Backup button
        backup_btn = HoverButton(buttons_frame, 
                               text="Create Backup", 
                               bg=config.COLORS["primary"],
                               fg=config.COLORS["button_text"],
                               padx=10, pady=5,
                               command=self.create_backup)
        backup_btn.pack(side=tk.LEFT, padx=10)
        
        # Restore button
        restore_btn = HoverButton(buttons_frame, 
                                text="Restore from Backup", 
                                bg=config.COLORS["secondary"],
                                fg=config.COLORS["button_text"],
                                padx=10, pady=5,
                                command=self.restore_backup)
        restore_btn.pack(side=tk.LEFT, padx=10)
        
        # Export backup button
        export_btn = HoverButton(buttons_frame, 
                               text="Export Backup", 
                               bg=config.COLORS["button_alt"],
                               fg=config.COLORS["button_text"],
                               padx=10, pady=5,
                               command=self.export_backup)
        export_btn.pack(side=tk.LEFT, padx=10)
        
        # Recent backups list
        list_frame = ttk.LabelFrame(backup_frame, text="Recent Backups")
        list_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=(10,5))
        
        # Create treeview for backups
        columns = ("date", "time", "files", "size")
        self.backups_tree = ttk.Treeview(list_frame, columns=columns, show="headings", height=8)
        
        # Define column headings
        self.backups_tree.heading("date", text="Date")
        self.backups_tree.heading("time", text="Time")
        self.backups_tree.heading("files", text="Files")
        self.backups_tree.heading("size", text="Size")
        
        # Define column widths
        self.backups_tree.column("date", width=100)
        self.backups_tree.column("time", width=80)
        self.backups_tree.column("files", width=150)
        self.backups_tree.column("size", width=80)
        
        # Add scrollbar
        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.backups_tree.yview)
        self.backups_tree.configure(yscroll=scrollbar.set)
        
        # Pack widgets
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.backups_tree.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Refresh the backups list
        self.refresh_backups_list()
        
        return backup_frame
        
    def refresh_backups_list(self):
        """Refresh the list of backups"""
        try:
            # Clear existing items
            for item in self.backups_tree.get_children():
                self.backups_tree.delete(item)
                
            # Get list of backup folders
            backups = []
            if os.path.exists(self.backup_folder):
                for backup_name in os.listdir(self.backup_folder):
                    backup_path = os.path.join(self.backup_folder, backup_name)
                    if os.path.isdir(backup_path):
                        # Extract date and time from folder name
                        try:
                            date_str, time_str = backup_name.split('_')
                            # Format date
                            date_obj = datetime.datetime.strptime(date_str, "%Y%m%d")
                            formatted_date = date_obj.strftime("%d-%m-%Y")
                            # Format time
                            time_obj = datetime.datetime.strptime(time_str, "%H%M%S")
                            formatted_time = time_obj.strftime("%H:%M:%S")
                            
                            # Count files
                            file_count = sum(1 for f in os.listdir(backup_path) if os.path.isfile(os.path.join(backup_path, f)))
                            
                            # Calculate folder size
                            folder_size = sum(os.path.getsize(os.path.join(backup_path, f)) 
                                            for f in os.listdir(backup_path) 
                                            if os.path.isfile(os.path.join(backup_path, f)))
                            
                            # Format size
                            if folder_size < 1024:
                                size_str = f"{folder_size} B"
                            elif folder_size < 1024*1024:
                                size_str = f"{folder_size/1024:.1f} KB"
                            else:
                                size_str = f"{folder_size/(1024*1024):.1f} MB"
                                
                            backups.append((backup_name, formatted_date, formatted_time, file_count, size_str))
                        except:
                            # Skip folders with invalid format
                            continue
            
            # Sort backups by name (effectively by date and time) in descending order
            backups.sort(reverse=True)
            
            # Add to treeview
            for backup in backups:
                folder_name, date, time, file_count, size = backup
                self.backups_tree.insert("", tk.END, values=(
                    date,
                    time,
                    f"{file_count} files",
                    size
                ), tags=(folder_name,))
            
            # Apply alternating row colors
            self._apply_row_colors()
        except Exception as e:
            print(f"Error refreshing backups list: {e}")
            
    def _apply_row_colors(self):
        """Apply alternating row colors to treeview"""
        for i, item in enumerate(self.backups_tree.get_children()):
            if i % 2 == 0:
                self.backups_tree.item(item, tags=("evenrow", self.backups_tree.item(item, "tags")[0]))
            else:
                self.backups_tree.item(item, tags=("oddrow", self.backups_tree.item(item, "tags")[0]))
        
        self.backups_tree.tag_configure("evenrow", background=config.COLORS["table_row_even"])
        self.backups_tree.tag_configure("oddrow", background=config.COLORS["table_row_odd"])
        
    def create_backup(self):
        """Create a backup of all data files"""
        try:
            # Create backup timestamp
            now = datetime.datetime.now()
            backup_name = now.strftime("%Y%m%d_%H%M%S")
            backup_path = os.path.join(self.backup_folder, backup_name)
            
            # Create backup folder if it doesn't exist
            if not os.path.exists(backup_path):
                os.makedirs(backup_path)
                
            # Collect files to backup
            files_to_backup = []
            
            # Add CSV data file
            if os.path.exists(config.DATA_FILE):
                files_to_backup.append(config.DATA_FILE)
                
            # Add settings files
            settings_files = [
                os.path.join(config.DATA_FOLDER, 'app_settings.json'),
                os.path.join(config.DATA_FOLDER, 'users.json'),
                os.path.join(config.DATA_FOLDER, 'sites.json')
            ]
            
            for file_path in settings_files:
                if os.path.exists(file_path):
                    files_to_backup.append(file_path)
            
            # Copy files to backup folder
            for file_path in files_to_backup:
                shutil.copy2(file_path, backup_path)
                
            # Refresh the backups list
            self.refresh_backups_list()
            
            # Show success message
            messagebox.showinfo("Backup Complete", 
                             f"Backup created successfully!\n{len(files_to_backup)} files backed up.")
            
        except Exception as e:
            messagebox.showerror("Backup Error", f"Error creating backup: {str(e)}")
    
    def restore_backup(self):
        """Restore from selected backup"""
        # Get selected backup
        selected_items = self.backups_tree.selection()
        if not selected_items:
            messagebox.showinfo("Selection", "Please select a backup to restore from")
            return
            
        # Get the folder name from the selection's tags
        folder_name = self.backups_tree.item(selected_items[0], "tags")[0]
        backup_path = os.path.join(self.backup_folder, folder_name)
        
        # Confirm restore
        confirm = messagebox.askyesno("Confirm Restore", 
                                    f"Are you sure you want to restore from backup {folder_name}?\n\n"
                                    "This will replace your current data with the backup data.",
                                    icon=messagebox.WARNING)
        if not confirm:
            return
            
        try:
            # Create a backup of the current data before restoring
            self.create_backup()
            
            # Copy files from backup to main data folder
            files_restored = 0
            
            # Only restore files that exist in the backup folder
            for filename in os.listdir(backup_path):
                source_path = os.path.join(backup_path, filename)
                
                # Skip directories
                if os.path.isdir(source_path):
                    continue
                    
                # Determine destination path
                if filename.endswith('.csv'):
                    # CSV data file
                    dest_path = config.DATA_FILE
                elif filename.endswith('.json'):
                    # JSON settings files
                    dest_path = os.path.join(config.DATA_FOLDER, filename)
                else:
                    # Skip other file types
                    continue
                
                # Copy file
                shutil.copy2(source_path, dest_path)
                files_restored += 1
            
            # Show success message
            messagebox.showinfo("Restore Complete", 
                             f"Restored {files_restored} files from backup {folder_name}.\n"
                             "You may need to restart the application for all changes to take effect.")
            
            # Refresh the backups list
            self.refresh_backups_list()
            
        except Exception as e:
            messagebox.showerror("Restore Error", f"Error restoring from backup: {str(e)}")
    
    def export_backup(self):
        """Export a backup to an external location"""
        # Get selected backup
        selected_items = self.backups_tree.selection()
        if not selected_items:
            messagebox.showinfo("Selection", "Please select a backup to export")
            return
            
        # Get the folder name from the selection's tags
        folder_name = self.backups_tree.item(selected_items[0], "tags")[0]
        backup_path = os.path.join(self.backup_folder, folder_name)
        
        # Ask for save location
        export_path = filedialog.asksaveasfilename(
            defaultextension=".zip",
            filetypes=[("ZIP files", "*.zip"), ("All files", "*.*")],
            initialfile=f"backup_{folder_name}.zip",
            title="Export Backup"
        )
        
        if not export_path:
            return
            
        try:
            # Create a ZIP file
            with zipfile.ZipFile(export_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                # Add all files from the backup folder
                for root, dirs, files in os.walk(backup_path):
                    for file in files:
                        file_path = os.path.join(root, file)
                        # Add file to ZIP with relative path
                        arcname = os.path.relpath(file_path, os.path.dirname(backup_path))
                        zipf.write(file_path, arcname)
            
            # Show success message
            messagebox.showinfo("Export Complete", 
                             f"Backup {folder_name} exported to:\n{export_path}")
            
        except Exception as e:
            messagebox.showerror("Export Error", f"Error exporting backup: {str(e)}")