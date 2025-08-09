from tkinter import messagebox
import logging

class FormValidator:
    """FIXED: Handles form validation logic with correct pending vehicle validation"""
    
    def __init__(self, main_form):
        """Initialize form validator
        
        Args:
            main_form: Reference to the main form instance
        """
        self.main_form = main_form
        self.logger = logging.getLogger('FormValidator')
        self.logger.info("FormValidator initialized")
    
    def validate_basic_fields(self):
        """Validate that basic required fields are filled"""
        try:
            self.logger.info("Validating basic fields")
            
            # Get field values and strip whitespace
            ticket_no = self.main_form.rst_var.get().strip()
            vehicle_no = self.main_form.vehicle_var.get().strip()
            agency_name = self.main_form.agency_var.get().strip()
            material_type = self.main_form.material_type_var.get().strip()
            
            self.logger.info(f"Field values: ticket='{ticket_no}', vehicle='{vehicle_no}', agency='{agency_name}', material_type='{material_type}'")
            
            required_fields = {
                "Ticket No": ticket_no,
                "Vehicle No": vehicle_no,
                "Agency Name": agency_name,
                "Material Type": material_type
            }
            
            missing_fields = [field for field, value in required_fields.items() if not value]
            
            if missing_fields:
                error_msg = f"Please fill in the following required fields: {', '.join(missing_fields)}"
                self.logger.error(f"Basic validation failed: {error_msg}")
                messagebox.showerror("Validation Error", error_msg)
                return False
            
            self.logger.info("Basic validation passed")
            return True
            
        except Exception as e:
            self.logger.error(f"Error in basic validation: {e}")
            return False
    
    def validate_weighment_data(self):
        """Validate weighment data consistency"""
        try:
            self.logger.info("Validating weighment data")
            
            first_weight = self.main_form.first_weight_var.get().strip()
            first_timestamp = self.main_form.first_timestamp_var.get().strip()
            second_weight = self.main_form.second_weight_var.get().strip()
            second_timestamp = self.main_form.second_timestamp_var.get().strip()
            
            self.logger.info(f"Weighment data: first_weight='{first_weight}', first_timestamp='{first_timestamp}', "
                        f"second_weight='{second_weight}', second_timestamp='{second_timestamp}'")
            
            # Check for consistent weighment data
            if first_weight and not first_timestamp:
                error_msg = "First weighment timestamp is missing"
                self.logger.error(error_msg)
                messagebox.showerror("Validation Error", error_msg)
                return False
            
            if second_weight and not second_timestamp:
                error_msg = "Second weighment timestamp is missing"
                self.logger.error(error_msg)
                messagebox.showerror("Validation Error", error_msg)
                return False
            
            # For new entries, first weighment is required UNLESS we're in test mode
            if self.main_form.current_weighment == "first" and not first_weight:
                # Check if test mode is enabled
                try:
                    if hasattr(self.main_form, 'weight_manager'):
                        weight_manager = self.main_form.weight_manager
                        if hasattr(weight_manager, 'is_test_mode_enabled') and weight_manager.is_test_mode_enabled():
                            # In test mode, we can generate weight on demand
                            self.logger.info("Test mode enabled - weight can be generated on capture")
                            return True
                except:
                    pass
                    
                error_msg = "Please capture first weighment before saving"
                self.logger.error(error_msg)
                messagebox.showerror("Validation Error", error_msg)
                return False
            
            self.logger.info("Weighment validation passed")
            return True
            
        except Exception as e:
            self.logger.error(f"Error in weighment validation: {e}")
            return False

    def find_main_app(self):
        """Find the main app instance properly"""
        try:
            # Use the main form's find_main_app method which is properly implemented
            if hasattr(self.main_form, 'find_main_app'):
                app = self.main_form.find_main_app()
                if app:
                    self.logger.info("Found main app via main_form.find_main_app()")
                    return app
            
            # Alternative method: Check if main_form has data_manager directly
            if hasattr(self.main_form, 'data_manager') and self.main_form.data_manager:
                # Create a mock app object with the data_manager
                class MockApp:
                    def __init__(self, data_manager):
                        self.data_manager = data_manager
                
                self.logger.info("Using data_manager from main_form directly")
                return MockApp(self.main_form.data_manager)
            
            # Try to traverse up the widget hierarchy
            widget = self.main_form.parent
            attempts = 0
            max_attempts = 15
            
            while widget and attempts < max_attempts:
                attempts += 1
                
                # Check for main app indicators
                if hasattr(widget, 'data_manager') and widget.data_manager:
                    self.logger.info(f"Found main app with data_manager at level {attempts}")
                    return widget
                
                # Check class name for app identification
                if hasattr(widget, '__class__'):
                    class_name = widget.__class__.__name__
                    if 'App' in class_name and hasattr(widget, 'data_manager'):
                        self.logger.info(f"Found app class with data_manager: {class_name}")
                        return widget
                
                # Try different parent references
                if hasattr(widget, 'master') and widget.master:
                    widget = widget.master
                elif hasattr(widget, 'parent') and widget.parent:
                    widget = widget.parent
                elif hasattr(widget, 'winfo_parent'):
                    try:
                        parent_name = widget.winfo_parent()
                        if parent_name:
                            widget = widget._root().nametowidget(parent_name)
                        else:
                            break
                    except Exception:
                        break
                else:
                    break
            
            self.logger.warning(f"Could not find main app after {attempts} attempts")
            return None
            
        except Exception as e:
            self.logger.error(f"Error finding main app: {e}")
            return None

    def validate_vehicle_not_in_pending_for_new_weighment(self, operation_type="save"):
        """FIXED: Check if vehicle is pending ONLY for NEW first weighments
        
        Args:
            operation_type: Type of operation - "save", "image", "weight" etc.
            
        Returns:
            bool: True if operation is allowed, False if blocked
        """
        try:
            vehicle_no = self.main_form.vehicle_var.get().strip().upper()
            
            if not vehicle_no:
                return True  # Empty vehicle number will be caught by other validation
            
            # CRITICAL FIX: Check the current weighment state
            current_weighment = getattr(self.main_form, 'current_weighment', 'first')
            
            # If this is a SECOND weighment, ALWAYS allow it (even if vehicle was pending)
            if current_weighment == "second":
                self.logger.info(f"ALLOWING {operation_type} - This is a SECOND weighment for vehicle {vehicle_no}")
                return True
            
            # Only check pending status for FIRST weighments
            self.logger.info(f"STRICT CHECK: Checking if vehicle {vehicle_no} is already pending (for FIRST weighment)")
            
            # Get the main app to access data manager
            app = self.find_main_app()
            if not app or not hasattr(app, 'data_manager') or not app.data_manager:
                self.logger.error("CRITICAL: Cannot access data manager - this means we cannot verify vehicle status")
                
                # Show a user-friendly error message
                error_msg = (f"🔧 System Configuration Issue\n\n"
                           f"The system cannot verify if vehicle {vehicle_no} is already pending.\n"
                           f"This is a safety check to prevent duplicate records.\n\n"
                           f"Please check:\n"
                           f"1. The application is properly initialized\n"
                           f"2. Data files are accessible\n"
                           f"3. Try restarting the application\n\n"
                           f"For safety, this operation is blocked until the issue is resolved.")
                
                messagebox.showerror("System Configuration Error", error_msg)
                return False  # BLOCK for safety
            
            # Get all records and check for pending vehicles
            try:
                records = app.data_manager.get_all_records()
                self.logger.info(f"Successfully retrieved {len(records)} records for validation")
            except Exception as e:
                self.logger.error(f"Failed to get records from data manager: {e}")
                messagebox.showerror("Database Error", 
                                   f"Cannot access vehicle records to verify status.\n"
                                   f"Error: {str(e)}\n\n"
                                   f"Operation blocked for data safety.")
                return False  # BLOCK for safety
            
            for record in records:
                record_vehicle = record.get('vehicle_no', '').strip().upper()
                
                if record_vehicle == vehicle_no:
                    # Check if this vehicle has a pending record (first weighment but no second)
                    first_weight = record.get('first_weight', '').strip()
                    first_timestamp = record.get('first_timestamp', '').strip()
                    has_first = first_weight != '' and first_timestamp != ''
                    
                    second_weight = record.get('second_weight', '').strip()
                    second_timestamp = record.get('second_timestamp', '').strip()
                    missing_second = (second_weight == '' or second_timestamp == '')
                    
                    if has_first and missing_second:
                        # Vehicle is already in pending list - BLOCK NEW FIRST WEIGHMENT
                        pending_ticket = record.get('ticket_no', 'Unknown')
                        error_msg = (f"🚫 OPERATION BLOCKED\n\n"
                                   f"Vehicle {vehicle_no} already has a pending record!\n\n"
                                   f"🎫 Pending Ticket: {pending_ticket}\n"
                                   f"⚖️ First Weight: {first_weight} kg\n"
                                   f"🕐 First Time: {first_timestamp}\n\n"
                                   f"❌ You CANNOT create a new record for this vehicle.\n"
                                   f" You MUST complete the SECOND weighment first.\n\n"
                                   f" Click on Pending Vehicles panel → Select ticket {pending_ticket} → Complete second weighment")
                        
                        self.logger.error(f"BLOCKED: Vehicle {vehicle_no} already in pending list with ticket {pending_ticket}")
                        
                        # Show BLOCKING error message
                        messagebox.showerror("Vehicle Already Pending - Operation Blocked", error_msg)
                        return False  # STRICT BLOCK
            
            self.logger.info(f"Vehicle {vehicle_no} not in pending list - NEW first weighment operation allowed")
            return True
            
        except Exception as e:
            self.logger.error(f"CRITICAL ERROR checking pending vehicles: {e}")
            # STRICT: If there's an error, BLOCK the operation for safety
            messagebox.showerror("System Error", 
                               f"Critical error checking vehicle status.\n"
                               f"Operation blocked for data integrity.\n\n"
                               f"Error: {str(e)}\n\n"
                               f"Please restart the application.")
            return False  # STRICT BLOCK on errors

    def validate_form(self):
        """ENHANCED: Validate all form fields before saving - FIXED pending logic"""
        try:
            self.logger.info("Starting comprehensive form validation")
            
            # Step 1: Validate basic required fields
            if not self.validate_basic_fields():
                return False
            
            # Step 2: FIXED - Check if vehicle is pending ONLY for NEW first weighments
            current_weighment = getattr(self.main_form, 'current_weighment', 'first')
            if current_weighment == "first":
                # Only check pending for NEW first weighments
                if not self.validate_vehicle_not_in_pending_for_new_weighment("save"):
                    return False
            else:
                # For second weighments, allow even if vehicle was pending
                self.logger.info("SECOND weighment - skipping pending check (this is correct)")
            
            # Step 3: Validate weighment data
            if not self.validate_weighment_data():
                return False
            
            # Step 4: Validate images (optional but warn user)
            if not self.validate_images():
                # Images validation failed, but ask user if they want to continue
                result = messagebox.askyesno("Missing Images", 
                                        "No images have been captured for this weighment. "
                                        "Continue without images?")
                if not result:
                    self.logger.info("User chose not to continue without images")
                    return False
                else:
                    self.logger.info("User chose to continue without images")
            
            self.logger.info("Form validation passed successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Error in form validation: {e}")
            return False
    
    def validate_images(self):
        """Validate that at least one image is captured for current weighment"""
        try:
            current_weighment = self.main_form.current_weighment
            self.logger.info(f"Validating images for {current_weighment} weighment")
            
            if current_weighment == "first":
                # Check first weighment images
                front_image = self.main_form.first_front_image_path
                back_image = self.main_form.first_back_image_path
            else:
                # Check second weighment images
                front_image = self.main_form.second_front_image_path
                back_image = self.main_form.second_back_image_path
            
            has_images = bool(front_image or back_image)
            self.logger.info(f"Images validation for {current_weighment}: front={bool(front_image)}, back={bool(back_image)}")
            
            return has_images
            
        except Exception as e:
            self.logger.error(f"Error validating images: {e}")
            return False
    
    def validate_vehicle_number(self):
        """Validate that vehicle number is entered before capturing images"""
        try:
            vehicle_no = self.main_form.vehicle_var.get().strip()
            
            if not vehicle_no:
                error_msg = "Please enter a vehicle number before capturing images."
                self.logger.error(f"Vehicle validation failed: {error_msg}")
                messagebox.showerror("Error", error_msg)
                return False
            
            self.logger.info(f"Vehicle validation passed: {vehicle_no}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error validating vehicle number: {e}")
            return False
    
    def validate_numeric_field(self, value, field_name):
        """Validate that a field contains a valid numeric value"""
        try:
            if not value or not value.strip():
                return True  # Empty is okay, will be handled by required field validation
            
            float_value = float(value.strip())
            
            if float_value < 0:
                error_msg = f"{field_name} cannot be negative"
                self.logger.error(error_msg)
                messagebox.showerror("Validation Error", error_msg)
                return False
            
            if float_value > 999999:  # Reasonable upper limit
                error_msg = f"{field_name} value seems too large"
                self.logger.error(error_msg)
                messagebox.showerror("Validation Error", error_msg)
                return False
            
            return True
            
        except ValueError:
            error_msg = f"{field_name} must be a valid number"
            self.logger.error(error_msg)
            messagebox.showerror("Validation Error", error_msg)
            return False
        except Exception as e:
            self.logger.error(f"Error validating numeric field {field_name}: {e}")
            return False