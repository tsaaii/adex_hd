import hashlib
import config

class HardcodedSettingsStorage:
    """Hardcoded settings storage that doesn't use JSON files"""
    
    def __init__(self):
        """Initialize with hardcoded values"""
        pass
    
    def hash_password(self, password):
        """Hash password using SHA-256"""
        return hashlib.sha256(password.encode()).hexdigest()
    
    def get_sites(self):
        """Get hardcoded sites data"""
        return {
            "sites": config.HARDCODED_SITES,
            "incharges": config.HARDCODED_INCHARGES,
            "transfer_parties": config.HARDCODED_TRANSFER_PARTIES,
            "agencies": config.HARDCODED_AGENCIES
        }
    
    def verify_settings_integrity(self):
        """Verify settings integrity using original storage"""
        return self._original_settings.verify_settings_integrity() if hasattr(self._original_settings, 'verify_settings_integrity') else True
    
    
    def get_users(self):
        """Get hardcoded users"""
        return {
            config.HARDCODED_USER: {
                "password": self.hash_password(config.HARDCODED_PASSWORD),
                "role": "admin",
                "name": "Administrator"
            }
        }
    
    def authenticate_user(self, username, password):
        """Authenticate user with hardcoded credentials"""
        if username == config.HARDCODED_USER:
            hashed_password = self.hash_password(password)
            stored_hash = self.hash_password(config.HARDCODED_PASSWORD)
            return (hashed_password == stored_hash, "admin")
        return (False, None)
    
    def isAuthenticated(self, username, password):
        """Check if user is authenticated"""
        success, role = self.authenticate_user(username, password)
        return success
    
    def isAdminUser(self, username):
        """Check if user is admin"""
        return username == config.HARDCODED_USER
    
    # Camera and weighbridge settings - delegate to original SettingsStorage
    def __init__(self):
        """Initialize with hardcoded values and original settings for cameras/weighbridge"""
        # Import here to avoid circular imports
        from settings_storage import SettingsStorage
        self._original_settings = SettingsStorage()
    
    def get_weighbridge_settings(self):
        """Get weighbridge settings from original settings storage"""
        return self._original_settings.get_weighbridge_settings()
    
    def save_weighbridge_settings(self, settings):
        """Save weighbridge settings using original settings storage"""
        return self._original_settings.save_weighbridge_settings(settings)
    
    def get_camera_settings(self):
        """Get camera settings from original settings storage"""
        return self._original_settings.get_camera_settings()
    
    def save_camera_settings(self, settings):
        """Save camera settings using original settings storage"""
        return self._original_settings.save_camera_settings(settings)
    
    # Other stub methods to maintain compatibility
    def save_sites(self, sites_data):
        return True
    
    def save_users(self, users):
        return True
    
    def get_ticket_counter(self):
        """Get ticket counter from original settings storage"""
        return self._original_settings.get_ticket_counter()
    
    def save_ticket_counter(self, counter):
        """Save ticket counter using original settings storage"""
        return self._original_settings.save_ticket_counter(counter)
    
    def check_integrity(self):
        """Check integrity using original settings storage"""
        return self._original_settings.check_integrity()
    
    def initialize_files(self):
        """Initialize files using original settings storage"""
        return self._original_settings.initialize_files()
    
    # Delegate other methods that might be needed
    def get_app_settings(self):
        """Get app settings from original storage"""
        return self._original_settings.get_app_settings() if hasattr(self._original_settings, 'get_app_settings') else {}
    
    def save_app_settings(self):
        """Save app settings using original storage"""
        return self._original_settings.save_app_settings() if hasattr(self._original_settings, 'save_app_settings') else True