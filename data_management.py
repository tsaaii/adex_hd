# Fixed data_management.py - Resolves today_json_folder attribute error

import os
import csv
import pandas as pd
import datetime
import logging
import json
from tkinter import messagebox, filedialog
import config
import shutil
from cloud_storage import CloudStorageService
import config
import threading
import time
from contextlib import contextmanager

# Global file lock for CSV operations
_csv_file_lock = threading.RLock()  # RLock allows same thread to acquire multiple times

@contextmanager
def safe_csv_operation(max_retries=3, retry_delay=0.1):
    """Context manager for safe CSV file operations with retries"""
    for attempt in range(max_retries):
        try:
            with _csv_file_lock:
                yield
                break  # Success, exit the retry loop
        except Exception as e:
            if "closed file" in str(e).lower() and attempt < max_retries - 1:
                # Wait a bit and retry for closed file errors
                time.sleep(retry_delay)
                continue
            else:
                # Re-raise the exception if it's not a closed file error or max retries reached
                raise
    else:
        # This should not happen, but just in case
        raise RuntimeError("Max retries exceeded for CSV operation")
# Import PDF generation capabilities
try:
    from reportlab.lib.pagesizes import letter, A4
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
    print("ReportLab not available - PDF auto-generation will be disabled")



def setup_logging():
    """Use the existing unified logging system that already handles Unicode"""
    try:
        from unified_logging import setup_enhanced_logger
        return setup_enhanced_logger("DataManager", config.LOGS_FOLDER).logger
    except:
        # Fallback that won't crash
        logger = logging.getLogger('DataManager')
        logger.addHandler(logging.NullHandler())  # Prevent logging errors
        return logger


class DataManager:
    def __init__(self):
        """Initialize data manager with logging and proper folder setup"""
        # Set up logging first
        self.logger = setup_logging()
        self.logger.info("DataManager initialized with OFFLINE-FIRST approach + JSON local storage")
        self.is_shutting_down = False
        self.data_file = config.DATA_FILE
        self.reports_folder = config.REPORTS_FOLDER
        self.pdf_reports_folder = config.REPORTS_FOLDER
        self.json_backup_folder = config.JSON_BACKUPS_FOLDER
        self.today_reports_folder = config.DATA_FOLDER
        
        # CRITICAL FIX: Initialize these attributes with safe defaults FIRST
        self.today_json_folder = None
        self.today_pdf_folder = None
        self.today_folder_name = None
        
        # Initialize CSV structure
        self.initialize_new_csv_structure()

        # Setup folder structure with error handling FIRST
        try:
            self.setup_unified_folder_structure()
        except Exception as e:
            self.logger.error(f"Error setting up unified folder structure: {e}")
            # Fallback to safe defaults
            self._setup_fallback_folders()
        
        # Ensure we have all required folder attributes after setup
        self._ensure_folder_attributes()
        
        # Load address config for PDF generation
        self.address_config = self.load_address_config()
        
        # DO NOT initialize cloud storage here - only when explicitly requested
        self.cloud_storage = None
        
        # NOW check archive after everything is set up
        try:
            self.check_and_archive()
        except Exception as e:
            self.logger.error(f"Error in initial archive check: {e}")
        
        self.logger.info(f"Data file: {self.data_file}")
        self.logger.info(f"Reports folder: {self.reports_folder}")
        self.logger.info(f"JSON backup folder: {self.json_backup_folder}")
        self.logger.info(f"Today's JSON folder: {self.today_json_folder}")
        self.logger.info(f"Today's PDF folder: {self.today_pdf_folder}")
        self.logger.info("Cloud storage will only be initialized when backup is requested")

    def save_record(self, data):
        """RESTORED: Save record using your proven working logic + I/O error protection"""
        try:
            # ADD: Shutdown protection (new safety feature)
            if getattr(self, 'is_shutting_down', False):
                print("🛑 DATA MANAGER: Save blocked - shutdown in progress")
                return {'success': False, 'error': 'Application shutting down'}
            
            # SAFE LOGGING: Use safe logging wrapper to prevent I/O errors
            def safe_log(level, message):
                """Safe logging that handles closed files"""
                try:
                    if not getattr(self, 'is_shutting_down', False):
                        getattr(self.logger, level)(message)
                    else:
                        print(f"[{level.upper()}] {message}")
                except (ValueError, OSError, AttributeError) as e:
                    if "closed file" in str(e).lower():
                        print(f"[{level.upper()}] {message}")
                    else:
                        print(f"[LOG-ERROR] {e}")
                except Exception:
                    print(f"[{level.upper()}] {message}")
            
            safe_log("info", "="*50)
            safe_log("info", "STARTING OFFLINE-FIRST RECORD SAVE")
            safe_log("info", f"Input data keys: {list(data.keys())}")
            
            # RESTORED: Use your original validation method name
            validation_result = self.validate_record_data(data)
            if not validation_result['valid']:
                safe_log("error", f"Validation failed: {validation_result['errors']}")
                if messagebox and not getattr(self, 'is_shutting_down', False):
                    messagebox.showerror("Validation Error", f"Record validation failed:\n" + "\n".join(validation_result['errors']))
                return {'success': False, 'error': 'Validation failed'}
            
            # FIXED: Calculate and set net weight properly (your original logic)
            data = self.calculate_and_set_net_weight(data)
            
            # Use the current data file
            current_file = self.get_current_data_file()
            safe_log("info", f"Using data file: {current_file}")
            
            # Check if this is an update to an existing record
            ticket_no = data.get('ticket_no', '')
            is_update = False
            
            if ticket_no:
                # Check if record with this ticket number exists
                records = self.get_filtered_records(ticket_no)
                for record in records:
                    if record.get('ticket_no') == ticket_no:
                        is_update = True
                        safe_log("info", f"Updating existing record: {ticket_no}")
                        break
            
            if not is_update:
                safe_log("info", f"Adding new record: {ticket_no}")
            
            # PRIORITY 1: Save to CSV locally (this MUST work) - RESTORED your working logic
            csv_success = False
            try:
                # Check shutdown again before CSV operations
                if getattr(self, 'is_shutting_down', False):
                    print("🛑 DATA MANAGER: Save blocked before CSV write - shutdown in progress")
                    return {'success': False, 'error': 'Application shutting down before CSV write'}
                
                if is_update:
                    csv_success = self.update_record(data)
                else:
                    csv_success = self.add_new_record(data)
                
                if csv_success:
                    safe_log("info", f"✅ Record {ticket_no} saved to local CSV successfully")
                else:
                    safe_log("error", f"❌ Failed to save record {ticket_no} to local CSV")
                    return {'success': False, 'error': 'Failed to save to CSV'}
            except Exception as csv_error:
                safe_log("error", f"❌ Critical error saving to CSV: {csv_error}")
                return {'success': False, 'error': f'CSV error: {str(csv_error)}'}
            
            # Check if this is a complete record (both weighments) - RESTORED
            is_complete_record = self.is_record_complete(data)
            
            # Analyze weighment state for logging - RESTORED your original logic
            first_weight = data.get('first_weight', '').strip()
            first_timestamp = data.get('first_timestamp', '').strip()
            second_weight = data.get('second_weight', '').strip()
            second_timestamp = data.get('second_timestamp', '').strip()
            
            has_first_weighment = bool(first_weight and first_timestamp)
            has_second_weighment = bool(second_weight and second_timestamp)
            is_first_weighment_save = has_first_weighment and not has_second_weighment
            
            safe_log("info", f"Weighment analysis:")
            safe_log("info", f"  - Has first weighment: {has_first_weighment}")
            safe_log("info", f"  - Has second weighment: {has_second_weighment}")
            safe_log("info", f"  - Is first weighment save: {is_first_weighment_save}")
            safe_log("info", f"  - Is complete record: {is_complete_record}")
            safe_log("info", f"  - Is update: {is_update}")
            
            # PRIORITY 2: Save complete records as JSON locally - RESTORED
            json_saved = False
            if is_complete_record:
                safe_log("info", f"Complete record detected - saving JSON backup locally...")
                try:
                    json_saved = self.save_json_backup_locally(data)
                    if json_saved:
                        safe_log("info", f"✅ JSON backup saved locally for {ticket_no}")
                    else:
                        safe_log("warning", f"⚠️ Failed to save JSON backup for {ticket_no}")
                except Exception as json_error:
                    safe_log("error", f"⚠️ JSON backup error (non-critical): {json_error}")
            
            # PRIORITY 3: Auto-generate PDF for complete records - RESTORED
            pdf_generated = False
            pdf_path = None
            todays_reports_folder = None
            
            if is_complete_record:
                safe_log("info", f"Complete record detected for ticket {ticket_no} - generating PDF locally...")
                try:
                    # Get today's reports folder path
                    todays_reports_folder = self.get_todays_reports_folder()
                    safe_log("info", f"Reports will be saved to: {todays_reports_folder}")
                    
                    pdf_generated, pdf_path = self.auto_generate_pdf_for_complete_record(data)
                    if pdf_generated:
                        safe_log("info", f"✅ PDF auto-generated locally: {pdf_path}")
                    else:
                        safe_log("warning", "⚠️ PDF generation failed, but record and JSON were saved locally")
                except Exception as pdf_error:
                    safe_log("error", f"⚠️ PDF generation error (non-critical): {pdf_error}")
            
            # IMPORTANT: NO CLOUD STORAGE ATTEMPTS HERE - RESTORED
            safe_log("info", "✅ OFFLINE-FIRST SAVE COMPLETED - Local CSV, JSON backup, and PDF generated")
            if todays_reports_folder:
                safe_log("info", f"📂 PDF saved to today's reports folder: {todays_reports_folder}")
            safe_log("info", "💡 Cloud backup available via Settings > Cloud Storage > Backup")
            safe_log("info", "="*50)

            # RESTORED: Check archive on EVERY complete record save
            if is_complete_record:
                try:
                    safe_log("info", "🔍 Checking archive after complete record save...")
                    archive_success, archive_message = self.check_and_archive()
                    if archive_success:
                        safe_log("info", f"📦 Archive completed: {archive_message}")
                    else:
                        safe_log("info", f"📦 Archive check: {archive_message}")
                except Exception as archive_error:
                    safe_log("error", f"Archive check error (non-critical): {archive_error}")
            
            # Return success and weighment info for the app to handle ticket flow - RESTORED
            return {
                'success': True,
                'is_complete_record': is_complete_record,
                'is_first_weighment_save': is_first_weighment_save,
                'is_update': is_update,
                'ticket_no': ticket_no,
                'pdf_generated': pdf_generated,
                'pdf_path': pdf_path,
                'todays_reports_folder': todays_reports_folder
            }
                    
        except Exception as e:
            # SAFE ERROR LOGGING
            try:
                if not getattr(self, 'is_shutting_down', False):
                    self.logger.error(f"❌ Critical error saving record: {e}")
                else:
                    print(f"[CRITICAL-ERROR] Critical error saving record: {e}")
            except Exception:
                print(f"[CRITICAL-ERROR] Critical error saving record: {e}")
            
            try:
                if messagebox and not getattr(self, 'is_shutting_down', False):
                    messagebox.showerror("Save Error", f"Failed to save record:\n{str(e)}")
            except Exception:
                print(f"[ERROR-DIALOG] Failed to save record: {e}")
            
            return {'success': False, 'error': str(e)}

    def get_filtered_records(self, filter_text=""):
        """Get records filtered by text with simplified safe file handling"""
        try:
            # Check shutdown status first
            if getattr(self, 'is_shutting_down', False):
                print("🛑 DATA MANAGER: get_filtered_records blocked - shutdown in progress")
                return []
            
            # Get the current data file
            current_file = self.get_current_data_file()
            
            if not os.path.exists(current_file):
                self._safe_data_log("warning", f"CSV file does not exist: {current_file}")
                return []
            
            # Simple retry logic without complex context managers
            for attempt in range(3):
                try:
                    all_records = []
                    
                    # Read all data at once with simple file handling
                    with open(current_file, 'r', newline='', encoding='utf-8', errors='replace') as csv_file:
                        reader = csv.DictReader(csv_file)
                        all_records = list(reader)  # Read everything immediately
                    
                    self._safe_data_log("info", f"Successfully loaded {len(all_records)} records")
                    
                    # Filter outside of file operations
                    if not filter_text:
                        self._safe_data_log("info", f"Returning all {len(all_records)} records (no filter)")
                        return all_records
                    
                    filter_text = filter_text.lower().strip()
                    filtered_records = []
                    
                    for record in all_records:
                        try:
                            # Check if filter text exists in any field
                            if any(filter_text in str(value).lower() for value in record.values() if value is not None):
                                filtered_records.append(record)
                        except Exception as filter_error:
                            self._safe_data_log("warning", f"Error filtering record: {filter_error}")
                            continue
                    
                    self._safe_data_log("info", f"Filtered {len(all_records)} records to {len(filtered_records)} using filter: '{filter_text}'")
                    return filtered_records
                    
                except Exception as read_error:
                    error_str = str(read_error).lower()
                    if ("closed file" in error_str or "i/o operation" in error_str) and attempt < 2:
                        print(f"[RETRY] get_filtered_records attempt {attempt + 1} failed, retrying: {read_error}")
                        time.sleep(0.3 * (attempt + 1))  # Progressive delay
                        continue
                    else:
                        raise
            
            # If all retries failed
            self._safe_data_log("error", f"All retry attempts failed for get_filtered_records")
            return []
            
        except Exception as e:
            self._safe_data_log("error", f"Error in get_filtered_records: {e}")
            return []

    def get_all_records(self):
        """Simplified get_all_records with retry logic"""
        # Check shutdown status first
        if getattr(self, 'is_shutting_down', False):
            print("🛑 DATA MANAGER: get_all_records blocked - shutdown in progress")
            return []
        
        records = []
        current_file = self.get_current_data_file()
        
        if not os.path.exists(current_file):
            self._safe_data_log("warning", f"CSV file does not exist: {current_file}")
            return records
        
        # Simple retry logic without complex context managers
        for attempt in range(3):
            try:
                with open(current_file, 'r', newline='', encoding='utf-8', errors='replace') as csv_file:
                    reader = csv.reader(csv_file)
                    
                    # Skip header
                    header = next(reader, None)
                    if not header:
                        self._safe_data_log("warning", "CSV file has no header")
                        return records
                    
                    # Read all records at once
                    all_rows = list(reader)
                
                # Process records outside the file context
                for row_num, row in enumerate(all_rows, 1):
                    # Check shutdown during processing
                    if getattr(self, 'is_shutting_down', False):
                        print("🛑 DATA MANAGER: Breaking record read - shutdown in progress")
                        break
                    
                    try:
                        if len(row) >= 13:  # Minimum fields required
                            record = {
                                'date': row[0] if len(row) > 0 else '',
                                'time': row[1] if len(row) > 1 else '',
                                'site_name': row[2] if len(row) > 2 else '',
                                'agency_name': row[3] if len(row) > 3 else '',
                                'material': row[4] if len(row) > 4 else '',
                                'ticket_no': row[5] if len(row) > 5 else '',
                                'vehicle_no': row[6] if len(row) > 6 else '',
                                'transfer_party_name': row[7] if len(row) > 7 else '',
                                'first_weight': row[8] if len(row) > 8 else '',
                                'first_timestamp': row[9] if len(row) > 9 else '',
                                'second_weight': row[10] if len(row) > 10 else '',
                                'second_timestamp': row[11] if len(row) > 11 else '',
                                'net_weight': row[12] if len(row) > 12 else '',
                                'material_type': row[13] if len(row) > 13 else '',
                                'first_front_image': row[14] if len(row) > 14 else '',
                                'first_back_image': row[15] if len(row) > 15 else '',
                                'second_front_image': row[16] if len(row) > 16 else '',
                                'second_back_image': row[17] if len(row) > 17 else '',
                                'site_incharge': row[18] if len(row) > 18 else '',
                                'user_name': row[19] if len(row) > 19 else ''
                            }
                            records.append(record)
                    except Exception as row_error:
                        self._safe_data_log("warning", f"Error processing row {row_num}: {row_error}")
                        continue
                
                self._safe_data_log("info", f"Successfully loaded {len(records)} records from {current_file}")
                return records
                
            except Exception as read_error:
                error_str = str(read_error).lower()
                if ("closed file" in error_str or "i/o operation" in error_str) and attempt < 2:
                    print(f"[RETRY] get_all_records attempt {attempt + 1} failed, retrying: {read_error}")
                    time.sleep(0.3 * (attempt + 1))  # Progressive delay
                    continue
                else:
                    raise
        
        # If all retries failed
        self._safe_data_log("error", f"All retry attempts failed for get_all_records")
        return []

    def _setup_fallback_folders(self):
        """Setup fallback folders when main setup fails"""
        try:
            # Create basic folder structure
            today = datetime.datetime.now()
            self.today_folder_name = today.strftime("%Y-%m-%d")
            
            # Create base folders
            self.reports_folder = os.path.join(config.DATA_FOLDER, 'reports')
            self.json_backup_folder = os.path.join(config.DATA_FOLDER, 'json_backups')
            
            os.makedirs(self.reports_folder, exist_ok=True)
            os.makedirs(self.json_backup_folder, exist_ok=True)
            
            # Create today's folders
            self.today_reports_folder = os.path.join(self.reports_folder, self.today_folder_name)
            self.today_json_folder = os.path.join(self.json_backup_folder, self.today_folder_name)
            self.today_pdf_folder = self.today_reports_folder  # Same as reports folder
            
            os.makedirs(self.today_reports_folder, exist_ok=True)
            os.makedirs(self.today_json_folder, exist_ok=True)
            
            self.logger.info("Fallback folder structure created successfully")
            
        except Exception as e:
            self.logger.error(f"Error in fallback folder setup: {e}")
            # Ultimate fallback - use data folder
            self.today_reports_folder = config.DATA_FOLDER
            self.today_json_folder = config.DATA_FOLDER
            self.today_pdf_folder = config.DATA_FOLDER
            self.today_folder_name = datetime.datetime.now().strftime("%Y-%m-%d")
    
    def _ensure_folder_attributes(self):
        """Ensure all required folder attributes are set"""
        try:
            today = datetime.datetime.now()
            today_str = today.strftime("%Y-%m-%d")
            
            # Ensure today_folder_name is set
            if not hasattr(self, 'today_folder_name') or not self.today_folder_name:
                self.today_folder_name = today_str
            
            # Ensure today_json_folder is set
            if not hasattr(self, 'today_json_folder') or not self.today_json_folder:
                if hasattr(self, 'json_backup_folder') and self.json_backup_folder:
                    self.today_json_folder = os.path.join(self.json_backup_folder, today_str)
                else:
                    self.today_json_folder = os.path.join(config.DATA_FOLDER, 'json_backups', today_str)
                os.makedirs(self.today_json_folder, exist_ok=True)
            
            # Ensure today_pdf_folder is set
            if not hasattr(self, 'today_pdf_folder') or not self.today_pdf_folder:
                if hasattr(self, 'reports_folder') and self.reports_folder:
                    self.today_pdf_folder = os.path.join(self.reports_folder, today_str)
                else:
                    self.today_pdf_folder = os.path.join(config.DATA_FOLDER, 'reports', today_str)
                os.makedirs(self.today_pdf_folder, exist_ok=True)
            
            # Ensure today_reports_folder is set
            if not hasattr(self, 'today_reports_folder') or not self.today_reports_folder:
                self.today_reports_folder = self.today_pdf_folder
            
            self.logger.info("All folder attributes ensured and validated")
            
        except Exception as e:
            self.logger.error(f"Error ensuring folder attributes: {e}")
            # Final fallback
            self.today_json_folder = config.DATA_FOLDER
            self.today_pdf_folder = config.DATA_FOLDER
            self.today_reports_folder = config.DATA_FOLDER
            self.today_folder_name = datetime.datetime.now().strftime("%Y-%m-%d")
    
    def get_or_create_json_folder(self):
        """FIXED: Get or create today's JSON folder with comprehensive error handling"""
        try:
            # Check if we need to update folder (date changed)
            today = datetime.datetime.now()
            today_str = today.strftime("%Y-%m-%d")
            
            if not hasattr(self, 'today_folder_name') or self.today_folder_name != today_str:
                self.today_folder_name = today_str
                # Update folder path
                if hasattr(self, 'json_backup_folder') and self.json_backup_folder:
                    self.today_json_folder = os.path.join(self.json_backup_folder, today_str)
                else:
                    # Fallback path
                    self.json_backup_folder = os.path.join(config.DATA_FOLDER, 'json_backups')
                    self.today_json_folder = os.path.join(self.json_backup_folder, today_str)
                
                # Ensure folders exist
                os.makedirs(self.today_json_folder, exist_ok=True)
                self.logger.info(f"Updated JSON folder for {today_str}: {self.today_json_folder}")
            
            # Final validation
            if not hasattr(self, 'today_json_folder') or not self.today_json_folder:
                # Emergency fallback
                self.today_json_folder = config.DATA_FOLDER
                self.logger.warning("Using emergency fallback for JSON folder")
            
            return self.today_json_folder
            
        except Exception as e:
            self.logger.error(f"Error getting JSON folder: {e}")
            # Emergency fallback
            fallback_folder = config.DATA_FOLDER
            os.makedirs(fallback_folder, exist_ok=True)
            return fallback_folder
    
    def save_json_backup_locally(self, data):
        """FIXED: Save complete record as JSON backup locally with proper folder handling"""
        try:
            # Get today's JSON folder with error handling
            json_folder = self.get_or_create_json_folder()
            
            # Generate JSON filename: TicketNo_AgencyName_SiteName_Timestamp.json
            ticket_no = data.get('ticket_no', 'Unknown').replace('/', '_')
            agency_name = data.get('agency_name', 'Unknown').replace(' ', '_').replace('/', '_')
            site_name = data.get('site_name', 'Unknown').replace(' ', '_').replace('/', '_')
            timestamp = datetime.datetime.now().strftime("%H%M%S")
            
            json_filename = f"{ticket_no}_{agency_name}_{site_name}_{timestamp}.json"
            json_path = os.path.join(json_folder, json_filename)
            
            # Add metadata to JSON
            json_data = data.copy()
            json_data['json_backup_timestamp'] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            json_data['record_status'] = 'complete'
            json_data['backup_type'] = 'local'
            
            # FIXED: Ensure net weight is properly included
            if not json_data.get('net_weight'):
                json_data = self.calculate_and_set_net_weight(json_data)
            
            # CHECK FOR DUPLICATE CONTENT - Calculate content hash
            import hashlib
            content_str = json.dumps({k: v for k, v in json_data.items() 
                                    if k not in ['json_backup_timestamp', 'backup_type']}, 
                                sort_keys=True, ensure_ascii=False)
            content_hash = hashlib.md5(content_str.encode()).hexdigest()
            
            # Check if this content already exists in the folder
            if os.path.exists(json_folder):
                for existing_file in os.listdir(json_folder):
                    if existing_file.endswith('.json') and existing_file.startswith(f"{ticket_no}_"):
                        existing_path = os.path.join(json_folder, existing_file)
                        try:
                            with open(existing_path, 'r', encoding='utf-8') as f:
                                existing_data = json.load(f)
                            
                            # Calculate hash of existing content (excluding timestamps)
                            existing_content_str = json.dumps({k: v for k, v in existing_data.items() 
                                                            if k not in ['json_backup_timestamp', 'backup_type']}, 
                                                            sort_keys=True, ensure_ascii=False)
                            existing_hash = hashlib.md5(existing_content_str.encode()).hexdigest()
                            
                            if existing_hash == content_hash:
                                self.logger.info(f"⏭️  Skipping duplicate JSON backup for {ticket_no} (content unchanged)")
                                return True
                                
                        except Exception as e:
                            self.logger.warning(f"Error checking existing JSON file {existing_file}: {e}")
                            continue
            
            # Content is new or changed - save JSON file
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(json_data, f, indent=4, ensure_ascii=False)
            
            self.logger.info(f" JSON backup saved: {json_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error saving JSON backup: {e}")
            return False
    



    def check_and_archive(self):
        """Check if archive is due and perform it - IMPROVED"""
        try:
            self.logger.info(" Checking if archive is due...")
            
            if self.should_archive_csv():
                self.logger.info(" Archive is due - starting archive process...")
                success, message = self.archive_complete_records()
                
                if success:
                    self.logger.info(f" Archive completed: {message}")
                    # Optional: Show notification
                    try:
                        from tkinter import messagebox
                        messagebox.showinfo("Archive Created", message)
                    except:
                        pass  # Skip if no GUI
                else:
                    self.logger.warning(f" Archive failed: {message}")
                    
                return success, message
            else:
                self.logger.info(" Archive not due yet")
                return False, "Archive not due yet"
                
        except Exception as e:
            self.logger.error(f" Error in archive check: {e}")
            return False, f"Error: {e}"



    def setup_unified_folder_structure(self):
        """FIXED: Set up unified folder structure with comprehensive error handling"""
        try:
            # Create base folders
            self.reports_folder = os.path.join(config.DATA_FOLDER, 'reports')
            self.json_backup_folder = os.path.join(config.DATA_FOLDER, 'json_backups')
            
            os.makedirs(self.reports_folder, exist_ok=True)
            os.makedirs(self.json_backup_folder, exist_ok=True)
            
            # FIXED: Use consistent date format YYYY-MM-DD for all folders
            today = datetime.datetime.now()
            self.today_folder_name = today.strftime("%Y-%m-%d")  # Format: 2024-05-29
            
            # Create today's subfolders
            self.today_reports_folder = os.path.join(self.reports_folder, self.today_folder_name)
            self.today_json_folder = os.path.join(self.json_backup_folder, self.today_folder_name)
            self.today_pdf_folder = self.today_reports_folder  # Use same as reports folder
            
            os.makedirs(self.today_reports_folder, exist_ok=True)
            os.makedirs(self.today_json_folder, exist_ok=True)
            
            self.logger.info(f"Unified folder structure ready:")
            self.logger.info(f"  Reports: {self.today_reports_folder}")
            self.logger.info(f"  JSON Backups: {self.today_json_folder}")
            self.logger.info(f"  PDF Folder: {self.today_pdf_folder}")
            
            # Create README files
            self.create_folder_readme_files()
            
        except Exception as e:
            self.logger.error(f"Error setting up folder structure: {e}")
            # Call fallback setup
            self._setup_fallback_folders()


    def get_todays_reports_folder(self):
        """Get or create today's reports folder in data/reports/YYYY-MM-DD format
        
        Returns:
            str: Path to today's reports folder
        """
        try:
            import datetime
            
            # Create base reports folder structure
            base_reports_folder = os.path.join(config.DATA_FOLDER, 'reports')
            os.makedirs(base_reports_folder, exist_ok=True)
            
            # Create today's folder with YYYY-MM-DD format
            today = datetime.datetime.now()
            today_folder_name = today.strftime("%Y-%m-%d")  # Format: 2025-05-29
            todays_folder = os.path.join(base_reports_folder, today_folder_name)
            
            # Ensure today's folder exists
            os.makedirs(todays_folder, exist_ok=True)
            
            self.logger.info(f"Today's reports folder ensured: {todays_folder}")
            
            # Update the DataManager's today_pdf_folder reference
            self.today_pdf_folder = todays_folder
            
            return todays_folder
            
        except Exception as e:
            self.logger.error(f"Error creating today's reports folder: {e}")
            # Fallback to data folder
            fallback_folder = config.DATA_FOLDER
            os.makedirs(fallback_folder, exist_ok=True)
            return fallback_folder


    def should_archive_csv(self):
        """Check if CSV should be archived (every 5 days) - FIXED VERSION"""
        try:
            archive_tracking_file = os.path.join(config.DATA_FOLDER, 'last_archive.json')
            current_file = self.get_current_data_file()
            
            # Check if CSV file exists
            if not os.path.exists(current_file):
                self.logger.info("No CSV file to archive")
                return False
            
            # Validate CSV file can be read
            try:
                with open(current_file, 'r', newline='', encoding='utf-8') as f:
                    reader = csv.reader(f)
                    header = next(reader, None)
                    if not header:
                        self.logger.warning("CSV file has no header - cannot archive")
                        return False
            except Exception as csv_read_error:
                self.logger.error(f"Cannot read CSV file for archiving: {csv_read_error}")
                return False
                
            # Count archivable records (complete AND from 2+ days ago)
            archivable_records = 0
            cutoff_date = datetime.datetime.now() - datetime.timedelta(days=2)
            cutoff_date_str = cutoff_date.strftime('%Y-%m-%d')
            
            try:
                with open(current_file, 'r', newline='', encoding='utf-8') as f:
                    reader = csv.reader(f)
                    header = next(reader, None)
                    
                    for row in reader:
                        if len(row) >= 13:  # Valid record
                            # Check if complete (both weights)
                            first_weight = row[8].strip() if len(row) > 8 else ''
                            second_weight = row[10].strip() if len(row) > 10 else ''
                            
                            # Check if record is from 2+ days ago
                            record_date = row[0].strip() if len(row) > 0 else ''
                            
                            if (first_weight and first_weight not in ['0', '0.0', ''] and 
                                second_weight and second_weight not in ['0', '0.0', ''] and
                                record_date and record_date < cutoff_date_str):
                                archivable_records += 1
                                
            except Exception as count_error:
                self.logger.error(f"Error counting archivable records: {count_error}")
                return False
            
            self.logger.info(f"CSV analysis: {archivable_records} records are complete and 2+ days old (before {cutoff_date_str})")
            
            if archivable_records == 0:
                self.logger.info("CSV file has no records ready for archiving (complete + 2+ days old)")
                return False
            
            # Check last archive date
            if os.path.exists(archive_tracking_file):
                try:
                    with open(archive_tracking_file, 'r') as f:
                        data = json.load(f)
                        last_archive = datetime.datetime.fromisoformat(data['last_archive_date'])
                        days_since = (datetime.datetime.now() - last_archive).days
                        
                        self.logger.info(f"Last archive: {days_since} days ago ({last_archive.strftime('%Y-%m-%d')})")
                        self.logger.info(f"Records ready for archive: {archivable_records}")
                        
                        should_archive = days_since >= 5
                        if should_archive:
                            self.logger.info(f" Archive DUE: {days_since} days >= 5 days")
                        else:
                            self.logger.info(f" Archive not due: {days_since} days < 5 days")
                        return should_archive
                        
                except Exception as tracking_error:
                    self.logger.error(f"Error reading archive tracking: {tracking_error}")
                    # If tracking file is corrupted, archive if we have archivable records
                    self.logger.info("Archive tracking corrupted - will archive due to archivable records")
                    return archivable_records > 0
            else:
                # FIXED: No tracking file exists - this is the first run
                # Don't archive on first run, just create the tracking file
                self.logger.info(f"First run detected. CSV has {archivable_records} archivable records.")
                self.logger.info(" Skipping archive on first run to prevent immediate archiving")
                
                # Create tracking file with current date so archive will be due in 5 days
                tracking_data = {
                    'last_archive_date': datetime.datetime.now().isoformat(),
                    'archive_filename': 'first_run_no_archive',
                    'complete_records': 0,
                    'incomplete_records': 0,
                    'archivable_records': archivable_records,
                    'note': 'First run - no archive performed, next archive due in 5 days'
                }
                with open(archive_tracking_file, 'w') as f:
                    json.dump(tracking_data, f, indent=2)
                
                self.logger.info(" Archive tracking file created - next archive will be due in 5 days")
                return False
                    
        except Exception as e:
            self.logger.error(f"Error checking archive status: {e}")
            return False


    def archive_complete_records(self):
        """Archive complete records from 2+ days ago, keep recent and incomplete ones - FIXED VERSION"""
        try:
            current_file = self.get_current_data_file()
            if not os.path.exists(current_file):
                return False, "No CSV file to archive"
            
            self.logger.info(" Starting archive process...")
            
            # Calculate cutoff date (2 days ago)
            cutoff_date = datetime.datetime.now() - datetime.timedelta(days=2)
            cutoff_date_str = cutoff_date.strftime('%Y-%m-%d')
            
            self.logger.info(f" Archive cutoff date: {cutoff_date_str} (records before this date will be archived)")
            
            # Read all records and categorize them
            archive_records = []        # Complete records from 2+ days ago
            keep_records = []          # Recent records (< 2 days) OR incomplete records
            
            with open(current_file, 'r', newline='', encoding='utf-8') as f:
                reader = csv.reader(f)
                header = next(reader, None)
                
                for row_num, row in enumerate(reader, 1):
                    if len(row) < 13:
                        self.logger.warning(f"Row {row_num}: Insufficient data, skipping")
                        continue
                        
                    # Get record details
                    record_date = row[0].strip() if len(row) > 0 else ''
                    first_weight = row[8].strip() if len(row) > 8 else ''
                    second_weight = row[10].strip() if len(row) > 10 else ''
                    ticket_no = row[5] if len(row) > 5 else 'Unknown'
                    
                    # Check if record is complete (has both weights)
                    has_first = bool(first_weight and first_weight not in ['0', '0.0', ''])
                    has_second = bool(second_weight and second_weight not in ['0', '0.0', ''])
                    is_complete = has_first and has_second
                    
                    # Check if record is old enough (2+ days ago)
                    is_old_enough = record_date and record_date < cutoff_date_str
                    
                    if is_complete and is_old_enough:
                        # Archive: Complete AND old enough
                        archive_records.append(row)
                        self.logger.info(f"ARCHIVE: Ticket {ticket_no} - Date: {record_date} (Complete & Old)")
                    else:
                        # Keep: Either incomplete OR recent
                        keep_records.append(row)
                        if not is_complete:
                            self.logger.info(f"KEEP: Ticket {ticket_no} - Date: {record_date} (Incomplete)")
                        elif not is_old_enough:
                            self.logger.info(f"KEEP: Ticket {ticket_no} - Date: {record_date} (Recent)")
            
            self.logger.info(f" Archive analysis:")
            self.logger.info(f"   Records to archive (complete + 2+ days old): {len(archive_records)}")
            self.logger.info(f"   Records to keep (recent or incomplete): {len(keep_records)}")
            
            if not archive_records:
                return False, f"No records ready for archiving. {len(keep_records)} records kept (recent or incomplete)."
            
            # Create archive file
            archives_folder = os.path.join(config.DATA_FOLDER, 'archives')
            os.makedirs(archives_folder, exist_ok=True)
            
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            archive_filename = f"archive_{timestamp}_{len(archive_records)}records_before_{cutoff_date_str.replace('-', '')}.csv"
            archive_path = os.path.join(archives_folder, archive_filename)
            
            # Write archive with records from 2+ days ago
            with open(archive_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(config.CSV_HEADER)
                for record in archive_records:
                    writer.writerow(record)
            
            self.logger.info(f" Created archive: {archive_filename}")
            
            # Create fresh CSV with recent and incomplete records
            with open(current_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(config.CSV_HEADER)
                for record in keep_records:
                    writer.writerow(record)
            
            self.logger.info(f" Fresh CSV created with {len(keep_records)} records (recent + incomplete)")
            
            # Update tracking file
            tracking_file = os.path.join(config.DATA_FOLDER, 'last_archive.json')
            tracking_data = {
                'last_archive_date': datetime.datetime.now().isoformat(),
                'archive_filename': archive_filename,
                'archived_records': len(archive_records),
                'kept_records': len(keep_records),
                'archive_path': archive_path,
                'cutoff_date': cutoff_date_str,
                'note': f'Archived complete records from before {cutoff_date_str}'
            }
            with open(tracking_file, 'w') as f:
                json.dump(tracking_data, f, indent=2)
            
            self.logger.info(f" Archive completed successfully!")
            self.logger.info(f"    Archive file: {archive_filename}")
            self.logger.info(f"    Records archived: {len(archive_records)} (complete + 2+ days old)")
            self.logger.info(f"    Records kept: {len(keep_records)} (recent or incomplete)")
            
            return True, f"Archive created: {len(archive_records)} records archived (before {cutoff_date_str}), {len(keep_records)} records kept."
            
        except Exception as e:
            self.logger.error(f" Archive error: {e}")
            return False, f"Archive failed: {e}"

    # Continue with rest of the methods...
    def calculate_and_set_net_weight(self, data):
        """FIXED: Properly calculate and set net weight in the data with safe logging"""
        try:
            first_weight_str = data.get('first_weight', '').strip()
            second_weight_str = data.get('second_weight', '').strip()
            
            # Only calculate if both weights are present
            if first_weight_str and second_weight_str:
                try:
                    first_weight = float(first_weight_str)
                    second_weight = float(second_weight_str)
                    net_weight = abs(first_weight - second_weight)
                    
                    # CRITICAL FIX: Set the calculated net weight in the data
                    data['net_weight'] = f"{net_weight:.2f}"
                    
                    # SAFE LOGGING: Use safe logging to prevent I/O errors
                    self._safe_data_log("info", f"Net weight calculated: {first_weight} - {second_weight} = {net_weight:.2f}")
                    
                except (ValueError, TypeError) as e:
                    self._safe_data_log("error", f"Error calculating net weight: {e}")
                    data['net_weight'] = ""
            else:
                # If either weight is missing, clear net weight
                data['net_weight'] = ""
                self._safe_data_log("info", "Net weight cleared - incomplete weighments")
            
            return data
            
        except Exception as e:
            self._safe_data_log("error", f"Error in calculate_and_set_net_weight: {e}")
            return data



    def _safe_shutdown_protection_log(self, level, message):
        """Enhanced safe logging with shutdown protection"""
        try:
            # Check shutdown status first
            if getattr(self, 'is_shutting_down', False):
                print(f"[{level.upper()}] {message}")
                return
            
            # Try normal logging
            if hasattr(self, 'logger'):
                getattr(self.logger, level)(message)
        except (ValueError, OSError, AttributeError) as e:
            if "closed file" in str(e).lower():
                print(f"[{level.upper()}] {message}")
            else:
                print(f"[LOG-ERROR] {e}")
                print(f"[{level.upper()}] {message}")
        except Exception:
            print(f"[{level.upper()}] {message}")


    def auto_generate_pdf_for_complete_record(self, record_data):
        """Automatically generate PDF for a complete record - Save to today's reports folder
        
        Args:
            record_data: Complete record data dictionary
            
        Returns:
            tuple: (success, pdf_path)
        """
        # Check if ReportLab is available
        try:
            global REPORTLAB_AVAILABLE
            if not REPORTLAB_AVAILABLE:
                self.logger.warning("ReportLab not available - skipping PDF generation")
                return False, None
        except:
            self.logger.warning("PDF generation not available")
            return False, None
        
        try:
            # Check if record is complete (both weighments)
            if not self.is_record_complete(record_data):
                self.logger.info("Record incomplete - skipping PDF generation")
                return False, None
            
            # Get today's reports folder
            todays_reports_folder = self.get_todays_reports_folder()
            
            # Generate PDF filename
            ticket_no = record_data.get('ticket_no', 'Unknown').replace('/', '_')
            vehicle_no = record_data.get('vehicle_no', 'Unknown').replace('/', '_').replace(' ', '_')
            site_name = record_data.get('site_name', 'Unknown').replace(' ', '_').replace('/', '_')
            agency_name = record_data.get('agency_name', 'Unknown').replace(' ', '_').replace('/', '_')
            timestamp = datetime.datetime.now().strftime("%H%M%S")
            
            # PDF filename format: AgencyName_SiteName_TicketNo_VehicleNo_HHMMSS.pdf
            pdf_filename = f"{agency_name}_{site_name}_{ticket_no}_{vehicle_no}_{timestamp}.pdf"
            
            # Full path to save PDF in today's reports folder
            pdf_path = os.path.join(todays_reports_folder, pdf_filename)
            
            # Generate the PDF
            success = self.create_pdf_report([record_data], pdf_path)
            
            if success:
                self.logger.info(f"Auto-generated PDF: {pdf_path}")
                self.logger.info(f"PDF saved to today's reports folder: {todays_reports_folder}")
                return True, pdf_path
            else:
                self.logger.error("Failed to generate PDF")
                return False, None
                
        except Exception as e:
            self.logger.error(f"Error in auto PDF generation (non-critical): {e}")
            return False, None

    def setup_daily_pdf_folders(self):
        """Set up daily folder structure for PDF generation - Updated for data/reports structure"""
        try:
            # Create base reports folder structure
            self.base_reports_folder = os.path.join(config.DATA_FOLDER, 'reports')
            os.makedirs(self.base_reports_folder, exist_ok=True)
            
            # Get today's folder
            today = datetime.datetime.now()
            self.today_folder_name = today.strftime("%Y-%m-%d")  # Format: 2025-05-29
            self.today_pdf_folder = os.path.join(self.base_reports_folder, self.today_folder_name)
            os.makedirs(self.today_pdf_folder, exist_ok=True)
            
            self.logger.info(f"Daily PDF folder structure ready:")
            self.logger.info(f"  Base reports folder: {self.base_reports_folder}")
            self.logger.info(f"  Today's folder: {self.today_pdf_folder}")
            
            # Create a README file in the base reports folder if it doesn't exist
            readme_path = os.path.join(self.base_reports_folder, "README.txt")
            if not os.path.exists(readme_path):
                with open(readme_path, 'w') as f:
                    f.write("""REPORTS FOLDER STRUCTURE
    =========================

    This folder contains daily reports organized by date.

    Structure:
    data/reports/
    ├── YYYY-MM-DD/          # Daily folder (e.g., 2025-05-29)
    │   ├── report1.pdf      # Auto-generated PDFs for complete weighments
    │   ├── report2.pdf      # Each PDF contains vehicle info, weights, and images
    │   └── [more PDFs...]   # Named: Agency_Site_Ticket_Vehicle_Time.pdf
    ├── YYYY-MM-DD/
    │   └── [more reports...]
    └── README.txt           # This file

    GENERATED BY: Swaccha Andhra Corporation Weighbridge System
    OFFLINE-FIRST: All reports saved locally first, cloud backup available via Settings
    """)
            
        except Exception as e:
            self.logger.error(f"Error setting up daily PDF folders: {e}")
            # Fallback to data folder
            self.today_pdf_folder = config.DATA_FOLDER

    def save_to_cloud_with_images(self, data):
        """Save record with images to Google Cloud Storage - ONLY WHEN EXPLICITLY CALLED"""
        try:
            # Check if both weighments are complete before saving to cloud
            first_weight = data.get('first_weight', '').strip()
            first_timestamp = data.get('first_timestamp', '').strip()
            second_weight = data.get('second_weight', '').strip()
            second_timestamp = data.get('second_timestamp', '').strip()
            
            # Only save to cloud if both weighments are complete
            if not (first_weight and first_timestamp and second_weight and second_timestamp):
                self._safe_data_log("info", f"Skipping cloud save for ticket {data.get('ticket_no', 'unknown')} - incomplete weighments")
                return False, 0, 0
            
            # Check if cloud storage is enabled
            if not (hasattr(config, 'USE_CLOUD_STORAGE') and config.USE_CLOUD_STORAGE):
                self._safe_data_log("info", "Cloud storage disabled - skipping")
                return False, 0, 0
            
            # Initialize cloud storage if needed
            if not self.init_cloud_storage_if_needed():
                return False, 0, 0
            
            # Check if connected to cloud storage
            try:
                if not self.cloud_storage.is_connected():
                    self._safe_data_log("warning", "Not connected to cloud storage (offline or configuration issue)")
                    return False, 0, 0
            except Exception as conn_error:
                self._safe_data_log("error", f"Cloud connection check failed: {conn_error}")
                return False, 0, 0
            
            # Get site name and ticket number for folder structure
            site_name = data.get('site_name', 'Unknown_Site').replace(' ', '_').replace('/', '_')
            agency_name = data.get('agency_name', 'Unknown_Agency').replace(' ', '_').replace('/', '_')
            ticket_no = data.get('ticket_no', 'unknown')
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            
            # Create structured filename: agency_name/site_name/ticket_number/timestamp.json
            json_filename = f"{agency_name}/{site_name}/{ticket_no}/{timestamp}.json"
            
            # Add some additional metadata to the JSON
            enhanced_data = data.copy()
            enhanced_data['cloud_upload_timestamp'] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            enhanced_data['record_status'] = 'complete'  # Mark as complete record
            enhanced_data['net_weight_calculated'] = self._calculate_net_weight_for_cloud(
                enhanced_data.get('first_weight', ''), 
                enhanced_data.get('second_weight', '')
            )
            
            # Upload record with images using the new method
            json_success, images_uploaded, total_images = self.cloud_storage.upload_record_with_images(
                enhanced_data, 
                json_filename, 
                config.IMAGES_FOLDER
            )
            
            if json_success:
                self._safe_data_log("info", f"Record {ticket_no} successfully saved to cloud at {json_filename}")
                if images_uploaded > 0:
                    self._safe_data_log("info", f"Uploaded {images_uploaded}/{total_images} images for ticket {ticket_no}")
                else:
                    self._safe_data_log("info", f"No images found to upload for ticket {ticket_no}")
            else:
                self._safe_data_log("error", f"Failed to save record {ticket_no} to cloud")
                
            return json_success, images_uploaded, total_images
            
        except Exception as e:
            self._safe_data_log("error", f"Error saving to cloud with images: {str(e)}")
            return False, 0, 0

    def _safe_data_log(self, level, message):
        """Safe logging method for DataManager that won't fail on closed files"""
        try:
            if hasattr(self, 'logger') and not getattr(self, 'is_shutting_down', False):
                getattr(self.logger, level)(message)
        except (ValueError, OSError, AttributeError) as e:
            if "closed file" in str(e).lower() or "I/O operation" in str(e):
                # Fallback to print for closed file errors
                print(f"DataManager {level.upper()}: {message}")
            else:
                print(f"DataManager LOG-ERROR: {e}")
                print(f"DataManager {level.upper()}: {message}")
        except Exception:
            # Ultimate fallback - just print
            print(f"DataManager {level.upper()}: {message}")

    def is_record_complete(self, record_data):
        """Check if a record has both weighments complete with safe logging"""
        try:
            first_weight = record_data.get('first_weight', '').strip()
            first_timestamp = record_data.get('first_timestamp', '').strip()
            second_weight = record_data.get('second_weight', '').strip()
            second_timestamp = record_data.get('second_timestamp', '').strip()
            
            is_complete = bool(first_weight and first_timestamp and second_weight and second_timestamp)
            
            self._safe_data_log("debug", f"Record completion check:")
            self._safe_data_log("debug", f"  First weight: '{first_weight}' ({bool(first_weight)})")
            self._safe_data_log("debug", f"  First timestamp: '{first_timestamp}' ({bool(first_timestamp)})")
            self._safe_data_log("debug", f"  Second weight: '{second_weight}' ({bool(second_weight)})")
            self._safe_data_log("debug", f"  Second timestamp: '{second_timestamp}' ({bool(second_timestamp)})")
            self._safe_data_log("debug", f"  Complete: {is_complete}")
            
            return is_complete
            
        except Exception as e:
            self._safe_data_log("error", f"Error checking record completion: {e}")
            return False

    def get_daily_pdf_folder(self):
        """Get or create today's PDF folder"""
        try:
            today = datetime.datetime.now()
            folder_name = today.strftime("%Y-%m-%d")  # Format: 28-05
            
            # Check if we need to create a new folder (date changed)
            if not hasattr(self, 'today_folder_name') or self.today_folder_name != folder_name:
                self.today_folder_name = folder_name
                
                # Ensure base folder exists
                if not hasattr(self, 'pdf_reports_folder'):
                    self.pdf_reports_folder = os.path.join(config.DATA_FOLDER, 'daily_reports')
                    os.makedirs(self.pdf_reports_folder, exist_ok=True)
                
                # Create today's folder
                self.today_pdf_folder = os.path.join(self.pdf_reports_folder, folder_name)
                os.makedirs(self.today_pdf_folder, exist_ok=True)
                self.logger.info(f"Created new daily folder: {self.today_pdf_folder}")
            
            return self.today_pdf_folder
            
        except Exception as e:
            self.logger.error(f"Error getting daily PDF folder: {e}")
            # Fallback
            fallback_folder = os.path.join(config.DATA_FOLDER, 'reports')
            os.makedirs(fallback_folder, exist_ok=True)
            return fallback_folder

    def create_folder_readme_files(self):
        """Create README files explaining folder structure"""
        try:
            # Main reports folder README
            reports_readme = os.path.join(self.reports_folder, "README.txt")
            if not os.path.exists(reports_readme):
                with open(reports_readme, 'w') as f:
                    f.write("""REPORTS FOLDER STRUCTURE
=========================

This folder contains daily PDF reports organized by date.

Structure:
reports/
├── YYYY-MM-DD/          # Daily folder (e.g., 2024-05-29)
│   ├── AgencyName_SiteName_T0001_VehicleNo_123456.pdf
│   ├── AgencyName_SiteName_T0002_VehicleNo_234567.pdf
│   └── [more PDFs...]
├── 2024-05-30/
│   └── [next day PDFs...]
└── README.txt           # This file

OFFLINE-FIRST BEHAVIOR:
- PDFs are auto-generated locally when both weighments complete
- Cloud backup is only attempted when explicitly requested via Settings
- This prevents internet connection delays during normal operations

GENERATED BY: Swaccha Andhra Corporation Weighbridge System
""")
            
            # JSON backup folder README
            json_readme = os.path.join(self.json_backup_folder, "README.txt")
            if not os.path.exists(json_readme):
                with open(json_readme, 'w') as f:
                    f.write("""JSON BACKUPS FOLDER STRUCTURE
===============================

This folder contains daily JSON backups of complete records.

Structure:
json_backups/
├── YYYY-MM-DD/          # Daily folder (e.g., 2024-05-29)
│   ├── T0001_AgencyName_SiteName_123456.json
│   ├── T0002_AgencyName_SiteName_234567.json
│   └── [more JSONs...]
├── 2024-05-30/
│   └── [next day JSONs...]
└── README.txt           # This file

PURPOSE:
- Local JSON backup of complete records (both weighments done)
- Used for bulk cloud upload when internet is available
- Redundant backup in case CSV gets corrupted
- Easy to parse for data analysis

BULK UPLOAD:
- Use Settings > Cloud Storage > Backup to upload all JSONs to cloud
- Only complete records are backed up
- Incremental upload (only new/changed files)

GENERATED BY: Swaccha Andhra Corporation Weighbridge System
""")
                
        except Exception as e:
            self.logger.error(f"Error creating README files: {e}")


    def get_daily_reports_info(self):
        """Get information about today's daily reports"""
        try:
            import datetime
            import os
            
            today_str = datetime.datetime.now().strftime("%Y-%m-%d")
            reports_folder = "data/daily_reports"
            today_reports_folder = os.path.join(reports_folder, today_str)
            
            info = {
                "date": today_str,
                "folder_exists": os.path.exists(today_reports_folder),
                "total_files": 0,
                "total_size": 0,
                "file_types": {}
            }
            
            if info["folder_exists"]:
                # Count files and calculate size
                for root, dirs, files in os.walk(today_reports_folder):
                    for file in files:
                        file_path = os.path.join(root, file)
                        if os.path.exists(file_path):
                            info["total_files"] += 1
                            info["total_size"] += os.path.getsize(file_path)
                            
                            # Track file types
                            ext = os.path.splitext(file)[1].lower()
                            info["file_types"][ext] = info["file_types"].get(ext, 0) + 1
                
                # Format size
                size_bytes = info["total_size"]
                if size_bytes < 1024:
                    info["total_size_formatted"] = f"{size_bytes} B"
                elif size_bytes < 1024 * 1024:
                    info["total_size_formatted"] = f"{size_bytes / 1024:.1f} KB"
                else:
                    info["total_size_formatted"] = f"{size_bytes / (1024 * 1024):.1f} MB"
            else:
                info["total_size_formatted"] = "0 B"
            
            return info
            
        except Exception as e:
            print(f"Error getting daily reports info: {e}")
            return {
                "date": datetime.datetime.now().strftime("%Y-%m-%d"),
                "folder_exists": False,
                "total_files": 0,
                "total_size": 0,
                "total_size_formatted": "0 B",
                "file_types": {},
                "error": str(e)
            }


    def get_daily_folder(self, folder_type="reports"):
        """FIXED: Get or create today's folder with consistent date format"""
        today = datetime.datetime.now()
        folder_name = today.strftime("%Y-%m-%d")  # Consistent format
        
        # Check if we need to create a new folder (date changed)
        if not hasattr(self, 'today_folder_name') or self.today_folder_name != folder_name:
            self.today_folder_name = folder_name
            
            if folder_type == "reports":
                self.today_reports_folder = os.path.join(self.reports_folder, folder_name)
                os.makedirs(self.today_reports_folder, exist_ok=True)
                self.logger.info(f"Created new daily reports folder: {self.today_reports_folder}")
                return self.today_reports_folder
            elif folder_type == "json":
                self.today_json_folder = os.path.join(self.json_backup_folder, folder_name)
                os.makedirs(self.today_json_folder, exist_ok=True)
                self.logger.info(f"Created new daily JSON folder: {self.today_json_folder}")
                return self.today_json_folder
        
        # Return existing folder
        if folder_type == "reports":
            return self.today_reports_folder
        elif folder_type == "json":
            return self.today_json_folder
        else:
            return self.today_reports_folder  # Default

    
    def load_address_config(self):
        """Load address configuration for PDF generation"""
        try:
            config_file = os.path.join(config.DATA_FOLDER, 'address_config.json')
            if os.path.exists(config_file):
                with open(config_file, 'r') as f:
                    return json.load(f)
            else:
                # Create default config for PDF generation
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
                        }
                    }
                }
                
                # Save default config
                os.makedirs(config.DATA_FOLDER, exist_ok=True)
                with open(config_file, 'w') as f:
                    json.dump(default_config, f, indent=4)
                
                return default_config
        except Exception as e:
            self.logger.error(f"Error loading address config for PDF: {e}")
            return {"agencies": {}, "sites": {}}

    def get_current_data_file(self):
        """Get the current data file path based on context"""
        return config.get_current_data_file()
        
    def initialize_new_csv_structure(self):
        """Update CSV structure to include weighment fields if needed"""
        current_file = self.get_current_data_file()
        
        if not os.path.exists(current_file):
            # Create new file with updated header
            try:
                os.makedirs(os.path.dirname(current_file), exist_ok=True)
                with open(current_file, 'w', newline='', encoding='utf-8') as csv_file:
                    writer = csv.writer(csv_file)
                    writer.writerow(config.CSV_HEADER)
                self.logger.info(f"Created new CSV file: {current_file}")
            except Exception as e:
                self.logger.error(f"Error creating CSV file: {e}")
            return
            
        try:
            # Check if existing file has the new structure
            with open(current_file, 'r', newline='', encoding='utf-8') as csv_file:
                reader = csv.reader(csv_file)
                header = next(reader, None)
                
                # Check if our new fields exist in the header
                if header and all(field in header for field in ['First Weight', 'First Timestamp', 'Second Weight', 'Second Timestamp']):
                    # Structure is already updated
                    self.logger.info("CSV structure is up to date")
                    return
                    
                # Need to migrate old data to new structure
                data = list(reader)  # Read all existing data
            
            # Create backup of old file
            backup_file = f"{current_file}.backup_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}"
            shutil.copy2(current_file, backup_file)
            self.logger.info(f"Created backup: {backup_file}")
            
            # Create new file with updated structure
            with open(current_file, 'w', newline='', encoding='utf-8') as csv_file:
                writer = csv.writer(csv_file)
                
                # Write new header
                writer.writerow(config.CSV_HEADER)
                
                # Migrate old data - map old fields to new structure
                for row in data:
                    if len(row) >= 12:  # Ensure we have minimum fields
                        new_row = [
                            row[0],  # Date
                            row[1],  # Time
                            row[2],  # Site Name
                            row[3],  # Agency Name
                            row[4],  # Material
                            row[5],  # Ticket No
                            row[6],  # Vehicle No
                            row[7],  # Transfer Party Name
                            row[8] if len(row) > 8 else "",  # Gross Weight -> First Weight
                            "",      # First Timestamp (new field)
                            row[9] if len(row) > 9 else "",  # Tare Weight -> Second Weight
                            "",      # Second Timestamp (new field)
                            row[10] if len(row) > 10 else "",  # Net Weight
                            row[11] if len(row) > 11 else "",  # Material Type
                            row[12] if len(row) > 12 else "",  # First Front Image
                            row[13] if len(row) > 13 else "",  # First Back Image
                            row[14] if len(row) > 14 else "",  # Second Front Image
                            row[15] if len(row) > 15 else "",  # Second Back Image
                            row[16] if len(row) > 16 else "",  # Site Incharge
                            row[17] if len(row) > 17 else ""   # User Name
                        ]
                        writer.writerow(new_row)
                        
            self.logger.info("Database structure updated successfully")
            if messagebox:
                messagebox.showinfo("Database Updated", 
                                 "The data structure has been updated to support the new weighment system.\n"
                                 f"A backup of your old data has been saved to {backup_file}")
                             
        except Exception as e:
            self.logger.error(f"Error updating database structure: {e}")
            if messagebox:
                messagebox.showerror("Database Update Error", 
                                  f"Error updating database structure: {e}\n"
                                  "The application may not function correctly.")

    def set_agency_site_context(self, agency_name, site_name):
        """Set the current agency and site context for file operations"""
        # Update the global context
        config.set_current_context(agency_name, site_name)
        
        # Update our local reference
        self.data_file = self.get_current_data_file()
        
        # Ensure the new file exists with proper structure
        self.initialize_new_csv_structure()
        
        self.logger.info(f"Data context set to: Agency='{agency_name}', Site='{site_name}'")
        self.logger.info(f"Data file: {self.data_file}")



    def get_all_json_backups(self):
        """Get all JSON backup files for bulk upload"""
        try:
            json_files = []
            
            if not os.path.exists(self.json_backup_folder):
                return json_files
            
            # Walk through all date folders
            for date_folder in os.listdir(self.json_backup_folder):
                date_path = os.path.join(self.json_backup_folder, date_folder)
                
                if os.path.isdir(date_path):
                    # Get all JSON files in this date folder
                    for json_file in os.listdir(date_path):
                        if json_file.endswith('.json'):
                            json_path = os.path.join(date_path, json_file)
                            json_files.append(json_path)
            
            self.logger.info(f"Found {len(json_files)} JSON backup files for bulk upload")
            return json_files
            
        except Exception as e:
            self.logger.error(f"Error getting JSON backup files: {e}")
            return []

    def bulk_upload_json_backups_to_cloud(self):
        """FIXED: Bulk upload all JSON backups to cloud with duplicate checking"""
        try:
            # Initialize cloud storage if needed
            if not self.init_cloud_storage_if_needed():
                return {
                    "success": False,
                    "error": "Failed to initialize cloud storage",
                    "uploaded": 0,
                    "total": 0
                }
            
            # Check if connected to cloud storage
            if not self.cloud_storage.is_connected():
                return {
                    "success": False,
                    "error": "Not connected to cloud storage",
                    "uploaded": 0,
                    "total": 0
                }
            
            # Get all JSON backup files
            json_files = self.get_all_json_backups()
            
            if not json_files:
                return {
                    "success": True,
                    "message": "No JSON backups found to upload",
                    "uploaded": 0,
                    "total": 0
                }
            
            uploaded_count = 0
            skipped_count = 0
            errors = []
            
            for json_path in json_files:
                try:
                    # Load JSON data
                    with open(json_path, 'r', encoding='utf-8') as f:
                        record_data = json.load(f)
                    
                    # Generate cloud filename
                    agency_name = record_data.get('agency_name', 'Unknown_Agency').replace(' ', '_').replace('/', '_')
                    site_name = record_data.get('site_name', 'Unknown_Site').replace(' ', '_').replace('/', '_')
                    ticket_no = record_data.get('ticket_no', 'unknown')
                    
                    # Use the JSON record method which has duplicate checking
                    json_filename = f"{ticket_no}_{agency_name}_{site_name}.json"
                    
                    # Upload using save_json_record which has duplicate checking
                    json_success = self.cloud_storage.save_json_record(
                        record_data, 
                        json_filename,
                        agency_name,
                        site_name
                    )
                    
                    if json_success:
                        # Check if it was actually uploaded or skipped
                        # You can add logging here to distinguish between new upload and skipped duplicate
                        uploaded_count += 1
                        self.logger.info(f" Processed JSON backup: {os.path.basename(json_path)}")
                    else:
                        errors.append(f"Failed to upload {os.path.basename(json_path)}")
                            
                except Exception as file_error:
                    error_msg = f"Error uploading {os.path.basename(json_path)}: {str(file_error)}"
                    errors.append(error_msg)
                    self.logger.error(error_msg)
            
            return {
                "success": uploaded_count > 0,
                "uploaded": uploaded_count,
                "total": len(json_files),
                "skipped": skipped_count,
                "errors": errors
            }
            
        except Exception as e:
            error_msg = f"Error during bulk JSON upload: {str(e)}"
            self.logger.error(error_msg)
            return {
                "success": False,
                "error": error_msg,
                "uploaded": 0,
                "total": 0
            }

    def validate_record_data(self, data):
        """Enhanced validation with detailed error reporting"""
        errors = []
        
        # Check required fields
        required_fields = {
            'ticket_no': 'Ticket Number',
            'vehicle_no': 'Vehicle Number',
            'agency_name': 'Agency Name'
        }
        
        for field, display_name in required_fields.items():
            value = data.get(field, '').strip()
            if not value:
                errors.append(f"{display_name} is required")
        
        # Check weighment data consistency
        first_weight = data.get('first_weight', '').strip()
        first_timestamp = data.get('first_timestamp', '').strip()
        second_weight = data.get('second_weight', '').strip()
        second_timestamp = data.get('second_timestamp', '').strip()
        
        # If first weight exists, timestamp should also exist
        if first_weight and not first_timestamp:
            errors.append("First weighment timestamp is missing")
        
        # If second weight exists, timestamp should also exist
        if second_weight and not second_timestamp:
            errors.append("Second weighment timestamp is missing")
        
        # At least first weighment should be present for new records
        if not first_weight and not first_timestamp:
            errors.append("At least first weighment is required")
        
        return {
            'valid': len(errors) == 0,
            'errors': errors
        }

    def add_new_record(self, data):
        """Thread-safe version of add_new_record"""
        try:
            # Prepare record as list
            record = [
                data.get('date', ''),
                data.get('time', ''),
                data.get('site_name', ''),
                data.get('agency_name', ''),
                data.get('material', ''),
                data.get('ticket_no', ''),
                data.get('vehicle_no', ''),
                data.get('transfer_party_name', ''),
                data.get('first_weight', ''),
                data.get('first_timestamp', ''),
                data.get('second_weight', ''),
                data.get('second_timestamp', ''),
                data.get('net_weight', ''),
                data.get('material_type', ''),
                data.get('first_front_image', ''),
                data.get('first_back_image', ''),
                data.get('second_front_image', ''),
                data.get('second_back_image', ''),
                data.get('site_incharge', ''),
                data.get('user_name', '')
            ]
            
            current_file = self.get_current_data_file()
            
            with safe_csv_operation():
                # Ensure the directory exists
                os.makedirs(os.path.dirname(current_file), exist_ok=True)
                
                # Write to CSV
                with open(current_file, 'a', newline='', encoding='utf-8') as csv_file:
                    writer = csv.writer(csv_file)
                    writer.writerow(record)
                    csv_file.flush()  # Force write to disk
            
            self.logger.info(f"New record added to {current_file}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error adding new record: {e}")
            return False

    def update_record(self, data):
        """FIXED: Update an existing record in the CSV file with enhanced error handling and logging"""
        try:
            current_file = self.get_current_data_file()
            ticket_no = data.get('ticket_no', '')
            
            self.logger.info(f"Updating record {ticket_no} in {current_file}")
            
            if not os.path.exists(current_file):
                self.logger.warning(f"CSV file doesn't exist, creating new one: {current_file}")
                return self.add_new_record(data)
            
            # Read all records
            all_records = []
            header = None
            try:
                with open(current_file, 'r', newline='', encoding='utf-8') as csv_file:
                    reader = csv.reader(csv_file)
                    header = next(reader, None)  # Read header
                    all_records = list(reader)
                    
                self.logger.info(f"Read {len(all_records)} records from CSV")
            except Exception as read_error:
                self.logger.error(f"Error reading CSV file: {read_error}")
                return False
            
            # Find and update the record
            updated = False
            
            for i, row in enumerate(all_records):
                if len(row) >= 6 and row[5] == ticket_no:  # Ticket number is index 5
                    self.logger.info(f"Found record to update at index {i}")
                    
                    # Update the row with new data including all fields
                    updated_row = [
                        data.get('date', row[0] if len(row) > 0 else ''),
                        data.get('time', row[1] if len(row) > 1 else ''),
                        data.get('site_name', row[2] if len(row) > 2 else ''),
                        data.get('agency_name', row[3] if len(row) > 3 else ''),
                        data.get('material', row[4] if len(row) > 4 else ''),
                        data.get('ticket_no', row[5] if len(row) > 5 else ''),
                        data.get('vehicle_no', row[6] if len(row) > 6 else ''),
                        data.get('transfer_party_name', row[7] if len(row) > 7 else ''),
                        data.get('first_weight', row[8] if len(row) > 8 else ''),
                        data.get('first_timestamp', row[9] if len(row) > 9 else ''),
                        data.get('second_weight', row[10] if len(row) > 10 else ''),
                        data.get('second_timestamp', row[11] if len(row) > 11 else ''),
                        data.get('net_weight', row[12] if len(row) > 12 else ''),
                        data.get('material_type', row[13] if len(row) > 13 else ''),
                        data.get('first_front_image', row[14] if len(row) > 14 else ''),
                        data.get('first_back_image', row[15] if len(row) > 15 else ''),
                        data.get('second_front_image', row[16] if len(row) > 16 else ''),
                        data.get('second_back_image', row[17] if len(row) > 17 else ''),
                        data.get('site_incharge', row[18] if len(row) > 18 else ''),
                        data.get('user_name', row[19] if len(row) > 19 else '')
                    ]
                    
                    all_records[i] = updated_row
                    updated = True
                    self.logger.info(f"Updated record data: {updated_row}")
                    break
            
            if not updated:
                self.logger.warning(f"Record with ticket {ticket_no} not found, adding as new record")
                return self.add_new_record(data)
                
            # Write all records back to the file
            try:
                # Create backup before updating
                backup_file = f"{current_file}.backup"
                if os.path.exists(current_file):
                    shutil.copy2(current_file, backup_file)
                
                with open(current_file, 'w', newline='', encoding='utf-8') as csv_file:
                    writer = csv.writer(csv_file)
                    if header:
                        writer.writerow(header)  # Write header
                    writer.writerows(all_records)  # Write all records
                
                # Remove backup if write was successful
                if os.path.exists(backup_file):
                    os.remove(backup_file)
                    
                self.logger.info(f" Record {ticket_no} updated in {current_file}")
                return True
            except Exception as write_error:
                self.logger.error(f"Error writing updated records: {write_error}")
                # Restore from backup if write failed
                backup_file = f"{current_file}.backup"
                if os.path.exists(backup_file):
                    shutil.copy2(backup_file, current_file)
                    os.remove(backup_file)
                    self.logger.info("Restored from backup due to write error")
                return False
                
        except Exception as e:
            self.logger.error(f" Error updating record: {e}")
            return False



    def get_daily_pdf_folder(self):
        """Get or create today's PDF folder"""
        today = datetime.datetime.now()
        folder_name = today.strftime("%Y-%m-%d")
        # Check if we need to create a new folder (date changed)
        if not hasattr(self, 'today_folder_name') or self.today_folder_name != folder_name:
            self.today_folder_name = folder_name
            self.today_pdf_folder = os.path.join(self.pdf_reports_folder, folder_name)
            os.makedirs(self.today_pdf_folder, exist_ok=True)
            self.logger.info(f"Created new daily folder: {self.today_pdf_folder}")
        
        return self.today_pdf_folder
    
    def create_pdf_report(self, records_data, save_path):
        """Create PDF report with 4-image grid for complete records - FIXED image handling
        
        Args:
            records_data: List of record dictionaries
            save_path: Path to save the PDF
            
        Returns:
            bool: True if successful, False otherwise
        """
        if not REPORTLAB_AVAILABLE:
            self.logger.error("ReportLab not available for PDF generation")
            return False
            
        try:
            # Ensure output directory exists
            os.makedirs(os.path.dirname(save_path), exist_ok=True)
            
            doc = SimpleDocTemplate(save_path, pagesize=A4,
                                    rightMargin=36, leftMargin=36, topMargin=36, bottomMargin=36)
            
            styles = getSampleStyleSheet()
            elements = []
            temp_files_to_cleanup = []  # Track temp files for cleanup

            # Create styles (same as before)
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

                # Vehicle Information (same as before)
                elements.append(Paragraph("VEHICLE INFORMATION", section_header_style))
                
                material_value = record.get('material', '') or record.get('material_type', '')
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
                    ('FONTSIZE', (0,0), (-1,-1), 13),
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

# COMPLETE WEIGHMENT SECTION - Replace everything from "Weighment Information" to elements.append(Spacer)

# Weighment Information
                elements.append(Paragraph("WEIGHMENT DETAILS", section_header_style))

                # Simple test version - no complex formatting
                first_weight_str = record.get('first_weight', '').strip()
                second_weight_str = record.get('second_weight', '').strip()
                net_weight_str = record.get('net_weight', '').strip()

                # Force calculate net weight
                if first_weight_str and second_weight_str:
                    try:
                        first_weight = float(first_weight_str)
                        second_weight = float(second_weight_str)
                        calculated_net = abs(first_weight - second_weight)
                        net_weight_str = f"{calculated_net:.2f}"
                    except:
                        net_weight_str = "Error"

                # Simple display values - NO fancy formatting
                first_display = f"{first_weight_str} kg" if first_weight_str else "Not captured"
                second_display = f"{second_weight_str} kg" if second_weight_str else "Not captured"
                net_display = f"{net_weight_str} kg" if net_weight_str else "Not calculated"

                self.logger.info(f"SIMPLE TEST - Net display: '{net_display}'")

                # Create simple table data - NO Paragraph objects for net weight
                weighment_data = [
                    ["First Weight:", first_display, "First Time:", record.get('first_timestamp', '') or "Not captured"],
                    ["Second Weight:", second_display, "Second Time:", record.get('second_timestamp', '') or "Not captured"],
                    ["", "", "Net Weight:", net_display]  # Plain string, no Paragraph
                ]

                # Simple table creation
                weighment_inner_table = Table(weighment_data, colWidths=[1.5*inch, 1.5*inch, 1.2*inch, 2.8*inch])
                weighment_inner_table.setStyle(TableStyle([
                    ('FONTNAME', (0,0), (-1,-1), 'Helvetica'),
                    ('FONTSIZE', (0,0), (-1,-1), 11),
                    ('ALIGN', (0,0), (-1,-1), 'LEFT'),
                    ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
                    ('GRID', (0,0), (-1,-1), 1, colors.black),
                    ('LEFTPADDING', (0,0), (-1,-1), 6),
                    ('RIGHTPADDING', (0,0), (-1,-1), 6),
                    ('TOPPADDING', (0,0), (-1,-1), 6),
                    ('BOTTOMPADDING', (0,0), (-1,-1), 6),
                    # Make net weight bold
                    ('FONTNAME', (2,2), (3,2), 'Helvetica-Bold'),
                    ('FONTSIZE', (2,2), (3,2), 12),
                ]))

                # Continue with your existing table wrapper code
                weighment_table = Table([[weighment_inner_table]], colWidths=[7*inch])
                # Add to elements
                elements.append(weighment_table)
                elements.append(Spacer(1, 0.15*inch))

                # 4-Image Grid Section - FIXED IMAGE HANDLING
                elements.append(Paragraph("VEHICLE IMAGES (4-Image System)", section_header_style))
                
                # Get all 4 image paths with validation
                image_paths = [
                    (record.get('first_front_image', ''), f"Ticket: {ticket_no}"),
                    (record.get('first_back_image', ''), f"Ticket: {ticket_no}"),
                    (record.get('second_front_image', ''), f"Ticket: {ticket_no}"),
                    (record.get('second_back_image', ''), f"Ticket: {ticket_no}")
                ]

                # Create 2x2 image grid with headers
                img_data = [
                    ["1ST WEIGHMENT - FRONT", "1ST WEIGHMENT - BACK"],
                    [None, None],  # Will be filled with first weighment images
                    ["2ND WEIGHMENT - FRONT", "2ND WEIGHMENT - BACK"], 
                    [None, None]   # Will be filled with second weighment images
                ]

                # Process all 4 images with better error handling
                processed_images = []
                
                for img_filename, watermark_text in image_paths:
                    if img_filename and img_filename.strip():
                        # Build full path
                        img_path = os.path.join(config.IMAGES_FOLDER, img_filename.strip())
                        
                        if os.path.exists(img_path):
                            try:
                                temp_img_path = self.prepare_image_for_pdf(img_path, watermark_text)
                                if temp_img_path and os.path.exists(temp_img_path):
                                    processed_img = RLImage(temp_img_path, width=3.5*inch, height=2.0*inch)
                                    processed_images.append(processed_img)
                                    temp_files_to_cleanup.append(temp_img_path)  # Track for cleanup
                                    self.logger.debug(f"Successfully processed image: {img_filename}")
                                else:
                                    processed_images.append("Image processing failed")
                                    self.logger.warning(f"Failed to process image: {img_filename}")
                            except Exception as e:
                                self.logger.error(f"Error processing image {img_filename}: {e}")
                                processed_images.append("Image processing error")
                        else:
                            processed_images.append("Image file not found")
                            self.logger.warning(f"Image file not found: {img_path}")
                    else:
                        processed_images.append("No image captured")
                        self.logger.debug("No image filename provided")

                # Fill the image grid
                img_data[1] = [processed_images[0], processed_images[1]]  # First weighment
                img_data[3] = [processed_images[2], processed_images[3]]  # Second weighment

                # Create images table with 2x2 grid
                img_table = Table(img_data, colWidths=[3.5*inch, 3.5*inch], 
                                rowHeights=[0.3*inch, 2*inch, 0.3*inch, 2*inch])
                img_table.setStyle(TableStyle([
                    ('GRID', (0,0), (-1,-1), 0.5, colors.black),
                    ('FONTNAME', (0,0), (-1,-1), 'Helvetica-Bold'),
                    ('FONTSIZE', (0,0), (1,0), 10),  # Header row 1
                    ('FONTSIZE', (0,2), (1,2), 10),  # Header row 2
                    ('ALIGN', (0,0), (-1,-1), 'CENTER'),
                    ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
                    ('LEFTPADDING', (0,0), (-1,-1), 6),
                    ('RIGHTPADDING', (0,0), (-1,-1), 6),
                    ('TOPPADDING', (0,0), (-1,-1), 6),
                    ('BOTTOMPADDING', (0,0), (-1,-1), 6),
                    # Header background
                    ('BACKGROUND', (0,0), (1,0), colors.lightgrey),
                    ('BACKGROUND', (0,2), (1,2), colors.lightgrey),
                ]))
                elements.append(img_table)
                
                # Add operator signature line at bottom right
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
            self.logger.info(f"Building PDF document: {save_path}")
            doc.build(elements)
            
            # Clean up temporary files
            for temp_file in temp_files_to_cleanup:
                try:
                    if os.path.exists(temp_file):
                        os.remove(temp_file)
                        self.logger.debug(f"Cleaned up temporary file: {temp_file}")
                except Exception as cleanup_error:
                    self.logger.warning(f"Could not clean up temporary file {temp_file}: {cleanup_error}")
            
            # Verify PDF was created
            if os.path.exists(save_path) and os.path.getsize(save_path) > 0:
                self.logger.info(f"PDF created successfully: {save_path} ({os.path.getsize(save_path)} bytes)")
                return True
            else:
                self.logger.error(f"PDF was not created or is empty: {save_path}")
                return False
                
        except Exception as e:
            self.logger.error(f"Error creating PDF report: {e}")
            import traceback
            self.logger.error(f"PDF generation traceback: {traceback.format_exc()}")
            return False
    
    def prepare_image_for_pdf(self, image_path, watermark_text):
        """Prepare image for PDF by resizing and adding watermark - FIXED path handling"""
        try:
            # Validate input path
            if not image_path or not os.path.exists(image_path):
                self.logger.warning(f"Image path does not exist: {image_path}")
                return None
            
            self.logger.debug(f"Preparing image for PDF: {image_path}")
            
            # Read image with error handling
            img = cv2.imread(image_path)
            if img is None:
                self.logger.warning(f"Could not read image: {image_path}")
                return None
            
            # Resize image for PDF (maintain aspect ratio)
            height, width = img.shape[:2]
            max_width = 400
            max_height = 300
            
            # Calculate scaling factor
            scale_w = max_width / width
            scale_h = max_height / height
            scale = min(scale_w, scale_h)
            
            new_width = int(width * scale)
            new_height = int(height * scale)
            
            img_resized = cv2.resize(img, (new_width, new_height))
            
            # Add watermark
            try:
                from camera import add_watermark  # Import the watermark function
                watermarked_img = add_watermark(img_resized, watermark_text)
            except ImportError:
                # Fallback if watermark function not available
                self.logger.warning("Watermark function not available, using image without watermark")
                watermarked_img = img_resized
            except Exception as watermark_error:
                self.logger.warning(f"Watermark error: {watermark_error}, using image without watermark")
                watermarked_img = img_resized
            
            # Create unique temporary filename with proper path
            timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S_%f')
            temp_filename = f"temp_pdf_image_{timestamp}.jpg"
            
            # Ensure images folder exists
            os.makedirs(config.IMAGES_FOLDER, exist_ok=True)
            temp_path = os.path.join(config.IMAGES_FOLDER, temp_filename)
            
            # Save temporary file with error handling
            success = cv2.imwrite(temp_path, watermarked_img)
            
            if not success:
                self.logger.error(f"Failed to save temporary image: {temp_path}")
                return None
            
            # Verify the file was created and is readable
            if not os.path.exists(temp_path):
                self.logger.error(f"Temporary image was not created: {temp_path}")
                return None
            
            # Verify file size
            if os.path.getsize(temp_path) == 0:
                self.logger.error(f"Temporary image is empty: {temp_path}")
                os.remove(temp_path)  # Clean up empty file
                return None
            
            self.logger.debug(f"Successfully prepared temporary image: {temp_path}")
            return temp_path
            
        except Exception as e:
            self.logger.error(f"Error preparing image for PDF: {e}")
            return None

    # ========== CLOUD STORAGE METHODS (ONLY USED WHEN EXPLICITLY REQUESTED) ==========
    
    def init_cloud_storage_if_needed(self):
        """Initialize cloud storage only when explicitly needed"""
        if self.cloud_storage is None:
            try:
                self.cloud_storage = CloudStorageService(
                    config.CLOUD_BUCKET_NAME,
                    config.CLOUD_CREDENTIALS_PATH
                )
                self.logger.info("Cloud storage initialized on demand")
            except Exception as e:
                self.logger.error(f"Failed to initialize cloud storage: {e}")
                return False
        return True



    def _calculate_net_weight_for_cloud(self, first_weight_str, second_weight_str):
        """Calculate net weight for cloud storage"""
        try:
            if first_weight_str and second_weight_str:
                first_weight = float(first_weight_str)
                second_weight = float(second_weight_str)
                return abs(first_weight - second_weight)
            return 0.0
        except (ValueError, TypeError):
            return 0.0

    def backup_complete_records_to_cloud_with_reports(self):
        """Enhanced backup: records, images, and daily reports - ONLY WHEN EXPLICITLY CALLED"""
        try:
            import config  # Import config at the beginning
            
            # Initialize cloud storage if not already initialized
            if not self.init_cloud_storage_if_needed():
                return {
                    "success": False,
                    "error": "Failed to initialize cloud storage",
                    "records_uploaded": 0,
                    "total_records": 0,
                    "images_uploaded": 0,
                    "total_images": 0,
                    "reports_uploaded": 0,
                    "total_reports": 0
                }
            
            # Check if connected to cloud storage
            if not self.cloud_storage.is_connected():
                return {
                    "success": False,
                    "error": "Not connected to cloud storage",
                    "records_uploaded": 0,
                    "total_records": 0,
                    "images_uploaded": 0,
                    "total_images": 0,
                    "reports_uploaded": 0,
                    "total_reports": 0
                }
            
            # Get all records and filter for complete ones
            all_records = self.get_all_records()
            complete_records = []
            
            for record in all_records:
                first_weight = record.get('first_weight', '').strip()
                first_timestamp = record.get('first_timestamp', '').strip()
                second_weight = record.get('second_weight', '').strip()
                second_timestamp = record.get('second_timestamp', '').strip()
                
                if (first_weight and first_timestamp and second_weight and second_timestamp):
                    complete_records.append(record)
            
            print(f"Found {len(complete_records)} complete records out of {len(all_records)} total records")
            agency_name, site_name = config.get_current_agency_site()
            results = self.cloud_storage.comprehensive_backup(agency_name, site_name)
            
            print(f"Backup completed:")
            print(f"  Records: {results['records_uploaded']}/{results['total_records']}")
            print(f"  Images: {results['images_uploaded']}/{results['total_images']}")
            print(f"  Daily Reports: {results['reports_uploaded']}/{results['total_reports']}")
            if results['errors']:
                print(f"  Errors: {len(results['errors'])}")
            
            return results
            
        except Exception as e:
            error_msg = f"Error during comprehensive backup: {str(e)}"
            print(error_msg)
            return {
                "success": False,
                "error": error_msg,
                "records_uploaded": 0,
                "total_records": 0,
                "images_uploaded": 0,
                "total_images": 0,
                "reports_uploaded": 0,
                "total_reports": 0
            }

    def get_enhanced_cloud_upload_summary(self):
        """Get enhanced summary including daily reports - ONLY WHEN EXPLICITLY CALLED"""
        try:
            import config  # Import config at the beginning
            
            if not self.init_cloud_storage_if_needed():
                return {"error": "Failed to initialize cloud storage"}
            
            if not self.cloud_storage.is_connected():
                return {"error": "Not connected to cloud storage"}
            
            # Get current agency and site for filtering
            agency_name = config.CURRENT_AGENCY or "Unknown_Agency"
            site_name = config.CURRENT_SITE or "Unknown_Site"
            
            # Clean names for filtering
            clean_agency = agency_name.replace(' ', '_').replace('/', '_')
            clean_site = site_name.replace(' ', '_').replace('/', '_')
            
            # Get summary for current agency/site
            prefix = f"{clean_agency}/{clean_site}/"
            summary = self.cloud_storage.get_upload_summary(prefix)
            
            # Add daily reports summary (no prefix filter for reports)
            reports_summary = self.cloud_storage.get_upload_summary("daily_reports/")
            
            # Combine summaries
            if "error" not in summary and "error" not in reports_summary:
                summary["daily_report_files"] = reports_summary.get("total_files", 0)
                summary["daily_reports_size"] = reports_summary.get("total_size", "0 B")
            
            # Add context information
            summary["agency"] = agency_name
            summary["site"] = site_name
            summary["context"] = f"{agency_name} - {site_name}"
            
            # Add today's reports info
            daily_reports_info = self.get_daily_reports_info()
            summary["todays_reports"] = daily_reports_info
            
            return summary
            
        except Exception as e:
            return {"error": f"Error getting enhanced cloud summary: {str(e)}"}



    # Update the existing backup_complete_records_to_cloud method to use the new enhanced version
    def backup_complete_records_to_cloud(self):
        """Legacy method - now calls enhanced backup with reports
        
        Returns:
            tuple: (success_count, total_complete_records, images_uploaded, total_images) for backward compatibility
        """
        try:
            # Use the enhanced backup method
            results = self.backup_complete_records_to_cloud_with_reports()
            
            # Return in the old format for backward compatibility
            return (
                results.get("records_uploaded", 0),
                results.get("total_records", 0), 
                results.get("images_uploaded", 0),
                results.get("total_images", 0)
            )
            
        except Exception as e:
            print(f"Error in legacy backup method: {e}")
            return 0, 0, 0, 0

    def get_cloud_upload_summary(self):
        """Get summary of files uploaded to cloud storage - ONLY WHEN EXPLICITLY CALLED"""
        try:
            if not self.init_cloud_storage_if_needed():
                return {"error": "Failed to initialize cloud storage"}
            
            if not self.cloud_storage.is_connected():
                return {"error": "Not connected to cloud storage"}
            
            # Get current agency and site for filtering
            agency_name = config.CURRENT_AGENCY or "Unknown_Agency"
            site_name = config.CURRENT_SITE or "Unknown_Site"
            
            # Clean names for filtering
            clean_agency = agency_name.replace(' ', '_').replace('/', '_')
            clean_site = site_name.replace(' ', '_').replace('/', '_')
            
            # Get summary for current agency/site
            prefix = f"{clean_agency}/{clean_site}/"
            summary = self.cloud_storage.get_upload_summary(prefix)
            
            # Add context information
            summary["agency"] = agency_name
            summary["site"] = site_name
            summary["context"] = f"{agency_name} - {site_name}"
            
            return summary
            
        except Exception as e:
            return {"error": f"Error getting cloud summary: {str(e)}"}

    # ========== UTILITY METHODS ==========
    
    def save_to_cloud(self, data):
        """Legacy method - now calls the new save_to_cloud_with_images method
        
        Args:
            data: Record data dictionary
            
        Returns:
            bool: True if successful, False otherwise
        """
        success, _, _ = self.save_to_cloud_with_images(data)
        return success

    def get_record_by_vehicle(self, vehicle_no):
        """Get a specific record by vehicle number
        
        Args:
            vehicle_no: Vehicle number to search for
            
        Returns:
            dict: Record as dictionary or None if not found
        """
        current_file = self.get_current_data_file()
        
        if not os.path.exists(current_file):
            return None
            
        try:
            with open(current_file, 'r', newline='') as csv_file:
                reader = csv.reader(csv_file)
                
                # Skip header
                next(reader, None)
                
                for row in reader:
                    if len(row) >= 7 and row[6] == vehicle_no:  # Vehicle number is index 6
                        record = {
                            'date': row[0],
                            'time': row[1],
                            'site_name': row[2],
                            'agency_name': row[3],
                            'material': row[4],
                            'ticket_no': row[5],
                            'vehicle_no': row[6],
                            'transfer_party_name': row[7],
                            'first_weight': row[8] if len(row) > 8 else '',
                            'first_timestamp': row[9] if len(row) > 9 else '',
                            'second_weight': row[10] if len(row) > 10 else '',
                            'second_timestamp': row[11] if len(row) > 11 else '',
                            'net_weight': row[12] if len(row) > 12 else '',
                            'material_type': row[13] if len(row) > 13 else '',
                            'first_front_image': row[14] if len(row) > 14 else '',
                            'first_back_image': row[15] if len(row) > 15 else '',
                            'second_front_image': row[16] if len(row) > 16 else '',
                            'second_back_image': row[17] if len(row) > 17 else '',
                            'site_incharge': row[18] if len(row) > 18 else '',
                            'user_name': row[19] if len(row) > 19 else ''
                        }
                        return record
                        
            return None
                
        except Exception as e:
            print(f"Error finding record: {e}")
            return None
    
    def validate_record(self, data):
        """Validate record data
        
        Args:
            data: Record data
            
        Returns:
            tuple: (is_valid, error_message)
        """
        required_fields = {
            "Ticket No": data.get('ticket_no', ''),
            "Vehicle No": data.get('vehicle_no', ''),
            "Agency Name": data.get('agency_name', '')
        }
        
        missing_fields = [field for field, value in required_fields.items() 
                         if not str(value).strip()]
        
        if missing_fields:
            return False, f"Missing required fields: {', '.join(missing_fields)}"
        
        # Check if we have at least the first weighment for a new entry
        if not data.get('first_weight', '').strip():
            return False, "First weighment is required"
            
        return True, ""

    def cleanup_orphaned_images(self):
        """Clean up image files that are not referenced in any records
        
        Returns:
            tuple: (cleaned_files, total_size_freed)
        """
        try:
            # Get all records
            all_records = self.get_all_records()
            
            # Collect all referenced image filenames
            referenced_images = set()
            for record in all_records:
                # Check all 4 image fields
                for img_field in ['first_front_image', 'first_back_image', 'second_front_image', 'second_back_image']:
                    img_filename = record.get(img_field, '').strip()
                    if img_filename:
                        referenced_images.add(img_filename)
            
            # Get all image files in the images folder
            if not os.path.exists(config.IMAGES_FOLDER):
                return 0, 0
            
            all_image_files = [f for f in os.listdir(config.IMAGES_FOLDER) 
                             if f.lower().endswith(('.jpg', '.jpeg', '.png', '.gif', '.bmp'))]
            
            # Find orphaned images
            orphaned_images = []
            for image_file in all_image_files:
                if image_file not in referenced_images:
                    orphaned_images.append(image_file)
            
            # Clean up orphaned images
            cleaned_files = 0
            total_size_freed = 0
            
            for image_file in orphaned_images:
                image_path = os.path.join(config.IMAGES_FOLDER, image_file)
                if os.path.exists(image_path):
                    try:
                        # Get file size before deletion
                        file_size = os.path.getsize(image_path)
                        
                        # Delete the file
                        os.remove(image_path)
                        
                        cleaned_files += 1
                        total_size_freed += file_size
                        
                        print(f"Cleaned up orphaned image: {image_file}")
                        
                    except Exception as e:
                        print(f"Error cleaning up {image_file}: {e}")
            
            return cleaned_files, total_size_freed
            
        except Exception as e:
            print(f"Error during image cleanup: {e}")
            return 0, 0