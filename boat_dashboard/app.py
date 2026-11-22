from flask import Flask, redirect, url_for, session, request, flash
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from datetime import datetime
from translations import get_text, get_category_text
from werkzeug.middleware.proxy_fix import ProxyFix
import os
from datetime import timedelta
app = Flask(__name__)
app.permanent_session_lifetime = timedelta(days=30)
app.config['SESSION_COOKIE_PATH'] = '/'
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_NAME'] = 'boat_session'
app.config['SESSION_COOKIE_SECURE'] = True
#app.config['SESSION_COOKIE_PATH'] = '/boat'
app.config['SESSION_COOKIE_DOMAIN'] = None
#app.config['APPLICATION_ROOT'] = '/boat'
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)
app.config['MAX_CONTENT_LENGTH'] = 25 * 1024 * 1024  # 25 MB
app.config['UPLOAD_FOLDER'] = 'uploads'

limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=["100 per minute"],
    storage_uri="memory://"
)

# Custom date filter
@app.template_filter('ddmmyyyy')
def ddmmyyyy(value):
    if value:
        try:
            if isinstance(value, str):
                dt = datetime.fromisoformat(value.replace('Z', '+00:00'))
            else:
                dt = value
            return dt.strftime('%d.%m.%Y')
        except:
            return str(value)[:10]
    return ''

app.config.from_object('config.Config')

# ====================== IMPORTS ======================
import models
import auth
from routes import register_routes

# ====================== SAFE INITIALIZATION ======================
models.init_main_db()

# Auto-initialize all existing boats
try:
    conn = models.get_main_db()
    boats = conn.execute("SELECT id FROM boats").fetchall()
    conn.close()

    for boat in boats:
        try:
            models.init_boat_db(boat['id'])
        except:
            pass  # already exists or minor error
except:
    pass  # main.db might be missing on first run

# ====================== TRANSLATION SUPPORT ======================
@app.context_processor
def inject_translations():
    def translate(key, lang=None):
        if lang is None:
            lang = session.get('language', 'en')
        return get_text(key, lang)
    
    def category_text(cat, lang=None):
        if lang is None:
            lang = session.get('language', 'en')
        return get_category_text(cat, lang)
    
    return {
        'get_text': translate,
        'get_category_text': category_text
    }

@app.before_request
def set_default_language():
    if 'language' not in session:
        session['language'] = 'en'


# ====================== REGISTER ROUTES ======================
register_routes(app)

if __name__ == '__main__':
    print("🚤 Boat Dashboard (Multi-Boat) started at http://0.0.0.0:5000")
    print("Default Admin: admin / admin123")
    app.run(host='0.0.0.0', port=5000, debug=True)
