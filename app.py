from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, send_from_directory, Response
from api_client import SpeedianceClient
import json
import os
import sys
import webbrowser
from threading import Timer, Thread
import requests
import tkinter as tk
from tkinter import scrolledtext
from urllib.parse import urlparse

# Determine if running as a script or frozen exe (PyInstaller)
if getattr(sys, 'frozen', False):
    # If frozen, use the temporary folder created by PyInstaller
    base_dir = sys._MEIPASS
    template_folder = os.path.join(base_dir, 'templates')
    static_folder = os.path.join(base_dir, 'static')
    app = Flask(__name__, template_folder=template_folder, static_folder=static_folder)
else:
    # If running as script, use default paths
    app = Flask(__name__)

app.secret_key = "speediance_secret_key" # For Flash Messages
client = SpeedianceClient()

# --- Media Caching Logic ---
# Define local cache path
# Use base_dir to ensure it works in exe mode (though usually we want cache outside the temp exe folder)
# For the cache, we actually want it next to the executable, not inside the temp folder
if getattr(sys, 'frozen', False):
    # If exe, store cache next to the exe file
    current_dir = os.path.dirname(sys.executable)
else:
    current_dir = app.root_path
    
CACHE_ROOT = os.path.join(current_dir, 'static', 'media_cache')

def get_cache_path(url):
    """Determines local path and subfolder based on URL extension."""
    parsed = urlparse(url)
    filename = os.path.basename(parsed.path)
    if not filename: return None, None

    ext = os.path.splitext(filename)[1].lower()
    if ext in ['.jpg', '.jpeg', '.png', '.gif', '.webp']:
        subfolder = 'images'
    elif ext in ['.mp4', '.mov', '.webm']:
        subfolder = 'videos'
    elif ext in ['.mp3', '.wav', '.aac']:
        subfolder = 'audio'
    else:
        subfolder = 'misc'
    
    return os.path.join(CACHE_ROOT, subfolder, filename), subfolder

@app.template_filter('local_cache')
def local_cache_filter(url, force=False):
    """Jinja filter to rewrite remote URLs to local proxy URLs."""
    if not url: return ""
    
    # Check if file exists locally
    local_path, _ = get_cache_path(url)
    if local_path and os.path.exists(local_path):
        return url_for('media_proxy', url=url)
    
    # If forced (e.g. on detail page), use proxy to trigger download
    if force:
        return url_for('media_proxy', url=url)
    
    # If not cached and not forced, return original URL to let browser fetch directly
    return url

@app.route('/media_proxy')
def media_proxy():
    """Downloads and serves media files locally."""
    remote_url = request.args.get('url')
    if not remote_url:
        return "No URL provided", 400

    local_path, subfolder = get_cache_path(remote_url)
    if not local_path:
        return redirect(remote_url) # Fallback if filename parsing fails

    filename = os.path.basename(local_path)

    # Serve from cache if exists
    if os.path.exists(local_path):
        size = os.path.getsize(local_path)
        print(f"[CACHE HIT] Served {filename} from disk. Saved {size/1024:.2f} KB of CDN traffic.")
        return send_from_directory(os.path.dirname(local_path), filename)

    # Download if missing
    try:
        # Ensure directory exists
        os.makedirs(os.path.dirname(local_path), exist_ok=True)
        
        # Stream download
        print(f"[CACHE MISS] Downloading {filename} from CDN...")
        resp = requests.get(remote_url, stream=True, timeout=10)
        if resp.status_code == 200:
            with open(local_path, 'wb') as f:
                for chunk in resp.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            size = os.path.getsize(local_path)
            print(f"[DOWNLOAD] Saved {filename} ({size/1024:.2f} KB) to cache.")
            return send_from_directory(os.path.dirname(local_path), filename)
        else:
            # If download fails, redirect to original URL
            print(f"[ERROR] Failed to download {remote_url} (Status {resp.status_code})")
            return redirect(remote_url)
    except Exception as e:
        print(f"[ERROR] Cache download failed for {remote_url}: {e}")
        return redirect(remote_url)

@app.route('/')
def index():
    if not client.credentials.get("token"):
        return redirect(url_for('settings'))
    
    try:
        workouts = client.get_user_workouts()
    except:
        flash("Error loading workouts. Invalid token?", "error")
        workouts = []
    
    unit = client.credentials.get('unit', 0)
    return render_template('index.html', workouts=workouts, unit=unit)

@app.route('/settings', methods=['GET', 'POST'])
def settings():
    if request.method == 'POST':
        # Manual config save
        client.save_config(
            request.form['user_id'], 
            request.form['token'], 
            request.form.get('region', 'Global'),
            int(request.form.get('unit', 0))
        )
        flash("Settings saved!", "success")
        return redirect(url_for('index'))
    
    creds = client.load_config()
    return render_template('settings.html', creds=creds)

@app.route('/settings/unit', methods=['POST'])
def update_unit():
    unit = request.form.get('unit')
    success, msg = client.update_unit(unit)
    if success:
        flash("Unit preference updated!", "success")
    else:
        flash(f"Error updating unit: {msg}", "error")
    return redirect(url_for('settings'))

@app.route('/login', methods=['POST'])
def login():
    email = request.form.get('email')
    password = request.form.get('password')
    region = request.form.get('region', 'Global')
    
    if not email or not password:
        flash("Email and password required", "error")
        return redirect(url_for('settings'))
    
    # Update client region before login attempt
    client.region = region
    client.host = "euapi.speediance.com" if region == "EU" else "api2.speediance.com"
    client.base_url = "https://" + client.host
        
    success, message = client.login(email, password)
    if success:
        flash("Login successful!", "success")
        return redirect(url_for('index'))
    else:
        flash(f"Login failed: {message}", "error")
        return redirect(url_for('settings'))

@app.route('/logout')
def logout():
    client.logout()
    flash("Logged out successfully", "success")
    return redirect(url_for('settings'))

@app.route('/settings/preload')
def preload_assets():
    """Streamed response that downloads all assets."""
    if not client.credentials.get("token"): return "Unauthorized", 401

    def download_url(url):
        if not url or not url.startswith('http'): return "Skipped (Invalid URL)"
        
        local_path, subfolder = get_cache_path(url)
        if not local_path: return "Skipped (Path error)"
        
        if os.path.exists(local_path) and os.path.getsize(local_path) > 0:
            return "Skipped (Already exists)"
            
        try:
            os.makedirs(os.path.dirname(local_path), exist_ok=True)
            resp = requests.get(url, stream=True, timeout=20)
            if resp.status_code == 200:
                with open(local_path, 'wb') as f:
                    for chunk in resp.iter_content(chunk_size=8192):
                        f.write(chunk)
                return "Downloaded"
            else:
                return f"Failed (Status {resp.status_code})"
        except Exception as e:
            return f"Error: {e}"

    def extract_urls_from_exercise(ex):
        urls = set()
        if ex.get('img'): urls.add(ex['img'])
        
        # Variants
        for variant in ex.get('actionLibraryList', []):
            if variant.get('videoPath'): urls.add(variant['videoPath'])
            if variant.get('leftVideo'): urls.add(variant['leftVideo'])
            if variant.get('rightVideo'): urls.add(variant['rightVideo'])
            if variant.get('endVideo'): urls.add(variant['endVideo'])
            
            if variant.get('startVideo'):
                for v in variant['startVideo'].split(','):
                    if v.strip(): urls.add(v.strip())
            
            if variant.get('coach', {}).get('avatar'):
                urls.add(variant['coach']['avatar'])
                
            for key in ['actionNameVoice', 'completionTimeVoice', 'completionNumberVoice', 'goVoice', 'restConfigVoice']:
                if variant.get(key): urls.add(variant[key])
            
            for i in range(1, 7):
                key = f'guideVoice{i}'
                if variant.get(key): urls.add(variant[key])

        # Steps
        try:
            if ex.get('showDetails'):
                steps = json.loads(ex['showDetails'])
                for step in steps:
                    if step.get('img'): urls.add(step['img'])
        except:
            pass
        return urls

    def generate():
        yield "Starting deep discovery and download of assets...\n"
        yield "This process fetches full details for every exercise to ensure no video is missed.\n"
        yield "It may take several minutes. Please do not close this tab.\n\n"
        
        # 1. Accessories
        yield "--- Processing Accessories ---\n"
        try:
            accessories = client.get_accessories()
            for acc in accessories:
                if acc.get('img'): 
                    res = download_url(acc['img'])
                    yield f"Accessory {acc.get('name', 'Unknown')}: {res}\n"
        except Exception as e:
            yield f"Error scanning accessories: {e}\n"

        # 2. Library
        yield "\n--- Processing Exercise Library ---\n"
        try:
            # Get the list of groups first
            library_groups = client.get_library()
            total_groups = len(library_groups)
            
            for i, group in enumerate(library_groups):
                group_id = group.get('id')
                group_title = group.get('title', f'ID {group_id}')
                yield f"[{i+1}/{total_groups}] Processing: {group_title} ... "
                
                # Fetch FULL details for this exercise group
                # This ensures we get all variants and videos even if the list endpoint was incomplete
                try:
                    detail = client.get_exercise_detail(group_id)
                    if not detail:
                        yield "Failed to fetch details.\n"
                        continue
                        
                    urls = extract_urls_from_exercise(detail)
                    yield f"Found {len(urls)} assets.\n"
                    
                    for url in urls:
                        filename = os.path.basename(urlparse(url).path)
                        res = download_url(url)
                        if "Downloaded" in res:
                            yield f"    -> {filename}: {res}\n"
                            
                except Exception as e:
                    yield f"Error fetching details: {e}\n"
                    
        except Exception as e:
            yield f"Error scanning library: {e}\n"
        
        yield "\nDone! All assets have been processed."

    return Response(generate(), mimetype='text/plain')

@app.route('/library')
def library():
    if not client.credentials.get("token"): return redirect(url_for('settings'))
    exercises = client.get_library()
    accessories = client.get_accessories()
    accessory_map = {str(acc['id']): acc['name'] for acc in accessories}
    
    # Enrich exercises with equipment names
    for ex in exercises:
        acc_ids = str(ex.get('accessories', '')).split(',')
        names = [accessory_map.get(aid, 'Standard') for aid in acc_ids if aid]
        ex['equipment_name'] = ', '.join(names) if names else 'Standard'
        
    return render_template('library.html', exercises=exercises)

@app.route('/api_docs')
def api_docs():
    return render_template('api_docs.html')

@app.route('/exercise/<int:ex_id>')
def exercise_detail(ex_id):
    if not client.credentials.get("token"): return redirect(url_for('settings'))
    
    # 1. Load details
    detail = client.get_exercise_detail(ex_id)
    
    # 2. Resolve accessories (IDs -> Objects with Image/Name)
    all_accessories = client.get_accessories()
    required_ids = detail.get('accessories', '').split(',')
    
    mapped_accessories = []
    for acc in all_accessories:
        # Check if the ID is in the required list
        if str(acc['id']) in required_ids:
            mapped_accessories.append(acc)
            
    # 3. "showDetails" is a JSON string in the API response, we need to parse it
    # Format: [{"context": "Text...", "img": "url..."}, ...]
    try:
        if detail.get('showDetails'):
            detail['steps'] = json.loads(detail['showDetails'])
        else:
            detail['steps'] = []
    except Exception as e:
        print(f"JSON Parse Error: {e}")
        detail['steps'] = []

    return render_template('exercise_detail.html', ex=detail, accessories=mapped_accessories)

@app.route('/api/exercise/<int:ex_id>')
def api_exercise_detail(ex_id):
    """Returns details as JSON for the frontend (dropdowns)"""
    if not client.credentials.get("token"): 
        return jsonify({"error": "Unauthorized"}), 401
    
    # Uses the existing cache/request
    detail = client.get_exercise_detail(ex_id)
    return jsonify(detail)

@app.route('/edit/<string:code>')  # HERE: string instead of int
def edit(code):
    if not client.credentials.get("token"): return redirect(url_for('settings'))
    
    # Load workout details via code
    workout = client.get_workout_detail(code)
    
    if not workout:
        flash("Could not load workout details.", "error")
        return redirect(url_for('index'))

    library = client.get_library()
    unit = client.credentials.get("unit", 0)
    return render_template('create.html', library=library, existing_workout=workout, unit=unit)


@app.route('/create', methods=['GET', 'POST'])
def create():
    if not client.credentials.get("token"): return redirect(url_for('settings'))
    
    if request.method == 'POST':
        data = request.json 
        name = data.get('name')
        exercises = data.get('exercises')
        template_id = data.get('id') 
        
        result = client.save_workout(name, exercises, template_id)
        
        if result.get('code') == 0:
            return jsonify({"status": "success"})
        else:
            return jsonify({"status": "error", "message": result.get('message')})

    library = client.get_library()
    unit = client.credentials.get("unit", 0)
    
    # HERE: We pass 'None' so the template knows: "No data to preload"
    # This has NO influence on the edit route, which sends its own data.
    return render_template('create.html', library=library, existing_workout=None, unit=unit)

@app.route('/delete/<int:id>')
def delete(id):
    client.delete_workout(id)
    flash("Workout deleted.", "info")
    return redirect(url_for('index'))

class TextRedirector(object):
    def __init__(self, widget, tag="stdout"):
        self.widget = widget
        self.tag = tag

    def write(self, str):
        try:
            self.widget.configure(state="normal")
            self.widget.insert("end", str, (self.tag,))
            self.widget.see("end")
            self.widget.configure(state="disabled")
        except:
            pass
    
    def flush(self):
        pass

def open_browser():
    webbrowser.open_new("http://127.0.0.1:5001")

def run_flask_server():
    try:
        app.run(debug=False, port=5001, host='0.0.0.0', use_reloader=False)
    except Exception as e:
        print(f"Error starting server: {e}")

def start_gui():
    root = tk.Tk()
    root.title("Unofficial Speediance Workout Manager Server")
    root.geometry("700x500")
    
    lbl = tk.Label(root, text="Unofficial Speediance Workout Manager is running.\nDo not close this window while using the app.", font=("Arial", 10), pady=10)
    lbl.pack()

    btn_frame = tk.Frame(root)
    btn_frame.pack(pady=5)

    btn_open = tk.Button(btn_frame, text="Open in Browser", command=open_browser, bg="#4CAF50", fg="white", font=("Arial", 10, "bold"), padx=10, pady=5)
    btn_open.pack(side=tk.LEFT, padx=10)

    def on_close():
        root.destroy()
        sys.exit(0)

    btn_close = tk.Button(btn_frame, text="Stop Server & Exit", command=on_close, bg="#f44336", fg="white", font=("Arial", 10, "bold"), padx=10, pady=5)
    btn_close.pack(side=tk.LEFT, padx=10)

    log_frame = tk.Frame(root)
    log_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
    
    tk.Label(log_frame, text="Server Logs:", anchor="w").pack(fill=tk.X)
    
    text_area = scrolledtext.ScrolledText(log_frame, state='disabled', font=("Consolas", 9))
    text_area.pack(fill=tk.BOTH, expand=True)
    
    sys.stdout = TextRedirector(text_area, "stdout")
    sys.stderr = TextRedirector(text_area, "stderr")

    root.protocol("WM_DELETE_WINDOW", on_close)

    t = Thread(target=run_flask_server, daemon=True)
    t.start()

    Timer(2.0, open_browser).start()

    root.mainloop()

if __name__ == '__main__':
    if getattr(sys, 'frozen', False):
        start_gui()
    else:
        app.run(debug=True, port=5001, host='0.0.0.0')