import os
import json
import datetime
import shutil
from google.cloud import storage
from google.api_core.exceptions import Forbidden, NotFound
import hashlib

class CloudStorageService:
    """Enhanced service for Google Cloud Storage operations with agency/site/date organization and auto-cleanup"""
    
    def __init__(self, bucket_name, credentials_path=None):
        """Initialize cloud storage service
        
        Args:
            bucket_name (str): Name of the Google Cloud Storage bucket
            credentials_path (str, optional): Path to the service account key file
        """
        try:
            # Set credentials path as environment variable if provided
            if credentials_path:
                os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = credentials_path
            
            # Initialize client
            self.client = storage.Client()
            
            # Get bucket - don't check if it exists to avoid permission issues
            self.bucket = self.client.bucket(bucket_name)
            
            # Test connection with a simple operation
            try:
                # Try to list blobs (limited to 1) to test permissions
                next(self.bucket.list_blobs(max_results=1), None)
                print(f"✅ Successfully connected to GCS bucket: {bucket_name}")
            except Forbidden as e:
                print(f"❌ Permission error: {e}")
                print(f"Make sure the service account has 'Storage Object Admin' role for bucket {bucket_name}")
                self.bucket = None
            except NotFound:
                # Bucket doesn't exist, try to create it
                try:
                    self.bucket = self.client.create_bucket(bucket_name)
                    print(f"✅ Created new bucket: {bucket_name}")
                except Exception as create_err:
                    print(f"❌ Cannot create bucket: {create_err}")
                    self.bucket = None
            
            # Initialize backup tracking file path
            self.backup_tracking_file = "data/backup_tracking.json"
            
        except Exception as e:
            print(f"❌ Error initializing cloud storage: {e}")
            self.client = None
            self.bucket = None

        try:
            import config
            self.default_agency = config.CURRENT_AGENCY or "Unknown_Agency"
            self.default_site = config.CURRENT_SITE or "Unknown_Site"
        except:
            self.default_agency = "Unknown_Agency"
            self.default_site = "Unknown_Site"
    
    def is_connected(self):
        """Check if connected to cloud storage"""
        return self.client is not None and self.bucket is not None
    
    def get_backup_tracking_data(self):
        """Get backup tracking data from local file
        
        Returns:
            dict: Tracking data with last backup timestamps and file hashes
        """
        try:
            if os.path.exists(self.backup_tracking_file):
                with open(self.backup_tracking_file, 'r') as f:
                    return json.load(f)
            else:
                return {
                    "last_backup_date": "",
                    "backed_up_files": {},
                    "daily_reports_backed_up": {},
                    "images_backed_up": {},
                    "json_backups_backed_up": {},
                    "last_cleanup_date": ""
                }
        except Exception as e:
            print(f"Error reading backup tracking: {e}")
            return {
                "last_backup_date": "",
                "backed_up_files": {},
                "daily_reports_backed_up": {},
                "images_backed_up": {},
                "json_backups_backed_up": {},
                "last_cleanup_date": ""
            }
    
    def save_backup_tracking_data(self, tracking_data):
        """Save backup tracking data to local file
        
        Args:
            tracking_data (dict): Tracking data to save
        """
        try:
            os.makedirs(os.path.dirname(self.backup_tracking_file), exist_ok=True)
            with open(self.backup_tracking_file, 'w') as f:
                json.dump(tracking_data, f, indent=4)
        except Exception as e:
            print(f"Error saving backup tracking: {e}")
    
    def get_file_hash(self, file_path):
        """Get MD5 hash of a file for change detection
        
        This is the core method that enables incremental backups.
        Files are only uploaded if their content has changed.
        
        Args:
            file_path (str): Path to file
            
        Returns:
            str: MD5 hash of file content, or empty string if error
        """
        try:
            import hashlib
            hash_md5 = hashlib.md5()
            
            # Read file in chunks to handle large files efficiently
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(8192), b""):  # 8KB chunks
                    hash_md5.update(chunk)
            
            return hash_md5.hexdigest()
        except Exception as e:
            print(f"⚠️  Error getting file hash for {file_path}: {e}")
            return ""
    
    def get_backup_statistics(self):
        """Get detailed statistics about backup tracking
        
        Returns:
            dict: Backup statistics including file counts and tracking info
        """
        try:
            tracking_data = self.get_backup_tracking_data()
            
            stats = {
                "total_tracked_files": 0,
                "images_tracked": len(tracking_data.get("images_backed_up", {})),
                "json_tracked": len(tracking_data.get("json_backups_backed_up", {})),
                "reports_tracked": len(tracking_data.get("daily_reports_backed_up", {})),
                "last_backup_date": tracking_data.get("last_backup_date", "Never"),
                "last_cleanup_date": tracking_data.get("last_cleanup_date", "Never"),
                "tracking_file_size": 0
            }
            
            stats["total_tracked_files"] = (stats["images_tracked"] + 
                                          stats["json_tracked"] + 
                                          stats["reports_tracked"])
            
            # Get tracking file size
            if os.path.exists(self.backup_tracking_file):
                stats["tracking_file_size"] = os.path.getsize(self.backup_tracking_file)
            
            return stats
            
        except Exception as e:
            return {"error": f"Error getting backup statistics: {str(e)}"}
    
    def reset_backup_tracking(self, confirm=False):
        """Reset backup tracking to force re-upload of all files
        
        Args:
            confirm (bool): Must be True to actually reset
            
        Returns:
            bool: True if reset, False if cancelled or error
        """
        if not confirm:
            print("⚠️  Use reset_backup_tracking(confirm=True) to actually reset tracking")
            return False
        
        try:
            # Clear tracking data
            empty_tracking = {
                "last_backup_date": "",
                "backed_up_files": {},
                "daily_reports_backed_up": {},
                "images_backed_up": {},
                "json_backups_backed_up": {},
                "last_cleanup_date": ""
            }
            
            self.save_backup_tracking_data(empty_tracking)
            print("🔄 Backup tracking reset - all files will be re-uploaded on next backup")
            return True
            
        except Exception as e:
            print(f"❌ Error resetting backup tracking: {e}")
            return False
    
    def get_cloud_path(self, agency_name, site_name, date_str, folder_type):
        """Generate cloud storage path with agency/site/date structure
        
        Args:
            agency_name (str): Agency name
            site_name (str): Site name  
            date_str (str): Date string (YYYY-MM-DD)
            folder_type (str): Type of folder (images, json_backups, reports)
            
        Returns:
            str: Cloud storage path
        """
        # Clean names for cloud storage (remove spaces and special characters)
        clean_agency = str(agency_name).replace(' ', '_').replace('/', '_').replace('\\', '_').replace(':', '_')
        clean_site = str(site_name).replace(' ', '_').replace('/', '_').replace('\\', '_').replace(':', '_')
        
        return f"{clean_agency}/{clean_site}/{date_str}/{folder_type}/"
    
    def backup_images_folder(self, agency_name, site_name, images_folder=None):
        """Backup images folder organized by agency/site/date
        
        Args:
            agency_name (str): Agency name
            site_name (str): Site name
            images_folder (str, optional): Path to images folder. If None, uses "data/images"
            
        Returns:
            tuple: (files_uploaded, total_files_found, errors)
        """
        # Fix: Use correct default path
        if images_folder is None:
            images_folder = "data/images"
        if not self.is_connected():
            return 0, 0, ["❌ Not connected to cloud storage"]
        
        try:
            if not os.path.exists(images_folder):
                print(f"⚠️  Images folder not found: {images_folder}")
                return 0, 0, [f"Images folder not found: {images_folder}"]
            
            today_str = datetime.datetime.now().strftime("%Y-%m-%d")
            cloud_base_path = self.get_cloud_path(agency_name, site_name, today_str, "images")
            
            tracking_data = self.get_backup_tracking_data()
            images_tracking = tracking_data.get("images_backed_up", {})
            
            files_uploaded = 0
            total_files_found = 0
            errors = []
            
            print(f"🖼️  Starting images backup to: {cloud_base_path}")
            
            # Get all image files
            image_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.tiff', '.tif'}
            
            # Walk through images folder
            for root, dirs, files in os.walk(images_folder):
                for file in files:
                    if not any(file.lower().endswith(ext) for ext in image_extensions):
                        continue
                        
                    total_files_found += 1
                    local_file_path = os.path.join(root, file)
                    
                    # Create relative path from images folder root
                    rel_path = os.path.relpath(local_file_path, images_folder)
                    cloud_filename = f"{cloud_base_path}{rel_path.replace(os.sep, '/')}"
                    
                    # Check if file needs backup using hash comparison
                    current_hash = self.get_file_hash(local_file_path)
                    
                    # Check tracking data to see if file was already uploaded
                    if (local_file_path in images_tracking and 
                        images_tracking[local_file_path].get("hash") == current_hash):
                        print(f"   ⏭️  Skipping unchanged: {rel_path} (already backed up)")
                        continue
                    
                    # File is new or changed - upload it
                    try:
                        blob = self.bucket.blob(cloud_filename)
                        
                        # Set appropriate content type
                        file_extension = os.path.splitext(local_file_path)[1].lower()
                        content_type_map = {
                            '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.png': 'image/png',
                            '.gif': 'image/gif', '.bmp': 'image/bmp', '.webp': 'image/webp',
                            '.tiff': 'image/tiff', '.tif': 'image/tiff'
                        }
                        content_type = content_type_map.get(file_extension, 'image/jpeg')
                        
                        blob.upload_from_filename(local_file_path, content_type=content_type)
                        
                        # Update tracking with new hash and metadata
                        images_tracking[local_file_path] = {
                            "hash": current_hash,
                            "upload_date": datetime.datetime.now().isoformat(),
                            "cloud_path": cloud_filename,
                            "file_size": os.path.getsize(local_file_path),
                            "agency": agency_name,
                            "site": site_name,
                            "date": today_str,
                            "last_modified": datetime.datetime.fromtimestamp(os.path.getmtime(local_file_path)).isoformat()
                        }
                        
                        files_uploaded += 1
                        print(f"   ✅ Uploaded: {rel_path}")
                        
                    except Exception as e:
                        error_msg = f"Error uploading {file}: {str(e)}"
                        errors.append(error_msg)
                        print(f"   ❌ {error_msg}")
            
            # Save tracking data
            tracking_data["images_backed_up"] = images_tracking
            tracking_data["last_backup_date"] = datetime.datetime.now().isoformat()
            self.save_backup_tracking_data(tracking_data)
            
            print(f"📊 Images backup completed: {files_uploaded}/{total_files_found} files uploaded")
            return files_uploaded, total_files_found, errors
            
        except Exception as e:
            error_msg = f"Error backing up images: {str(e)}"
            print(f"❌ {error_msg}")
            return 0, 0, [error_msg]
    
    def backup_json_backups_folder(self, agency_name, site_name, json_backups_folder=None):
        """Backup JSON backups folder organized by agency/site/date
        
        Args:
            agency_name (str): Agency name
            site_name (str): Site name
            json_backups_folder (str, optional): Path to json_backups folder. If None, uses "data/json_backups"
            
        Returns:
            tuple: (files_uploaded, total_files_found, errors)
        """
        # Fix: Use correct default path
        if json_backups_folder is None:
            json_backups_folder = "data/json_backups"
        if not self.is_connected():
            return 0, 0, ["❌ Not connected to cloud storage"]
        
        try:
            if not os.path.exists(json_backups_folder):
                print(f"⚠️  JSON backups folder not found: {json_backups_folder}")
                return 0, 0, [f"JSON backups folder not found: {json_backups_folder}"]
            
            today_str = datetime.datetime.now().strftime("%Y-%m-%d")
            cloud_base_path = self.get_cloud_path(agency_name, site_name, today_str, "json_backups")
            
            tracking_data = self.get_backup_tracking_data()
            json_tracking = tracking_data.get("json_backups_backed_up", {})
            
            files_uploaded = 0
            total_files_found = 0
            errors = []
            
            print(f"📄 Starting JSON backups backup to: {cloud_base_path}")
            
            # Walk through json_backups folder
            for root, dirs, files in os.walk(json_backups_folder):
                for file in files:
                    if not file.lower().endswith('.json'):
                        continue
                        
                    total_files_found += 1
                    local_file_path = os.path.join(root, file)
                    
                    # Create relative path from json_backups folder root
                    rel_path = os.path.relpath(local_file_path, json_backups_folder)
                    cloud_filename = f"{cloud_base_path}{rel_path.replace(os.sep, '/')}"
                    
                    # Check if file needs backup using hash comparison
                    current_hash = self.get_file_hash(local_file_path)
                    
                    # Check tracking data to see if file was already uploaded
                    if (local_file_path in json_tracking and 
                        json_tracking[local_file_path].get("hash") == current_hash):
                        print(f"   ⏭️  Skipping unchanged: {rel_path} (already backed up)")
                        continue
                    
                    # File is new or changed - upload it
                    try:
                        blob = self.bucket.blob(cloud_filename)
                        blob.upload_from_filename(local_file_path, content_type="application/json")
                        
                        # Update tracking with new hash and metadata
                        json_tracking[local_file_path] = {
                            "hash": current_hash,
                            "upload_date": datetime.datetime.now().isoformat(),
                            "cloud_path": cloud_filename,
                            "file_size": os.path.getsize(local_file_path),
                            "agency": agency_name,
                            "site": site_name,
                            "date": today_str,
                            "last_modified": datetime.datetime.fromtimestamp(os.path.getmtime(local_file_path)).isoformat()
                        }
                        
                        files_uploaded += 1
                        print(f"   ✅ Uploaded: {rel_path}")
                        
                    except Exception as e:
                        error_msg = f"Error uploading {file}: {str(e)}"
                        errors.append(error_msg)
                        print(f"   ❌ {error_msg}")
            
            # Save tracking data
            tracking_data["json_backups_backed_up"] = json_tracking
            tracking_data["last_backup_date"] = datetime.datetime.now().isoformat()
            self.save_backup_tracking_data(tracking_data)
            
            print(f"📊 JSON backups completed: {files_uploaded}/{total_files_found} files uploaded")
            return files_uploaded, total_files_found, errors
            
        except Exception as e:
            error_msg = f"Error backing up JSON backups: {str(e)}"
            print(f"❌ {error_msg}")
            return 0, 0, [error_msg]
    
    def backup_reports_folder(self, agency_name, site_name, reports_folder=None):
        """Backup reports folder organized by agency/site/date
        
        Args:
            agency_name (str): Agency name
            site_name (str): Site name
            reports_folder (str, optional): Path to reports folder. If None, uses "data/reports"
            
        Returns:
            tuple: (files_uploaded, total_files_found, errors)
        """
        # Fix: Use correct default path
        if reports_folder is None:
            reports_folder = "data/reports"
        if not self.is_connected():
            return 0, 0, ["❌ Not connected to cloud storage"]
        
        try:
            if not os.path.exists(reports_folder):
                print(f"⚠️  Reports folder not found: {reports_folder}")
                return 0, 0, [f"Reports folder not found: {reports_folder}"]
            
            today_str = datetime.datetime.now().strftime("%Y-%m-%d")
            cloud_base_path = self.get_cloud_path(agency_name, site_name, today_str, "reports")
            
            tracking_data = self.get_backup_tracking_data()
            reports_tracking = tracking_data.get("daily_reports_backed_up", {})
            
            files_uploaded = 0
            total_files_found = 0
            errors = []
            
            print(f"📊 Starting reports backup to: {cloud_base_path}")
            
            # Walk through reports folder
            for root, dirs, files in os.walk(reports_folder):
                for file in files:
                    total_files_found += 1
                    local_file_path = os.path.join(root, file)
                    
                    # Get relative path from reports folder
                    rel_path = os.path.relpath(local_file_path, reports_folder)
                    cloud_filename = f"{cloud_base_path}{rel_path.replace(os.sep, '/')}"
                    
                    # Check if file needs backup using hash comparison
                    current_hash = self.get_file_hash(local_file_path)
                    
                    # Check tracking data to see if file was already uploaded
                    if (local_file_path in reports_tracking and 
                        reports_tracking[local_file_path].get("hash") == current_hash):
                        print(f"   ⏭️  Skipping unchanged: {rel_path} (already backed up)")
                        continue
                    
                    # File is new or changed - upload it
                    try:
                        blob = self.bucket.blob(cloud_filename)
                        
                        # Set appropriate content type based on file extension
                        file_extension = os.path.splitext(local_file_path)[1].lower()
                        content_type_map = {
                            '.pdf': 'application/pdf', 
                            '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg',
                            '.png': 'image/png', 
                            '.json': 'application/json', 
                            '.txt': 'text/plain',
                            '.csv': 'text/csv', 
                            '.html': 'text/html',
                            '.xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                            '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
                        }
                        content_type = content_type_map.get(file_extension, 'application/octet-stream')
                        
                        blob.upload_from_filename(local_file_path, content_type=content_type)
                        
                        # Update tracking with new hash and metadata
                        reports_tracking[local_file_path] = {
                            "hash": current_hash,
                            "upload_date": datetime.datetime.now().isoformat(),
                            "cloud_path": cloud_filename,
                            "file_size": os.path.getsize(local_file_path),
                            "agency": agency_name,
                            "site": site_name,
                            "date": today_str,
                            "last_modified": datetime.datetime.fromtimestamp(os.path.getmtime(local_file_path)).isoformat()
                        }
                        
                        files_uploaded += 1
                        print(f"   ✅ Uploaded: {rel_path}")
                        
                    except Exception as e:
                        error_msg = f"Error uploading {file}: {str(e)}"
                        errors.append(error_msg)
                        print(f"   ❌ {error_msg}")
            
            # Save tracking data
            tracking_data["daily_reports_backed_up"] = reports_tracking
            tracking_data["last_backup_date"] = datetime.datetime.now().isoformat()
            self.save_backup_tracking_data(tracking_data)
            
            print(f"📊 Reports backup completed: {files_uploaded}/{total_files_found} files uploaded")
            return files_uploaded, total_files_found, errors
            
        except Exception as e:
            error_msg = f"Error backing up reports: {str(e)}"
            print(f"❌ {error_msg}")
            return 0, 0, [error_msg]
    
    def comprehensive_backup(self, agency_name, site_name, data_folder="data"):
        """🎯 MAIN BACKUP METHOD: Perform comprehensive backup of all data folders organized by agency/site/date
        
        This is the method you should call when clicking "Backup" or "Full Backup"
        It will upload all folders to: Agency/Site/YYYY-MM-DD/folder_type/
        
        Args:
            agency_name (str): Agency name (e.g., "Tharuni") 
                             OR complete_records list (for backward compatibility)
            site_name (str): Site name (e.g., "Guntur")
                           OR images_folder path (for backward compatibility)  
            data_folder (str): Base data folder path (default: "data")
                             OR reports_folder path (for backward compatibility)
            
        Returns:
            dict: Comprehensive backup results with detailed statistics
        """
        # Handle backward compatibility with old method signature
        if isinstance(agency_name, list):
            # Old signature: comprehensive_backup(complete_records, images_folder, reports_folder)
            print("⚠️  Using legacy comprehensive_backup signature - please update your code")
            print("   New signature: comprehensive_backup(agency_name, site_name, data_folder)")
            
            # Get agency and site from config
            try:
                import config
                agency_name_real = config.CURRENT_AGENCY or "Unknown_Agency"
                site_name_real = config.CURRENT_SITE or "Unknown_Site"
            except:
                agency_name_real = "Unknown_Agency"
                site_name_real = "Unknown_Site"
            
            # Call the new method with correct parameters
            return self._comprehensive_backup_new(agency_name_real, site_name_real, "data")
        
        # New signature: comprehensive_backup(agency_name, site_name, data_folder)
        return self._comprehensive_backup_new(agency_name, site_name, data_folder)
    
    def _comprehensive_backup_new(self, agency_name, site_name, data_folder="data"):
        """Internal method with the new comprehensive backup logic"""

        if not self.is_connected():
            return {
                "success": False,
                "error": "❌ Not connected to cloud storage",
                "images": {"uploaded": 0, "total": 0},
                "json_backups": {"uploaded": 0, "total": 0},
                "reports": {"uploaded": 0, "total": 0}
            }
        
        start_time = datetime.datetime.now()
        today_str = start_time.strftime("%Y-%m-%d")
        
        # FIX: Force use the correct data folder from config
        try:
            import config
            data_folder = config.DATA_FOLDER  # Always use "data" from config
        except:
            data_folder = "data"  # Fallback
        
        print(f"\n🚀 Starting comprehensive backup for {agency_name} - {site_name}")
        print(f"📅 Date: {today_str}")
        print(f"📁 Data folder: {data_folder}")
        print(f"☁️  Cloud structure: {agency_name}/{site_name}/{today_str}/[images|json_backups|reports]/")
        print("=" * 80)
        
        results = {
            "success": True,
            "agency": agency_name,
            "site": site_name,
            "date": today_str,
            "start_time": start_time.isoformat(),
            "images": {"uploaded": 0, "total": 0, "errors": []},
            "json_backups": {"uploaded": 0, "total": 0, "errors": []},
            "reports": {"uploaded": 0, "total": 0, "errors": []},
            "total_files_uploaded": 0,
            "total_files_found": 0,
            "all_errors": [],
            "cloud_structure": {
                "images": f"{agency_name}/{site_name}/{today_str}/images/",
                "json_backups": f"{agency_name}/{site_name}/{today_str}/json_backups/",
                "reports": f"{agency_name}/{site_name}/{today_str}/reports/"
            }
        }
        
        # 1. Backup images folder - FORCE correct path
        print(f"\n1️⃣  IMAGES BACKUP")
        try:
            # FIX: Use config constants directly
            try:
                import config
                images_folder = config.IMAGES_FOLDER  # Should be "data/images"
            except:
                images_folder = os.path.join(data_folder, "images")
            
            print(f"🔍 Looking for images in: {os.path.abspath(images_folder)}")
            uploaded, total, errors = self.backup_images_folder(agency_name, site_name, images_folder)
            results["images"]["uploaded"] = uploaded
            results["images"]["total"] = total
            results["images"]["errors"] = errors
            results["all_errors"].extend(errors)
            print(f"   📊 Images: {uploaded}/{total} files uploaded")
        except Exception as e:
            error_msg = f"Images backup error: {str(e)}"
            results["images"]["errors"].append(error_msg)
            results["all_errors"].append(error_msg)
            print(f"   ❌ Images backup failed: {error_msg}")
        
        # 2. Backup JSON backups folder - FORCE correct path
        print(f"\n2️⃣  JSON BACKUPS")
        try:
            # FIX: Use config constants directly
            try:
                import config
                json_folder = config.JSON_BACKUPS_FOLDER  # Should be "data/json_backups"
            except:
                json_folder = os.path.join(data_folder, "json_backups")
            
            print(f"🔍 Looking for JSON backups in: {os.path.abspath(json_folder)}")
            uploaded, total, errors = self.backup_json_backups_folder(agency_name, site_name, json_folder)
            results["json_backups"]["uploaded"] = uploaded
            results["json_backups"]["total"] = total
            results["json_backups"]["errors"] = errors
            results["all_errors"].extend(errors)
            print(f"   📊 JSON backups: {uploaded}/{total} files uploaded")
        except Exception as e:
            error_msg = f"JSON backups backup error: {str(e)}"
            results["json_backups"]["errors"].append(error_msg)
            results["all_errors"].append(error_msg)
            print(f"   ❌ JSON backups failed: {error_msg}")
        
        # 3. Backup reports folder - FORCE correct path
        print(f"\n3️⃣  REPORTS BACKUP")
        try:
            # FIX: Use config constants directly
            try:
                import config
                base_reports_folder = config.REPORTS_FOLDER
                todays_reports_folder = os.path.join(base_reports_folder, today_str)  
                reports_folder = todays_reports_folder
            except:
                reports_folder = os.path.join(data_folder, "reports")
            
            print(f"🔍 Looking for reports in: {os.path.abspath(reports_folder)}")
            uploaded, total, errors = self.backup_reports_folder(agency_name, site_name, reports_folder)
            results["reports"]["uploaded"] = uploaded
            results["reports"]["total"] = total
            results["reports"]["errors"] = errors
            results["all_errors"].extend(errors)
            print(f"   📊 Reports: {uploaded}/{total} files uploaded")
        except Exception as e:
            error_msg = f"Reports backup error: {str(e)}"
            results["reports"]["errors"].append(error_msg)
            results["all_errors"].append(error_msg)
            print(f"   ❌ Reports backup failed: {error_msg}")
        
        # Calculate totals and completion time
        results["total_files_uploaded"] = (results["images"]["uploaded"] + 
                                         results["json_backups"]["uploaded"] + 
                                         results["reports"]["uploaded"])
        results["total_files_found"] = (results["images"]["total"] + 
                                      results["json_backups"]["total"] + 
                                      results["reports"]["total"])
        
        end_time = datetime.datetime.now()
        duration = end_time - start_time
        results["end_time"] = end_time.isoformat()
        results["duration_seconds"] = duration.total_seconds()
        
        # Determine overall success
        results["success"] = len(results["all_errors"]) == 0
        
        # Print final summary
        print("\n" + "=" * 80)
        print(f"🎯 BACKUP COMPLETED for {agency_name} - {site_name}")
        print(f"⏱️  Duration: {duration.total_seconds():.1f} seconds")
        print(f"📊 Total files: {results['total_files_uploaded']}/{results['total_files_found']} uploaded")
        print(f"🖼️  Images: {results['images']['uploaded']}/{results['images']['total']}")
        print(f"📄 JSON: {results['json_backups']['uploaded']}/{results['json_backups']['total']}")
        print(f"📊 Reports: {results['reports']['uploaded']}/{results['reports']['total']}")
        
        if results["success"]:
            print(f"✅ SUCCESS! All files backed up to cloud")
        else:
            print(f"⚠️  PARTIAL SUCCESS - {len(results['all_errors'])} errors occurred")
            for error in results["all_errors"][:3]:  # Show first 3 errors
                print(f"   • {error}")
            if len(results["all_errors"]) > 3:
                print(f"   • ... and {len(results['all_errors']) - 3} more errors")
        
        print(f"☁️  Cloud location: gs://{self.bucket.name}/")
        for folder_type, cloud_path in results["cloud_structure"].items():
            print(f"   📁 {folder_type}: {cloud_path}")
        print("=" * 80)
        
        return results
    
    # NEW: TODAY-ONLY BACKUP METHODS
    def backup_today_only(self, agency_name, site_name, data_folder="data"):
        """🎯 BACKUP TODAY'S FILES ONLY - Modified comprehensive backup for current day only
        
        This method backs up ONLY today's files when "Full Backup Today" is clicked.
        It will upload only current day files to: Agency/Site/YYYY-MM-DD/folder_type/
        
        Args:
            agency_name (str): Agency name
            site_name (str): Site name
            data_folder (str): Base data folder path (default: "data")
            
        Returns:
            dict: Backup results with detailed statistics for today's files only
        """
        if not self.is_connected():
            return {
                "success": False,
                "error": "❌ Not connected to cloud storage",
                "images": {"uploaded": 0, "total": 0},
                "json_backups": {"uploaded": 0, "total": 0},
                "reports": {"uploaded": 0, "total": 0}
            }
        
        start_time = datetime.datetime.now()
        today_str = start_time.strftime("%Y-%m-%d")
        
        # Force use the correct data folder from config
        try:
            import config
            data_folder = config.DATA_FOLDER  # Always use "data" from config
        except:
            data_folder = "data"  # Fallback
        
        print(f"\n🚀 Starting TODAY ONLY backup for {agency_name} - {site_name}")
        print(f"📅 Date: {today_str}")
        print(f"📁 Data folder: {data_folder}")
        print(f"⚠️  BACKING UP TODAY'S FILES ONLY - OTHER DAYS WILL BE IGNORED")
        print(f"☁️  Cloud structure: {agency_name}/{site_name}/{today_str}/[images|json_backups|reports]/")
        print("=" * 80)
        
        results = {
            "success": True,
            "agency": agency_name,
            "site": site_name,
            "date": today_str,
            "start_time": start_time.isoformat(),
            "images": {"uploaded": 0, "total": 0, "errors": []},
            "json_backups": {"uploaded": 0, "total": 0, "errors": []},
            "reports": {"uploaded": 0, "total": 0, "errors": []},
            "total_files_uploaded": 0,
            "total_files_found": 0,
            "all_errors": [],
            "cloud_structure": {
                "images": f"{agency_name}/{site_name}/{today_str}/images/",
                "json_backups": f"{agency_name}/{site_name}/{today_str}/json_backups/",
                "reports": f"{agency_name}/{site_name}/{today_str}/reports/"
            }
        }
        
        # 1. Backup today's images only
        print(f"\n1️⃣  TODAY'S IMAGES BACKUP")
        try:
            # Get today's images folder
            try:
                import config
                base_images_folder = config.IMAGES_FOLDER if hasattr(config, 'IMAGES_FOLDER') else os.path.join(data_folder, "images")
                todays_images_folder = os.path.join(base_images_folder, today_str)
            except:
                todays_images_folder = os.path.join(data_folder, "images", today_str)
            
            print(f"🔍 Looking for today's images in: {os.path.abspath(todays_images_folder)}")
            
            if os.path.exists(todays_images_folder):
                uploaded, total, errors = self.backup_images_folder_today_only(agency_name, site_name, todays_images_folder)
                results["images"]["uploaded"] = uploaded
                results["images"]["total"] = total
                results["images"]["errors"] = errors
                results["all_errors"].extend(errors)
                print(f"   📊 Today's Images: {uploaded}/{total} files uploaded")
            else:
                print(f"   ⚠️ Today's images folder not found: {todays_images_folder}")
                print(f"   📊 Today's Images: 0/0 files uploaded")
        except Exception as e:
            error_msg = f"Today's images backup error: {str(e)}"
            results["images"]["errors"].append(error_msg)
            results["all_errors"].append(error_msg)
            print(f"   ❌ Today's images backup failed: {error_msg}")
        
        # 2. Backup today's JSON backups only
        print(f"\n2️⃣  TODAY'S JSON BACKUPS")
        try:
            # Get today's JSON backups folder
            try:
                import config
                base_json_folder = config.JSON_BACKUPS_FOLDER if hasattr(config, 'JSON_BACKUPS_FOLDER') else os.path.join(data_folder, "json_backups")
                todays_json_folder = os.path.join(base_json_folder, today_str)
            except:
                todays_json_folder = os.path.join(data_folder, "json_backups", today_str)
            
            print(f"🔍 Looking for today's JSON backups in: {os.path.abspath(todays_json_folder)}")
            
            if os.path.exists(todays_json_folder):
                uploaded, total, errors = self.backup_json_backups_folder_today_only(agency_name, site_name, todays_json_folder)
                results["json_backups"]["uploaded"] = uploaded
                results["json_backups"]["total"] = total
                results["json_backups"]["errors"] = errors
                results["all_errors"].extend(errors)
                print(f"   📊 Today's JSON: {uploaded}/{total} files uploaded")
            else:
                print(f"   ⚠️ Today's JSON backups folder not found: {todays_json_folder}")
                print(f"   📊 Today's JSON: 0/0 files uploaded")
        except Exception as e:
            error_msg = f"Today's JSON backups error: {str(e)}"
            results["json_backups"]["errors"].append(error_msg)
            results["all_errors"].append(error_msg)
            print(f"   ❌ Today's JSON backups failed: {error_msg}")
        
        # 3. Backup today's reports only - MOST IMPORTANT
        print(f"\n3️⃣  TODAY'S REPORTS BACKUP")
        try:
            # Get today's reports folder
            try:
                import config
                base_reports_folder = config.REPORTS_FOLDER
                todays_reports_folder = os.path.join(base_reports_folder, today_str)
            except:
                todays_reports_folder = os.path.join(data_folder, "reports", today_str)
            
            print(f"🔍 Looking for today's reports in: {os.path.abspath(todays_reports_folder)}")
            
            if os.path.exists(todays_reports_folder):
                uploaded, total, errors = self.backup_reports_folder_today_only(agency_name, site_name, todays_reports_folder)
                results["reports"]["uploaded"] = uploaded
                results["reports"]["total"] = total
                results["reports"]["errors"] = errors
                results["all_errors"].extend(errors)
                print(f"   📊 Today's Reports: {uploaded}/{total} files uploaded")
            else:
                print(f"   ⚠️ Today's reports folder not found: {todays_reports_folder}")
                print(f"   📊 Today's Reports: 0/0 files uploaded")
        except Exception as e:
            error_msg = f"Today's reports backup error: {str(e)}"
            results["reports"]["errors"].append(error_msg)
            results["all_errors"].append(error_msg)
            print(f"   ❌ Today's reports backup failed: {error_msg}")
        
        # Calculate totals and completion time
        results["total_files_uploaded"] = (results["images"]["uploaded"] + 
                                         results["json_backups"]["uploaded"] + 
                                         results["reports"]["uploaded"])
        results["total_files_found"] = (results["images"]["total"] + 
                                      results["json_backups"]["total"] + 
                                      results["reports"]["total"])
        
        end_time = datetime.datetime.now()
        duration = end_time - start_time
        results["end_time"] = end_time.isoformat()
        results["duration_seconds"] = duration.total_seconds()
        
        # Determine overall success
        results["success"] = len(results["all_errors"]) == 0
        
        # Print final summary
        print("\n" + "=" * 80)
        print(f"🎯 TODAY ONLY BACKUP COMPLETED for {agency_name} - {site_name}")
        print(f"📅 Date: {today_str}")
        print(f"⏱️  Duration: {duration.total_seconds():.1f} seconds")
        print(f"📊 Total files: {results['total_files_uploaded']}/{results['total_files_found']} uploaded")
        print(f"🖼️  Images: {results['images']['uploaded']}/{results['images']['total']}")
        print(f"📄 JSON: {results['json_backups']['uploaded']}/{results['json_backups']['total']}")
        print(f"📊 Reports: {results['reports']['uploaded']}/{results['reports']['total']}")
        
        if results["success"]:
            print(f"✅ SUCCESS! All today's files backed up successfully")
        else:
            print(f"⚠️  PARTIAL SUCCESS - {len(results['all_errors'])} errors occurred")
            for error in results["all_errors"][:3]:  # Show first 3 errors
                print(f"   ❌ {error}")
            if len(results["all_errors"]) > 3:
                print(f"   ... and {len(results['all_errors']) - 3} more errors")
        
        print("=" * 80)
        return results

    def backup_reports_folder_today_only(self, agency_name, site_name, todays_reports_folder):
        """Backup ONLY today's reports folder - NO recursion to other days
        
        Args:
            agency_name (str): Agency name
            site_name (str): Site name
            todays_reports_folder (str): Path to today's reports folder (e.g., data/reports/2024-05-29)
            
        Returns:
            tuple: (files_uploaded, total_files_found, errors)
        """
        if not self.is_connected():
            return 0, 0, ["❌ Not connected to cloud storage"]
        
        try:
            if not os.path.exists(todays_reports_folder):
                print(f"⚠️  Today's reports folder not found: {todays_reports_folder}")
                return 0, 0, [f"Today's reports folder not found: {todays_reports_folder}"]
            
            today_str = datetime.datetime.now().strftime("%Y-%m-%d")
            cloud_base_path = self.get_cloud_path(agency_name, site_name, today_str, "reports")
            
            tracking_data = self.get_backup_tracking_data()
            reports_tracking = tracking_data.get("daily_reports_backed_up", {})
            
            files_uploaded = 0
            total_files_found = 0
            errors = []
            
            print(f"📊 Starting today's reports backup to: {cloud_base_path}")
            print(f"📁 Source folder: {todays_reports_folder}")
            
            # ONLY scan files in today's folder - NO RECURSION
            try:
                files_in_today = os.listdir(todays_reports_folder)
                print(f"📋 Found {len(files_in_today)} items in today's folder")
                
                for file in files_in_today:
                    file_path = os.path.join(todays_reports_folder, file)
                    
                    # Skip if it's a directory (we only want files)
                    if os.path.isdir(file_path):
                        print(f"⏭️  Skipping directory: {file}")
                        continue
                    
                    # Only process files
                    if os.path.isfile(file_path):
                        total_files_found += 1
                        
                        # Cloud filename (just the filename, no subfolders)
                        cloud_filename = f"{cloud_base_path}{file}"
                        
                        # Check if file needs backup using hash comparison
                        current_hash = self.get_file_hash(file_path)
                        
                        # Check tracking data to avoid duplicates
                        if (file_path in reports_tracking and 
                            reports_tracking[file_path].get("hash") == current_hash):
                            print(f"⏭️  Skipping duplicate: {file}")
                            continue
                        
                        try:
                            # Upload file to cloud
                            blob = self.bucket.blob(cloud_filename)
                            
                            # Set appropriate content type based on file extension
                            file_extension = os.path.splitext(file_path)[1].lower()
                            content_type_map = {
                                '.pdf': 'application/pdf', 
                                '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg',
                                '.png': 'image/png', 
                                '.json': 'application/json', 
                                '.txt': 'text/plain',
                                '.csv': 'text/csv', 
                                '.html': 'text/html',
                                '.xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                                '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
                            }
                            content_type = content_type_map.get(file_extension, 'application/octet-stream')
                            
                            blob.upload_from_filename(file_path, content_type=content_type)
                            
                            # Update tracking data
                            reports_tracking[file_path] = {
                                "hash": current_hash,
                                "upload_date": datetime.datetime.now().isoformat(),
                                "cloud_path": cloud_filename,
                                "file_size": os.path.getsize(file_path),
                                "agency": agency_name,
                                "site": site_name,
                                "date": today_str,
                                "last_modified": datetime.datetime.fromtimestamp(os.path.getmtime(file_path)).isoformat()
                            }
                            
                            files_uploaded += 1
                            print(f"   ✅ Uploaded: {file}")
                            
                        except Exception as e:
                            error_msg = f"Error uploading {file}: {str(e)}"
                            errors.append(error_msg)
                            print(f"   ❌ {error_msg}")
                            
            except Exception as e:
                error_msg = f"Error reading today's reports folder: {str(e)}"
                errors.append(error_msg)
                print(f"❌ {error_msg}")
            
            # Save tracking data
            tracking_data["daily_reports_backed_up"] = reports_tracking
            tracking_data["last_backup_date"] = datetime.datetime.now().isoformat()
            self.save_backup_tracking_data(tracking_data)
            
            print(f"📊 Today's reports backup completed: {files_uploaded}/{total_files_found} files uploaded")
            return files_uploaded, total_files_found, errors
            
        except Exception as e:
            error_msg = f"Error backing up today's reports: {str(e)}"
            print(f"❌ {error_msg}")
            return 0, 0, [error_msg]

    def backup_images_folder_today_only(self, agency_name, site_name, todays_images_folder):
        """Backup ONLY today's images folder - NO recursion to other days
        
        Args:
            agency_name (str): Agency name
            site_name (str): Site name
            todays_images_folder (str): Path to today's images folder
            
        Returns:
            tuple: (files_uploaded, total_files_found, errors)
        """
        if not self.is_connected():
            return 0, 0, ["❌ Not connected to cloud storage"]
        
        try:
            if not os.path.exists(todays_images_folder):
                print(f"⚠️  Today's images folder not found: {todays_images_folder}")
                return 0, 0, [f"Today's images folder not found: {todays_images_folder}"]
            
            today_str = datetime.datetime.now().strftime("%Y-%m-%d")
            cloud_base_path = self.get_cloud_path(agency_name, site_name, today_str, "images")
            
            tracking_data = self.get_backup_tracking_data()
            images_tracking = tracking_data.get("images_backed_up", {})
            
            files_uploaded = 0
            total_files_found = 0
            errors = []
            
            print(f"🖼️  Starting today's images backup to: {cloud_base_path}")
            
            # Get all image files from today's folder only
            image_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.tiff', '.tif'}
            
            try:
                files_in_today = os.listdir(todays_images_folder)
                
                for file in files_in_today:
                    if not any(file.lower().endswith(ext) for ext in image_extensions):
                        continue
                        
                    file_path = os.path.join(todays_images_folder, file)
                    
                    if os.path.isfile(file_path):
                        total_files_found += 1
                        
                        cloud_filename = f"{cloud_base_path}{file}"
                        
                        # Check if file needs backup using hash comparison
                        current_hash = self.get_file_hash(file_path)
                        
                        if (file_path in images_tracking and 
                            images_tracking[file_path].get("hash") == current_hash):
                            print(f"⏭️  Skipping duplicate image: {file}")
                            continue
                        
                        try:
                            # Upload image to cloud
                            blob = self.bucket.blob(cloud_filename)
                            
                            # Set appropriate content type
                            file_extension = os.path.splitext(file_path)[1].lower()
                            content_type_map = {
                                '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.png': 'image/png',
                                '.gif': 'image/gif', '.bmp': 'image/bmp', '.webp': 'image/webp',
                                '.tiff': 'image/tiff', '.tif': 'image/tiff'
                            }
                            content_type = content_type_map.get(file_extension, 'image/jpeg')
                            
                            blob.upload_from_filename(file_path, content_type=content_type)
                            
                            # Update tracking data
                            images_tracking[file_path] = {
                                "hash": current_hash,
                                "upload_date": datetime.datetime.now().isoformat(),
                                "cloud_path": cloud_filename,
                                "file_size": os.path.getsize(file_path),
                                "agency": agency_name,
                                "site": site_name,
                                "date": today_str,
                                "last_modified": datetime.datetime.fromtimestamp(os.path.getmtime(file_path)).isoformat()
                            }
                            
                            files_uploaded += 1
                            print(f"   ✅ Uploaded: {file}")
                            
                        except Exception as e:
                            error_msg = f"Error uploading {file}: {str(e)}"
                            errors.append(error_msg)
                            print(f"   ❌ {error_msg}")
                            
            except Exception as e:
                error_msg = f"Error reading today's images folder: {str(e)}"
                errors.append(error_msg)
                print(f"❌ {error_msg}")
            
            # Save tracking data
            tracking_data["images_backed_up"] = images_tracking
            tracking_data["last_backup_date"] = datetime.datetime.now().isoformat()
            self.save_backup_tracking_data(tracking_data)
            
            print(f"📊 Today's images backup completed: {files_uploaded}/{total_files_found} files uploaded")
            return files_uploaded, total_files_found, errors
            
        except Exception as e:
            error_msg = f"Error backing up today's images: {str(e)}"
            print(f"❌ {error_msg}")
            return 0, 0, [error_msg]

    def backup_json_backups_folder_today_only(self, agency_name, site_name, todays_json_folder):
        """Backup ONLY today's JSON backups folder - NO recursion to other days
        
        Args:
            agency_name (str): Agency name
            site_name (str): Site name
            todays_json_folder (str): Path to today's JSON backups folder
            
        Returns:
            tuple: (files_uploaded, total_files_found, errors)
        """
        if not self.is_connected():
            return 0, 0, ["❌ Not connected to cloud storage"]
        
        try:
            if not os.path.exists(todays_json_folder):
                print(f"⚠️  Today's JSON backups folder not found: {todays_json_folder}")
                return 0, 0, [f"Today's JSON backups folder not found: {todays_json_folder}"]
            
            today_str = datetime.datetime.now().strftime("%Y-%m-%d")
            cloud_base_path = self.get_cloud_path(agency_name, site_name, today_str, "json_backups")
            
            tracking_data = self.get_backup_tracking_data()
            json_tracking = tracking_data.get("json_backups_backed_up", {})
            
            files_uploaded = 0
            total_files_found = 0
            errors = []
            
            print(f"📄 Starting today's JSON backups backup to: {cloud_base_path}")
            
            try:
                files_in_today = os.listdir(todays_json_folder)
                
                for file in files_in_today:
                    if not file.lower().endswith('.json'):
                        continue
                        
                    file_path = os.path.join(todays_json_folder, file)
                    
                    if os.path.isfile(file_path):
                        total_files_found += 1
                        
                        cloud_filename = f"{cloud_base_path}{file}"
                        
                        # Check if file needs backup using hash comparison
                        current_hash = self.get_file_hash(file_path)
                        
                        if (file_path in json_tracking and 
                            json_tracking[file_path].get("hash") == current_hash):
                            print(f"⏭️  Skipping duplicate JSON: {file}")
                            continue
                        
                        try:
                            # Upload JSON to cloud
                            blob = self.bucket.blob(cloud_filename)
                            blob.upload_from_filename(file_path, content_type="application/json")
                            
                            # Update tracking data
                            json_tracking[file_path] = {
                                "hash": current_hash,
                                "upload_date": datetime.datetime.now().isoformat(),
                                "cloud_path": cloud_filename,
                                "file_size": os.path.getsize(file_path),
                                "agency": agency_name,
                                "site": site_name,
                                "date": today_str,
                                "last_modified": datetime.datetime.fromtimestamp(os.path.getmtime(file_path)).isoformat()
                            }
                            
                            files_uploaded += 1
                            print(f"   ✅ Uploaded: {file}")
                            
                        except Exception as e:
                            error_msg = f"Error uploading {file}: {str(e)}"
                            errors.append(error_msg)
                            print(f"   ❌ {error_msg}")
                            
            except Exception as e:
                error_msg = f"Error reading today's JSON backups folder: {str(e)}"
                errors.append(error_msg)
                print(f"❌ {error_msg}")
            
            # Save tracking data
            tracking_data["json_backups_backed_up"] = json_tracking
            tracking_data["last_backup_date"] = datetime.datetime.now().isoformat()
            self.save_backup_tracking_data(tracking_data)
            
            print(f"📊 Today's JSON backups completed: {files_uploaded}/{total_files_found} files uploaded")
            return files_uploaded, total_files_found, errors
            
        except Exception as e:
            error_msg = f"Error backing up today's JSON backups: {str(e)}"
            print(f"❌ {error_msg}")
            return 0, 0, [error_msg]
    
    # END OF TODAY-ONLY BACKUP METHODS
    
    def quick_backup_single_folder(self, agency_name, site_name, folder_type, data_folder="data"):
        """Quick backup of a single folder type
        
        Args:
            agency_name (str): Agency name
            site_name (str): Site name  
            folder_type (str): One of: "images", "json_backups", "reports"
            data_folder (str): Base data folder path
            
        Returns:
            tuple: (files_uploaded, total_files_found, errors)
        """
        # Fix: Use correct folder paths
        if folder_type == "images":
            folder_path = os.path.join(data_folder, "images")
            if not os.path.isabs(folder_path):
                folder_path = os.path.abspath(folder_path)
            return self.backup_images_folder(agency_name, site_name, folder_path)
        elif folder_type == "json_backups":
            folder_path = os.path.join(data_folder, "json_backups")
            if not os.path.isabs(folder_path):
                folder_path = os.path.abspath(folder_path)
            return self.backup_json_backups_folder(agency_name, site_name, folder_path)
        elif folder_type == "reports":
            folder_path = os.path.join(data_folder, "reports")
            if not os.path.isabs(folder_path):
                folder_path = os.path.abspath(folder_path)
            return self.backup_reports_folder(agency_name, site_name, folder_path)
        else:
            return 0, 0, [f"Unknown folder type: {folder_type}"]
    
    # Keep all existing methods for compatibility...
    def cleanup_old_local_files(self, data_folder="data", days_to_keep=10):
        """Clean up local data folders older than specified days
        
        Args:
            data_folder (str): Base data folder path
            days_to_keep (int): Number of days to keep files (default: 10)
            
        Returns:
            dict: Cleanup results
        """
        try:
            cutoff_date = datetime.datetime.now() - datetime.timedelta(days=days_to_keep)
            
            results = {
                "success": True,
                "cutoff_date": cutoff_date.strftime("%Y-%m-%d"),
                "folders_cleaned": [],
                "files_deleted": 0,
                "errors": []
            }
            
            folders_to_clean = ["images", "json_backups", "reports"]
            
            for folder_name in folders_to_clean:
                folder_path = os.path.join(data_folder, folder_name)
                
                if not os.path.exists(folder_path):
                    continue
                
                print(f"🧹 Cleaning {folder_name} folder older than {days_to_keep} days...")
                
                try:
                    if folder_name == "reports":
                        # Reports folder has date subfolders (YYYY-MM-DD)
                        for item in os.listdir(folder_path):
                            item_path = os.path.join(folder_path, item)
                            
                            if os.path.isdir(item_path):
                                try:
                                    # Check if folder name matches YYYY-MM-DD format
                                    folder_date = datetime.datetime.strptime(item, "%Y-%m-%d")
                                    
                                    if folder_date < cutoff_date:
                                        # Count files before deletion
                                        file_count = sum([len(files) for r, d, files in os.walk(item_path)])
                                        
                                        shutil.rmtree(item_path)
                                        results["files_deleted"] += file_count
                                        results["folders_cleaned"].append(f"{folder_name}/{item}")
                                        print(f"  ✓ Deleted {item} ({file_count} files)")
                                        
                                except ValueError:
                                    # Not a date folder, skip
                                    continue
                    else:
                        # Images and json_backups folders - delete old files directly
                        for root, dirs, files in os.walk(folder_path):
                            for file in files:
                                file_path = os.path.join(root, file)
                                
                                try:
                                    file_mtime = datetime.datetime.fromtimestamp(os.path.getmtime(file_path))
                                    
                                    if file_mtime < cutoff_date:
                                        os.remove(file_path)
                                        results["files_deleted"] += 1
                                        print(f"  ✓ Deleted old file: {file}")
                                        
                                except Exception as e:
                                    error_msg = f"Error deleting {file}: {str(e)}"
                                    results["errors"].append(error_msg)
                                    print(f"  ✗ {error_msg}")
                
                except Exception as e:
                    error_msg = f"Error cleaning {folder_name}: {str(e)}"
                    results["errors"].append(error_msg)
                    print(f"  ✗ {error_msg}")
            
            # Update tracking
            tracking_data = self.get_backup_tracking_data()
            tracking_data["last_cleanup_date"] = datetime.datetime.now().isoformat()
            self.save_backup_tracking_data(tracking_data)
            
            results["success"] = len(results["errors"]) == 0
            
            print(f"🧹 Cleanup completed:")
            print(f"   Files deleted: {results['files_deleted']}")
            print(f"   Folders cleaned: {len(results['folders_cleaned'])}")
            
            return results
            
        except Exception as e:
            error_msg = f"Error during cleanup: {str(e)}"
            print(error_msg)
            return {
                "success": False,
                "error": error_msg,
                "files_deleted": 0,
                "folders_cleaned": []
            }
    
    def auto_cleanup_if_needed(self, data_folder="data", days_to_keep=10, cleanup_interval_days=1):
        """Automatically cleanup old files if cleanup interval has passed
        
        Args:
            data_folder (str): Base data folder path
            days_to_keep (int): Number of days to keep files
            cleanup_interval_days (int): Days between automatic cleanups
            
        Returns:
            dict: Cleanup results or None if not needed
        """
        try:
            tracking_data = self.get_backup_tracking_data()
            last_cleanup_str = tracking_data.get("last_cleanup_date", "")
            
            if last_cleanup_str:
                last_cleanup = datetime.datetime.fromisoformat(last_cleanup_str)
                days_since_cleanup = (datetime.datetime.now() - last_cleanup).days
                
                if days_since_cleanup < cleanup_interval_days:
                    print(f"⏳ Cleanup not needed (last cleanup {days_since_cleanup} days ago)")
                    return None
            
            print(f"🧹 Automatic cleanup triggered (keeping last {days_to_keep} days)")
            return self.cleanup_old_local_files(data_folder, days_to_keep)
            
        except Exception as e:
            print(f"Error in auto cleanup: {e}")
            return None

    def get_backup_summary(self, agency_name=None, site_name=None):
        """Get comprehensive backup summary for agency/site organization
        
        Args:
            agency_name (str, optional): Filter by agency
            site_name (str, optional): Filter by site
            
        Returns:
            dict: Backup summary with organized structure
        """
        if not self.is_connected():
            return {"error": "Not connected to cloud storage"}
        
        try:
            summary = {
                "total_files": 0,
                "by_agency": {},
                "by_date": {},
                "by_type": {"images": 0, "json_backups": 0, "reports": 0, "legacy": 0},
                "total_size_bytes": 0,
                "last_backup": None,
                "structure_example": "Agency/Site/YYYY-MM-DD/[images|json_backups|reports]/"
            }
            
            # List all blobs
            print("📊 Analyzing cloud storage structure...")
            blobs = list(self.client.list_blobs(self.bucket))
            
            latest_time = None
            
            for blob in blobs:
                summary["total_files"] += 1
                summary["total_size_bytes"] += blob.size or 0
                
                # Track latest upload
                if blob.time_created:
                    if latest_time is None or blob.time_created > latest_time:
                        latest_time = blob.time_created
                
                # Parse path structure: agency/site/date/type/filename
                path_parts = blob.name.split('/')
                
                if len(path_parts) >= 4:
                    agency = path_parts[0]
                    site = path_parts[1] 
                    date = path_parts[2]
                    file_type = path_parts[3]
                    
                    # Filter by agency/site if specified
                    if agency_name and agency != agency_name.replace(' ', '_').replace('/', '_'):
                        continue
                    if site_name and site != site_name.replace(' ', '_').replace('/', '_'):
                        continue
                    
                    # Track by agency
                    if agency not in summary["by_agency"]:
                        summary["by_agency"][agency] = {"sites": {}, "total_files": 0}
                    
                    if site not in summary["by_agency"][agency]["sites"]:
                        summary["by_agency"][agency]["sites"][site] = {"dates": {}, "total_files": 0}
                    
                    if date not in summary["by_agency"][agency]["sites"][site]["dates"]:
                        summary["by_agency"][agency]["sites"][site]["dates"][date] = {"types": {}, "total_files": 0}
                    
                    if file_type not in summary["by_agency"][agency]["sites"][site]["dates"][date]["types"]:
                        summary["by_agency"][agency]["sites"][site]["dates"][date]["types"][file_type] = 0
                    
                    # Increment counters
                    summary["by_agency"][agency]["total_files"] += 1
                    summary["by_agency"][agency]["sites"][site]["total_files"] += 1
                    summary["by_agency"][agency]["sites"][site]["dates"][date]["total_files"] += 1
                    summary["by_agency"][agency]["sites"][site]["dates"][date]["types"][file_type] += 1
                    
                    # Track by date globally
                    if date not in summary["by_date"]:
                        summary["by_date"][date] = 0
                    summary["by_date"][date] += 1
                    
                    # Track by type globally
                    if file_type in summary["by_type"]:
                        summary["by_type"][file_type] += 1
                    
                elif path_parts[0] == "legacy":
                    summary["by_type"]["legacy"] += 1
            
            if latest_time:
                summary["last_backup"] = latest_time.strftime("%Y-%m-%d %H:%M:%S UTC")
            
            # Convert size to human readable format
            size_bytes = summary["total_size_bytes"]
            if size_bytes < 1024:
                summary["total_size"] = f"{size_bytes} B"
            elif size_bytes < 1024 * 1024:
                summary["total_size"] = f"{size_bytes / 1024:.1f} KB"
            elif size_bytes < 1024 * 1024 * 1024:
                summary["total_size"] = f"{size_bytes / (1024 * 1024):.1f} MB"
            else:
                summary["total_size"] = f"{size_bytes / (1024 * 1024 * 1024):.1f} GB"
            
            return summary
            
        except Exception as e:
            return {"error": f"Error getting backup summary: {str(e)}"}
    
    def list_files_by_structure(self, agency_name=None, site_name=None, date_str=None, file_type=None):
        """List files by the new agency/site/date structure
        
        Args:
            agency_name (str, optional): Filter by agency
            site_name (str, optional): Filter by site  
            date_str (str, optional): Filter by date (YYYY-MM-DD)
            file_type (str, optional): Filter by type (images, json_backups, reports)
            
        Returns:
            list: List of matching files with metadata
        """
        if not self.is_connected():
            return []
        
        try:
            # Build prefix for filtering
            prefix_parts = []
            if agency_name:
                clean_agency = agency_name.replace(' ', '_').replace('/', '_').replace('\\', '_')
                prefix_parts.append(clean_agency)
                if site_name:
                    clean_site = site_name.replace(' ', '_').replace('/', '_').replace('\\', '_')
                    prefix_parts.append(clean_site)
                    if date_str:
                        prefix_parts.append(date_str)
                        if file_type:
                            prefix_parts.append(file_type)
            
            prefix = "/".join(prefix_parts) + "/" if prefix_parts else None
            
            # List blobs with prefix
            blobs = self.client.list_blobs(self.bucket, prefix=prefix)
            
            files = []
            for blob in blobs:
                # Parse path structure
                path_parts = blob.name.split('/')
                
                if len(path_parts) >= 5:  # agency/site/date/type/filename
                    file_info = {
                        "name": blob.name,
                        "filename": path_parts[-1],
                        "agency": path_parts[0],
                        "site": path_parts[1],
                        "date": path_parts[2],
                        "type": path_parts[3],
                        "size": blob.size or 0,
                        "created": blob.time_created.strftime("%Y-%m-%d %H:%M:%S UTC") if blob.time_created else "Unknown",
                        "full_path": blob.name
                    }
                    files.append(file_info)
            
            return files
            
        except Exception as e:
            print(f"Error listing files: {str(e)}")
            return []
    
    def get_upload_summary(self, prefix=None):
        """Get a summary of uploaded files with daily reports info
        
        Args:
            prefix (str, optional): Prefix to filter files by
            
        Returns:
            dict: Summary with file counts and sizes
        """
        if not self.is_connected():
            return {"error": "Not connected to cloud storage"}
            
        try:
            blobs = list(self.client.list_blobs(self.bucket, prefix=prefix))
            
            summary = {
                "total_files": len(blobs),
                "json_files": 0,
                "image_files": 0,
                "daily_report_files": 0,
                "total_size_bytes": 0,
                "last_upload": None
            }
            
            latest_time = None
            
            for blob in blobs:
                summary["total_size_bytes"] += blob.size or 0
                
                # Track latest upload time
                if blob.time_created:
                    if latest_time is None or blob.time_created > latest_time:
                        latest_time = blob.time_created
                
                # Categorize files
                if blob.name.endswith('.json'):
                    summary["json_files"] += 1
                elif any(blob.name.lower().endswith(ext) for ext in ['.jpg', '.jpeg', '.png', '.gif', '.bmp']):
                    summary["image_files"] += 1
                elif blob.name.startswith('daily_reports/'):
                    summary["daily_report_files"] += 1
            
            if latest_time:
                summary["last_upload"] = latest_time.strftime("%Y-%m-%d %H:%M:%S UTC")
            
            # Convert size to human readable format
            size_bytes = summary["total_size_bytes"]
            if size_bytes < 1024:
                summary["total_size"] = f"{size_bytes} B"
            elif size_bytes < 1024 * 1024:
                summary["total_size"] = f"{size_bytes / 1024:.1f} KB"
            elif size_bytes < 1024 * 1024 * 1024:
                summary["total_size"] = f"{size_bytes / (1024 * 1024):.1f} MB"
            else:
                summary["total_size"] = f"{size_bytes / (1024 * 1024 * 1024):.1f} GB"
            
            return summary
            
        except Exception as e:
            return {"error": f"Error getting upload summary: {str(e)}"}

    def upload_single_file(self, local_file_path, agency_name, site_name, file_type=None):
        """Upload a single file to the organized cloud structure
        
        Args:
            local_file_path (str): Path to local file
            agency_name (str): Agency name
            site_name (str): Site name
            file_type (str, optional): Override file type detection
            
        Returns:
            bool: True if successful, False otherwise
        """
        if not self.is_connected():
            print("❌ Not connected to cloud storage")
            return False
            
        if not os.path.exists(local_file_path):
            print(f"❌ Local file not found: {local_file_path}")
            return False
            
        try:
            # Auto-detect file type if not provided
            if not file_type:
                file_extension = os.path.splitext(local_file_path)[1].lower()
                if file_extension in {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.tiff', '.tif'}:
                    file_type = "images"
                elif file_extension == '.json':
                    file_type = "json_backups"
                elif file_extension in {'.pdf', '.csv', '.xlsx', '.docx', '.txt', '.html'}:
                    file_type = "reports"
                else:
                    file_type = "reports"  # Default to reports for unknown types
            
            # Generate cloud path
            today_str = datetime.datetime.now().strftime("%Y-%m-%d")
            cloud_base_path = self.get_cloud_path(agency_name, site_name, today_str, file_type)
            filename = os.path.basename(local_file_path)
            cloud_path = f"{cloud_base_path}{filename}"
            
            # Create blob and upload
            blob = self.bucket.blob(cloud_path)
            
            # Set appropriate content type
            file_extension = os.path.splitext(local_file_path)[1].lower()
            content_type_map = {
                '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.png': 'image/png',
                '.gif': 'image/gif', '.bmp': 'image/bmp', '.webp': 'image/webp',
                '.tiff': 'image/tiff', '.tif': 'image/tiff', '.pdf': 'application/pdf',
                '.json': 'application/json', '.txt': 'text/plain', '.csv': 'text/csv',
                '.html': 'text/html', '.xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
            }
            content_type = content_type_map.get(file_extension, 'application/octet-stream')
            
            blob.upload_from_filename(local_file_path, content_type=content_type)
            
            print(f"✅ Uploaded: {local_file_path} → {cloud_path}")
            return True
            
        except Exception as e:
            print(f"❌ Error uploading file: {str(e)}")
            return False
    
    def download_file(self, cloud_path, local_path):
        """Download a file from cloud storage
        
        Args:
            cloud_path (str): Cloud storage path
            local_path (str): Local path to save file
            
        Returns:
            bool: True if successful, False otherwise
        """
        if not self.is_connected():
            print("❌ Not connected to cloud storage")
            return False
            
        try:
            # Create local directory if it doesn't exist
            os.makedirs(os.path.dirname(local_path), exist_ok=True)
            
            # Download file
            blob = self.bucket.blob(cloud_path)
            blob.download_to_filename(local_path)
            
            print(f"✅ Downloaded: {cloud_path} → {local_path}")
            return True
            
        except Exception as e:
            print(f"❌ Error downloading file: {str(e)}")
            return False
    
    def upload_record_with_images(self, record_data, json_filename, images_folder_path, agency_name=None, site_name=None):
        """Upload a complete record with JSON data and associated images to organized cloud structure
        
        Args:
            record_data (dict): Record data to save as JSON
            json_filename (str): Base filename for JSON
            images_folder_path (str): Local folder path containing images
            agency_name (str, optional): Agency name for organization
            site_name (str, optional): Site name for organization
            
        Returns:
            tuple: (json_success, images_uploaded, total_images)
        """
        if not self.is_connected():
            print("❌ Not connected to cloud storage")
            return False, 0, 0
        
        # First, upload the JSON data
        json_success = self.save_json_record(record_data, json_filename, agency_name, site_name)
        
        if not json_success:
            print("❌ Failed to upload JSON data, skipping images")
            return False, 0, 0
        
        # Upload associated images
        images_uploaded = 0
        total_images = 0
        
        # Check for all 4 image types
        image_types = [
            ('first_front', record_data.get('first_front_image', '')),
            ('first_back', record_data.get('first_back_image', '')),
            ('second_front', record_data.get('second_front_image', '')),
            ('second_back', record_data.get('second_back_image', ''))
        ]
        
        for image_type, image_filename in image_types:
            if image_filename:
                total_images += 1
                local_image_path = os.path.join(images_folder_path, image_filename)
                
                if os.path.exists(local_image_path):
                    # Upload image with descriptive name
                    descriptive_name = f"{image_type}_{image_filename}"
                    
                    if self.upload_image(local_image_path, descriptive_name, agency_name, site_name):
                        images_uploaded += 1
                        print(f"✅ Uploaded {image_type} image: {image_filename}")
                    else:
                        print(f"❌ Failed to upload {image_type} image: {image_filename}")
                else:
                    print(f"⚠️  Local {image_type} image not found: {local_image_path}")
        
        return json_success, images_uploaded, total_images
    


    def save_json(self, data, filename):
        """Legacy method - now uses organized structure with duplicate checking"""
        # Get agency and site from data or use defaults
        agency_name = data.get('agency_name') or getattr(self, 'default_agency', 'Unknown_Agency')
        site_name = data.get('site_name') or getattr(self, 'default_site', 'Unknown_Site')
        
        # Use the new organized method which has duplicate checking built-in
        return self.save_json_record(data, filename, agency_name, site_name)

    def save_json_record(self, data, filename, agency_name=None, site_name=None):
        """Save record data as JSON to cloud storage with duplicate checking"""
        if not self.is_connected():
            print("❌ Not connected to cloud storage")
            return False
            
        try:
            # Use defaults if agency/site not provided
            if not agency_name:
                agency_name = getattr(self, 'default_agency', 'Unknown_Agency')
            if not site_name:
                site_name = getattr(self, 'default_site', 'Unknown_Site')
            
            # Generate cloud path
            today_str = datetime.datetime.now().strftime("%Y-%m-%d")
            cloud_base_path = self.get_cloud_path(agency_name, site_name, today_str, "json_backups")
            
            file_base, file_ext = os.path.splitext(filename)
            if not file_ext:
                file_ext = '.json'
            cloud_path = f"{cloud_base_path}{file_base}{file_ext}"
            
            # Calculate content hash for duplicate detection
            content_str = json.dumps(data, sort_keys=True, ensure_ascii=False)
            current_hash = hashlib.md5(content_str.encode()).hexdigest()
            
            # Check tracking data for duplicates
            tracking_data = self.get_backup_tracking_data()
            json_tracking = tracking_data.get("json_backups_backed_up", {})
            
            # Create a unique key for this JSON record
            json_key = f"{agency_name}_{site_name}_{file_base}"
            
            # Check if this JSON content was already uploaded
            if (json_key in json_tracking and 
                json_tracking[json_key].get("content_hash") == current_hash):
                print(f"⏭️  Skipping duplicate JSON: {filename} (content already backed up)")
                return True
            
            # Upload to cloud (content is new or changed)
            blob = self.bucket.blob(cloud_path)
            blob.upload_from_string(json.dumps(data, indent=4, ensure_ascii=False), content_type="application/json")
            
            # Update tracking with content hash
            json_tracking[json_key] = {
                "content_hash": current_hash,
                "upload_date": datetime.datetime.now().isoformat(),
                "cloud_path": cloud_path,
                "agency": agency_name,
                "site": site_name,
                "date": today_str,
                "filename": filename
            }
            
            # Save tracking data
            tracking_data["json_backups_backed_up"] = json_tracking
            tracking_data["last_backup_date"] = datetime.datetime.now().isoformat()
            self.save_backup_tracking_data(tracking_data)
            
            print(f"✅ Saved JSON record as {cloud_path}")
            return True
            
        except Exception as e:
            print(f"❌ Error saving JSON record to cloud storage: {str(e)}")
            return False
    
    # Legacy methods for backward compatibility
    def backup_daily_reports(self, reports_folder="data/reports"):
        """Legacy method - Use comprehensive_backup instead"""
        print("⚠️  backup_daily_reports is deprecated. Use comprehensive_backup instead.")
        return 0, 0, ["Use comprehensive_backup method instead"]


    def upload_image(self, local_image_path, cloud_filename=None, agency_name=None, site_name=None):
        """Updated to always use organized structure"""
        if not self.is_connected():
            print("❌ Not connected to cloud storage")
            return False
            
        if not os.path.exists(local_image_path):
            print(f"❌ Local image file not found: {local_image_path}")
            return False
            
        try:
            # Use defaults if agency/site not provided
            if not agency_name:
                agency_name = getattr(self, 'default_agency', 'Unknown_Agency')
            if not site_name:
                site_name = getattr(self, 'default_site', 'Unknown_Site')
            
            # Always use organized structure - NO MORE LEGACY FOLDER
            today_str = datetime.datetime.now().strftime("%Y-%m-%d")
            cloud_base_path = self.get_cloud_path(agency_name, site_name, today_str, "images")
            filename = cloud_filename or os.path.basename(local_image_path)
            cloud_path = f"{cloud_base_path}{filename}"
            
            # Check for duplicates using existing hash tracking
            current_hash = self.get_file_hash(local_image_path)
            tracking_data = self.get_backup_tracking_data()
            images_tracking = tracking_data.get("images_backed_up", {})
            
            # Check if file was already uploaded
            if (local_image_path in images_tracking and 
                images_tracking[local_image_path].get("hash") == current_hash):
                print(f"⏭️  Skipping duplicate image: {filename} (already backed up)")
                return True
            
            # Create blob and upload
            blob = self.bucket.blob(cloud_path)
            
            # Set content type
            file_extension = os.path.splitext(local_image_path)[1].lower()
            content_type_map = {
                '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.png': 'image/png',
                '.gif': 'image/gif', '.bmp': 'image/bmp', '.webp': 'image/webp',
                '.tiff': 'image/tiff', '.tif': 'image/tiff'
            }
            content_type = content_type_map.get(file_extension, 'image/jpeg')
            
            blob.upload_from_filename(local_image_path, content_type=content_type)
            
            # Update tracking
            images_tracking[local_image_path] = {
                "hash": current_hash,
                "upload_date": datetime.datetime.now().isoformat(),
                "cloud_path": cloud_path,
                "file_size": os.path.getsize(local_image_path),
                "agency": agency_name,
                "site": site_name,
                "date": today_str,
                "last_modified": datetime.datetime.fromtimestamp(os.path.getmtime(local_image_path)).isoformat()
            }
            
            tracking_data["images_backed_up"] = images_tracking
            self.save_backup_tracking_data(tracking_data)
            
            print(f"✅ Uploaded image {local_image_path} to {cloud_path}")
            return True
            
        except Exception as e:
            print(f"❌ Error uploading image to cloud storage: {str(e)}")
            return False

    def get_connection_status(self):
        """Get detailed connection status and bucket information
        
        Returns:
            dict: Connection status details
        """
        status = {
            "connected": self.is_connected(),
            "bucket_name": self.bucket.name if self.bucket else None,
            "client_initialized": self.client is not None,
            "bucket_accessible": False,
            "error": None
        }
        
        if self.is_connected():
            try:
                # Test bucket access
                next(self.bucket.list_blobs(max_results=1), None)
                status["bucket_accessible"] = True
                status["status_message"] = "✅ Connected and ready for backup"
            except Exception as e:
                status["error"] = str(e)
                status["status_message"] = f"❌ Connection error: {e}"
        else:
            status["status_message"] = "❌ Not connected to cloud storage"
        
        return status

# Convenience function for easy usage
def create_cloud_service(bucket_name, credentials_path=None):
    """Create and return a CloudStorageService instance
    
    Args:
        bucket_name (str): GCS bucket name
        credentials_path (str, optional): Path to service account credentials
        
    Returns:
        CloudStorageService: Configured cloud storage service
    """
    return CloudStorageService(bucket_name, credentials_path)

# Example usage function
def example_backup_usage():
    """Example of how to use the comprehensive backup feature"""
    print("🔧 EXAMPLE USAGE:")
    print("="*50)
    print("from cloud_storage import CloudStorageService")
    print("")
    print("# Initialize service")
    print('cloud_service = CloudStorageService("your-bucket-name", "path/to/credentials.json")')
    print("")
    print("# Perform comprehensive backup (all days)")
    print('results = cloud_service.comprehensive_backup("Tharuni", "Guntur")')
    print("")
    print("# Perform today-only backup")
    print('results = cloud_service.backup_today_only("Tharuni", "Guntur")')
    print("")
    print("# Check results")
    print("if results['success']:")
    print("    print(f'✅ Backup successful! {results[\"total_files_uploaded\"]} files uploaded')")
    print("else:")
    print("    print(f'❌ Backup had {len(results[\"all_errors\"])} errors')")
    print("")
    print("# Files will be organized as:")
    print("# Tharuni/Guntur/2025-06-14/images/")
    print("# Tharuni/Guntur/2025-06-14/json_backups/")
    print("# Tharuni/Guntur/2025-06-14/reports/")
    print("")
    print("# TODAY-ONLY vs COMPREHENSIVE:")
    print("# comprehensive_backup() - Backs up ALL days in all folders")
    print("# backup_today_only() - Backs up ONLY current day folder (2025-06-14)")
    print("="*50)