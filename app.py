"""
Premium URL Shortener with Admin Panel, Two-Step Verification & Ads
Single-file Flask application using MongoDB.
Run with: python app.py
"""

import os
import string
import random
from datetime import datetime
from flask import (
    Flask, render_template, request, redirect, url_for, flash, jsonify
)
from flask_login import (
    LoginManager, UserMixin, login_user, logout_user, login_required, current_user
)
from werkzeug.security import generate_password_hash, check_password_hash
import pymongo
from bson.objectid import ObjectId

# ---------- MongoDB Connection ----------
MONGO_URI = "mongodb+srv://daryllenicento:Cp7IfNCwEL9Idff2@cluster0.0gy8k.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0"
client = pymongo.MongoClient(MONGO_URI)
db = client['link_shortener']  # database name
admins_collection = db['admins']
links_collection = db['links']

# Create unique index on short_code for links
links_collection.create_index('short_code', unique=True)
admins_collection.create_index('username', unique=True)

# ---------- Ensure default admin ----------
if admins_collection.count_documents({}) == 0:
    default_admin = {
        'username': 'admin',
        'password_hash': generate_password_hash('admin123'),
        'api_key': ''.join(random.choices(string.ascii_letters + string.digits, k=32))
    }
    admins_collection.insert_one(default_admin)

# ---------- Folder structure for templates ----------
os.makedirs('templates', exist_ok=True)
os.makedirs('static', exist_ok=True)

# ---------- Write HTML templates to files (same as before) ----------
templates = {
    'base.html': '''<!DOCTYPE html>
<html>
<head>
    <title>Premium URL Shortener</title>
    <style>
        body { font-family: Arial; max-width: 600px; margin: 50px auto; text-align: center; }
        .ad-banner { background: #f0f0f0; padding: 10px; margin: 20px 0; border: 1px dashed #ccc; }
        .button { padding: 10px 20px; background: #007bff; color: white; border: none; cursor: pointer; }
        .hidden { display: none; }
    </style>
</head>
<body>
    {% block content %}{% endblock %}
</body>
</html>''',

    'index.html': '''{% extends "base.html" %}
{% block content %}
<h1>PREMIUM URL SHORTENER</h1>
<p>PREMIUM SHORTENER SYSTEM</p>
<form action="{{ url_for('shorten') }}" method="post">
    <input type="text" name="url" placeholder="PASTE LINK HERE..." style="width: 80%; padding: 10px;">
    <button type="submit" class="button">SHORTEN</button>
</form>
<div class="ad-banner">PARTNER CHANNELS TGLINKBASE</div>
{% endblock %}''',

    'verify.html': '''{% extends "base.html" %}
{% block content %}
<h2>STEP {{ step }} OF 2</h2>

<!-- Banner Ad Placeholder -->
<div class="ad-banner">ADS<br>New memecoin is here! Buy now!<br>NEW MEME HAS ARRIVED!</div>

<div id="step-container">
    {% if step == 1 %}
        <button id="verifyBtn" class="button">VERIFY (1/1)</button>
        <div id="continueContainer" class="hidden">
            <form action="{{ url_for('verify_continue', short_code=link.short_code) }}" method="post">
                <input type="hidden" name="step" value="1">
                <button type="submit" class="button">CONTINUE</button>
            </form>
        </div>
    {% elif step == 2 %}
        <button id="verifyBtn" class="button">VERIFY (2/2)</button>
        <div id="continueContainer" class="hidden">
            <form action="{{ url_for('verify_continue', short_code=link.short_code) }}" method="post">
                <input type="hidden" name="step" value="2">
                <button type="submit" class="button">CONTINUE</button>
            </form>
        </div>
    {% endif %}
</div>

<script>
    document.getElementById('verifyBtn').addEventListener('click', function() {
        // Popunder ad (opens new window behind current)
        window.open('https://example.com/ad', '_blank'); // Replace with actual ad URL
        // Show continue button
        document.getElementById('continueContainer').classList.remove('hidden');
        // Disable verify button to prevent multiple clicks
        this.disabled = true;
    });
</script>
{% endblock %}''',

    'success.html': '''{% extends "base.html" %}
{% block content %}
<h2>Your shortened link is ready!</h2>
<p><a href="{{ short_url }}" target="_blank">{{ short_url }}</a></p>
<div class="ad-banner">ADS - Thank you for using our service!</div>
<a href="{{ url_for('index') }}">Shorten another</a>
{% endblock %}''',

    'admin_login.html': '''<!DOCTYPE html>
<html>
<head><title>Admin Login</title></head>
<body>
    <h2>Admin Login</h2>
    {% with messages = get_flashed_messages() %}{% if messages %}<ul>{% for msg in messages %}<li>{{ msg }}</li>{% endfor %}</ul>{% endif %}{% endwith %}
    <form method="post">
        <input type="text" name="username" placeholder="Username" required><br>
        <input type="password" name="password" placeholder="Password" required><br>
        <button type="submit">Login</button>
    </form>
</body>
</html>''',

    'admin_dashboard.html': '''<h2>Admin Dashboard</h2>
<p>Total Links: {{ total }}</p>
<p>Active Links: {{ active }}</p>
<ul>
    <li><a href="{{ url_for('admin_links') }}">Manage Links</a></li>
    <li><a href="{{ url_for('admin_settings') }}">Settings (API Key)</a></li>
    <li><a href="{{ url_for('admin_logout') }}">Logout</a></li>
</ul>''',

    'admin_links.html': '''<h2>All Links</h2>
<table border="1">
    <tr>
        <th>Short Code</th>
        <th>Long URL</th>
        <th>Status</th>
        <th>Created</th>
    </tr>
    {% for link in links %}
    <tr>
        <td>{{ link.short_code }}</td>
        <td>{{ link.long_url[:50] }}...</td>
        <td>{{ link.status }}</td>
        <td>{{ link.created_at }}</td>
    </tr>
    {% endfor %}
</table>
<a href="{{ url_for('admin_dashboard') }}">Back</a>''',

    'admin_settings.html': '''<h2>Settings</h2>
<p>Your API Key: <strong>{{ api_key }}</strong></p>
<form method="post">
    <button type="submit">Regenerate API Key</button>
</form>
<a href="{{ url_for('admin_dashboard') }}">Back</a>'''
}

for filename, content in templates.items():
    with open(os.path.join('templates', filename), 'w', encoding='utf-8') as f:
        f.write(content)

# ---------- Flask App Initialization ----------
app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-here-change-in-production'

login_manager = LoginManager(app)
login_manager.login_view = 'admin_login'

# ---------- Flask-Login User Class ----------
class Admin(UserMixin):
    def __init__(self, admin_data):
        self.id = str(admin_data['_id'])
        self.username = admin_data['username']
        self.password_hash = admin_data['password_hash']
        self.api_key = admin_data.get('api_key', '')

    @staticmethod
    def get(admin_id):
        admin_data = admins_collection.find_one({'_id': ObjectId(admin_id)})
        return Admin(admin_data) if admin_data else None

@login_manager.user_loader
def load_user(user_id):
    return Admin.get(user_id)

# ---------- Helper Functions ----------
def generate_short_code(length=6):
    chars = string.ascii_letters + string.digits
    return ''.join(random.choices(chars, k=length))

# ---------- Public Routes ----------
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/shorten', methods=['POST'])
def shorten():
    long_url = request.form.get('url')
    if not long_url:
        flash('Please enter a URL')
        return redirect(url_for('index'))

    short_code = generate_short_code()
    while links_collection.find_one({'short_code': short_code}):
        short_code = generate_short_code()

    new_link = {
        'long_url': long_url,
        'short_code': short_code,
        'created_at': datetime.utcnow(),
        'status': 'pending',
        'step': 0
    }
    links_collection.insert_one(new_link)

    return redirect(url_for('verify', short_code=short_code, step=1))

@app.route('/verify/<short_code>')
def verify(short_code):
    link = links_collection.find_one({'short_code': short_code})
    if not link:
        return "Link not found", 404
    step = request.args.get('step', default=1, type=int)
    if step > 2:
        return redirect(url_for('success', short_code=short_code))
    return render_template('verify.html', link=link, step=step)

@app.route('/verify/<short_code>/continue', methods=['POST'])
def verify_continue(short_code):
    link = links_collection.find_one({'short_code': short_code})
    if not link:
        return "Link not found", 404
    current_step = int(request.form.get('step', 1))

    if current_step == 1:
        links_collection.update_one(
            {'short_code': short_code},
            {'$set': {'step': 1}}
        )
        return redirect(url_for('verify', short_code=short_code, step=2))
    elif current_step == 2:
        links_collection.update_one(
            {'short_code': short_code},
            {'$set': {'status': 'active', 'step': 2}}
        )
        return redirect(url_for('success', short_code=short_code))
    else:
        return redirect(url_for('index'))

@app.route('/success/<short_code>')
def success(short_code):
    link = links_collection.find_one({'short_code': short_code, 'status': 'active'})
    if not link:
        return "Link not found or not yet activated", 404
    short_url = url_for('redirect_to_long', short_code=short_code, _external=True)
    return render_template('success.html', short_url=short_url)

@app.route('/<short_code>')
def redirect_to_long(short_code):
    link = links_collection.find_one({'short_code': short_code, 'status': 'active'})
    if not link:
        return "Link not found or inactive", 404
    return redirect(link['long_url'])

# ---------- Admin Routes ----------
@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        admin_data = admins_collection.find_one({'username': username})
        if admin_data and check_password_hash(admin_data['password_hash'], password):
            admin = Admin(admin_data)
            login_user(admin)
            return redirect(url_for('admin_dashboard'))
        flash('Invalid credentials')
    return render_template('admin_login.html')

@app.route('/admin/logout')
@login_required
def admin_logout():
    logout_user()
    return redirect(url_for('admin_login'))

@app.route('/admin/dashboard')
@login_required
def admin_dashboard():
    total_links = links_collection.count_documents({})
    active_links = links_collection.count_documents({'status': 'active'})
    return render_template('admin_dashboard.html', total=total_links, active=active_links)

@app.route('/admin/links')
@login_required
def admin_links():
    links = list(links_collection.find().sort('created_at', -1))
    return render_template('admin_links.html', links=links)

@app.route('/admin/settings', methods=['GET', 'POST'])
@login_required
def admin_settings():
    if request.method == 'POST':
        new_api_key = generate_short_code(32)
        admins_collection.update_one(
            {'_id': ObjectId(current_user.id)},
            {'$set': {'api_key': new_api_key}}
        )
        flash('API key regenerated')
        # Update current_user object
        current_user.api_key = new_api_key
    return render_template('admin_settings.html', api_key=current_user.api_key)

# ---------- API ----------
@app.route('/api/shorten', methods=['POST'])
def api_shorten():
    api_key = request.headers.get('X-API-Key')
    if not api_key:
        return jsonify({'error': 'API key required'}), 401

    admin_data = admins_collection.find_one({'api_key': api_key})
    if not admin_data:
        return jsonify({'error': 'Invalid API key'}), 401

    data = request.get_json()
    long_url = data.get('url')
    if not long_url:
        return jsonify({'error': 'URL required'}), 400

    short_code = generate_short_code()
    while links_collection.find_one({'short_code': short_code}):
        short_code = generate_short_code()

    new_link = {
        'long_url': long_url,
        'short_code': short_code,
        'created_at': datetime.utcnow(),
        'status': 'active',
        'step': 2
    }
    links_collection.insert_one(new_link)

    short_url = url_for('redirect_to_long', short_code=short_code, _external=True)
    return jsonify({'short_url': short_url})

# ---------- Run the app ----------
if __name__ == '__main__':
    print("""
    ╔════════════════════════════════════════════════════════╗
    ║  Premium URL Shortener is running!                     ║
    ║  Access at: http://127.0.0.1:5000                      ║
    ║  Admin panel: http://127.0.0.1:5000/admin/login        ║
    ║  Default admin credentials: admin / admin123           ║
    ║  (Change immediately after first login)                 ║
    ╚════════════════════════════════════════════════════════╝
    """)
    app.run(debug=True, port=7400)
    
