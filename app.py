import contextlib
import time
from flask import Flask, render_template, Response, jsonify
import atexit
from queue import Queue, Empty
from camera import EmojiCamera
import threading


# Flask Web Application
app = Flask(__name__)

# Global camera variable
camera = None
frame_queue = Queue(maxsize=5)
camera_lock = threading.Lock()  # Add a lock to protect camera initialization

def init_camera():
    global camera
    
    # Use a lock to prevent concurrent initialization
    print("Acquiring camera lock...")
    # Add a timeout to the lock acquisition to prevent deadlocks
    if not camera_lock.acquire(timeout=5):
        print("ERROR: Could not acquire camera lock after 5 seconds, possible deadlock")
        return False
    
    try:
        print("Lock acquired, checking camera status...")
        if camera is None:
            try:
                print("Starting camera initialization...")
                
                # First make sure any existing camera is fully cleaned up
                try:
                    cleanup_without_lock()  # Use a version without the lock
                    print("Cleanup completed")
                except Exception as e:
                    print(f"Cleanup warning (continuing anyway): {e}")
                
                time.sleep(1)  # Give time for cleanup to complete
                
                print("Creating new camera object...")
                # Now initialize the camera with a timeout
                camera = EmojiCamera()
                
                # Only start producer thread if camera was initialized successfully
                if camera and camera.running:
                    producer_thread = threading.Thread(target=frame_producer, daemon=True)
                    producer_thread.start()
                    print("Frame producer thread started")
                    return True
                else:
                    print("Camera failed to initialize properly")
                    return False
            except Exception as e:
                print(f"Failed to initialize camera: {e}")
                return False
        
        # Return True if camera already exists and is running
        print(f"Using existing camera, running: {camera is not None and camera.running}")
        return camera is not None and camera.running
    finally:
        camera_lock.release()
        print("Camera lock released")

def frame_producer():
    """Separate thread to continuously capture frames"""
    global camera, frame_queue

    while camera and camera.running:
        try:
            frame = camera.get_frame()
            if frame is not None:
                try:
                    frame_queue.put(frame, block=False)
                except Exception:
                    with contextlib.suppress(Empty):
                        frame_queue.get_nowait()
                        frame_queue.put(frame, block=False)
            else:
                time.sleep(0.033)  # ~30 FPS
        except Exception as e:
            print(f"Frame producer error: {e}")
            time.sleep(0.1)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/video_feed')
def video_feed():
    def generate():
        if not init_camera():
            return

        print("Starting video feed...")

        while True:
            try:
                frame = frame_queue.get(timeout=1.0)
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n'
                       b'Cache-Control: no-cache\r\n\r\n' + frame + b'\r\n')
            except Empty:
                time.sleep(0.01)
                continue
            except Exception as e:
                print(f"Error in video feed: {e}")
                break

    return Response(generate(), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/emoji_feed')
def emoji_feed():
    """Stream emoji art"""
    def generate():
        if not init_camera():
            return

        print("Starting emoji feed...")

        while True:
            try:
                if camera:
                    emoji_art = camera.get_emoji_frame()
                    if emoji_art:
                        # Encode newlines for safe transmission through SSE
                        encoded_art = emoji_art.replace('\n', '\\n')
                        yield f"data: {encoded_art}\n\n"
                time.sleep(0.1)  # Update every 100ms
            except Exception as e:
                print(f"Error in emoji feed: {e}")
                break

    return Response(generate(), mimetype='text/event-stream')

@app.route('/status')
def status():
    if not init_camera():
        return jsonify({"status": "ERROR", "camera": "failed"}), 500
    camera_info = camera.get_camera_info()
    return jsonify({
        "status": "OK",
        "camera": "initialized",
        "queue_size": frame_queue.qsize(),
        **camera_info
    })

@app.route('/save_emoji')
def save_emoji():
    """Save current emoji art"""
    if camera:
        if filename := camera.save_emoji_art():
            return jsonify({"success": True, "filename": filename})
    return jsonify({"error": "Failed to save emoji art"}), 500

@app.route('/save_snapshot')
def save_snapshot():
    """Save current camera snapshot"""
    if camera:
        if filename := camera.save_snapshot():
            return jsonify({"success": True, "filename": filename})
    return jsonify({"error": "Failed to save snapshot"}), 500

@app.route('/set_emoji_size/<int:size>')
def set_emoji_size(size):
    """Set emoji grid size"""
    if camera and camera.set_emoji_size(size):
        return jsonify({"success": True, "size": size})
    return jsonify({"error": "Invalid size or camera not available"}), 400

@app.route('/toggle_conversion')
def toggle_conversion():
    """Toggle emoji conversion"""
    if camera:
        enabled = camera.toggle_conversion()
        return jsonify({"success": True, "conversion_enabled": enabled})
    return jsonify({"error": "Camera not available"}), 500

@app.route('/toggle_art_mode')
def toggle_art_mode():
    """Toggle between emoji and ASCII art modes"""
    if camera:
        mode = camera.toggle_art_mode()
        return jsonify({"success": True, "art_mode": mode})
    return jsonify({"error": "Camera not available"}), 500

@app.route('/restart_camera')
def restart_camera():
    """Restart the camera"""
    global camera
    try:
        if camera:
            camera.cleanup()
            camera = None
        time.sleep(2)
        success = init_camera()
        return jsonify({"success": success})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

def cleanup():
    global camera
    with camera_lock:  # Use the same lock for cleanup
        if camera:
            try:
                print("Cleaning up camera resources...")
                camera.cleanup()
                camera = None
                # Add a small delay to allow system resources to be fully released
                time.sleep(0.5)
                print("Camera cleanup complete")
            except Exception as e:
                print(f"Error during cleanup: {e}")

def cleanup_without_lock():
    """Cleanup function that doesn't use the camera lock"""
    global camera
    if camera:
        try:
            print("Cleaning up camera resources (without lock)...")
            camera.cleanup()
            camera = None
            # Add a small delay to allow system resources to be fully released
            time.sleep(0.5)
            print("Camera cleanup complete (without lock)")
        except Exception as e:
            print(f"Error during cleanup (without lock): {e}")

# Register cleanup
atexit.register(cleanup)

if __name__ == '__main__':
    print("Starting Emoji Camera Flask app...")

    app.config.update(
        SEND_FILE_MAX_AGE_DEFAULT=0,
        TEMPLATES_AUTO_RELOAD=False
    )

    app.run(
        host='0.0.0.0',
        port=5000,
        debug=False,
        use_reloader=False,
        threaded=True
    )
