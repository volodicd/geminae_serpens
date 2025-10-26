#!/usr/bin/env python3
"""
🎨 LED Color Controller Web App
Enhanced with color wheel, effects, and user preferences
"""
from flask import Flask, render_template, jsonify, request
import requests
import socket
import logging
import json
import hashlib
import os
from datetime import datetime

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

# Configuration
ESP32_IP = None
ESP32_PORT = 80
ESP32_KNOWN_IP = "10.42.0.232"
DISCOVER_TIMEOUT = 2

# User preferences storage
PREFS_DIR = "user_preferences"
os.makedirs(PREFS_DIR, exist_ok=True)

def generate_device_id(request):
    """Generate unique device ID based on user agent, IP, etc."""
    user_agent = request.headers.get('User-Agent', '')
    ip = request.remote_addr or 'unknown'
    
    # Create hash from user agent and other factors
    device_string = f"{user_agent}-{ip}"
    device_id = hashlib.md5(device_string.encode()).hexdigest()[:12]
    return device_id

def load_user_preferences(device_id):
    """Load user preferences from file"""
    pref_file = os.path.join(PREFS_DIR, f"{device_id}.json")
    
    default_prefs = {
        "favorites": [
            {"name": "Red", "r": 255, "g": 0, "b": 0},
            {"name": "Green", "r": 0, "g": 255, "b": 0},
            {"name": "Blue", "r": 0, "g": 0, "b": 255},
            {"name": "White", "r": 255, "g": 255, "b": 255},
            {"name": "Purple", "r": 128, "g": 0, "b": 128},
            {"name": "Orange", "r": 255, "g": 165, "b": 0}
        ],
        "last_color": {"r": 255, "g": 255, "b": 255},
        "last_effect": 0,
        "brightness": 100,
        "speed": 50,
        "gradient_colors": [
            {"r": 255, "g": 0, "b": 0},
            {"r": 0, "g": 0, "b": 255}
        ]
    }
    
    try:
        if os.path.exists(pref_file):
            with open(pref_file, 'r') as f:
                prefs = json.load(f)
                # Merge with defaults to ensure all keys exist
                for key, value in default_prefs.items():
                    if key not in prefs:
                        prefs[key] = value
                return prefs
    except Exception as e:
        logging.error(f"Error loading preferences: {e}")
    
    return default_prefs

def save_user_preferences(device_id, preferences):
    """Save user preferences to file"""
    pref_file = os.path.join(PREFS_DIR, f"{device_id}.json")
    
    try:
        with open(pref_file, 'w') as f:
            json.dump(preferences, f, indent=2)
        return True
    except Exception as e:
        logging.error(f"Error saving preferences: {e}")
        return False

def find_esp32():
    """Auto-discover ESP32 on local networks"""
    global ESP32_IP
    
    # Try known IP first
    if ESP32_KNOWN_IP:
        try:
            response = requests.get(f"http://{ESP32_KNOWN_IP}:{ESP32_PORT}/status", timeout=2)
            if response.status_code == 200:
                ESP32_IP = ESP32_KNOWN_IP
                logging.info(f"✅ Found ESP32 at known IP: {ESP32_KNOWN_IP}")
                return True
        except:
            pass
    
    # Basic network scan (simplified)
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            local_ip = s.getsockname()[0]
        
        network_base = '.'.join(local_ip.split('.')[:-1]) + '.'
        
        for i in range(1, 255):
            ip = f"{network_base}{i}"
            if ip == ESP32_KNOWN_IP:
                continue
                
            try:
                response = requests.get(f"http://{ip}:{ESP32_PORT}/status", timeout=0.3)
                if response.status_code == 200:
                    ESP32_IP = ip
                    logging.info(f"✅ Found ESP32 at {ip}")
                    return True
            except:
                continue
    except:
        pass
    
    logging.warning("❌ ESP32 not found")
    return False

def send_esp32_request(endpoint, method='GET', params=None):
    """Send request to ESP32"""
    global ESP32_IP
    
    if not ESP32_IP:
        if not find_esp32():
            return {"success": False, "error": "ESP32 not found"}
    
    try:
        url = f"http://{ESP32_IP}:{ESP32_PORT}/{endpoint}"
        
        if method == 'POST':
            response = requests.post(url, params=params, timeout=5)
        else:
            response = requests.get(url, timeout=5)
        
        if response.status_code == 200:
            try:
                return {"success": True, "data": response.json()}
            except:
                return {"success": True, "message": response.text}
        else:
            return {"success": False, "error": f"HTTP {response.status_code}"}
            
    except requests.exceptions.Timeout:
        return {"success": False, "error": "ESP32 timeout"}
    except requests.exceptions.ConnectionError:
        ESP32_IP = None
        return {"success": False, "error": "Connection failed"}
    except Exception as e:
        return {"success": False, "error": str(e)}

@app.route('/')
def index():
    """Main color controller page"""
    device_id = generate_device_id(request)
    preferences = load_user_preferences(device_id)
    
    return render_template('index.html', 
                         device_id=device_id,
                         esp32_ip=ESP32_IP,
                         preferences=json.dumps(preferences))

@app.route('/api/color', methods=['POST'])
def set_color():
    """Set LED color"""
    data = request.get_json()
    
    result = send_esp32_request('color', 'POST', {
        'r': data.get('r', 0),
        'g': data.get('g', 0), 
        'b': data.get('b', 0)
    })
    
    if result["success"]:
        # Save to user preferences
        device_id = generate_device_id(request)
        prefs = load_user_preferences(device_id)
        prefs["last_color"] = {"r": data.get('r', 0), "g": data.get('g', 0), "b": data.get('b', 0)}
        save_user_preferences(device_id, prefs)
        
        logging.info(f"🎨 Color set: RGB({data.get('r')}, {data.get('g')}, {data.get('b')})")
    
    return jsonify(result)

@app.route('/api/effect', methods=['POST'])
def set_effect():
    """Set LED effect"""
    data = request.get_json()
    effect = data.get('effect', 0)
    
    result = send_esp32_request('effect', 'POST', {'effect': effect})
    
    if result["success"]:
        # Save to user preferences
        device_id = generate_device_id(request)
        prefs = load_user_preferences(device_id)
        prefs["last_effect"] = effect
        save_user_preferences(device_id, prefs)
        
        logging.info(f"🎭 Effect set: {effect}")
    
    return jsonify(result)

@app.route('/api/brightness', methods=['POST'])
def set_brightness():
    """Set LED brightness"""
    data = request.get_json()
    brightness = data.get('brightness', 100)
    
    result = send_esp32_request('brightness', 'POST', {'brightness': brightness})
    
    if result["success"]:
        # Save to user preferences
        device_id = generate_device_id(request)
        prefs = load_user_preferences(device_id)
        prefs["brightness"] = brightness
        save_user_preferences(device_id, prefs)
        
        logging.info(f"💡 Brightness set: {brightness}%")
    
    return jsonify(result)

@app.route('/api/speed', methods=['POST'])
def set_speed():
    """Set effect speed"""
    data = request.get_json()
    speed = data.get('speed', 50)
    
    result = send_esp32_request('speed', 'POST', {'speed': speed})
    
    if result["success"]:
        # Save to user preferences
        device_id = generate_device_id(request)
        prefs = load_user_preferences(device_id)
        prefs["speed"] = speed
        save_user_preferences(device_id, prefs)
        
        logging.info(f"⚡ Speed set: {speed}%")
    
    return jsonify(result)

@app.route('/api/gradient', methods=['POST'])
def set_gradient():
    """Set gradient colors"""
    data = request.get_json()
    color1 = data.get('color1', {})
    color2 = data.get('color2', {})
    
    result = send_esp32_request('gradient', 'POST', {
        'r1': color1.get('r', 0), 'g1': color1.get('g', 0), 'b1': color1.get('b', 0),
        'r2': color2.get('r', 0), 'g2': color2.get('g', 0), 'b2': color2.get('b', 0)
    })
    
    if result["success"]:
        # Save to user preferences
        device_id = generate_device_id(request)
        prefs = load_user_preferences(device_id)
        prefs["gradient_colors"] = [color1, color2]
        save_user_preferences(device_id, prefs)
        
        logging.info(f"🌈 Gradient set")
    
    return jsonify(result)

@app.route('/api/favorites', methods=['GET', 'POST'])
def manage_favorites():
    """Get or update favorite colors"""
    device_id = generate_device_id(request)
    prefs = load_user_preferences(device_id)
    
    if request.method == 'GET':
        return jsonify({"success": True, "favorites": prefs["favorites"]})
    
    elif request.method == 'POST':
        data = request.get_json()
        action = data.get('action')
        
        if action == 'add':
            favorite = data.get('favorite')
            if favorite and len(prefs["favorites"]) < 20:  # Limit favorites
                prefs["favorites"].append(favorite)
                save_user_preferences(device_id, prefs)
                return jsonify({"success": True})
            return jsonify({"success": False, "error": "Invalid favorite or limit reached"})
        
        elif action == 'remove':
            index = data.get('index')
            if 0 <= index < len(prefs["favorites"]):
                prefs["favorites"].pop(index)
                save_user_preferences(device_id, prefs)
                return jsonify({"success": True})
            return jsonify({"success": False, "error": "Invalid index"})
        
        elif action == 'update':
            favorites = data.get('favorites', [])
            prefs["favorites"] = favorites[:20]  # Limit to 20
            save_user_preferences(device_id, prefs)
            return jsonify({"success": True})
    
    return jsonify({"success": False, "error": "Invalid request"})

@app.route('/api/status')
def get_status():
    """Get LED status"""
    result = send_esp32_request('status')
    return jsonify(result)

@app.route('/api/discover', methods=['POST'])
def discover_esp32():
    """Manually trigger ESP32 discovery"""
    global ESP32_IP
    ESP32_IP = None
    success = find_esp32()
    return jsonify({
        "success": success,
        "ip": ESP32_IP if success else None
    })

# Legacy endpoints for compatibility
@app.route('/api/off', methods=['POST'])
def turn_off():
    """Turn off LEDs"""
    result = send_esp32_request('off')
    return jsonify(result)

@app.route('/api/on', methods=['POST'])  
def turn_on():
    """Turn on LEDs"""
    result = send_esp32_request('on')
    return jsonify(result)


@app.route('/health')
def health():
    return jsonify({"status": "ok", "esp32_connected": ESP32_IP is not None})


if __name__ == '__main__':
    print("🎨 LED Color Controller Web App")
    print("=" * 40)
    print(f"🎯 Known ESP32 IP: {ESP32_KNOWN_IP}")
    
    # Try to find ESP32 on startup
    find_esp32()
    
    print("🌐 Starting web server...")
    print("📱 Access via: http://light.volodic.com:5000")
    
    app.run(host='0.0.0.0', port=5000, debug=False)
