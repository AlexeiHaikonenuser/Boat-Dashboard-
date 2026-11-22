# fresh_start.py - One-Click Fresh Start for Boat Dashboard
import os
import shutil
from models import get_main_db, init_main_db, init_boat_db
from werkzeug.security import generate_password_hash

print("🧹 Starting Fresh Start for Boat Dashboard...\n")

# Step 1: Remove old data
print("Removing old databases and files...")

for item in ['main.db', 'boats', 'static/uploads', 'logs']:
    if os.path.exists(item):
        if os.path.isdir(item):
            shutil.rmtree(item)
        else:
            os.remove(item)
        print(f"   Deleted {item}")

# Step 2: Create fresh folders
os.makedirs('boats', exist_ok=True)
os.makedirs('static/uploads', exist_ok=True)
os.makedirs('static/uploads/notifications', exist_ok=True)
os.makedirs('logs', exist_ok=True)
print("   Created fresh folders")

# Step 3: Initialize main database
print("\nInitializing main database...")
init_main_db()

conn = get_main_db()

# Create admin user
pw_hash = generate_password_hash('admin123')
conn.execute("""
    INSERT OR IGNORE INTO users (username, password_hash, role, preferred_language) 
    VALUES (?, ?, 'admin', 'en')
""", ('admin', pw_hash))
print("✅ Admin account created: admin / admin123")

# Insert default secure code
conn.execute("""
    INSERT OR IGNORE INTO secure_codes (code, description) 
    VALUES (?, ?)
""", ('1234', 'Default secure code'))
print("✅ Secure code created: 1234")

# Step 4: Create default boat
print("\nCreating default boat...")
conn.execute("INSERT OR IGNORE INTO boats (name, captain, journal_title) VALUES (?, ?, ?)", 
             ("My First Boat", "Captain", "Journal"))
conn.commit()

admin = conn.execute("SELECT id FROM users WHERE username='admin'").fetchone()
boat_row = conn.execute("SELECT id FROM boats ORDER BY id LIMIT 1").fetchone()
if admin and boat_row:
    conn.execute(
        "INSERT OR IGNORE INTO boat_users (boat_id, user_id) VALUES (?, ?)",
        (boat_row['id'], admin['id'])
    )
    conn.commit()
    print("✅ Admin assigned to the default boat")

boats = conn.execute("SELECT id FROM boats").fetchall()
conn.close()

for boat in boats:
    print(f"Initializing boat_{boat['id']}...")
    init_boat_db(boat['id'])

print("\n🎉 Fresh start completed successfully!")
print("="*70)
print("Login Info:")
print("   Secure Code : 1234")
print("   Username    : admin")
print("   Password    : admin123")
print("="*70)
print("\nNext steps:")
print("   1. pip install -r requirements.txt")
print("   2. python app.py")
print("   3. Open http://localhost:5000")
print("   4. Change the default password after first login!")
