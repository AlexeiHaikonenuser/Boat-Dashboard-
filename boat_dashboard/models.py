import sqlite3
import os
from datetime import datetime
import pytz
from config import Config

def get_main_db():
    conn = sqlite3.connect(Config.MAIN_DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def get_boat_db(boat_id):
    os.makedirs(Config.BOATS_FOLDER, exist_ok=True)
    db_path = os.path.join(Config.BOATS_FOLDER, f'boat_{boat_id}.db')
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn

def _ensure_column(conn, table, column, definition):
    """Add a column to an existing table. Does nothing if it is already there."""
    existing = {row[1] for row in conn.execute(f'PRAGMA table_info({table})').fetchall()}
    if column not in existing:
        conn.execute(f'ALTER TABLE {table} ADD COLUMN {column} {definition}')
        print(f"   added {table}.{column}")


def upgrade_main_db(conn):
    """Bring an older main.db up to the current schema without deleting rows."""
    _ensure_column(conn, 'users', 'preferred_language', "TEXT DEFAULT 'en'")
    _ensure_column(conn, 'users', 'notes', 'TEXT')
    _ensure_column(conn, 'boats', 'journal_title', "TEXT DEFAULT 'Journal'")
    _ensure_column(conn, 'boats', 'journal_public', 'INTEGER DEFAULT 0')
    _ensure_column(conn, 'boats', 'notes', 'TEXT')
    if _table_exists(conn, 'login_log'):
        _ensure_column(conn, 'login_log', 'success', 'INTEGER DEFAULT 1')
        _ensure_column(conn, 'login_log', 'created_at', 'TEXT')
    if _table_exists(conn, 'notifications'):
        _ensure_column(conn, 'notifications', 'active', 'INTEGER DEFAULT 1')
        _ensure_column(conn, 'notifications', 'image_path', 'TEXT')


def upgrade_boat_db(conn):
    """Bring an older boat_N.db up to the current schema without deleting rows."""
    _ensure_column(conn, 'sensor_readings', 'bilge_level', 'REAL')
    _ensure_column(conn, 'sensor_readings', 'humidity', 'REAL')
    _ensure_column(conn, 'sensor_readings', 'temperature', 'REAL')
    _ensure_column(conn, 'boat_settings', 'sensor_enabled', 'INTEGER DEFAULT 0')
    _ensure_column(conn, 'boat_settings', 'sensor_secret', 'TEXT')
    _ensure_column(conn, 'boat_settings', 'is_public', 'INTEGER DEFAULT 0')
    _ensure_column(conn, 'boat_settings', 'public_slug', 'TEXT')
    _ensure_column(conn, 'trips', 'is_public', 'INTEGER DEFAULT 0')
    _ensure_column(conn, 'trips', 'allow_comments', 'INTEGER DEFAULT 0')
    _ensure_column(conn, 'trips', 'is_published', 'INTEGER DEFAULT 0')
    _ensure_column(conn, 'trips', 'cover_image', 'TEXT')
    _ensure_column(conn, 'trips', 'published_at', 'TEXT')
    _ensure_column(conn, 'trips', 'views', 'INTEGER DEFAULT 0')
    _ensure_column(conn, 'expenses', 'receipt_path', 'TEXT')
    _ensure_column(conn, 'expenses', 'notes', 'TEXT')
    _ensure_column(conn, 'expenses', 'description', 'TEXT')
    if _table_exists(conn, 'trip_comments'):
        _ensure_column(conn, 'trip_comments', 'approved', 'INTEGER DEFAULT 1')


def _table_exists(conn, name):
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (name,),
    ).fetchone()
    return row is not None


def init_main_db():
    conn = get_main_db()
    conn.executescript('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT DEFAULT 'user',
            notes TEXT,
            preferred_language TEXT DEFAULT 'en',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS secure_codes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT UNIQUE NOT NULL,
            description TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS boats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            captain TEXT,
            description TEXT,
            journal_title TEXT DEFAULT 'Journal',
            journal_public INTEGER DEFAULT 0,
            notes TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS boat_users (
            boat_id INTEGER,
            user_id INTEGER,
            PRIMARY KEY (boat_id, user_id),
            FOREIGN KEY(boat_id) REFERENCES boats(id),
            FOREIGN KEY(user_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            message TEXT,
            image_path TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            active INTEGER DEFAULT 1
        );

        CREATE TABLE IF NOT EXISTS user_notifications (
            user_id INTEGER,
            notification_id INTEGER,
            seen_at TEXT DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (user_id, notification_id)
        );

        CREATE TABLE IF NOT EXISTS login_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            username TEXT,
            ip_address TEXT,
            user_agent TEXT,
            success INTEGER DEFAULT 1,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS app_settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );

        INSERT OR IGNORE INTO app_settings (key, value) VALUES ('secure_login', '1');
    ''')
    upgrade_main_db(conn)
    conn.commit()
    conn.close()


def secure_login_enabled():
    """True when visitors must enter a secure code before the login form."""
    conn = get_main_db()
    row = conn.execute(
        "SELECT value FROM app_settings WHERE key = 'secure_login'"
    ).fetchone()
    conn.close()
    if row is None:
        return True
    return row['value'] == '1'


def set_secure_login(enabled):
    conn = get_main_db()
    conn.execute(
        """
        INSERT INTO app_settings (key, value) VALUES ('secure_login', ?)
        ON CONFLICT(key) DO UPDATE SET value = excluded.value
        """,
        ('1' if enabled else '0',),
    )
    conn.commit()
    conn.close()

def init_boat_db(boat_id):
    """Initialize ALL tables for a specific boat"""
    conn = get_boat_db(boat_id)
    
    try:
        conn.executescript('''
            CREATE TABLE IF NOT EXISTS status (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                motor_running INTEGER DEFAULT 0,
                motor_start_time TEXT,
                total_motor_hours REAL DEFAULT 0
            );

        CREATE TABLE IF NOT EXISTS sensor_readings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
            temperature REAL,
            humidity REAL,
            boat_id INTEGER DEFAULT 1,
            bilge_level REAL
        );

            CREATE TABLE IF NOT EXISTS boat_settings (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                show_sensors INTEGER DEFAULT 0,
                boat_name TEXT DEFAULT 'My Boat',
                captain_name TEXT DEFAULT 'Captain',
                boat_number TEXT, 
                home_port TEXT, 
                registration TEXT,
                boat_type TEXT, 
                build_year TEXT, 
                length TEXT, 
                width TEXT,
                draft TEXT, 
                displacement TEXT, 
                engine TEXT, 
                sail_type TEXT, 
                notes TEXT,
                boat_image TEXT, 
                sensor_secret TEXT,
                is_public INTEGER DEFAULT 0,
                public_slug TEXT,
                sensor_enabled INTEGER DEFAULT 0,
                public_main INTEGER DEFAULT 1,
                public_info INTEGER DEFAULT 1,
                public_tips INTEGER DEFAULT 1,
                public_trips INTEGER DEFAULT 1,
                public_onboard INTEGER DEFAULT 1
            );
            CREATE TABLE IF NOT EXISTS boat_images (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                image_path TEXT NOT NULL,
                uploaded_at TEXT DEFAULT CURRENT_TIMESTAMP
            );

        CREATE TABLE IF NOT EXISTS documents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                category TEXT DEFAULT 'Other',
                file_path TEXT NOT NULL,
                expiry_date TEXT,
                notes TEXT,
                uploaded_at TEXT DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS guest_links (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                token TEXT UNIQUE NOT NULL,
                boat_id INTEGER NOT NULL,
                expires_at TEXT,
                can_edit INTEGER DEFAULT 0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS trips (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT,
                start_location TEXT,
                finish_location TEXT,
                start_time TEXT,
                end_time TEXT,
                captain TEXT,
                notes TEXT,
                motor_hours_end REAL,
                is_public INTEGER DEFAULT 0,
                allow_comments INTEGER DEFAULT 0,
                is_published INTEGER DEFAULT 0,
                cover_image TEXT,
                published_at TEXT,
                views INTEGER DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS motor_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                start_time TEXT, end_time TEXT, duration_hours REAL, notes TEXT
            );

            CREATE TABLE IF NOT EXISTS service_types (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                interval_hours INTEGER,
                category TEXT DEFAULT 'Other'
            );

            CREATE TABLE IF NOT EXISTS maintenance (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                service_type TEXT,
                done_at TEXT,
                motor_hours_at_service REAL,
                notes TEXT
            );

            CREATE TABLE IF NOT EXISTS onboard_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                category TEXT DEFAULT 'Other',
                checked INTEGER DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS passengers_master (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL
            );

            CREATE TABLE IF NOT EXISTS trip_passengers (
                trip_id INTEGER,
                passenger_id INTEGER,
                PRIMARY KEY (trip_id, passenger_id)
            );

        CREATE TABLE IF NOT EXISTS trip_images (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                trip_id INTEGER,
                image_path TEXT NOT NULL,
                uploaded_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(trip_id) REFERENCES trips(id) ON DELETE CASCADE
            );


            CREATE TABLE IF NOT EXISTS tips (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                category TEXT DEFAULT 'Other',
                content TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS tip_files (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tip_id INTEGER,
                file_path TEXT NOT NULL,
                file_type TEXT,
                uploaded_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
            
            CREATE TABLE IF NOT EXISTS expenses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                category TEXT NOT NULL,
                amount REAL NOT NULL,
                description TEXT,
                expense_date TEXT DEFAULT CURRENT_TIMESTAMP,
                receipt_path TEXT,
                notes TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS trip_comments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                trip_id INTEGER NOT NULL,
                author_name TEXT NOT NULL,
                content TEXT NOT NULL,
                approved INTEGER DEFAULT 0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(trip_id) REFERENCES trips(id) ON DELETE CASCADE
            );

            -- Default data
            INSERT OR IGNORE INTO status (id) VALUES (1);
            INSERT OR IGNORE INTO boat_settings (id, boat_name, captain_name) 
            VALUES (1, 'My Boat', 'Captain');
        ''')

        try:
            conn.execute("ALTER TABLE trip_comments ADD COLUMN approved INTEGER DEFAULT 1")
        except sqlite3.OperationalError:
            pass

        upgrade_boat_db(conn)
        conn.commit()
        print(f"✅ Boat_{boat_id} fully initialized with all tables!")
        
    except Exception as e:
        print(f"❌ Error initializing boat_{boat_id}: {e}")
    finally:
        conn.close()

def now_hki():
    tz = pytz.timezone(Config.TIMEZONE)
    return datetime.now(tz)
