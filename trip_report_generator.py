"""
Trip Report Generator
=====================

Dedicated module for generating individual trip PDF reports for complete weighbridge records.
This handles single record PDF generation with 4-image grid layout and high-quality formatting.

Author: Swaccha Andhra Corporation
Created: 2025
"""

import os
import datetime
import json
import cv2
from tkinter import messagebox

# Try to import required PDF libraries
try:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image as RLImage, PageBreak
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False
    print("ReportLab not available - PDF generation disabled")

import config


class TripReportGenerator:
    """
    Handles individual trip report PDF generation for complete weighbridge records
    """
    
    def __init__(self):
        """Initialize the trip report generator"""
        self.address_config = self.load_address_config()
        
        # Ensure reports folder exists
        self.reports_folder = config.REPORTS_FOLDER
        os.makedirs(self.reports_folder, exist_ok=True)
        
        # Create today's subfolder
        today = datetime.datetime.now().strftime("%Y-%m-%d")
        self.todays_folder = os.path.join(self.reports_folder, today)
        os.makedirs(self.todays_folder, exist_ok=True)
    
    def load_address_config(self):
        """Load address configuration from JSON file"""
        try:
            config_file = os.path.join(config.DATA_FOLDER, 'address_config.json')
            if os.path.exists(config_file):
                with open(config_file, 'r') as f:
                    return json.load(f)
            else:
                # Create default config
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
                        },
                        "Addanki": {
                            "name": "Addanki Collection Center",
                            "address": "Main Road, Addanki\nAndhra Pradesh - 523201",
                            "contact": "+91-9876543211"
                        }
                    }
                }
                
                # Save default config
                os.makedirs(config.DATA_FOLDER, exist_ok=True)
                with open(config_file, 'w') as f:
                    json.dump(default_config, f, indent=4)
                
                return default_config
        except Exception as e:
            print(f"Error loading address config: {e}")
            return {"agencies": {}, "sites": {}}
    
    def is_record_complete(self, record_data):
        """
        Check if a record is complete (has both weighments)
        
        Args:
            record_data (dict): Record data dictionary
            
        Returns:
            bool: True if record is complete, False otherwise
        """
        try:
            first_weight = record_data.get('first_weight', '').strip()
            second_weight = record_data.get('second_weight', '').strip()
            
            return bool(first_weight and second_weight)
        except Exception as e:
            print(f"Error checking record completeness: {e}")
            return False
    
    def generate_trip_report_filename(self, record_data):
        """
        Generate filename for trip report based on record data
        
        Args:
            record_data (dict): Record data dictionary
            
        Returns:
            str: Generated filename
        """
        try:
            # Get data with safe replacements
            ticket_no = record_data.get('ticket_no', 'Unknown').replace('/', '_').replace(' ', '_')
            vehicle_no = record_data.get('vehicle_no', 'Unknown').replace('/', '_').replace(' ', '_')
            site_name = record_data.get('site_name', 'Unknown').replace(' ', '_').replace('/', '_')
            agency_name = record_data.get('agency_name', 'Unknown').replace(' ', '_').replace('/', '_')
            timestamp = datetime.datetime.now().strftime("%H%M%S")
            
            # PDF filename format: AgencyName_SiteName_TicketNo_VehicleNo_HHMMSS.pdf
            filename = f"{agency_name}_{site_name}_{ticket_no}_{vehicle_no}_{timestamp}.pdf"
            
            return filename
            
        except Exception as e:
            print(f"Error generating filename: {e}")
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            return f"TripReport_{timestamp}.pdf"
    
    def create_trip_report_pdf(self, record_data, save_path=None):
        """
        Create trip report PDF for a single complete record
        
        Args:
            record_data (dict): Record data dictionary
            save_path (str, optional): Custom save path. If None, auto-generated in today's folder
            
        Returns:
            tuple: (success: bool, pdf_path: str or None)
        """
        if not REPORTLAB_AVAILABLE:
            print("ReportLab not available - cannot generate PDF")
            return False, None
        
        if not self.is_record_complete(record_data):
            print("Record is not complete - cannot generate trip report")
            return False, None
        
        # Initialize temp files list
        self._temp_files = []
        
        try:
            # Generate save path if not provided
            if save_path is None:
                filename = self.generate_trip_report_filename(record_data)
                save_path = os.path.join(self.todays_folder, filename)
            
            # Ensure directory exists
            os.makedirs(os.path.dirname(save_path), exist_ok=True)
            
            # Create PDF document
            doc = SimpleDocTemplate(save_path, pagesize=A4,
                                    rightMargin=20, leftMargin=20, topMargin=20, bottomMargin=20)
            
            # Build PDF content
            elements = self.build_pdf_content(record_data)
            
            # Generate PDF
            doc.build(elements)
            
            print(f" Trip Report PDF generated successfully: {save_path}")
            return True, save_path
            
        except Exception as e:
            print(f"❌ Error creating trip report PDF: {e}")
            import traceback
            print(f"Detailed error: {traceback.format_exc()}")
            return False, None
        finally:
            # Clean up temporary files after PDF generation
            self.cleanup_temp_files()
    
    def build_pdf_content(self, record_data):
        """
        Build PDF content elements for the trip report
        
        Args:
            record_data (dict): Record data dictionary
            
        Returns:
            list: List of ReportLab elements
        """
        elements = []
        
        # Define styles
        styles = self.get_pdf_styles()
        
        # Header section
        elements.extend(self.create_header_section(record_data, styles))
        
        # Vehicle information section
        elements.extend(self.create_vehicle_info_section(record_data, styles))
        
        # Weighment details section
        elements.extend(self.create_weighment_section(record_data, styles))
        
        # Images section (4-image grid)
        elements.extend(self.create_images_section(record_data, styles))
        
        # Signature section
        elements.extend(self.create_signature_section(styles))
        
        return elements
    
    def get_pdf_styles(self):
        """Get PDF paragraph styles"""
        base_styles = getSampleStyleSheet()
        
        custom_styles = {
            'header': ParagraphStyle(
                name='HeaderStyle',
                fontSize=18,
                alignment=TA_CENTER,
                fontName='Helvetica-Bold',
                textColor=colors.black,
                spaceAfter=6,
                spaceBefore=6
            ),
            'subheader': ParagraphStyle(
                name='SubHeaderStyle',
                fontSize=12,
                alignment=TA_CENTER,
                fontName='Helvetica',
                textColor=colors.black,
                spaceAfter=12
            ),
            'section_header': ParagraphStyle(
                name='SectionHeader',
                fontSize=13,
                alignment=TA_CENTER,
                fontName='Helvetica-Bold',
                textColor=colors.black,
                spaceAfter=6,
                spaceBefore=6
            ),
            'label': ParagraphStyle(
                name='LabelStyle',
                fontSize=11,
                fontName='Helvetica-Bold',
                textColor=colors.black
            ),
            'value': ParagraphStyle(
                name='ValueStyle',
                fontSize=11,
                fontName='Helvetica',
                textColor=colors.black
            )
        }
        
        return custom_styles
    
    def create_header_section(self, record_data, styles):
        """Create PDF header section with agency information"""
        elements = []
        
        # Get agency information
        agency_name = record_data.get('agency_name', 'Unknown Agency')
        agency_info = self.address_config.get('agencies', {}).get(agency_name, {})
        
        # Agency header
        elements.append(Paragraph(agency_info.get('name', agency_name), styles['header']))
        
        # Agency address
        if agency_info.get('address'):
            address_text = agency_info.get('address', '').replace('\n', '<br/>')
            elements.append(Paragraph(address_text, styles['subheader']))
        
        # Contact information
        contact_info = []
        if agency_info.get('contact'):
            contact_info.append(f"Phone: {agency_info.get('contact')}")
        if agency_info.get('email'):
            contact_info.append(f"Email: {agency_info.get('email')}")
        
        if contact_info:
            elements.append(Paragraph(" | ".join(contact_info), styles['subheader']))
        
        elements.append(Spacer(1, 0.2*inch))
        
        # Print date and ticket information
        print_date = datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        ticket_no = record_data.get('ticket_no', '000')
        
        elements.append(Paragraph(f"Print Date: {print_date}", styles['value']))
        elements.append(Paragraph(f"Ticket No: {ticket_no}", styles['header']))
        elements.append(Spacer(1, 0.15*inch))
        
        return elements
    
    def create_vehicle_info_section(self, record_data, styles):
        """Create vehicle information section"""
        elements = []
        
        # Section header
        elements.append(Paragraph("VEHICLE INFORMATION", styles['section_header']))
        
        # Get values with fallbacks
        material_value = record_data.get('material', '') or record_data.get('material', '')
        user_name_value = record_data.get('user_name', '') or "Not specified"
        site_incharge_value = record_data.get('site_incharge', '') or "Not specified"
        
        # Create vehicle information table
        vehicle_data = [
            [Paragraph("<b>Vehicle No:</b>", styles['label']), Paragraph(record_data.get('vehicle_no', ''), styles['value']), 
             Paragraph("<b>Date:</b>", styles['label']), Paragraph(record_data.get('date', ''), styles['value']), 
             Paragraph("<b>Time:</b>", styles['label']), Paragraph(record_data.get('time', ''), styles['value'])],
            [Paragraph("<b>Material:</b>", styles['label']), Paragraph(material_value, styles['value']), 
             Paragraph("<b>Site Name:</b>", styles['label']), Paragraph(record_data.get('site_name', ''), styles['value']), 
             Paragraph("<b>Transfer Party:</b>", styles['label']), Paragraph(record_data.get('transfer_party_name', ''), styles['value'])],
            [Paragraph("<b>Agency Name:</b>", styles['label']), Paragraph(record_data.get('agency_name', ''), styles['value']), 
             Paragraph("<b>User Name:</b>", styles['label']), Paragraph(user_name_value, styles['value']), 
             Paragraph("<b>Site Incharge:</b>", styles['label']), Paragraph(site_incharge_value, styles['value'])]
        ]
        
        vehicle_inner_table = Table(vehicle_data, colWidths=[1.2*inch, 1.3*inch, 1.0*inch, 1.3*inch, 1.2*inch, 1.5*inch])
        vehicle_inner_table.setStyle(TableStyle([
            ('FONTNAME', (0,0), (-1,-1), 'Helvetica'),
            ('FONTSIZE', (0,0), (-1,-1), 12),
            ('ALIGN', (0,0), (-1,-1), 'LEFT'),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ('LEFTPADDING', (0,0), (-1,-1), 2),
            ('RIGHTPADDING', (0,0), (-1,-1), 2),
            ('TOPPADDING', (0,0), (-1,-1), 4),
            ('BOTTOMPADDING', (0,0), (-1,-1), 4),
        ]))
        
        # Wrap in bordered table
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
        
        return elements
    
    def create_weighment_section(self, record_data, styles):
        """Create weighment details section"""
        elements = []
        
        # Section header
        elements.append(Paragraph("WEIGHMENT DETAILS", styles['section_header']))
        
        # Get weight values
        first_weight_str = record_data.get('first_weight', '').strip()
        second_weight_str = record_data.get('second_weight', '').strip()
        net_weight_str = record_data.get('net_weight', '').strip()
        
        # Calculate net weight if not present
        if not net_weight_str and first_weight_str and second_weight_str:
            try:
                first_weight = float(first_weight_str)
                second_weight = float(second_weight_str)
                calculated_net = abs(first_weight - second_weight)
                net_weight_str = f"{calculated_net:.2f}"
            except (ValueError, TypeError):
                net_weight_str = "Calculation Error"
        
        # Format display weights
        first_weight_display = f"{first_weight_str} kg" if first_weight_str else "Not captured"
        second_weight_display = f"{second_weight_str} kg" if second_weight_str else "Not captured"
        net_weight_display = f"{net_weight_str} kg" if net_weight_str and net_weight_str not in ["Not Available", "Unable to calculate", "Calculation Error"] else net_weight_str or "Not Available"
        
        # Create weighment table
        weighment_data = [
            [Paragraph("<b>First Weight:</b>", styles['label']), Paragraph(first_weight_display, styles['value']), 
             Paragraph("<b>First Time:</b>", styles['label']), Paragraph(record_data.get('first_timestamp', '') or "Not captured", styles['value'])],
            [Paragraph("<b>Second Weight:</b>", styles['label']), Paragraph(second_weight_display, styles['value']), 
             Paragraph("<b>Second Time:</b>", styles['label']), Paragraph(record_data.get('second_timestamp', '') or "Not captured", styles['value'])],
            [Paragraph("<b>Net Weight:</b>", styles['label']), Paragraph(net_weight_display, styles['value'])]
        ]
        
        weighment_inner_table = Table(weighment_data, colWidths=[1.5*inch, 1.5*inch, 1.2*inch, 2.8*inch])
        weighment_inner_table.setStyle(TableStyle([
            ('FONTNAME', (0,0), (-1,-1), 'Helvetica'),
            ('FONTSIZE', (0,0), (-1,-1), 12),
            ('ALIGN', (0,0), (-1,-1), 'LEFT'),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ('LEFTPADDING', (0,0), (-1,-1), 2),
            ('RIGHTPADDING', (0,0), (-1,-1), 2),
            ('TOPPADDING', (0,0), (-1,-1), 4),
            ('BOTTOMPADDING', (0,0), (-1,-1), 4),
            ('SPAN', (2,2), (3,2)),
            ('ALIGN', (2,2), (3,2), 'RIGHT'),
        ]))
        
        # Wrap in bordered table
        weighment_table = Table([[weighment_inner_table]], colWidths=[7.5*inch])
        weighment_table.setStyle(TableStyle([
            ('GRID', (0,0), (-1,-1), 1, colors.black),
            ('LEFTPADDING', (0,0), (-1,-1), 12),
            ('RIGHTPADDING', (0,0), (-1,-1), 12),
            ('TOPPADDING', (0,0), (-1,-1), 8),
            ('BOTTOMPADDING', (0,0), (-1,-1), 8),
            ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ]))
        
        elements.append(weighment_table)
        elements.append(Spacer(1, 0.15*inch))
        
        return elements
    
    def create_images_section(self, record_data, styles):
        """Create 4-image grid section"""
        elements = []
        
        # Section header
        elements.append(Paragraph("VEHICLE IMAGES (4-Image System)", styles['section_header']))
        
        # Get ticket number for watermark
        ticket_no = record_data.get('ticket_no', '000')
        
        # Get all 4 image paths
        first_front_img_path = os.path.join(config.IMAGES_FOLDER, record_data.get('first_front_image', ''))
        first_back_img_path = os.path.join(config.IMAGES_FOLDER, record_data.get('first_back_image', ''))
        second_front_img_path = os.path.join(config.IMAGES_FOLDER, record_data.get('second_front_image', ''))
        second_back_img_path = os.path.join(config.IMAGES_FOLDER, record_data.get('second_back_image', ''))
        
        # Create 2x2 image grid with headers
        img_data = [
            ["1ST WEIGHMENT - FRONT", "1ST WEIGHMENT - BACK"],
            [None, None],  # Will be filled with first weighment images
            ["2ND WEIGHMENT - FRONT", "2ND WEIGHMENT - BACK"], 
            [None, None]   # Will be filled with second weighment images
        ]
        
        # Calculate image dimensions
        IMG_WIDTH = 3.5*inch  # Slightly reduced to fit better on A4
        IMG_HEIGHT = 2.6*inch
        
        # Process images with high-quality method
        first_front_img = self.process_image_for_pdf(first_front_img_path, f"Ticket: {ticket_no} - 1st Front", IMG_WIDTH, IMG_HEIGHT)
        first_back_img = self.process_image_for_pdf(first_back_img_path, f"Ticket: {ticket_no} - 1st Back", IMG_WIDTH, IMG_HEIGHT)
        second_front_img = self.process_image_for_pdf(second_front_img_path, f"Ticket: {ticket_no} - 2nd Front", IMG_WIDTH, IMG_HEIGHT)
        second_back_img = self.process_image_for_pdf(second_back_img_path, f"Ticket: {ticket_no} - 2nd Back", IMG_WIDTH, IMG_HEIGHT)
        
        # Fill the image grid
        img_data[1] = [first_front_img or "1st Front\nImage not available", 
                       first_back_img or "1st Back\nImage not available"]
        img_data[3] = [second_front_img or "2nd Front\nImage not available", 
                       second_back_img or "2nd Back\nImage not available"]
        
        # Create images table
        img_table = Table(img_data, 
                         colWidths=[IMG_WIDTH, IMG_WIDTH],
                         rowHeights=[0.3*inch, IMG_HEIGHT, 0.3*inch, IMG_HEIGHT])
        img_table.setStyle(TableStyle([
            ('GRID', (0,0), (-1,-1), 0.5, colors.black),
            ('FONTNAME', (0,0), (-1,-1), 'Helvetica-Bold'),
            ('FONTSIZE', (0,0), (1,0), 12),
            ('FONTSIZE', (0,2), (1,2), 12),
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
        
        return elements
    
    def create_signature_section(self, styles):
        """Create signature section"""
        elements = []
        
        # Add spacing
        elements.append(Spacer(1, 0.3*inch))
        
        # Signature line
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
        
        return elements
    
    def process_image_for_pdf(self, image_path, watermark_text, width, height):
        """
        Process image for PDF with high quality (no additional watermark since images already have them)
        
        Args:
            image_path (str): Path to image file
            watermark_text (str): Text for watermark (not used since images already watermarked)
            width (float): Target width in ReportLab units
            height (float): Target height in ReportLab units
            
        Returns:
            RLImage or None: Processed ReportLab Image object
        """
        if not image_path or not os.path.exists(image_path):
            print(f"Image not found: {image_path}")
            return None
            
        try:
            # Prepare high-quality image (no additional watermark since images already have them)
            temp_path = self.prepare_image_with_watermark(image_path, watermark_text, add_watermark=False)
            if temp_path and os.path.exists(temp_path):
                # Create ReportLab Image object
                img = RLImage(temp_path, width=width, height=height)
                
                # Store temp path for later cleanup (don't delete immediately)
                if not hasattr(self, '_temp_files'):
                    self._temp_files = []
                self._temp_files.append(temp_path)
                
                return img
            else:
                print(f"Failed to create temporary image for: {image_path}")
                return None
        except Exception as e:
            print(f"Error processing image for PDF: {e}")
            import traceback
            print(f"Detailed error: {traceback.format_exc()}")
            return None
        
        return None
    
    def cleanup_temp_files(self):
        """Clean up temporary files after PDF generation"""
        if hasattr(self, '_temp_files'):
            for temp_file in self._temp_files:
                try:
                    if os.path.exists(temp_file):
                        os.remove(temp_file)
                        print(f"Cleaned up temp file: {temp_file}")
                except Exception as e:
                    print(f"Warning: Could not clean up temp file {temp_file}: {e}")
            self._temp_files = []
    
    def prepare_image_with_watermark(self, image_path, watermark_text, add_watermark=False):
        """
        Prepare image with high quality processing and optional watermark
        
        Args:
            image_path (str): Path to original image
            watermark_text (str): Text to add as watermark (if add_watermark=True)
            add_watermark (bool): Whether to add watermark (default False since images already have them)
            
        Returns:
            str or None: Path to temporary processed image file
        """
        try:
            # Verify the source image exists
            if not os.path.exists(image_path):
                print(f"❌ Source image not found: {image_path}")
                return None
            
            print(f"📷 Processing image: {os.path.basename(image_path)}")
            
            # Read image
            img = cv2.imread(image_path)
            if img is None:
                print(f"❌ Could not read image: {image_path}")
                return None
            
            # Get original dimensions
            original_height, original_width = img.shape[:2]
            print(f"📐 Original image size: {original_width}x{original_height}")
            
            # Calculate new dimensions while maintaining aspect ratio
            max_width = 1200   # High quality
            max_height = 900   # High quality
            
            # Calculate scaling factor
            scale_w = max_width / original_width
            scale_h = max_height / original_height
            scale = min(scale_w, scale_h)
            
            new_width = int(original_width * scale)
            new_height = int(original_height * scale)
            
            print(f"📐 Resized image size: {new_width}x{new_height} (scale: {scale:.3f})")
            
            # Use high-quality interpolation
            img_resized = cv2.resize(img, (new_width, new_height), interpolation=cv2.INTER_LANCZOS4)
            
            # Only add watermark if explicitly requested (images already have watermarks)
            if add_watermark:
                try:
                    from camera import add_watermark
                    watermarked_img = add_watermark(img_resized, watermark_text)
                    print(f"💧 Added additional watermark: {watermark_text}")
                except ImportError:
                    print("⚠️  Watermark function not available, using image as-is")
                    watermarked_img = img_resized
                except Exception as watermark_error:
                    print(f"⚠️  Watermark error: {watermark_error}, using image as-is")
                    watermarked_img = img_resized
            else:
                # Use image as-is (already has watermark from camera capture)
                watermarked_img = img_resized
                print(f"📷 Using existing watermark from camera capture")
            
            # Create unique temporary filename
            timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S_%f')
            original_name = os.path.splitext(os.path.basename(image_path))[0]
            temp_filename = f"trip_temp_{original_name}_{timestamp}.jpg"
            temp_path = os.path.join(config.IMAGES_FOLDER, temp_filename)
            
            # Ensure images folder exists
            os.makedirs(config.IMAGES_FOLDER, exist_ok=True)
            
            # Save with high quality (95% JPEG quality)
            success = cv2.imwrite(temp_path, watermarked_img, [int(cv2.IMWRITE_JPEG_QUALITY), 95])
            
            if success:
                print(f"💾 Prepared high-quality image: {temp_path}")
                # Verify the file was actually created
                if os.path.exists(temp_path):
                    file_size = os.path.getsize(temp_path)
                    print(f" Temp file verified: {file_size} bytes")
                    return temp_path
                else:
                    print(f"❌ Temp file not found after creation: {temp_path}")
                    return None
            else:
                print(f"❌ Failed to save temporary image: {temp_path}")
                return None
            
        except Exception as e:
            print(f"❌ Error preparing image with watermark: {e}")
            import traceback
            print(f"Detailed error: {traceback.format_exc()}")
            return None
    
    def auto_generate_trip_report(self, record_data):
        """
        Automatically generate trip report for a complete record
        
        Args:
            record_data (dict): Record data dictionary
            
        Returns:
            tuple: (success: bool, pdf_path: str or None)
        """
        try:
            print(f"🚀 AUTO-GENERATING Trip Report for Ticket: {record_data.get('ticket_no', 'Unknown')}")
            
            # Check if record is complete
            if not self.is_record_complete(record_data):
                print("⚠️  Record is not complete - skipping auto-generation")
                return False, None
            
            # Generate the PDF
            success, pdf_path = self.create_trip_report_pdf(record_data)
            
            if success:
                print(f" Auto-generated trip report: {pdf_path}")
                
                # Optional: Show success message
                try:
                    from tkinter import messagebox
                    messagebox.showinfo("Trip Report Generated", 
                                      f"Trip report generated successfully!\n\n"
                                      f"File: {os.path.basename(pdf_path)}\n"
                                      f"Location: {self.todays_folder}")
                except:
                    pass  # GUI not available
                
                return True, pdf_path
            else:
                print("❌ Failed to auto-generate trip report")
                return False, None
                
        except Exception as e:
            print(f"❌ Error in auto-generation: {e}")
            return False, None


# Convenience functions for external usage
def generate_trip_report(record_data, save_path=None):
    """
    Generate trip report PDF for a single record
    
    Args:
        record_data (dict): Record data dictionary
        save_path (str, optional): Custom save path
        
    Returns:
        tuple: (success: bool, pdf_path: str or None)
    """
    generator = TripReportGenerator()
    return generator.create_trip_report_pdf(record_data, save_path)


def auto_generate_on_completion(record_data):
    """
    Automatically generate trip report when a record is completed
    
    Args:
        record_data (dict): Record data dictionary
        
    Returns:
        tuple: (success: bool, pdf_path: str or None)
    """
    generator = TripReportGenerator()
    return generator.auto_generate_trip_report(record_data)


def is_record_complete(record_data):
    """
    Check if a record is complete (has both weighments)
    
    Args:
        record_data (dict): Record data dictionary
        
    Returns:
        bool: True if record is complete, False otherwise
    """
    generator = TripReportGenerator()
    return generator.is_record_complete(record_data)


# Example usage
if __name__ == "__main__":
    # Example record data
    sample_record = {
        'ticket_no': 'T001',
        'vehicle_no': 'AP01AB1234',
        'date': '09-08-2025',
        'time': '14:30:00',
        'agency_name': 'Tharuni',
        'site_name': 'Guntur',
        'material': 'Plastic Waste',
        'transfer_party_name': 'ABC Recyclers',
        'user_name': 'John Doe',
        'site_incharge': 'Jane Smith',
        'first_weight': '5000.0',
        'second_weight': '3500.0',
        'net_weight': '1500.0',
        'first_timestamp': '09-08-2025 14:30:15',
        'second_timestamp': '09-08-2025 15:45:22',
        'first_front_image': 'sample_front1.jpg',
        'first_back_image': 'sample_back1.jpg',
        'second_front_image': 'sample_front2.jpg',
        'second_back_image': 'sample_back2.jpg'
    }
    
    # Test trip report generation
    success, pdf_path = generate_trip_report(sample_record)
    if success:
        print(f" Test successful! PDF generated: {pdf_path}")
    else:
        print("❌ Test failed!")