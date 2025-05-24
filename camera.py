from picamera2 import Picamera2
import cv2
import threading
import time
import os
from PIL import Image
import numpy as np

# Emoji color mapping
COLORS = [
    # Your existing colors
    ((0, 0, 0), "⬛"),       # Black
    ((0, 0, 255), "🟦"),    # Blue
    ((255, 0, 0), "🟥"),    # Red
    ((255, 255, 0), "🟨"),  # Yellow
    ((255, 165, 0), "🟧"),  # Orange
    ((255, 255, 255), "⬜"), # White
    ((0, 255, 0), "🟩"),    # Green
    ((128, 0, 128), "🟪"),  # Purple
    ((255, 192, 203), "🩷"), # Pink
    ((165, 42, 42), "🟫"),  # Brown
    
    # Add these for better video representation:
    ((128, 128, 128), "⬜"),  # Gray (could use ◻️ or ⚪)
    ((64, 64, 64), "◼️"),     # Dark gray
    ((192, 192, 192), "◻️"),  # Light gray
    ((0, 128, 128), "🟦"),    # Teal/Cyan (approximate with blue)
    ((128, 128, 0), "🟨"),    # Olive (approximate with yellow)
    ((128, 0, 0), "🟥"),      # Maroon (approximate with red)
    ((0, 128, 0), "🟩"),      # Dark green
    ((0, 0, 128), "🟦"),      # Navy (approximate with blue)
]

ASCII_CHARS = "@%#*+=-:. "  # Characters from dark to light

class EmojiCamera:
    def __init__(self):
        print("Initializing Emoji Camera...")
        self.running = False  # Set to false until fully initialized
        
        try:
            # Force kill any existing camera processes
            import subprocess
            import os
            
            # Try to kill any existing camera processes
            try:
                subprocess.run(['sudo', 'pkill', '-f', 'libcamera'], 
                              stderr=subprocess.DEVNULL, stdout=subprocess.DEVNULL, timeout=3)
            except:
                pass  # Ignore errors from pkill
                
            time.sleep(1)  # Wait for system to stabilize
            
            # Initialize camera with timeout
            self.picam2 = Picamera2()
            
            # Use a simpler configuration
            self.picam2.configure(self.picam2.create_preview_configuration())
            
            # Start with timeout
            start_timeout = threading.Thread(target=self._start_with_timeout)
            start_timeout.start()
            start_timeout.join(10)  # Wait up to 10 seconds for camera to start
            
            if not self.running:
                raise Exception("Camera start timed out")
            
            print("Emoji Camera initialized successfully")
            
        except Exception as e:
            print(f"Camera initialization failed: {e}")
            self.running = False
            if hasattr(self, 'picam2'):
                try:
                    self.picam2.close()
                except:
                    pass
            raise e
        
    def _start_with_timeout(self):
        """Start camera with timeout protection"""
        try:
            self.picam2.start()
            self.frame = None
            self.emoji_frame = None
            self.lock = threading.Lock()
            self.running = True
            self.emoji_size = 48
            self.conversion_enabled = True
            self.art_mode = "emoji"  # Add this line to initialize art_mode
            
            if not os.path.exists("captures"):
                os.makedirs("captures")
            
            # Start camera thread
            self.thread = threading.Thread(target=self.update, daemon=True)
            self.thread.start()
        except Exception as e:
            print(f"Error in camera start: {e}")
            self.running = False

    def euclidean_distance(self, color1, color2):
        """Calculate the Euclidean distance between two colors"""
        r1, g1, b1 = color1
        r2, g2, b2 = color2

        delta_r = r2 - r1
        delta_g = g2 - g1
        delta_b = b2 - b1

        squared_distance = delta_r ** 2 + delta_g ** 2 + delta_b ** 2
        return squared_distance ** 0.5

    def find_closest_emoji(self, target_color):
        """Find the closest emoji representation for a given color"""
        distances = [self.euclidean_distance(target_color, color[0]) for color in COLORS]
        closest_color_index = distances.index(min(distances))
        return COLORS[closest_color_index][1]

    def convert_to_emoji(self, frame):
        """Convert camera frame to emoji art"""
        try:
            # Convert numpy array to PIL Image
            pil_image = Image.fromarray(frame)
            
            # Convert to RGB mode to ensure we only have 3 channels
            pil_image = pil_image.convert('RGB')

            # Resize image for emoji conversion
            small_img = pil_image.resize((self.emoji_size, self.emoji_size), Image.NEAREST)

            # Load pixels
            pixels = small_img.load()

            return '\n'.join(
                ''.join(
                    self.find_closest_emoji(pixels[x, y])
                    for x in range(self.emoji_size)
                )
                for y in range(self.emoji_size)
            )
        except Exception as e:
            print(f"Error converting to emoji: {e}")
            return "❌ Conversion Error"

    def convert_to_ascii(self, frame):
        """Convert camera frame to ASCII art"""
        try:
            # Convert numpy array to PIL Image
            pil_image = Image.fromarray(frame)
            
            # Convert to grayscale
            pil_image = pil_image.convert('L')

            # Resize image for ASCII conversion
            small_img = pil_image.resize((self.emoji_size * 2, self.emoji_size), Image.NEAREST)
            
            # Get pixel data
            pixels = np.array(small_img)
            
            # Map brightness values to ASCII characters
            ascii_img = []
            for row in pixels:
                ascii_row = []
                for pixel in row:
                    # Map pixel value (0-255) to ASCII character
                    index = min(int(pixel / 255 * (len(ASCII_CHARS) - 1)), len(ASCII_CHARS) - 1)
                    ascii_row.append(ASCII_CHARS[index])
                ascii_img.append(''.join(ascii_row))
            
            return '\n'.join(ascii_img)
        except Exception as e:
            print(f"Error converting to ASCII: {e}")
            return "X Conversion Error"

    def update(self):
        """Main camera update loop"""
        print("Camera update thread started")

        while self.running:
            try:
                if not self.picam2:
                    break

                # Capture frame
                frame = self.picam2.capture_array()

                with self.lock:
                    self.frame = frame

                    # Convert to art if enabled
                    if self.conversion_enabled:
                        if self.art_mode == "emoji":
                            self.emoji_frame = self.convert_to_emoji(frame)
                        else:  # ASCII mode
                            self.emoji_frame = self.convert_to_ascii(frame)

                time.sleep(1/30)  # 30 FPS

            except Exception as e:
                print(f"Error in camera update: {e}")
                time.sleep(0.1)

    def get_frame(self):
        """Get the current camera frame as JPEG"""
        with self.lock:
            if self.frame is None:
                return None

            try:
                # Convert RGB to BGR for OpenCV
                bgr_frame = cv2.cvtColor(self.frame, cv2.COLOR_RGB2BGR)

                # Encode as JPEG
                encode_params = [cv2.IMWRITE_JPEG_QUALITY, 85]
                success, jpeg = cv2.imencode('.jpg', bgr_frame, encode_params)

                return jpeg.tobytes() if success else None
            except Exception as e:
                print(f"Error encoding frame: {e}")
                return None

    def get_emoji_frame(self):
        """Get the current emoji representation"""
        with self.lock:
            return self.emoji_frame

    def save_emoji_art(self):
        """Save current emoji art to file"""
        try:
            if emoji_art := self.get_emoji_frame():
                timestamp = time.strftime("%Y%m%d-%H%M%S")
                filename = f"captures/emoji_art_{timestamp}.txt"

                with open(filename, 'w', encoding='utf-8') as f:
                    f.write(emoji_art)

                print(f"Saved emoji art: {filename}")
                return filename

        except Exception as e:
            print(f"Error saving emoji art: {e}")
            return None

    def save_snapshot(self):
        """Save current camera frame"""
        try:
            with self.lock:
                if self.frame is None:
                    return None

                timestamp = time.strftime("%Y%m%d-%H%M%S")
                filename = f"captures/snapshot_{timestamp}.jpg"

                bgr = cv2.cvtColor(self.frame, cv2.COLOR_RGB2BGR)
                if success := cv2.imwrite(filename, bgr):
                    print(f"Saved snapshot: {filename}")
                    return filename

        except Exception as e:
            print(f"Error saving snapshot: {e}")
            return None

    def set_emoji_size(self, size):
        """Set the emoji grid size"""
        if 8 <= size <= 64:
            self.emoji_size = size
            print(f"Emoji size set to: {size}x{size}")
            return True
        return False

    def toggle_conversion(self):
        """Toggle emoji conversion on/off"""
        self.conversion_enabled = not self.conversion_enabled
        print(f"Emoji conversion: {'enabled' if self.conversion_enabled else 'disabled'}")
        return self.conversion_enabled

    def toggle_art_mode(self):
        """Toggle between emoji and ASCII art modes"""
        self.art_mode = "ascii" if self.art_mode == "emoji" else "emoji"
        print(f"Art mode switched to: {self.art_mode}")
        return self.art_mode
        
    def get_camera_info(self):
        """Get camera information"""
        return {
            "emoji_size": f"{self.emoji_size}x{self.emoji_size}",
            "conversion_enabled": self.conversion_enabled,
            "running": self.running,
            "art_mode": self.art_mode  # Add this line
        }

    def cleanup(self):
        """Clean up camera resources"""
        print("Cleaning up Emoji Camera...")
        self.running = False

        if hasattr(self, 'thread') and self.thread.is_alive():
            self.thread.join(timeout=2)

        if hasattr(self, 'picam2') and self.picam2:
            try:
                self.picam2.stop()
                self.picam2.close()
                print("Camera cleaned up successfully")
            except Exception as e:
                print(f"Error during cleanup: {e}")

