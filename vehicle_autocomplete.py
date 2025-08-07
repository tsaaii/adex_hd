import tkinter as tk

class VehicleAutocomplete:
    """Handles vehicle number autocomplete functionality"""
    
    def __init__(self, main_form):
        """Initialize vehicle autocomplete
        
        Args:
            main_form: Reference to the main form instance
        """
        self.main_form = main_form
        self.vehicle_numbers_cache = []
    
    def refresh_cache(self):
        """Refresh the cache of vehicle numbers for autocomplete"""
        self.vehicle_numbers_cache = self.get_vehicle_numbers()
        if hasattr(self.main_form, 'vehicle_entry'):
            self.main_form.vehicle_entry['values'] = self.vehicle_numbers_cache
    
    def get_vehicle_numbers(self):
        """Get a list of unique vehicle numbers from the database"""
        vehicle_numbers = []
        if hasattr(self.main_form, 'data_manager') and self.main_form.data_manager:
            records = self.main_form.data_manager.get_all_records()
            # Extract unique vehicle numbers from records
            for record in records:
                vehicle_no = record.get('vehicle_no', '')
                if vehicle_no and vehicle_no not in vehicle_numbers:
                    vehicle_numbers.append(vehicle_no)
        return vehicle_numbers
    
    def get_recent_vehicles(self, limit=5):
        """Get recent vehicle numbers for autocomplete"""
        try:
            if hasattr(self.main_form, 'data_manager') and self.main_form.data_manager:
                records = self.main_form.data_manager.get_all_records()
                # Get recent unique vehicle numbers
                recent_vehicles = []
                for record in reversed(records):  # Most recent first
                    vehicle_no = record.get('vehicle_no', '')
                    if vehicle_no and vehicle_no not in recent_vehicles:
                        recent_vehicles.append(vehicle_no)
                        if len(recent_vehicles) >= limit:
                            break
                return recent_vehicles
            return []
        except Exception as e:
            print(f"Error getting recent vehicles: {e}")
            return []
    
    def setup_vehicle_autocomplete(self):
        """Setup simplified vehicle autocomplete"""
        # Configure combobox for typing
        self.main_form.vehicle_entry.configure(state='normal')
        
        # Bind only essential events
        self.main_form.vehicle_entry.bind('<KeyRelease>', self.update_vehicle_autocomplete)
        self.main_form.vehicle_entry.bind('<Button-1>', self.on_vehicle_entry_click)
        self.main_form.vehicle_entry.bind('<FocusIn>', self.on_vehicle_entry_focus)
    
    def update_vehicle_autocomplete(self, event=None):
        """Update dropdown with filtered vehicle numbers"""
        current_text = self.main_form.vehicle_var.get().strip().upper()
        all_vehicles = self.get_vehicle_numbers()
        
        # Always update dropdown values
        if not current_text:
            # Show all vehicles when empty
            self.main_form.vehicle_entry['values'] = all_vehicles
        else:
            # Filter and sort matches
            exact_matches = []
            starts_with_matches = []
            contains_matches = []
            ends_with_matches = []
            
            for vehicle in all_vehicles:
                vehicle_upper = vehicle.upper()
                
                # Exact match (highest priority)
                if vehicle_upper == current_text:
                    exact_matches.append(vehicle)
                # Starts with match (second priority)
                elif vehicle_upper.startswith(current_text):
                    starts_with_matches.append(vehicle)
                # Ends with match (useful for vehicle numbers)
                elif vehicle_upper.endswith(current_text):
                    ends_with_matches.append(vehicle)
                # Contains match (lowest priority)
                elif current_text in vehicle_upper:
                    contains_matches.append(vehicle)
            
            # Combine all matches in priority order
            matches = exact_matches + starts_with_matches + ends_with_matches + contains_matches
            
            # Remove duplicates while preserving order
            seen = set()
            unique_matches = []
            for vehicle in matches:
                if vehicle not in seen:
                    seen.add(vehicle)
                    unique_matches.append(vehicle)
            
            # Update dropdown values - show matches or all vehicles if no matches
            self.main_form.vehicle_entry['values'] = unique_matches if unique_matches else all_vehicles
    
    def on_vehicle_entry_click(self, event=None):
        """Handle click on vehicle entry - simplified version"""
        current_text = self.main_form.vehicle_var.get().strip()
        
        if not current_text:
            # Show all vehicles for empty field
            all_vehicles = self.get_vehicle_numbers()
            self.main_form.vehicle_entry['values'] = all_vehicles
        else:
            # Update with current filtering
            self.update_vehicle_autocomplete()
        
        # Simple approach - just focus and update values
        self.main_form.vehicle_entry.focus_set()
    
    def on_vehicle_entry_focus(self, event=None):
        """Handle focus on vehicle entry - simplified version"""
        # Refresh vehicle cache
        self.refresh_cache()
        
        # Update autocomplete
        self.update_vehicle_autocomplete()