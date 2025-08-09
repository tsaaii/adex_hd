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
from threading import Lock
from io import BytesIO
from PIL import Image as PILImage
import contextlib
import cv2
# ADD THESE SAFE OPERATION FUNCTIONS after imports:
from trip_report_generator import auto_generate_on_completion, is_record_complete as trip_is_complete

# Global lock for all file operations
_global_file_lock = threading.RLock()

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
            with _global_file_lock:
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

def safe_csv_write(file_path, records, headers, retries=3):
    """Safely write CSV file with retries and proper error handling"""
    # Ensure directory exists
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    
    for attempt in range(retries):
        try:
            with safe_file_operation():
                # Create backup before writing
                backup_path = f"{file_path}.backup_{int(time.time())}"
                if os.path.exists(file_path):
                    shutil.copy2(file_path, backup_path)
                
                try:
                    with open(file_path, 'w', newline='', encoding='utf-8') as csv_file:
                        writer = csv.DictWriter(csv_file, fieldnames=headers)
                        writer.writeheader()
                        writer.writerows(records)
                    
                    # Remove backup on success
                    if os.path.exists(backup_path):
                        os.remove(backup_path)
                    
                    return True
                    
                except Exception as write_error:
                    # Restore from backup on failure
                    if os.path.exists(backup_path):
                        shutil.copy2(backup_path, file_path)
                        os.remove(backup_path)
                    raise write_error
                    
        except (OSError, ValueError) as e:
            if "closed file" in str(e).lower() and attempt < retries - 1:
                print(f"CSV write attempt {attempt + 1} failed, retrying: {e}")
                time.sleep(0.2 * (attempt + 1))
                continue
            else:
                print(f"CSV write failed after {retries} attempts: {e}")
                return False
        except Exception as e:
            print(f"Unexpected CSV write error: {e}")
            return False
    
    return False

@contextlib.contextmanager

def safe_file_operation(retries=3, delay=0.1):
    """Context manager for safe file operations with retries"""
    for attempt in range(retries):
        try:
            with _global_file_lock:
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

def safe_csv_write(file_path, records, headers, retries=3):
    """Safely write CSV file with retries and proper error handling"""
    # Ensure directory exists
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    
    for attempt in range(retries):
        try:
            with safe_file_operation():
                # Create backup before writing
                backup_path = f"{file_path}.backup_{int(time.time())}"
                if os.path.exists(file_path):
                    shutil.copy2(file_path, backup_path)
                
                try:
                    with open(file_path, 'w', newline='', encoding='utf-8') as csv_file:
                        writer = csv.DictWriter(csv_file, fieldnames=headers)
                        writer.writeheader()
                        writer.writerows(records)
                    
                    # Remove backup on success
                    if os.path.exists(backup_path):
                        os.remove(backup_path)
                    
                    return True
                    
                except Exception as write_error:
                    # Restore from backup on failure
                    if os.path.exists(backup_path):
                        shutil.copy2(backup_path, file_path)
                        os.remove(backup_path)
                    raise write_error
                    
        except (OSError, ValueError) as e:
            if "closed file" in str(e).lower() and attempt < retries - 1:
                print(f"CSV write attempt {attempt + 1} failed, retrying: {e}")
                time.sleep(0.2 * (attempt + 1))
                continue
            else:
                print(f"CSV write failed after {retries} attempts: {e}")
                return False
        except Exception as e:
            print(f"Unexpected CSV write error: {e}")
            return False
    
    return False



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
        self.safe_logger = SafeLogger('DataManager')
        self.is_shutting_down = False
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

    def get_all_records(self):
        """FIXED: Get all records with safe file operations and no I/O errors"""
        # Check shutdown status
        if getattr(self, 'is_shutting_down', False):
            print("🛑 DATA MANAGER: get_all_records blocked - shutdown in progress")
            return []
        
        current_file = self.get_current_data_file()
        
        # Use safe CSV read
        raw_records = safe_csv_read(current_file)
        
        if not raw_records:
            self.safe_logger.warning(f"No records found in {current_file}")
            return []
        
        # Normalize record keys (handle both old and new CSV formats)
        records = []
        for record in raw_records:
            normalized_record = {
                'date': record.get('Date', record.get('date', '')),
                'time': record.get('Time', record.get('time', '')),
                'site_name': record.get('Site Name', record.get('site_name', '')),
                'agency_name': record.get('Agency Name', record.get('agency_name', '')),
                'material': record.get('Material', record.get('material', '')),
                'ticket_no': record.get('Ticket No', record.get('ticket_no', '')),
                'vehicle_no': record.get('Vehicle No', record.get('vehicle_no', '')),
                'transfer_party_name': record.get('Transfer Party Name', record.get('transfer_party_name', '')),
                'first_weight': record.get('First Weight', record.get('first_weight', '')),
                'first_timestamp': record.get('First Timestamp', record.get('first_timestamp', '')),
                'second_weight': record.get('Second Weight', record.get('second_weight', '')),
                'second_timestamp': record.get('Second Timestamp', record.get('second_timestamp', '')),
                'net_weight': record.get('Net Weight', record.get('net_weight', '')),
                'material_type': record.get('Material Type', record.get('material_type', '')),
                'first_front_image': record.get('First Front Image', record.get('first_front_image', '')),
                'first_back_image': record.get('First Back Image', record.get('first_back_image', '')),
                'second_front_image': record.get('Second Front Image', record.get('second_front_image', '')),
                'second_back_image': record.get('Second Back Image', record.get('second_back_image', '')),
                'site_incharge': record.get('Site Incharge', record.get('site_incharge', '')),
                'user_name': record.get('User Name', record.get('user_name', ''))
            }
            records.append(normalized_record)
        
        self.safe_logger.info(f"Successfully loaded {len(records)} records")
        return records

    def save_record(self, data):
        """FIXED: Save record with comprehensive I/O error protection"""
        # Check shutdown status
        if getattr(self, 'is_shutting_down', False):
            print("🛑 DATA MANAGER: save_record blocked - shutdown in progress")
            return {'success': False, 'error': 'Application shutting down'}
        
        try:
            self.safe_logger.info("STARTING OFFLINE-FIRST RECORD SAVE")
            
            # Calculate net weight
            data = self.calculate_and_set_net_weight(data)
            
            # Validate data
            validation_result = self.validate_record_data(data)
            if not validation_result['valid']:
                self.safe_logger.error(f"Validation failed: {validation_result['errors']}")
                return {'success': False, 'error': 'Validation failed'}
            
            # Get current file and records
            current_file = self.get_current_data_file()
            all_records = safe_csv_read(current_file)
            
            # Check if this is an update
            ticket_no = data.get('ticket_no', '')
            is_update = False
            
            for i, record in enumerate(all_records):
                if record.get('Ticket No', record.get('ticket_no', '')) == ticket_no:
                    # Update existing record
                    all_records[i] = self._prepare_record_for_csv(data)
                    is_update = True
                    self.safe_logger.info(f"Updating existing record: {ticket_no}")
                    break
            
            if not is_update:
                # Add new record
                all_records.append(self._prepare_record_for_csv(data))
                self.safe_logger.info(f"Adding new record: {ticket_no}")
            
            # Write back to CSV safely
            headers = [
                'Date', 'Time', 'Site Name', 'Agency Name', 'Material', 'Ticket No', 
                'Vehicle No', 'Transfer Party Name', 'First Weight', 'First Timestamp',
                'Second Weight', 'Second Timestamp', 'Net Weight', 'Material Type',
                'First Front Image', 'First Back Image', 'Second Front Image', 
                'Second Back Image', 'Site Incharge', 'User Name'
            ]
            
            success = safe_csv_write(current_file, all_records, headers)
            
            if success:
                self.safe_logger.info(f" Record {ticket_no} saved successfully")
                
                # Additional processing for complete records
                is_complete = self.is_record_complete(data)
                if is_complete:
                    try:
                        self.save_json_backup_locally(data)
                        self.auto_generate_pdf_for_complete_record(data)
                    except Exception as e:
                        self.safe_logger.warning(f"Non-critical error in post-save processing: {e}")
                
                return {
                    'success': True,
                    'is_complete_record': is_complete,
                    'is_update': is_update,
                    'ticket_no': ticket_no
                }
            else:
                self.safe_logger.error(f" Failed to save record {ticket_no}")
                return {'success': False, 'error': 'Failed to save to CSV'}
        
        except Exception as e:
            self.safe_logger.error(f" Critical error saving record: {e}")
            return {'success': False, 'error': str(e)}

    def _prepare_record_for_csv(self, data):
        """Prepare record data for CSV writing"""
        return {
            'Date': data.get('date', ''),
            'Time': data.get('time', ''),
            'Site Name': data.get('site_name', ''),
            'Agency Name': data.get('agency_name', ''),
            'Material': data.get('material', ''),
            'Ticket No': data.get('ticket_no', ''),
            'Vehicle No': data.get('vehicle_no', ''),
            'Transfer Party Name': data.get('transfer_party_name', ''),
            'First Weight': data.get('first_weight', ''),
            'First Timestamp': data.get('first_timestamp', ''),
            'Second Weight': data.get('second_weight', ''),
            'Second Timestamp': data.get('second_timestamp', ''),
            'Net Weight': data.get('net_weight', ''),
            'Material Type': data.get('material_type', ''),
            'First Front Image': data.get('first_front_image', ''),
            'First Back Image': data.get('first_back_image', ''),
            'Second Front Image': data.get('second_front_image', ''),
            'Second Back Image': data.get('second_back_image', ''),
            'Site Incharge': data.get('site_incharge', ''),
            'User Name': data.get('user_name', '')
        }

    def normalize_record_keys(self, record):
        """Normalize CSV record keys to handle both formats (spaces and underscores)
        
        This ensures compatibility between CSV headers with spaces and code expecting underscores.
        
        Args:
            record: Dictionary from CSV DictReader
            
        Returns:
            dict: Record with both formats available
        """
        if not isinstance(record, dict):
            return record
        
        # Create normalized record with both formats
        normalized = record.copy()
        
        # Mapping from CSV headers (with spaces) to code expectations (with underscores)
        header_mapping = {
            'Date': 'date',
            'Time': 'time',
            'Site Name': 'site_name',
            'Agency Name': 'agency_name',
            'Material': 'material',
            'Ticket No': 'ticket_no',
            'Vehicle No': 'vehicle_no',
            'Transfer Party Name': 'transfer_party_name',
            'First Weight': 'first_weight',
            'First Timestamp': 'first_timestamp',
            'Second Weight': 'second_weight',
            'Second Timestamp': 'second_timestamp',
            'Net Weight': 'net_weight',
            'Material Type': 'material_type',
            'First Front Image': 'first_front_image',
            'First Back Image': 'first_back_image',
            'Second Front Image': 'second_front_image',
            'Second Back Image': 'second_back_image',
            'Site Incharge': 'site_incharge',
            'User Name': 'user_name'
        }
        
        # Add underscore versions for each spaced header
        for csv_header, underscore_key in header_mapping.items():
            if csv_header in record:
                normalized[underscore_key] = record[csv_header]
        
        # Also add spaced versions for each underscore key (reverse mapping)
        for underscore_key, csv_header in {v: k for k, v in header_mapping.items()}.items():
            if underscore_key in record:
                normalized[csv_header] = record[underscore_key]
        
        return normalized

    def get_filtered_records(self, filter_text=""):
        """Get records filtered by text with normalized keys - ENHANCED"""
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
                        raw_records = list(reader)  # Read everything immediately
                    
                    # Normalize all records to handle both header formats
                    all_records = [self.normalize_record_keys(record) for record in raw_records]
                    
                    self._safe_data_log("info", f"Successfully loaded {len(all_records)} records")
                    
                    # Filter outside of file operations
                    if not filter_text:
                        self._safe_data_log("info", f"Returning all {len(all_records)} records (no filter)")
                        return all_records
                    
                    filter_text = filter_text.lower().strip()
                    filtered_records = []
                    
                    for record in all_records:
                        try:
                            # SPECIAL CASE: If filter looks like a ticket number, do case-insensitive exact match first
                            ticket_no = record.get('ticket_no', '').strip()
                            if ticket_no and ticket_no.lower() == filter_text:
                                print(f"🔍 DEBUG: Found exact ticket match: {ticket_no} (searched for {filter_text})")
                                filtered_records.append(record)
                                continue
                            
                            # General case: Check if filter text exists in any field (case-insensitive)
                            if any(filter_text in str(value).lower() for value in record.values() if value is not None):
                                filtered_records.append(record)
                        except Exception as filter_error:
                            self._safe_data_log("warning", f"Error filtering record: {filter_error}")
                            continue
                    
                    self._safe_data_log("info", f"Filtered {len(all_records)} records to {len(filtered_records)} using filter: '{filter_text}'")
                    print(f"🔍 DEBUG: Filter '{filter_text}' found {len(filtered_records)} records")
                    
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
        """
        SIMPLIFIED: Get today's reports folder (trip_report_generator manages date folders)
        """
        try:
            import datetime
            
            # Create base reports folder structure
            base_reports_folder = os.path.join(config.DATA_FOLDER, 'reports')
            os.makedirs(base_reports_folder, exist_ok=True)
            
            # Create today's folder with YYYY-MM-DD format
            today = datetime.datetime.now()
            today_folder_name = today.strftime("%Y-%m-%d")
            todays_folder = os.path.join(base_reports_folder, today_folder_name)
            
            # Ensure today's folder exists
            os.makedirs(todays_folder, exist_ok=True)
            
            return todays_folder
            
        except Exception as e:
            self.logger.error(f"Error getting today's reports folder: {e}")
            # Fallback
            fallback_folder = os.path.join(config.DATA_FOLDER, 'reports')
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


    def auto_generate_pdf_on_completion(self, record_data):
        """
        NEW: Use trip_report_generator for PDF generation
        """
        try:
            # Check if record is complete
            if not trip_is_complete(record_data):
                self.logger.info("Record incomplete - skipping trip report generation")
                return False, None
            
            # Use new trip report generator
            success, pdf_path = auto_generate_on_completion(record_data)
            
            if success:
                self.logger.info(f"Auto-generated trip report: {pdf_path}")
                return True, pdf_path
            else:
                self.logger.warning("Failed to auto-generate trip report")
                return False, None
                
        except Exception as e:
            self.logger.error(f"Error in auto trip report generation: {e}")
            return False, None

    def auto_generate_pdf_for_complete_record(self, record_data):
        """Automatically generate PDF using trip_report_generator"""
        try:
            from trip_report_generator import auto_generate_on_completion, is_record_complete
            
            if is_record_complete(record_data):
                success, pdf_path = auto_generate_on_completion(record_data)
                if success:
                    self.logger.info(f" Auto-generated trip report: {pdf_path}")
                    return True, pdf_path
                else:
                    self.logger.warning(" Failed to generate trip report")
                    return False, None
            else:
                self.logger.info("Record incomplete - skipping trip report generation")
                return False, None
        except Exception as e:
            self.logger.error(f"Trip report generation error: {e}")
            return False, None



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
        """
        SIMPLIFIED: Load address configuration (trip_report_generator handles PDF usage)
        """
        try:
            config_file = os.path.join(config.DATA_FOLDER, 'address_config.json')
            if os.path.exists(config_file):
                with open(config_file, 'r') as f:
                    return json.load(f)
            else:
                # Return minimal default - trip_report_generator creates full defaults
                return {"agencies": {}, "sites": {}}
        except Exception as e:
            self.logger.error(f"Error loading address config: {e}")
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
            
            with safe_file_operation():
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

    def auto_generate_trip_report_on_completion(self, record_data):
        """
        Automatically generate trip report when a record is completed
        
        Args:
            record_data (dict): Record data dictionary
            
        Returns:
            tuple: (success: bool, pdf_path: str or None)
        """
        try:
            # Import here to avoid circular imports
            from trip_report_generator import auto_generate_on_completion
            
            # Check if record is complete before attempting generation
            if not self.is_record_complete(record_data):
                self.logger.info("Record incomplete - skipping auto trip report generation")
                return False, None
            
            # Generate trip report
            success, pdf_path = auto_generate_on_completion(record_data)
            
            if success:
                self.logger.info(f"Auto-generated trip report: {pdf_path}")
                return True, pdf_path
            else:
                self.logger.warning("Failed to auto-generate trip report")
                return False, None
                
        except Exception as e:
            self.logger.error(f"Error in auto trip report generation: {e}")
            return False, None


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
    

    def shutdown(self):
        """Graceful shutdown of DataManager"""
        try:
            self.is_shutting_down = True
            self.safe_logger.info("DataManager shutting down...")
            
            # Close any open file handles
            if hasattr(self, 'logger') and self.logger:
                for handler in self.logger.handlers:
                    try:
                        handler.close()
                    except:
                        pass
            
            self.safe_logger.info("DataManager shutdown completed")
        except Exception as e:
            print(f"Error during DataManager shutdown: {e}")
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