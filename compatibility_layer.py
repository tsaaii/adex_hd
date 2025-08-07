"""
Compatibility layer to bridge optimized modules with existing code
"""

import sys
import importlib

class CompatibilityManager:
    """Manages compatibility between old and new modules"""
    
    def __init__(self):
        self.patches_applied = []
    
    def patch_camera_imports(self):
        """Patch camera module imports for compatibility"""
        try:
            import camera
            
            # Ensure all expected camera classes exist
            if hasattr(camera, 'OptimizedCameraView'):
                if not hasattr(camera, 'CameraView'):
                    camera.CameraView = camera.OptimizedCameraView
                if not hasattr(camera, 'RobustCameraView'):
                    camera.RobustCameraView = camera.OptimizedCameraView
                    
            self.patches_applied.append("camera_imports")
            print("✅ Camera compatibility patches applied")
            
        except Exception as e:
            print(f"⚠️ Camera compatibility patch failed: {e}")
    
    def patch_data_manager(self):
        """Patch DataManager for missing attributes"""
        try:
            import data_management
            
            # Patch the DataManager class if needed
            original_init = data_management.DataManager.__init__
            
            def patched_init(self, *args, **kwargs):
                original_init(self, *args, **kwargs)
                if not hasattr(self, 'is_shutting_down'):
                    self.is_shutting_down = False
                    
            data_management.DataManager.__init__ = patched_init
            self.patches_applied.append("data_manager")
            print("✅ DataManager compatibility patches applied")
            
        except Exception as e:
            print(f"⚠️ DataManager compatibility patch failed: {e}")
    
    def apply_all_patches(self):
        """Apply all compatibility patches"""
        self.patch_camera_imports()
        self.patch_data_manager()
        
        print(f"✅ Compatibility patches applied: {', '.join(self.patches_applied)}")