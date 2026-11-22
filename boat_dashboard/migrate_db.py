# migrate_db.py
# Upgrade an existing Boat Dashboard database to this version.
# Does not delete boats, users, trips, or photos.
#
# Do NOT run fresh_start.py if you want to keep old data.

import os
import sqlite3
from models import init_main_db, init_boat_db, get_main_db
from config import Config

print("Upgrading existing Boat Dashboard databases...\n")

if not os.path.exists(Config.MAIN_DATABASE):
    print(f"No {Config.MAIN_DATABASE} in this folder.")
    print("Copy your old main.db here first. Do not run fresh_start.py.")
    raise SystemExit(1)

# Back up before changing anything
backup = Config.MAIN_DATABASE + '.bak'
if not os.path.exists(backup):
    import shutil
    shutil.copy2(Config.MAIN_DATABASE, backup)
    print(f"Backup written: {backup}")

init_main_db()

conn = get_main_db()
boats = conn.execute("SELECT id, name FROM boats ORDER BY id").fetchall()
conn.close()

if not boats:
    print("main.db has no boats.")
else:
    print("Boats found:")
    for boat in boats:
        print(f"   id {boat['id']}: {boat['name']}")
        db_path = os.path.join(Config.BOATS_FOLDER, f"boat_{boat['id']}.db")
        if not os.path.exists(db_path):
            print(f"   MISSING file: {db_path}")
            print("   Copy boats/boat_{0}.db from the old installation.".format(boat['id']))
            continue
        boat_backup = db_path + '.bak'
        if not os.path.exists(boat_backup):
            import shutil
            shutil.copy2(db_path, boat_backup)
            print(f"   Backup written: {boat_backup}")
        init_boat_db(boat['id'])

print("\nDone. Your boat IDs are unchanged.")
print("Start the app with: python app.py")
print("Do not run fresh_start.py — that deletes main.db and the boats folder.")
