import cv2
import tkinter as tk
from tkinter import ttk, messagebox
import threading
from PIL import Image, ImageTk
import os
from datetime import datetime
import time
import sys
import warnings

# Completely suppress all OpenCV/FFMPEG output
cv2.setLogLevel(0)
warnings.filterwarnings("ignore")

# Redirect stderr to suppress codec errors
class SuppressStderr:
    def __enter__(self):
        self.original_stderr = sys.stderr
        sys.stderr = open(os.devnull, 'w')
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        sys.stderr.close()
        sys.stderr = self.original_stderr

class RTSPCameraApp:
    def __init__(self, root):
        self.root = root
        self.root.title("RTSP Camera Capture")
        self.root.geometry("800x650")
        
        # Camera configurations with comprehensive HD options for each camera
        self.cameras = {
            "Camera 1 (192.168.0.102)": [
                "rtsp://admin:admin@123@192.168.0.102:554/cam/realmonitor?channel=01&subtype=01",
            ],
            "Camera 2 (192.168.0.103)": [
                # Keep working HD configuration first
                "rtsp://admin:admin@123@192.168.0.103:554/cam/realmonitor?channel=01&subtype=00",
            ]
        }
        
        self.cap = None
        self.is_streaming = False
        self.current_frame = None
        
        # Create captures directory
        os.makedirs("captured_images", exist_ok=True)
        
        self.setup_ui()
        
    def setup_ui(self):
        # Main frame
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Camera selection
        ttk.Label(main_frame, text="Select Camera:").pack(anchor=tk.W, pady=(0, 5))
        self.camera_var = tk.StringVar(value=list(self.cameras.keys())[0])
        ttk.Combobox(main_frame, textvariable=self.camera_var, 
                    values=list(self.cameras.keys()), state="readonly", width=35).pack(anchor=tk.W, pady=(0, 10))
        
        # Control buttons
        control_frame = ttk.Frame(main_frame)
        control_frame.pack(pady=10)
        
        self.start_btn = ttk.Button(control_frame, text="Start Stream", command=self.start_stream)
        self.start_btn.pack(side=tk.LEFT, padx=5)
        
        self.capture_btn = ttk.Button(control_frame, text="Capture HD Image", command=self.capture_image, state=tk.DISABLED)
        self.capture_btn.pack(side=tk.LEFT, padx=5)
        
        self.stop_btn = ttk.Button(control_frame, text="Stop", command=self.stop_stream, state=tk.DISABLED)
        self.stop_btn.pack(side=tk.LEFT, padx=5)
        
        # Status
        self.status_var = tk.StringVar(value="Ready")
        ttk.Label(main_frame, textvariable=self.status_var, foreground="blue").pack(pady=5)
        
        # Video display
        self.video_label = tk.Label(main_frame, text="Camera feed will appear here", 
                                   bg="black", fg="white", width=80, height=25)
        self.video_label.pack(pady=10, fill=tk.BOTH, expand=True)
        
    def start_stream(self):
        if self.is_streaming:
            return
            
        camera_urls = self.cameras[self.camera_var.get()]
        connection_successful = False
        
        for i, rtsp_url in enumerate(camera_urls):
            try:
                self.status_var.set(f"Connecting {i+1}/{len(camera_urls)}...")
                self.root.update()
                
                # Use Camera 2's working approach for both cameras
                with SuppressStderr():
                    self.cap = cv2.VideoCapture(rtsp_url)
                    
                    # Same settings that work for Camera 2
                    self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 3)
                    self.cap.set(cv2.CAP_PROP_FPS, 25)
                    
                    time.sleep(2)
                    
                    # Test stream quality
                    for attempt in range(10):
                        ret, test_frame = self.cap.read()
                        if ret and test_frame is not None and test_frame.size > 0:
                            h, w = test_frame.shape[:2]
                            if h >= 720 and w >= 1280:  # HD quality
                                connection_successful = True
                                self.status_var.set(f"HD Connected ({w}x{h})")
                                break
                        time.sleep(0.1)
                    
                    if connection_successful:
                        break
                    else:
                        self.cap.release()
                        self.cap = None
                        
            except Exception:
                if self.cap:
                    self.cap.release()
                    self.cap = None
                continue
        
        if not connection_successful:
            messagebox.showerror("Error", f"Could not connect to {self.camera_var.get()} in HD quality")
            self.status_var.set("HD connection failed")
            return
        
        # Success
        self.is_streaming = True
        self.start_btn.config(state=tk.DISABLED)
        self.stop_btn.config(state=tk.NORMAL)
        self.capture_btn.config(state=tk.NORMAL)
        
        # Start video thread
        threading.Thread(target=self.video_loop, daemon=True).start()
    
    def video_loop(self):
        """Simple HD video loop - same approach for both cameras"""
        stable_frames = 0
        
        while self.is_streaming and self.cap:
            try:
                with SuppressStderr():
                    ret, frame = self.cap.read()
                
                if ret and frame is not None and frame.size > 0:
                    h, w = frame.shape[:2]
                    
                    # Only accept HD quality frames
                    if h >= 720 and w >= 1280:
                        stable_frames += 1
                        
                        # Store HD frame for capture
                        self.current_frame = frame.copy()
                        
                        # Update display after stable frames
                        if stable_frames >= 3:
                            # Create HD display
                            display_w = 800
                            display_h = int(display_w * h / w)
                            
                            display_frame = cv2.resize(frame, (display_w, display_h), 
                                                     interpolation=cv2.INTER_CUBIC)
                            display_frame = cv2.cvtColor(display_frame, cv2.COLOR_BGR2RGB)
                            
                            img = Image.fromarray(display_frame)
                            photo = ImageTk.PhotoImage(img)
                            self.root.after(0, lambda p=photo: self.update_display(p))
                    else:
                        stable_frames = 0
                else:
                    stable_frames = 0
                
                time.sleep(0.04)  # 25 FPS
                
            except Exception:
                stable_frames = 0
                time.sleep(0.1)
                continue
                
        self.is_streaming = False
    
    def update_display(self, photo):
        """Update video display"""
        if self.video_label.winfo_exists():
            self.video_label.config(image=photo, text="")
            self.video_label.image = photo
    
    def capture_image(self):
        """Capture current frame in HD"""
        if self.current_frame is None:
            messagebox.showwarning("Warning", "No frame to capture")
            return
        
        try:
            # Generate filename
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            camera_name = self.camera_var.get().split('(')[0].strip().replace(' ', '_')
            filename = f"{camera_name}_{timestamp}.jpg"
            filepath = os.path.join("captured_images", filename)
            
            # Save HD image
            cv2.imwrite(filepath, self.current_frame, [cv2.IMWRITE_JPEG_QUALITY, 95])
            
            # Show success message
            file_size = os.path.getsize(filepath) / 1024
            h, w = self.current_frame.shape[:2]
            
            messagebox.showinfo("Success", 
                              f"Image saved!\n\n"
                              f"File: {filename}\n"
                              f"Resolution: {w}x{h}\n"
                              f"Size: {file_size:.1f} KB")
            
            self.status_var.set(f"Captured: {filename}")
            
        except Exception as e:
            messagebox.showerror("Error", f"Capture failed: {str(e)}")
    
    def stop_stream(self):
        """Stop streaming"""
        self.is_streaming = False
        
        if self.cap:
            self.cap.release()
            self.cap = None
        
        self.start_btn.config(state=tk.NORMAL)
        self.stop_btn.config(state=tk.DISABLED)
        self.capture_btn.config(state=tk.DISABLED)
        self.status_var.set("Stopped")
        
        # Clear display
        self.video_label.config(image="", text="Camera feed stopped")
    
    def on_closing(self):
        """Clean shutdown"""
        self.stop_stream()
        self.root.destroy()

def main():
    root = tk.Tk()
    app = RTSPCameraApp(root)
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    root.mainloop()

if __name__ == "__main__":
    main()