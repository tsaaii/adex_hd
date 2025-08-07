import os
import json
import hashlib
import config

class SettingsStorage:
    """Class for managing persistent settings storage"""
    
    def __init__(self):
        """Initialize the settings storage"""
        self.settings_file = os.path.join(config.DATA_FOLDER, 'app_settings.json')
        self.users_file = os.path.join(config.DATA_FOLDER, 'users.json')
        self.sites_file = os.path.join(config.DATA_FOLDER, 'sites.json')
        self.initialize_files()
        
    def initialize_files(self):
        """Initialize settings files if they don't exist"""
        # Create settings file with default settings including HTTP camera support and ticket counter
        if not os.path.exists(self.settings_file):
            default_settings = {
                "weighbridge": {
                    "com_port": "",
                    "baud_rate": 9600,
                    "data_bits": 8,
                    "parity": "None",
                    "stop_bits": 1.0
                },
                "cameras": {
                    "front_camera_type": "USB",
                    "front_camera_index": 0,
                    "front_rtsp_username": "",
                    "front_rtsp_password": "",
                    "front_rtsp_ip": "",
                    "front_rtsp_port": "554",
                    "front_rtsp_endpoint": "/stream1",
                    "front_http_username": "",
                    "front_http_password": "",
                    "front_http_ip": "",
                    "front_http_port": "80",
                    "front_http_endpoint": "/mjpeg",
                    "back_camera_type": "USB",
                    "back_camera_index": 1,
                    "back_rtsp_username": "",
                    "back_rtsp_password": "",
                    "back_rtsp_ip": "",
                    "back_rtsp_port": "554",
                    "back_rtsp_endpoint": "/stream1",
                    "back_http_username": "",
                    "back_http_password": "",
                    "back_http_ip": "",
                    "back_http_port": "80",
                    "back_http_endpoint": "/mjpeg"
                },
                "ticket_settings": {
                    "current_ticket_number": 1,
                    "ticket_prefix": "T",
                    "ticket_digits": 4,
                    "last_reset_date": ""
                }
            }
            os.makedirs(os.path.dirname(self.settings_file), exist_ok=True)
            with open(self.settings_file, 'w') as f:
                json.dump(default_settings, f, indent=4)
        else:
            # Update existing settings file to include HTTP and ticket settings if missing
            try:
                with open(self.settings_file, 'r') as f:
                    settings = json.load(f)
                
                # Check if cameras section needs updating
                cameras = settings.get("cameras", {})
                updated = False
                
                # Add missing HTTP settings for front camera
                if "front_http_username" not in cameras:
                    cameras.update({
                        "front_http_username": "",
                        "front_http_password": "",
                        "front_http_ip": "",
                        "front_http_port": "80",
                        "front_http_endpoint": "/mjpeg"
                    })
                    updated = True
                
                # Add missing HTTP settings for back camera
                if "back_http_username" not in cameras:
                    cameras.update({
                        "back_http_username": "",
                        "back_http_password": "",
                        "back_http_ip": "",
                        "back_http_port": "80",
                        "back_http_endpoint": "/mjpeg"
                    })
                    updated = True
                
                # Add missing RTSP settings for front camera (if not exists)
                if "front_camera_type" not in cameras:
                    cameras.update({
                        "front_camera_type": "USB",
                        "front_rtsp_username": "",
                        "front_rtsp_password": "",
                        "front_rtsp_ip": "",
                        "front_rtsp_port": "554",
                        "front_rtsp_endpoint": "/stream1"
                    })
                    updated = True
                
                # Add missing RTSP settings for back camera (if not exists)
                if "back_camera_type" not in cameras:
                    cameras.update({
                        "back_camera_type": "USB",
                        "back_rtsp_username": "",
                        "back_rtsp_password": "",
                        "back_rtsp_ip": "",
                        "back_rtsp_port": "554",
                        "back_rtsp_endpoint": "/stream1"
                    })
                    updated = True
                
                # Add ticket settings if missing
                if "ticket_settings" not in settings:
                    settings["ticket_settings"] = {
                        "current_ticket_number": 1,
                        "ticket_prefix": "T",
                        "ticket_digits": 4,
                        "last_reset_date": ""
                    }
                    updated = True
                
                if updated:
                    settings["cameras"] = cameras
                    with open(self.settings_file, 'w') as f:
                        json.dump(settings, f, indent=4)
                        
            except Exception as e:
                print(f"Error updating settings file: {e}")
        
        # Create users file with default admin user
        if not os.path.exists(self.users_file):
            default_users = {
                "admin": {
                    "password": self.hash_password("admin"),
                    "role": "admin",
                    "name": "Administrator"
                }
            }
            os.makedirs(os.path.dirname(self.users_file), exist_ok=True)
            with open(self.users_file, 'w') as f:
                json.dump(default_users, f, indent=4)
        
        # Create sites file with default site, incharge, and transfer party
        if not os.path.exists(self.sites_file):
            default_sites = {
                "sites": ["Guntur"],
                "incharges": ["Site Manager"],
                "transfer_parties": ["Advitia Labs"],
                "agencies": ["Default Agency"]  # Added default agency
            }
            os.makedirs(os.path.dirname(self.sites_file), exist_ok=True)
            with open(self.sites_file, 'w') as f:
                json.dump(default_sites, f, indent=4)
        else:
            # Update existing sites file to include agencies if missing
            try:
                with open(self.sites_file, 'r') as f:
                    sites_data = json.load(f)
                    
                # Add missing fields
                if 'transfer_parties' not in sites_data:
                    sites_data['transfer_parties'] = ["Advitia Labs"]
                if 'agencies' not in sites_data:
                    sites_data['agencies'] = ["Default Agency"]
                    
                with open(self.sites_file, 'w') as f:
                    json.dump(sites_data, f, indent=4)
            except Exception as e:
                print(f"Error updating sites file: {e}")

    def get_ticket_counter(self):
        """Get the current ticket counter
        
        Returns:
            int: Current ticket counter number
        """
        try:
            with open(self.settings_file, 'r') as f:
                settings = json.load(f)
                ticket_settings = settings.get("ticket_settings", {})
                return ticket_settings.get("current_ticket_number", 1)
        except Exception as e:
            print(f"Error reading ticket counter: {e}")
            return 1
    
    def save_ticket_counter(self, counter_value):
        """Save the ticket counter
        
        Args:
            counter_value: New counter value to save
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Read existing settings
            if os.path.exists(self.settings_file):
                with open(self.settings_file, 'r') as f:
                    all_settings = json.load(f)
            else:
                all_settings = {}
            
            # Ensure ticket_settings section exists
            if "ticket_settings" not in all_settings:
                all_settings["ticket_settings"] = {
                    "current_ticket_number": 1,
                    "ticket_prefix": "T",
                    "ticket_digits": 4,
                    "last_reset_date": ""
                }
            
            # Update counter
            all_settings["ticket_settings"]["current_ticket_number"] = counter_value
            
            # Write back to file
            with open(self.settings_file, 'w') as f:
                json.dump(all_settings, f, indent=4)
                
            return True
            
        except Exception as e:
            print(f"Error saving ticket counter: {e}")
            return False
    
    def get_ticket_settings(self):
        """Get all ticket settings
        
        Returns:
            dict: Ticket settings including prefix, digits, etc.
        """
        try:
            with open(self.settings_file, 'r') as f:
                settings = json.load(f)
                return settings.get("ticket_settings", {
                    "current_ticket_number": 1,
                    "ticket_prefix": "T",
                    "ticket_digits": 4,
                    "last_reset_date": ""
                })
        except Exception as e:
            print(f"Error reading ticket settings: {e}")
            return {
                "current_ticket_number": 1,
                "ticket_prefix": "T",
                "ticket_digits": 4,
                "last_reset_date": ""
            }
    
    def save_ticket_settings(self, ticket_settings):
        """Save ticket settings
        
        Args:
            ticket_settings: Dictionary with ticket configuration
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Read existing settings
            if os.path.exists(self.settings_file):
                with open(self.settings_file, 'r') as f:
                    all_settings = json.load(f)
            else:
                all_settings = {}
            
            # Update ticket settings section
            all_settings["ticket_settings"] = ticket_settings
            
            # Write back to file
            with open(self.settings_file, 'w') as f:
                json.dump(all_settings, f, indent=4)
                
            print(f"Ticket settings saved: {ticket_settings}")
            return True
            
        except Exception as e:
            print(f"Error saving ticket settings: {e}")
            return False
    
    def reset_ticket_counter(self, start_number=1):
        """Reset ticket counter to a specific starting number
        
        Args:
            start_number: Number to start counting from
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            import datetime
            
            ticket_settings = self.get_ticket_settings()
            ticket_settings["current_ticket_number"] = start_number
            ticket_settings["last_reset_date"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            return self.save_ticket_settings(ticket_settings)
            
        except Exception as e:
            print(f"Error resetting ticket counter: {e}")
            return False

    def get_weighbridge_settings(self):
        """Get weighbridge settings from file including test mode
        
        Returns:
            dict: Weighbridge settings with test_mode flag
        """
        try:
            print(f"Reading weighbridge settings from: {self.settings_file}")
            with open(self.settings_file, 'r') as f:
                settings = json.load(f)
                wb_settings = settings.get("weighbridge", {})
                
                # Add test_mode if it doesn't exist
                if "test_mode" not in wb_settings:
                    wb_settings["test_mode"] = False
                    
                print(f"Loaded weighbridge settings: {wb_settings}")
                return wb_settings
        except Exception as e:
            print(f"Error reading weighbridge settings: {e}")
            return {
                "com_port": "",
                "baud_rate": 9600,
                "data_bits": 8,
                "parity": "None",
                "stop_bits": 1.0,
                "test_mode": False  # Default to real weighbridge mode
            }
        
    def save_weighbridge_settings(self, settings):
        """Save weighbridge settings to file
        
        Args:
            settings: Weighbridge settings dict
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            print(f"Saving weighbridge settings to: {self.settings_file}")
            print(f"Settings to save: {settings}")
            
            # Read existing settings
            if os.path.exists(self.settings_file):
                with open(self.settings_file, 'r') as f:
                    all_settings = json.load(f)
            else:
                all_settings = {}
            
            # Update weighbridge section
            all_settings["weighbridge"] = settings
            
            # Ensure directory exists
            os.makedirs(os.path.dirname(self.settings_file), exist_ok=True)
            
            # Write back to file
            with open(self.settings_file, 'w') as f:
                json.dump(all_settings, f, indent=4)
                
            print("Weighbridge settings saved successfully")
            return True
            
        except Exception as e:
            print(f"Error saving weighbridge settings: {e}")
            return False
    
    def get_camera_settings(self):
        """Get camera settings from file
        
        Returns:
            dict: Camera settings
        """
        try:
            print(f"Reading camera settings from: {self.settings_file}")
            with open(self.settings_file, 'r') as f:
                settings = json.load(f)
                camera_settings = settings.get("cameras", {})
                print(f"Loaded camera settings: {camera_settings}")
                return camera_settings
        except Exception as e:
            print(f"Error reading camera settings: {e}")
            return {
                "front_camera_type": "USB",
                "front_camera_index": 0,
                "front_rtsp_username": "",
                "front_rtsp_password": "",
                "front_rtsp_ip": "",
                "front_rtsp_port": "554",
                "front_rtsp_endpoint": "/stream1",
                "front_http_username": "",
                "front_http_password": "",
                "front_http_ip": "",
                "front_http_port": "80",
                "front_http_endpoint": "/mjpeg",
                "back_camera_type": "USB",
                "back_camera_index": 1,
                "back_rtsp_username": "",
                "back_rtsp_password": "",
                "back_rtsp_ip": "",
                "back_rtsp_port": "554",
                "back_rtsp_endpoint": "/stream1",
                "back_http_username": "",
                "back_http_password": "",
                "back_http_ip": "",
                "back_http_port": "80",
                "back_http_endpoint": "/mjpeg"
            }
    
    def save_camera_settings(self, settings):
        """Save camera settings to file
        
        Args:
            settings: Camera settings dict
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            print(f"Saving camera settings to: {self.settings_file}")
            print(f"Camera settings to save: {settings}")
            
            # Read existing settings
            if os.path.exists(self.settings_file):
                with open(self.settings_file, 'r') as f:
                    all_settings = json.load(f)
            else:
                all_settings = {}
            
            # Update cameras section
            all_settings["cameras"] = settings
            
            # Ensure directory exists
            os.makedirs(os.path.dirname(self.settings_file), exist_ok=True)
            
            # Write back to file
            with open(self.settings_file, 'w') as f:
                json.dump(all_settings, f, indent=4)
                
            print("Camera settings saved successfully")
            return True
            
        except Exception as e:
            print(f"Error saving camera settings: {e}")
            return False
    
    def get_rtsp_url(self, camera_position):
        """Build RTSP URL for specified camera position
        
        Args:
            camera_position: "front" or "back"
            
        Returns:
            str: Complete RTSP URL or None if not configured
        """
        try:
            camera_settings = self.get_camera_settings()
            
            username = camera_settings.get(f"{camera_position}_rtsp_username", "")
            password = camera_settings.get(f"{camera_position}_rtsp_password", "")
            ip = camera_settings.get(f"{camera_position}_rtsp_ip", "")
            port = camera_settings.get(f"{camera_position}_rtsp_port", "554")
            endpoint = camera_settings.get(f"{camera_position}_rtsp_endpoint", "/stream1")
            
            if not ip:
                return None
                
            # Build RTSP URL
            if username and password:
                rtsp_url = f"rtsp://{username}:{password}@{ip}:{port}{endpoint}"
            else:
                rtsp_url = f"rtsp://{ip}:{port}{endpoint}"
                
            return rtsp_url
            
        except Exception as e:
            print(f"Error building RTSP URL: {e}")
            return None

    def get_http_url(self, camera_position):
        """Build HTTP URL for specified camera position
        
        Args:
            camera_position: "front" or "back"
            
        Returns:
            str: Complete HTTP URL or None if not configured
        """
        try:
            camera_settings = self.get_camera_settings()
            
            username = camera_settings.get(f"{camera_position}_http_username", "")
            password = camera_settings.get(f"{camera_position}_http_password", "")
            ip = camera_settings.get(f"{camera_position}_http_ip", "")
            port = camera_settings.get(f"{camera_position}_http_port", "80")
            endpoint = camera_settings.get(f"{camera_position}_http_endpoint", "/mjpeg")
            
            if not ip:
                return None
                
            # Build HTTP URL
            if username and password:
                http_url = f"http://{username}:{password}@{ip}:{port}{endpoint}"
            else:
                http_url = f"http://{ip}:{port}{endpoint}"
                
            return http_url
            
        except Exception as e:
            print(f"Error building HTTP URL: {e}")
            return None

    def get_sites(self):
        """Get sites, incharges, transfer parties and agencies
        
        Returns:
            dict: Sites data with 'sites', 'incharges', 'transfer_parties', and 'agencies' keys
        """
        try:
            with open(self.sites_file, 'r') as f:
                sites_data = json.load(f)
                
                # Ensure all fields exist
                if 'transfer_parties' not in sites_data:
                    sites_data['transfer_parties'] = ["Advitia Labs"]
                if 'agencies' not in sites_data:
                    sites_data['agencies'] = ["Default Agency"]
                
                return sites_data
        except Exception as e:
            print(f"Error reading sites: {e}")
            return {
                "sites": ["Guntur"], 
                "incharges": ["Site Manager"],
                "transfer_parties": ["Advitia Labs"],
                "agencies": ["Default Agency"]
            }

    def get_users(self):
        """Get all users
        
        Returns:
            dict: User data keyed by username
        """
        try:
            with open(self.users_file, 'r') as f:
                return json.load(f)
        except Exception as e:
            print(f"Error reading users: {e}")
            return {"admin": {"password": self.hash_password("admin"), "role": "admin", "name": "Administrator"}}
    
    def save_users(self, users):
        """Save users to file
        
        Args:
            users: Users dict
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            with open(self.users_file, 'w') as f:
                json.dump(users, f, indent=4)
            return True
        except Exception as e:
            print(f"Error saving users: {e}")
            return False
    
    def save_sites(self, sites_data):
        """Save sites, incharges and transfer parties to file with atomic write and backup
        
        Args:
            sites_data: Dict with 'sites', 'incharges', and 'transfer_parties' keys
            
        Returns:
            bool: True if successful, False otherwise
        """
        import tempfile
        import shutil
        import os
        
        try:
            # Validate input data
            if not isinstance(sites_data, dict):
                print(f"Error: sites_data must be a dict, got {type(sites_data)}")
                return False
                
            # Ensure all required keys exist with defaults
            if 'sites' not in sites_data:
                sites_data['sites'] = ["Guntur"]
            if 'incharges' not in sites_data:
                sites_data['incharges'] = ["Site Manager"]  
            if 'transfer_parties' not in sites_data:
                sites_data['transfer_parties'] = ["Advitia Labs"]
            if 'agencies' not in sites_data:
                sites_data['agencies'] = ["Default Agency"]
                
            # Ensure directory exists
            os.makedirs(os.path.dirname(self.sites_file), exist_ok=True)
            
            # Create backup of existing file (if it exists and is valid)
            backup_path = f"{self.sites_file}.backup"
            if os.path.exists(self.sites_file):
                try:
                    # Verify existing file is valid JSON before backing up
                    with open(self.sites_file, 'r') as f:
                        json.load(f)  # This will raise exception if invalid
                    shutil.copy2(self.sites_file, backup_path)
                    print(f"Created backup: {backup_path}")
                except (json.JSONDecodeError, Exception) as e:
                    print(f"Existing sites file is corrupt, not backing up: {e}")
            
            # Use atomic write with temporary file
            temp_file = None
            try:
                # Create temporary file in same directory as target
                temp_fd, temp_file = tempfile.mkstemp(
                    dir=os.path.dirname(self.sites_file),
                    prefix='sites_temp_',
                    suffix='.json'
                )
                
                # Write to temporary file
                with os.fdopen(temp_fd, 'w') as f:
                    json.dump(sites_data, f, indent=4)
                    f.flush()  # Ensure data is written to disk
                    os.fsync(f.fileno())  # Force write to disk
                
                # Verify the temporary file was written correctly
                with open(temp_file, 'r') as f:
                    verified_data = json.load(f)
                    
                # If verification passes, atomically replace the original file
                if os.name == 'nt':  # Windows
                    # On Windows, remove target first
                    if os.path.exists(self.sites_file):
                        os.remove(self.sites_file)
                    shutil.move(temp_file, self.sites_file)
                else:  # Unix/Linux
                    # On Unix, rename is atomic
                    os.rename(temp_file, self.sites_file)
                
                temp_file = None  # Successfully moved, don't clean up
                
                # Remove backup file after successful write
                if os.path.exists(backup_path):
                    os.remove(backup_path)
                    
                print(f"Sites data saved successfully to: {self.sites_file}")
                return True
                
            except Exception as write_error:
                print(f"Error during atomic write: {write_error}")
                
                # Clean up temporary file if it exists
                if temp_file and os.path.exists(temp_file):
                    try:
                        os.remove(temp_file)
                    except:
                        pass
                
                # Restore from backup if available
                if os.path.exists(backup_path):
                    try:
                        shutil.copy2(backup_path, self.sites_file)
                        print(f"Restored sites file from backup")
                    except Exception as restore_error:
                        print(f"Error restoring from backup: {restore_error}")
                
                return False
                
        except Exception as e:
            print(f"Error saving sites: {e}")
            
            # Last resort: create default sites file if it doesn't exist
            if not os.path.exists(self.sites_file):
                try:
                    default_sites = {
                        "sites": ["Guntur"],
                        "incharges": ["Site Manager"],
                        "transfer_parties": ["Advitia Labs"],
                        "agencies": ["Default Agency"]
                    }
                    
                    os.makedirs(os.path.dirname(self.sites_file), exist_ok=True)
                    with open(self.sites_file, 'w') as f:
                        json.dump(default_sites, f, indent=4)
                        
                    print("Created default sites file as fallback")
                    return True
                    
                except Exception as fallback_error:
                    print(f"Error creating fallback sites file: {fallback_error}")
                    
            return False
    
    def authenticate_user(self, username, password):
        """Authenticate user with username and password
        
        Args:
            username: Username
            password: Password
            
        Returns:
            tuple: (success, role) - success is bool, role is string or None
        """
        try:
            # Input validation
            if not username or not password:
                return False, None
                
            # Get users data
            users = self.get_users()
            
            # Check if user exists
            if username not in users:
                return False, None
                
            user_data = users[username]
            stored_hash = user_data.get('password', '')
            
            # Verify password using hash comparison
            input_hash = self.hash_password(password)
            
            if stored_hash == input_hash:
                role = user_data.get('role', 'user')
                print(f"Authentication successful for user: {username} (role: {role})")
                return True, role
            else:
                print(f"Authentication failed for user: {username} - password mismatch")
                return False, None
                
        except Exception as e:
            print(f"Error authenticating user {username}: {e}")
            return False, None


    def isAuthenticated(self, username, password):
        """Check if user is authenticated for settings access
        
        Args:
            username: Username
            password: Password
            
        Returns:
            bool: True if authenticated, False otherwise
        """
        users = self.get_users()
        if username in users:
            user_data = users[username]
            stored_hash = user_data.get('password', '')
            
            # Verify password
            if stored_hash == self.hash_password(password):
                return True
        
        return False
    
    def isAdminUser(self, username):
        """Check if user is an admin
        
        Args:
            username: Username
            
        Returns:
            bool: True if admin, False otherwise
        """
        users = self.get_users()
        if username in users:
            user_data = users[username]
            return user_data.get('role', '') == 'admin'
        
        return False
    
    def hash_password(self, password):
        """Hash password using SHA-256
        
        Args:
            password: Plain text password
            
        Returns:
            str: Hashed password
        """
        return hashlib.sha256(password.encode()).hexdigest()
    
    def get_user_name(self, username):
        """Get user's full name
        
        Args:
            username: Username
            
        Returns:
            str: User's full name
        """
        users = self.get_users()
        if username in users:
            return users[username].get('name', username)
        return username
    
    def user_exists(self, username):
        """Check if user exists
        
        Args:
            username: Username
            
        Returns:
            bool: True if user exists, False otherwise
        """
        users = self.get_users()
        return username in users
    
    def site_exists(self, site_name):
        """Check if site exists
        
        Args:
            site_name: Site name
            
        Returns:
            bool: True if site exists, False otherwise
        """
        sites_data = self.get_sites()
        return site_name in sites_data.get('sites', [])
    
    def incharge_exists(self, incharge_name):
        """Check if incharge exists
        
        Args:
            incharge_name: Incharge name
            
        Returns:
            bool: True if incharge exists, False otherwise
        """
        sites_data = self.get_sites()
        return incharge_name in sites_data.get('incharges', [])
    
    def get_all_settings(self):
        """Get all settings
        
        Returns:
            dict: All settings
        """
        try:
            with open(self.settings_file, 'r') as f:
                return json.load(f)
        except Exception as e:
            print(f"Error reading settings: {e}")
            return {
                "weighbridge": {
                    "com_port": "",
                    "baud_rate": 9600,
                    "data_bits": 8,
                    "parity": "None",
                    "stop_bits": 1.0
                },
                "cameras": {
                    "front_camera_type": "USB",
                    "front_camera_index": 0,
                    "front_rtsp_username": "",
                    "front_rtsp_password": "",
                    "front_rtsp_ip": "",
                    "front_rtsp_port": "554",
                    "front_rtsp_endpoint": "/stream1",
                    "front_http_username": "",
                    "front_http_password": "",
                    "front_http_ip": "",
                    "front_http_port": "80",
                    "front_http_endpoint": "/mjpeg",
                    "back_camera_type": "USB",
                    "back_camera_index": 1,
                    "back_rtsp_username": "",
                    "back_rtsp_password": "",
                    "back_rtsp_ip": "",
                    "back_rtsp_port": "554",
                    "back_rtsp_endpoint": "/stream1",
                    "back_http_username": "",
                    "back_http_password": "",
                    "back_http_ip": "",
                    "back_http_port": "80",
                    "back_http_endpoint": "/mjpeg"
                }
            }

    def verify_settings_integrity(self):
        """Verify that settings files exist and are valid
        
        Returns:
            bool: True if all settings are valid
        """
        try:
            # Check weighbridge settings
            wb_settings = self.get_weighbridge_settings()
            if not isinstance(wb_settings, dict):
                print("Invalid weighbridge settings format")
                return False
                
            # Check camera settings
            cam_settings = self.get_camera_settings()
            if not isinstance(cam_settings, dict):
                print("Invalid camera settings format")
                return False
                
            # Check required keys exist
            required_wb_keys = ["com_port", "baud_rate", "data_bits", "parity", "stop_bits"]
            for key in required_wb_keys:
                if key not in wb_settings:
                    print(f"Missing weighbridge setting: {key}")
                    return False
                    
            print("Settings integrity check passed")
            return True
            
        except Exception as e:
            print(f"Settings integrity check failed: {e}")
            return False

    def backup_settings(self, backup_filename=None):
        """Create a backup of all settings
        
        Args:
            backup_filename: Optional backup filename
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            import datetime
            
            if not backup_filename:
                timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                backup_filename = f"settings_backup_{timestamp}.json"
            
            backup_path = os.path.join(config.DATA_FOLDER, backup_filename)
            
            # Collect all settings
            all_settings = {
                "weighbridge": self.get_weighbridge_settings(),
                "cameras": self.get_camera_settings(),
                "sites": self.get_sites(),
                "users": self.get_users(),
                "backup_timestamp": datetime.datetime.now().isoformat()
            }
            
            # Save backup
            with open(backup_path, 'w') as f:
                json.dump(all_settings, f, indent=4)
                
            print(f"Settings backup created: {backup_path}")
            return True
            
        except Exception as e:
            print(f"Error creating settings backup: {e}")
            return False

    def restore_settings(self, backup_filename):
        """Restore settings from backup
        
        Args:
            backup_filename: Backup filename to restore from
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            backup_path = os.path.join(config.DATA_FOLDER, backup_filename)
            
            if not os.path.exists(backup_path):
                print(f"Backup file not found: {backup_path}")
                return False
            
            # Load backup
            with open(backup_path, 'r') as f:
                backup_data = json.load(f)
            
            # Restore weighbridge settings
            if "weighbridge" in backup_data:
                self.save_weighbridge_settings(backup_data["weighbridge"])
            
            # Restore camera settings
            if "cameras" in backup_data:
                self.save_camera_settings(backup_data["cameras"])
            
            # Restore sites
            if "sites" in backup_data:
                self.save_sites(backup_data["sites"])
            
            # Restore users
            if "users" in backup_data:
                self.save_users(backup_data["users"])
            
            print(f"Settings restored from: {backup_path}")
            return True
            
        except Exception as e:
            print(f"Error restoring settings: {e}")
            return False

    def reset_to_defaults(self):
        """Reset all settings to default values
        
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Remove existing settings files
            files_to_remove = [self.settings_file, self.users_file, self.sites_file]
            
            for file_path in files_to_remove:
                if os.path.exists(file_path):
                    os.remove(file_path)
                    print(f"Removed: {file_path}")
            
            # Reinitialize with defaults
            self.initialize_files()
            
            print("Settings reset to defaults")
            return True
            
        except Exception as e:
            print(f"Error resetting settings: {e}")
            return False

    def export_settings(self, export_path):
        """Export settings to a specified path
        
        Args:
            export_path: Path to export settings to
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            import datetime
            
            # Collect all settings
            export_data = {
                "weighbridge": self.get_weighbridge_settings(),
                "cameras": self.get_camera_settings(),
                "sites": self.get_sites(),
                "export_timestamp": datetime.datetime.now().isoformat(),
                "application": "Swaccha Andhra Corporation Weighbridge"
            }
            
            # Don't export user passwords for security
            sites_data = self.get_sites()
            export_data["sites"] = sites_data
            
            # Save export
            with open(export_path, 'w') as f:
                json.dump(export_data, f, indent=4)
                
            print(f"Settings exported to: {export_path}")
            return True
            
        except Exception as e:
            print(f"Error exporting settings: {e}")
            return False

    def import_settings(self, import_path):
        """Import settings from a specified path
        
        Args:
            import_path: Path to import settings from
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            if not os.path.exists(import_path):
                print(f"Import file not found: {import_path}")
                return False
            
            # Load import data
            with open(import_path, 'r') as f:
                import_data = json.load(f)
            
            # Import weighbridge settings
            if "weighbridge" in import_data:
                self.save_weighbridge_settings(import_data["weighbridge"])
                print("Weighbridge settings imported")
            
            # Import camera settings
            if "cameras" in import_data:
                self.save_camera_settings(import_data["cameras"])
                print("Camera settings imported")
            
            # Import sites (but not users for security)
            if "sites" in import_data:
                self.save_sites(import_data["sites"])
                print("Sites data imported")
            
            print(f"Settings imported from: {import_path}")
            return True
            
        except Exception as e:
            print(f"Error importing settings: {e}")
            return False