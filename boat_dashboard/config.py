import os
from datetime import timedelta

class Config:
    # Security
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'boat-dashboard-super-secret-key-2026'
    
    # Databases
    MAIN_DATABASE = 'main.db'
    BOATS_FOLDER = 'boats'
    
    # Uploads
    UPLOADS_FOLDER = 'uploads'
    
    # Other settings
    TIMEZONE = 'Europe/Helsinki'
    PERMANENT_SESSION_LIFETIME = timedelta(hours=12)
    
    # Flask settings
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp', 'pdf', 'gpx'}
    MAX_CONTENT_LENGTH = 25 * 1024 * 1024  # 25 MB

