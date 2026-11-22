from functools import wraps
from flask import session, redirect, url_for, flash
from werkzeug.security import generate_password_hash, check_password_hash
from models import get_main_db, init_main_db

def init_auth():
    init_main_db()
    conn = get_main_db()
    if not conn.execute("SELECT 1 FROM users WHERE username='admin'").fetchone():
        pw_hash = generate_password_hash('admin123')
        conn.execute("INSERT INTO users (username, password_hash, role) VALUES (?, ?, 'admin')", 
                     ('admin', pw_hash))
        print("✅ Admin account created: admin / admin123")
    conn.commit()
    conn.close()

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def boat_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'current_boat_id' not in session:
            flash('Please select a boat to continue.', 'info')
            return redirect(url_for('select_boat'))
        return f(*args, **kwargs)
    return decorated_function
