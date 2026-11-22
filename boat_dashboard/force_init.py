from models import get_boat_db, init_boat_db
import os

print("=== FORCING DATABASE INITIALIZATION ===")

# Delete old database
if os.path.exists("boats/boat_1.db"):
    os.remove("boats/boat_1.db")
    print("Deleted old boat_1.db")

# Create and initialize
print("Creating boat_1...")
init_boat_db(1)

# Check result
conn = get_boat_db(1)
tables = [row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
print("Tables found:", tables)

status = conn.execute("SELECT * FROM status WHERE id=1").fetchone()
print("Status table exists:", status is not None)

conn.close()
print("Diagnostic finished.")
