from flask import render_template, request, redirect, url_for, flash, session
from models import get_main_db, get_boat_db, init_boat_db, now_hki, secure_login_enabled, set_secure_login
from utils import get_motor_hours_formatted, save_upload
from auth import login_required, boat_required
from datetime import datetime, date
from werkzeug.security import check_password_hash, generate_password_hash
import os
import shutil
from config import Config
from werkzeug.utils import secure_filename

def allowed_file(filename):
    """Only allow images, PDF and GPX files"""
    if not filename:
        return False
    ext = filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''
    return ext in Config.ALLOWED_EXTENSIONS


def write_login_log(username, ip, user_agent, success=True):
    try:
        log_dir = os.path.join(os.path.dirname(__file__), "logs")
        os.makedirs(log_dir, exist_ok=True)
        log_file = os.path.join(log_dir, "login.log")
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        status = "OK" if success else "FAIL"
        line = f"{now} | {status} | {username} | {ip} | {user_agent[:120]}\n"
        with open(log_file, "a") as f:
            f.write(line)
    except Exception:
        pass

def register_routes(app):

    @app.route('/mark_notification_seen', methods=['POST'])
    @login_required
    def mark_notification_seen():
        if session.get('show_notification'):
            nid = session['show_notification']['id']
            print(f"DEBUG mark_seen: user={session['user_id']}, notif={nid}")
            conn = get_main_db()
            conn.execute("""
                INSERT OR IGNORE INTO user_notifications (user_id, notification_id)
                VALUES (?, ?)
            """, (session['user_id'], nid))
            conn.commit()
            conn.close()
            session.pop('show_notification', None)
            session.modified = True
        return redirect(request.referrer or url_for('index'))

    # ======================  API ENDPOINT =====================
    @app.route('/api/sensor', methods=['POST'])
    def receive_sensor_data():
        try:
            data = request.get_json()
            boat_id = data.get('boat_id')
            secret = data.get('secret')
            temperature = data.get('temperature')
            humidity = data.get('humidity')
            bilge_level = data.get('bilge_level')   # ← new

            if not all([boat_id, secret, temperature is not None, humidity is not None]):
                return {"status": "error", "message": "Missing data"}, 400

            conn = get_boat_db(boat_id)

            # Verify secret
            row = conn.execute("SELECT sensor_secret FROM boat_settings WHERE id=1").fetchone()
            if not row or row['sensor_secret'] != secret:
                conn.close()
                return {"status": "error", "message": "Invalid secret"}, 403

            # Save data (including bilge_level)
            conn.execute("""
                INSERT INTO sensor_readings (temperature, humidity, bilge_level)
                VALUES (?, ?, ?)
            """, (temperature, humidity, bilge_level))
            conn.commit()
            conn.close()

            return {"status": "success"}, 200

        except Exception as e:
            return {"status": "error", "message": str(e)}, 500

#===========================SECURE CODE for uplod sensor data ==========
    @app.route('/admin/boats/update_sensor_secret', methods=['POST'])
    @login_required
    def update_boat_sensor_secret():
        if session.get('role') != 'admin':
            flash('Access denied.', 'danger')
            return redirect(url_for('admin_boats'))

        boat_id = request.form.get('boat_id')
        sensor_secret = request.form.get('sensor_secret', '').strip()

        if not boat_id:
            flash('Boat ID missing.', 'danger')
            return redirect(url_for('admin_boats'))

        try:
            conn = get_boat_db(int(boat_id))
            conn.execute("UPDATE boat_settings SET sensor_secret = ? WHERE id=1", (sensor_secret,))
            conn.commit()
            conn.close()
            flash('Sensor secret updated.', 'success')
        except Exception as e:
            flash(f'Error: {e}', 'danger')

        return redirect(url_for('admin_boats'))


# ====================== API HISTORY =========================
    @app.route('/api/sensor/history')
    @login_required
    @boat_required
    def sensor_history():
        boat_id = session['current_boat_id']
        conn = get_boat_db(boat_id)

        settings = conn.execute("SELECT sensor_enabled FROM boat_settings WHERE id=1").fetchone()
        if not settings or not settings['sensor_enabled']:
            conn.close()
            flash('Sensor integration is disabled for this boat.', 'warning')
            return redirect(url_for('index'))

        readings = conn.execute("""
            SELECT timestamp, temperature, humidity, bilge_level
            FROM sensor_readings
            ORDER BY timestamp DESC
            LIMIT 500
        """).fetchall()
        conn.close()

        return render_template('sensor_history.html', readings=readings)

#=================== Sensor Enable / Disable ===================
    @app.route('/admin/boats/update_sensors/<int:boat_id>', methods=['POST'])
    @login_required
    def update_boat_sensors(boat_id):
        if session.get('role') != 'admin':
            flash('Access denied.', 'danger')
            return redirect(url_for('admin_boats'))

        sensor_enabled = 1 if request.form.get('sensor_enabled') else 0

        conn = get_boat_db(boat_id)
        conn.execute("UPDATE boat_settings SET sensor_enabled = ? WHERE id = 1", (sensor_enabled,))
        conn.commit()
        conn.close()

        flash('Sensor setting saved.', 'success')
        return redirect(url_for('admin_boats'))

#=================== SECURE ===================
    @app.route('/secure', methods=['GET', 'POST'])
    def secure_code():
        if not secure_login_enabled():
            return redirect(url_for('login'))
        if request.method == 'POST':
            entered_code = request.form.get('secure_code', '').strip()
            ip = request.headers.get('X-Forwarded-For', request.remote_addr)
            if ip and ',' in ip:
                ip = ip.split(',')[0].strip()
            user_agent = request.headers.get('User-Agent', '')[:250]

            success = False
            if entered_code:
                conn = get_main_db()
                row = conn.execute(
                    "SELECT id FROM secure_codes WHERE code = ?",
                    (entered_code,)
                ).fetchone()
                conn.close()
                success = row is not None

        # log
            try:
                write_login_log(
                    f"SECURE_CODE_{'OK' if success else 'FAIL'}",
                    ip,
                    user_agent,
                    success=success
                )
            except:
                pass

            conn = get_main_db()
            conn.execute("""
                INSERT INTO login_log (username, ip_address, user_agent)
                VALUES (?, ?, ?)
            """, (
                f"SECURE_CODE_{'OK' if success else 'FAIL'}",
                ip,
                user_agent
            ))
            conn.commit()
            conn.close()

            if success:
                session['secure_passed'] = True
                session.modified = True
                return redirect(url_for('login'))

#            flash('Wrong secure code.', 'danger')

        return render_template('secure.html')
#================== secure codes ============================
    @app.route('/admin/secure_codes', methods=['GET', 'POST'])
    @login_required
    def admin_secure_codes():
        if session.get('role') != 'admin':
            flash('Access denied.', 'danger')
            return redirect(url_for('index'))

        conn = get_main_db()
        if request.method == 'POST':
            action = request.form.get('action')
            if action == 'add':
                code = request.form.get('code', '').strip()
                desc = request.form.get('description', '').strip()
                if code:
                    try:
                        conn.execute(
                            "INSERT INTO secure_codes (code, description) VALUES (?, ?)",
                            (code, desc)
                        )
                        conn.commit()
                        flash('Code added.', 'success')
                    except sqlite3.IntegrityError:
                        flash('Code already exists.', 'danger')
            elif action == 'delete':
                code_id = request.form.get('code_id')
                if code_id:
                    conn.execute("DELETE FROM secure_codes WHERE id = ?", (code_id,))
                    conn.commit()
                    flash('Code deleted.', 'success')
            elif action == 'toggle_secure':
                set_secure_login(request.form.get('secure_login') == '1')
                flash('Secure code login updated.', 'success')
        codes = conn.execute("SELECT * FROM secure_codes ORDER BY created_at DESC").fetchall()
        enabled = secure_login_enabled()
        conn.close()
        return render_template('admin_secure_codes.html', codes=codes, secure_login=enabled)

	#==================== LOGIN ==========================
    @app.route('/login', methods=['GET', 'POST'])
    def login():
        if secure_login_enabled() and not session.get('secure_passed'):
            return redirect(url_for('secure_code'))

        if request.method == 'POST':
            username = request.form.get('username', '').strip()
            password = request.form.get('password', '')

            conn = get_main_db()
            user = conn.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()

            if user and check_password_hash(user['password_hash'], password):
                # Successful login
                session['user_id'] = user['id']
                session['username'] = user['username']
                session['role'] = user['role'] if user['role'] is not None else 'user'

                # Preferred language
                preferred_lang = user['preferred_language'] if 'preferred_language' in dict(user).keys() else None
                if preferred_lang and preferred_lang in ['en', 'fi', 'sv', 'ru', 'de']:
                    session['language'] = preferred_lang
                else:
                    session['language'] = 'en'

                # Log the login
                ip = request.headers.get('X-Forwarded-For', request.remote_addr)
                if ip and ',' in ip:
                    ip = ip.split(',')[0].strip()
                user_agent = request.headers.get('User-Agent', '')[:250]

                write_login_log(user['username'], ip, user_agent, success=True)

                conn.execute("""
                    INSERT INTO login_log (user_id, username, ip_address, user_agent)
                    VALUES (?, ?, ?, ?)
                """, (user['id'], user['username'], ip, user_agent))
                conn.commit()

                # Check for new notification
                notif = conn.execute("""
                    SELECT * FROM notifications
                    WHERE active = 1
                    ORDER BY created_at DESC LIMIT 1
                """).fetchone()

                if notif:
                    seen = conn.execute("""
                        SELECT 1 FROM user_notifications
                        WHERE user_id = ? AND notification_id = ?
                    """, (user['id'], notif['id'])).fetchone()
                    print("DEBUG: notif found, seen =", seen)
                    if not seen:
                        image_path = notif['image_path'] if 'image_path' in dict(notif).keys() else None
                        session['show_notification'] = {
                            'id': notif['id'],
                            'title': notif['title'],
                            'message': notif['message'],
                            'image_path': image_path
                        }
                        print("DEBUG: notif found, seen =", seen)

                conn.close()
                session.pop('secure_passed', None)
#                flash(f'Welcome back, {user["username"]}!', 'success')
                return redirect(url_for('select_boat'))
            else:
                # Failed login
                ip = request.headers.get('X-Forwarded-For', request.remote_addr)
                if ip and ',' in ip:
                    ip = ip.split(',')[0].strip()
                user_agent = request.headers.get('User-Agent', '')[:250]
                write_login_log(username or "UNKNOWN", ip, user_agent, success=False)

#                flash('Invalid username or password.', 'danger')
                if conn:
                    conn.close()

        return render_template('login.html')

#==================== SET LANGUAGE ======================
    @app.route('/set_language/<lang>')
    @app.route('/set_language/<lang>/')
    def set_language(lang):
        if lang in ['en', 'fi', 'sv', 'ru', 'de']:
            session['language'] = lang
            session.permanent = True
            session.modified = True
        next_url = request.args.get('next') or request.referrer or '/'
        if next_url.endswith('?'):
            next_url = next_url[:-1]
        return redirect(next_url)

# ====================== LOGOUT ======================
    @app.route('/logout')
    def logout():
        session.clear()
        if secure_login_enabled():
            return redirect(url_for('secure_code'))
        return redirect(url_for('login'))

# ====================== PASSWORD CHANGE ======================
    @app.route('/change_password', methods=['GET', 'POST'])
    @login_required
    def change_password():
        if request.method == 'POST':
            current_password = request.form.get('current_password')
            new_password = request.form.get('new_password')
            confirm_password = request.form.get('confirm_password')
            new_username = request.form.get('new_username', '').strip() if session.get('role') == 'admin' else None

            conn = get_main_db()
            user = conn.execute("SELECT * FROM users WHERE id=?", (session['user_id'],)).fetchone()
            conn.close()

            if not check_password_hash(user['password_hash'], current_password):
                flash('Current password is incorrect.', 'danger')
                return redirect(url_for('change_password'))

            if new_password and new_password != confirm_password:
                flash('New passwords do not match.', 'danger')
                return redirect(url_for('change_password'))

            if new_password and len(new_password) < 6:
                flash('New password must be at least 6 characters.', 'danger')
                return redirect(url_for('change_password'))

            conn = get_main_db()
            new_hash = generate_password_hash(new_password) if new_password else user['password_hash']
            new_un = new_username if new_username and session.get('role') == 'admin' else user['username']

            conn.execute("UPDATE users SET username=?, password_hash=? WHERE id=?", 
                        (new_un, new_hash, session['user_id']))
            conn.commit()
            conn.close()

            session['username'] = new_un
            flash('✅ Password updated successfully!', 'success')
            return redirect(url_for('index'))

        return render_template('change_password.html')

# ====================== ADMIN NOTIFICATIONS ======================
    @app.route('/admin/notifications', methods=['GET', 'POST'])
    @login_required
    def admin_notifications():
        if session.get('role') != 'admin':
            flash('Admin access only.', 'danger')
            return redirect(url_for('index'))

        conn = get_main_db()

        if request.method == 'POST':
            title = request.form.get('title', '').strip()
            message = request.form.get('message', '').strip()
            image = request.files.get('image')

            image_path = None
            if image and image.filename and allowed_file(image.filename):
                filename = secure_filename(image.filename)
                upload_dir = os.path.join('static', 'uploads', 'notifications')
                stored = save_upload(image, upload_dir, filename)
                image_path = f'uploads/notifications/{stored}'

            if title and message:
                conn.execute("""
                    INSERT INTO notifications (title, message, image_path)
                    VALUES (?, ?, ?)
                """, (title, message, image_path))
                conn.commit()
                flash('Notification created successfully!', 'success')

        notifications = conn.execute("SELECT * FROM notifications ORDER BY created_at DESC").fetchall()
        conn.close()
        return render_template('admin_notifications.html', notifications=notifications)


    @app.route('/admin/notifications/delete/<int:nid>', methods=['POST'])
    @login_required
    def delete_notification(nid):
        if session.get('role') != 'admin':
            return redirect(url_for('index'))
        conn = get_main_db()
        conn.execute("DELETE FROM notifications WHERE id=?", (nid,))
        conn.execute("DELETE FROM user_notifications WHERE notification_id=?", (nid,))
        conn.commit()
        conn.close()
        flash('Notification deleted.', 'success')
        return redirect(url_for('admin_notifications'))


# ====================== DOCUMENTS ======================
    @app.route('/documents')
    @login_required
    @boat_required
    def documents():
        boat_id = session['current_boat_id']
        conn = get_boat_db(boat_id)
        docs = conn.execute("SELECT * FROM documents ORDER BY category, uploaded_at DESC").fetchall()
        categories = sorted({d['category'] for d in docs if d['category']})
        conn.close()
        return render_template('documents.html', documents=docs, categories=categories)

    @app.route('/documents/upload', methods=['POST'])
    @login_required
    @boat_required
    def upload_document():
        boat_id = session['current_boat_id']
        title = request.form.get('title', '').strip()
        category = request.form.get('category', 'Other')
        expiry_date = request.form.get('expiry_date') or None
        notes = request.form.get('notes', '').strip()

        if 'file' not in request.files or not title:
            flash('Enter a title and choose a file.', 'danger')
            return redirect(url_for('documents'))

        file = request.files['file']
        if file and file.filename and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            upload_dir = os.path.join('static', 'uploads', f'boat_{boat_id}', 'documents')
            stored = save_upload(file, upload_dir, filename)

            conn = get_boat_db(boat_id)
            conn.execute("""
                INSERT INTO documents (title, category, file_path, expiry_date, notes)
                VALUES (?, ?, ?, ?, ?)
            """, (title, category, f'uploads/boat_{boat_id}/documents/{stored}', expiry_date, notes))
            conn.commit()
            conn.close()
            flash('Document uploaded.', 'success')
        else:
            flash('File type is not allowed.', 'danger')
        return redirect(url_for('documents'))

    @app.route('/documents/delete/<int:doc_id>', methods=['POST'])
    @login_required
    @boat_required
    def delete_document(doc_id):
        boat_id = session['current_boat_id']
        conn = get_boat_db(boat_id)
        doc = conn.execute("SELECT file_path FROM documents WHERE id=?", (doc_id,)).fetchone()
        if doc:
            filepath = os.path.join('static', doc['file_path'])
            if os.path.exists(filepath):
                try:
                    os.remove(filepath)
                except Exception:
                    pass
            conn.execute("DELETE FROM documents WHERE id=?", (doc_id,))
            conn.commit()
            flash('Document deleted.', 'success')
        conn.close()
        return redirect(url_for('documents'))

#==================== EXPORT DATA ==================
    @app.route('/export_boat/<int:boat_id>')
    @login_required
    def export_boat(boat_id):
        if session.get('role') != 'admin' and session.get('current_boat_id') != boat_id:
            flash('Access denied.', 'danger')
            return redirect(url_for('index'))

        import shutil
        import zipfile
        import sqlite3
        from datetime import datetime
        from flask import send_file

        timestamp = datetime.now().strftime('%Y%m%d_%H%M')
        boat_folder = f"export_boat_{boat_id}_{timestamp}"
        zip_path = f"{boat_folder}.zip"

        try:
            os.makedirs(boat_folder, exist_ok=True)
            notes_folder = os.path.join(boat_folder, 'notes')
            os.makedirs(notes_folder, exist_ok=True)

            src_db = os.path.join(Config.BOATS_FOLDER, f'boat_{boat_id}.db')
            if os.path.exists(src_db):
                dest_db = os.path.join(boat_folder, f'boat_{boat_id}.db')
                shutil.copy2(src_db, dest_db)

                conn = sqlite3.connect(dest_db)
                conn.row_factory = sqlite3.Row
                try:
                    conn.execute("UPDATE boat_settings SET sensor_secret = NULL WHERE id = 1")
                    conn.commit()

                    settings = conn.execute("SELECT notes FROM boat_settings WHERE id=1").fetchone()
                    if settings and settings['notes']:
                        with open(os.path.join(notes_folder, 'boat_notes.txt'), 'w', encoding='utf-8') as f:
                            f.write(settings['notes'])

                    tips = conn.execute("SELECT title, category, content, created_at FROM tips ORDER BY created_at").fetchall()
                    for i, tip in enumerate(tips, 1):
                        safe_title = "".join(c for c in (tip['title'] or '') if c.isalnum() or c in (' ', '-', '_')).strip()[:40]
                        filename = f"tip_{i}_{safe_title}.txt"
                        with open(os.path.join(notes_folder, filename), 'w', encoding='utf-8') as f:
                            f.write(f"Title: {tip['title']}\n")
                            f.write(f"Category: {tip['category']}\n")
                            f.write(f"Created: {tip['created_at']}\n\n")
                            f.write(tip['content'] or '')
                except Exception as e:
                    print("Notes export error:", e)
                finally:
                    conn.close()

            upload_src = os.path.join('static', 'uploads', f'boat_{boat_id}')
            if os.path.exists(upload_src):
                shutil.copytree(upload_src, os.path.join(boat_folder, 'uploads'), dirs_exist_ok=True)

            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for root, dirs, files in os.walk(boat_folder):
                    for file in files:
                        file_path = os.path.join(root, file)
                        arcname = os.path.relpath(file_path, boat_folder)
                        zipf.write(file_path, arcname)

            return send_file(
                zip_path,
                as_attachment=True,
                download_name=f"boat_{boat_id}_backup_{timestamp}.zip",
                mimetype='application/zip'
            )
        finally:
            if os.path.exists(boat_folder):
                shutil.rmtree(boat_folder, ignore_errors=True)
# ====================== IMAGE ======================
    @app.route('/upload_boat_images', methods=['POST'])
    @login_required
    @boat_required
    def upload_boat_images():
        if 'files' not in request.files:
            flash('No files selected', 'danger')
            return redirect(url_for('index'))

        boat_id = session['current_boat_id']
        files = request.files.getlist('files')
        uploaded = 0

        # Create upload directory for this boat
        upload_dir = os.path.join('static', 'uploads', f'boat_{boat_id}')
        os.makedirs(upload_dir, exist_ok=True)

        conn = get_boat_db(boat_id)

        for file in files:
            if file and file.filename and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                stored = save_upload(file, upload_dir, filename)
                
                # Save to database
                conn.execute("""
                    INSERT INTO boat_images (image_path) 
                    VALUES (?)
                """, (f'uploads/boat_{boat_id}/{stored}',))
                uploaded += 1

        conn.commit()
        conn.close()

        #if uploaded > 0:
            #flash(f'✅ {uploaded} file(s) uploaded successfully!', 'success')
        #else:
            #flash('❌ No valid files uploaded. Allowed: Images, PDF, GPX', 'danger')

        return redirect(url_for('index'))


    @app.route('/delete_boat_images', methods=['POST'])
    @login_required
    @boat_required
    def delete_boat_images():
        boat_id = session.get('current_boat_id')
        ids = request.form.getlist('image_ids')
        if not boat_id or not ids:
            flash('Nothing to delete.', 'warning')
            return redirect('/boat')

        conn = get_boat_db(boat_id)
        deleted = 0
        for image_id in ids:
            image = conn.execute("SELECT image_path FROM boat_images WHERE id=?", (image_id,)).fetchone()
            if image:
                filepath = os.path.join('static', image['image_path'])
                if os.path.exists(filepath):
                    try:
                        os.remove(filepath)
                    except Exception:
                        pass
                conn.execute("DELETE FROM boat_images WHERE id=?", (image_id,))
                deleted += 1
        conn.commit()
        conn.close()
        flash(f'{deleted} photo(s) deleted.', 'success')
        return redirect('/boat/?nocache=' + str(int(datetime.now().timestamp())))

    # ====================== BOAT SELECTION ======================
    @app.route('/select_boat')
    @login_required
    def select_boat():
        conn = get_main_db()
        boats = conn.execute("""
            SELECT b.* FROM boats b
            JOIN boat_users bu ON b.id = bu.boat_id
            WHERE bu.user_id = ? ORDER BY b.name
        """, (session['user_id'],)).fetchall()
        conn.close()
        return render_template('select_boat.html', boats=boats)

    @app.route('/switch_boat/<int:boat_id>')
    @login_required
    def switch_boat(boat_id):
        conn = get_main_db()
        access = conn.execute("SELECT 1 FROM boat_users WHERE boat_id=? AND user_id=?", 
                            (boat_id, session['user_id'])).fetchone()
        if not access:
            conn.close()
            flash('Access denied.', 'danger')
            return redirect(url_for('select_boat'))

        boat_row = conn.execute("SELECT name FROM boats WHERE id=?", (boat_id,)).fetchone()
        conn.close()

        if boat_row:
            session['current_boat_id'] = boat_id
            session['current_boat_name'] = boat_row['name']
            #flash(f'Switched to boat: {boat_row["name"]}', 'success')
            return redirect(url_for('index'))
        else:
            #flash('Boat not found.', 'danger')
            return redirect(url_for('select_boat'))

# ====================== ADMIN: BOATS ======================
    @app.route('/admin/boats')
    @login_required
    def admin_boats():
        if session.get('role') != 'admin':
            return redirect(url_for('index'))
        conn = get_main_db()
        boats = conn.execute("SELECT * FROM boats ORDER BY name").fetchall()
        users = conn.execute("SELECT id, username FROM users ORDER BY username").fetchall()
        boat_users = {}
        rows = conn.execute("""
            SELECT bu.boat_id, u.id, u.username
            FROM boat_users bu
            JOIN users u ON u.id = bu.user_id
        """).fetchall()
        for row in rows:
            boat_users.setdefault(row['boat_id'], []).append(row)
        conn.close()

        boats_list = []
        for boat in boats:
            b = dict(boat)
            b['is_public'] = boat['journal_public'] or 0
            try:
                bconn = get_boat_db(boat['id'])
                settings = bconn.execute(
                    "SELECT sensor_enabled, public_slug FROM boat_settings WHERE id=1"
                ).fetchone()
                bconn.close()
                b['sensor_enabled'] = 1 if settings and settings['sensor_enabled'] else 0
                b['public_slug'] = settings['public_slug'] if settings else None
            except Exception as e:
                print(f"admin_boats error for boat {boat['id']}: {e}")
                b['sensor_enabled'] = 0
            boats_list.append(b)

        return render_template('admin_boats.html',
                               boats=boats_list,
                               users=users,
                               boat_users=boat_users)


    @app.route('/admin/boats/create', methods=['POST'])
    @login_required
    def create_boat():
        if session.get('role') != 'admin':
            return redirect(url_for('index'))

        name = request.form.get('name', '').strip()
        captain = request.form.get('captain', '').strip()

        if not name:
            flash('Boat name is required.', 'danger')
            return redirect(url_for('admin_boats'))

        conn = get_main_db()
        cursor = conn.execute("INSERT INTO boats (name, captain) VALUES (?, ?)", (name, captain))
        boat_id = cursor.lastrowid
        conn.commit()
        conn.close()

        init_boat_db(boat_id)
        flash(f'Boat "{name}" created successfully!', 'success')
        return redirect(url_for('admin_boats'))

    @app.route('/admin/boats/update_notes', methods=['POST'])
    @login_required
    def update_boat_notes():
        if session.get('role') != 'admin':
            flash('Admin access only.', 'danger')
            return redirect(url_for('admin_boats'))

        boat_id = request.form.get('boat_id')
        notes = request.form.get('notes', '').strip()

        if boat_id:
            conn = get_main_db()
            conn.execute("UPDATE boats SET notes=? WHERE id=?", (notes, boat_id))
            conn.commit()
            conn.close()
            flash('Boat notes updated successfully.', 'success')
        else:
            flash('Failed to update notes.', 'danger')

        return redirect(url_for('admin_boats'))

    @app.route('/admin/boats/assign', methods=['POST'])
    @login_required
    def assign_user_to_boat():
        if session.get('role') != 'admin':
            return redirect(url_for('index'))
        boat_id = request.form.get('boat_id')
        user_id = request.form.get('user_id')
        if boat_id and user_id:
            conn = get_main_db()
            conn.execute("INSERT OR IGNORE INTO boat_users (boat_id, user_id) VALUES (?, ?)", (boat_id, user_id))
            conn.commit()
            conn.close()
            flash('User assigned to boat.', 'success')
        return redirect(url_for('admin_boats'))

    @app.route('/admin/boats/unassign', methods=['POST'])
    @login_required
    def unassign_user_from_boat():
        if session.get('role') != 'admin':
            flash('Admin access only.', 'danger')
            return redirect(url_for('admin_boats'))

        boat_id = request.form.get('boat_id')
        user_id = request.form.get('user_id')

        if boat_id and user_id:
            conn = get_main_db()
            conn.execute("DELETE FROM boat_users WHERE boat_id=? AND user_id=?", 
                        (boat_id, user_id))
            conn.commit()
            conn.close()
            flash('User removed from boat successfully.', 'success')
        else:
            flash('Failed to remove user.', 'danger')

        return redirect(url_for('admin_boats'))

    @app.route('/admin/boats/delete/<int:boat_id>', methods=['POST'])
    @login_required
    def delete_boat(boat_id):
        if session.get('role') != 'admin':
            flash('Admin access only.', 'danger')
            return redirect(url_for('admin_boats'))

        conn = get_main_db()
        
        # Check if boat has users assigned
        users_count = conn.execute("SELECT COUNT(*) FROM boat_users WHERE boat_id=?", 
                                 (boat_id,)).fetchone()[0]

        if users_count > 0:
            flash('Cannot delete boat: Users are still assigned to it.', 'danger')
            conn.close()
            return redirect(url_for('admin_boats'))

        # Get boat name for confirmation message
        boat = conn.execute("SELECT name FROM boats WHERE id=?", (boat_id,)).fetchone()
        
        if boat:
            # Delete boat data
            conn.execute("DELETE FROM boat_users WHERE boat_id=?", (boat_id,))
            conn.execute("DELETE FROM boats WHERE id=?", (boat_id,))
            conn.commit()
            conn.close()

            # Delete boat database file
            db_path = os.path.join(Config.BOATS_FOLDER, f'boat_{boat_id}.db')
            if os.path.exists(db_path):
                os.remove(db_path)

            flash(f'Boat "{boat["name"]}" has been deleted successfully.', 'success')
        else:
            flash('Boat not found.', 'danger')
            conn.close()

        return redirect(url_for('admin_boats'))

# ====================== ADMIN: USERS ======================
    @app.route('/admin/users')
    @login_required
    def admin_users():
        if session.get('role') != 'admin':
            flash('Admin access only.', 'danger')
            return redirect(url_for('index'))
        conn = get_main_db()
        users = conn.execute("SELECT id, username, role, notes, created_at FROM users ORDER BY username").fetchall()
        conn.close()
        return render_template('admin_users.html', users=users)

    @app.route('/admin/users/add', methods=['POST'])
    @login_required
    def add_user():
        if session.get('role') != 'admin':
            flash('Admin access only.', 'danger')
            return redirect(url_for('index'))

        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        role = request.form.get('role', 'user')

        if len(username) < 3 or len(password) < 6:
            flash('Username ≥ 3, Password ≥ 6 characters', 'danger')
            return redirect(url_for('admin_users'))

        conn = get_main_db()
        try:
            pw_hash = generate_password_hash(password)
            conn.execute("INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)",
                        (username, pw_hash, role))
            conn.commit()
            flash(f'User "{username}" created!', 'success')
        except:
            flash('Username already exists!', 'danger')
        conn.close()
        return redirect(url_for('admin_users'))

    @app.route('/admin/users/edit/<int:user_id>', methods=['GET', 'POST'])
    @login_required
    def edit_user(user_id):
        if session.get('role') != 'admin':
            flash('Admin access only.', 'danger')
            return redirect(url_for('index'))

        conn = get_main_db()
        if request.method == 'POST':
            username = request.form.get('username', '').strip()
            password = request.form.get('password', '').strip()
            role = request.form.get('role')
            notes = request.form.get('notes', '').strip()

            try:
                if password:
                    pw_hash = generate_password_hash(password)
                    conn.execute("UPDATE users SET username=?, password_hash=?, role=?, notes=? WHERE id=?",
                                (username, pw_hash, role, notes, user_id))
                else:
                    conn.execute("UPDATE users SET username=?, role=?, notes=? WHERE id=?",
                                (username, role, notes, user_id))
                conn.commit()
                flash('User updated successfully!', 'success')
            except:
                flash('Username already exists!', 'danger')
            return redirect(url_for('admin_users'))

        user = conn.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
        conn.close()
        return render_template('admin_edit_user.html', user=user)

    @app.route('/admin/users/delete/<int:user_id>', methods=['POST'])
    @login_required
    def delete_user(user_id):
        if session.get('role') != 'admin':
            return redirect(url_for('index'))

        conn = get_main_db()
        user = conn.execute("SELECT username FROM users WHERE id=?", (user_id,)).fetchone()
        if user and user['username'] == 'admin':
            flash('Cannot delete main admin!', 'danger')
        else:
            conn.execute("DELETE FROM users WHERE id=?", (user_id,))
            conn.execute("DELETE FROM boat_users WHERE user_id=?", (user_id,))
            conn.commit()
            flash('User deleted.', 'success')
        conn.close()
        return redirect(url_for('admin_users'))

    # ====================== DASHBOARD ======================
    @app.route('/')
    @app.route('/boat')
    @login_required
    @boat_required
    def index():
        boat_id = session['current_boat_id']
        conn = get_boat_db(boat_id)

        status = conn.execute("SELECT * FROM status WHERE id=1").fetchone()
        current_trip = conn.execute("SELECT * FROM trips WHERE end_time IS NULL ORDER BY id DESC LIMIT 1").fetchone()
        settings = conn.execute("SELECT * FROM boat_settings WHERE id=1").fetchone()
        sensor_enabled = settings['sensor_enabled'] if settings and settings['sensor_enabled'] else 0

        # Get all boat images for gallery
        boat_images = conn.execute("""
            SELECT * FROM boat_images
            ORDER BY uploaded_at DESC
        """).fetchall()

        # Get latest sensor reading
        latest_sensor = conn.execute("""
            SELECT temperature, humidity, bilge_level
            FROM sensor_readings
            ORDER BY timestamp DESC LIMIT 1
        """).fetchone()

        latest_temp = latest_sensor['temperature'] if latest_sensor else None
        latest_hum = latest_sensor['humidity'] if latest_sensor else None
        latest_bilge = latest_sensor['bilge_level'] if latest_sensor else None

        conn.close()

        return render_template('index.html',
            boat_name=session.get('current_boat_name', 'My Boat'),
            settings=settings,
            sensor_enabled=sensor_enabled,
            latest_temp=latest_temp,
            latest_hum=latest_hum,
            latest_bilge=latest_bilge,
            boat_images=boat_images,
            status=status,
            current_trip=current_trip
        )

#=============== Expenses ==========================
    @app.route('/expenses', methods=['GET', 'POST'])
    @login_required
    @boat_required
    def expenses():
        boat_id = session['current_boat_id']
        conn = get_boat_db(boat_id)

        if request.method == 'POST':
            # ADD
            if 'add_expense' in request.form:
                expense_date = request.form.get('expense_date') or date.today().isoformat()
                category = request.form.get('category', 'Other').strip() or 'Other'
                description = request.form.get('description', '').strip()
                amount = request.form.get('amount', type=float)
                notes = request.form.get('notes', '').strip()

                if amount and amount > 0:
                    receipt_path = None
                    if 'receipt' in request.files:
                        file = request.files['receipt']
                        if file and file.filename and allowed_file(file.filename):
                            filename = secure_filename(file.filename)
                            upload_dir = os.path.join('static', 'uploads', f'boat_{boat_id}', 'expenses')
                            stored = save_upload(file, upload_dir, filename)
                            receipt_path = f'uploads/boat_{boat_id}/expenses/{stored}'

                    conn.execute("""
                        INSERT INTO expenses (expense_date, category, description, amount, receipt_path, notes)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, (expense_date, category, description, amount, receipt_path, notes))
                    conn.commit()
#                    flash('Expense added!', 'success')
#                else:
#                    flash('Valid amount required.', 'danger')

            # EDIT
            elif 'edit_expense' in request.form:
                exp_id = request.form.get('expense_id')
                expense_date = request.form.get('expense_date')
                category = request.form.get('category', 'Other').strip() or 'Other'
                description = request.form.get('description', '').strip()
                amount = request.form.get('amount', type=float)
                notes = request.form.get('notes', '').strip()
                remove_receipt = request.form.get('remove_receipt') == '1'

                if exp_id and amount and amount > 0:
                    receipt_path = None
                    if 'receipt' in request.files and request.files['receipt'].filename:
                        file = request.files['receipt']
                        if allowed_file(file.filename):
                            filename = secure_filename(file.filename)
                            upload_dir = os.path.join('static', 'uploads', f'boat_{boat_id}', 'expenses')
                            stored = save_upload(file, upload_dir, filename)
                            receipt_path = f'uploads/boat_{boat_id}/expenses/{stored}'

                    if receipt_path:
                        conn.execute("""
                            UPDATE expenses
                            SET expense_date=?, category=?, description=?, amount=?, notes=?, receipt_path=?
                            WHERE id=?
                        """, (expense_date, category, description, amount, notes, receipt_path, exp_id))
                    elif remove_receipt:
                        conn.execute("""
                            UPDATE expenses
                            SET expense_date=?, category=?, description=?, amount=?, notes=?, receipt_path=NULL
                            WHERE id=?
                        """, (expense_date, category, description, amount, notes, exp_id))
                    else:
                        conn.execute("""
                            UPDATE expenses
                            SET expense_date=?, category=?, description=?, amount=?, notes=?
                            WHERE id=?
                        """, (expense_date, category, description, amount, notes, exp_id))

                    conn.commit()
#                    flash('Expense updated!', 'success')
#                else:
#                    flash('Failed to update expense.', 'danger')

            # DELETE
            elif 'delete_expense' in request.form:
                exp_id = request.form.get('expense_id')
                if exp_id:
                    conn.execute("DELETE FROM expenses WHERE id=?", (exp_id,))
                    conn.commit()
#                    flash('Expense deleted.', 'success')

            return redirect(url_for('expenses'))

        # GET
        expenses_list = conn.execute("""
            SELECT * FROM expenses ORDER BY expense_date DESC, id DESC
        """).fetchall()

        total = conn.execute("SELECT COALESCE(SUM(amount), 0) FROM expenses").fetchone()[0]
        by_category = conn.execute("""
            SELECT category, SUM(amount) as total
            FROM expenses GROUP BY category ORDER BY total DESC
        """).fetchall()

        categories = sorted({row['category'] for row in expenses_list if row['category']})

        conn.close()
        return render_template('expenses.html',
                               expenses=expenses_list,
                               total=round(total, 2),
                               by_category=by_category,
                               categories=categories,
                               today=date.today().isoformat())

    # ====================== MOTOR ======================
    @app.route('/start_motor', methods=['POST'])
    @login_required
    @boat_required
    def start_motor():
        boat_id = session['current_boat_id']
        conn = get_boat_db(boat_id)
        conn.execute("UPDATE status SET motor_running=1, motor_start_time=? WHERE id=1",
                    (now_hki().isoformat(),))
        conn.commit()
        conn.close()
        return redirect(url_for('index'))

    @app.route('/stop_motor', methods=['POST'])
    @login_required
    @boat_required
    def stop_motor():
        boat_id = session['current_boat_id']
        conn = get_boat_db(boat_id)
        status = conn.execute("SELECT * FROM status WHERE id=1").fetchone()
        if status and status['motor_running'] == 1 and status['motor_start_time']:
            end_time = now_hki()
            start_time = datetime.fromisoformat(status['motor_start_time'].replace('Z', '+00:00'))
            hours_added = (end_time - start_time).total_seconds() / 3600

            conn.execute("""
                INSERT INTO motor_history (start_time, end_time, duration_hours, notes)
                VALUES (?, ?, ?, ?)
            """, (status['motor_start_time'], end_time.isoformat(), hours_added, 'Motor run'))

            conn.execute("UPDATE status SET total_motor_hours = total_motor_hours + ?, motor_running=0, motor_start_time=NULL WHERE id=1", 
                        (hours_added,))
            conn.commit()
        conn.close()
        return redirect(url_for('index'))

    @app.route('/motor_history')
    @login_required
    @boat_required
    def motor_history():
        boat_id = session['current_boat_id']
        conn = get_boat_db(boat_id)
        history = conn.execute("SELECT * FROM motor_history ORDER BY end_time DESC").fetchall()
        conn.close()
        return render_template('motor_history.html', history=history)

    @app.route('/add_motor_run', methods=['GET', 'POST'])
    @login_required
    @boat_required
    def add_motor_run():
        if request.method == 'POST':
            start_time = request.form.get('start_time')
            end_time = request.form.get('end_time')
            notes = request.form.get('notes', '').strip()
            
            if start_time and end_time:
                try:
                    start = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
                    end = datetime.fromisoformat(end_time.replace('Z', '+00:00'))
                    duration_hours = (end - start).total_seconds() / 3600
                    
                    boat_id = session['current_boat_id']
                    conn = get_boat_db(boat_id)
                    
                    conn.execute("""
                        INSERT INTO motor_history (start_time, end_time, duration_hours, notes)
                        VALUES (?, ?, ?, ?)
                    """, (start_time, end_time, duration_hours, notes))
                    
                    conn.execute("""
                        UPDATE status 
                        SET total_motor_hours = total_motor_hours + ?
                        WHERE id = 1
                    """, (duration_hours,))
                    
                    conn.commit()
                    conn.close()
                    
                    #flash(f'✅ Motor run added (+{duration_hours:.2f} hours)', 'success')
                    return redirect(url_for('motor_history'))
                    
                except Exception as e:
                    #flash('❌ Error adding motor run', 'danger')
                    print(e)
            
        return render_template('add_motor_run.html')

    @app.route('/motor_history/delete/<int:run_id>', methods=['POST'])
    @login_required
    @boat_required
    def delete_motor_run(run_id):
        boat_id = session['current_boat_id']
        conn = get_boat_db(boat_id)
        
        # Get the duration before deleting
        run = conn.execute("SELECT duration_hours FROM motor_history WHERE id=?", (run_id,)).fetchone()
        
        if run and run['duration_hours']:
            # Subtract from total motor hours
            conn.execute("""
                UPDATE status 
                SET total_motor_hours = total_motor_hours - ? 
                WHERE id = 1
            """, (run['duration_hours'],))
        
        # Delete the record
        conn.execute("DELETE FROM motor_history WHERE id=?", (run_id,))
        conn.commit()
        conn.close()
        
        #flash('Motor run entry deleted and total hours updated.', 'success')
        return redirect(url_for('motor_history'))

    @app.route('/motor_history/edit/<int:run_id>', methods=['POST'])
    @login_required
    @boat_required
    def update_motor_note(run_id):
        boat_id = session['current_boat_id']
        notes = request.form.get('notes', '').strip()
        conn = get_boat_db(boat_id)
        conn.execute("UPDATE motor_history SET notes=? WHERE id=?", (notes, run_id))
        conn.commit()
        conn.close()
        #flash('Note updated successfully!', 'success')

        conn.close()
        return redirect(url_for('motor_history'))

    # ====================== SERVICE ======================
    @app.route('/service')
    @login_required
    @boat_required
    def service():
        boat_id = session['current_boat_id']
        conn = get_boat_db(boat_id)
        
        services = conn.execute("SELECT * FROM service_types ORDER BY category, name").fetchall()
        history = conn.execute("SELECT * FROM maintenance ORDER BY done_at DESC LIMIT 20").fetchall()
        
        current_hours_row = conn.execute("SELECT total_motor_hours FROM status WHERE id=1").fetchone()
        current_hours = current_hours_row['total_motor_hours'] if current_hours_row else 0.0
        
        categories = sorted({s['category'] for s in services if s['category']})
        conn.close()

        return render_template('service.html', 
                               services=services, 
                               history=history, 
                               current_hours=round(current_hours, 1),
                               today=date.today().isoformat(),
                               categories=categories)

    @app.route('/service/add_type', methods=['POST'])
    @login_required
    @boat_required
    def add_service_type():
        boat_id = session['current_boat_id']
        name = request.form.get('name', '').strip()
        interval = request.form.get('interval')

        if name:
            conn = get_boat_db(boat_id)
            try:
                conn.execute("INSERT INTO service_types (name, interval_hours) VALUES (?, ?)",
                           (name, int(interval) if interval and interval.isdigit() else None))
                conn.commit()
                flash('Service type added!', 'success')
            except:
                flash('Service type already exists.', 'warning')
            conn.close()
        return redirect(url_for('service'))

    @app.route('/service/do/<int:sid>', methods=['POST'])
    @login_required
    @boat_required
    def do_service(sid):
        boat_id = session['current_boat_id']
        done_date = request.form.get('done_date') or date.today().isoformat()
        notes = request.form.get('notes', '').strip()

        conn = get_boat_db(boat_id)
        service = conn.execute("SELECT name FROM service_types WHERE id=?", (sid,)).fetchone()
        
        if service:
            current_hours = conn.execute("SELECT total_motor_hours FROM status WHERE id=1").fetchone()['total_motor_hours'] or 0
            conn.execute('''
                INSERT INTO maintenance (service_type, done_at, motor_hours_at_service, notes)
                VALUES (?, ?, ?, ?)
            ''', (service['name'], done_date, current_hours, notes))
            conn.commit()
            #flash(f'Service "{service["name"]}" marked as done.', 'success')
        conn.close()
        return redirect(url_for('service'))

    @app.route('/service/delete_type/<int:sid>', methods=['POST'])
    @login_required
    @boat_required
    def delete_service_type(sid):
        boat_id = session['current_boat_id']
        conn = get_boat_db(boat_id)
        conn.execute("DELETE FROM service_types WHERE id=?", (sid,))
        conn.commit()
        conn.close()
        #flash('Service type deleted successfully.', 'success')
        return redirect(url_for('service'))


    @app.route('/service/delete_history/<int:hid>', methods=['POST'])
    @login_required
    @boat_required
    def delete_maintenance_history(hid):
        boat_id = session['current_boat_id']
        conn = get_boat_db(boat_id)
        conn.execute("DELETE FROM maintenance WHERE id=?", (hid,))
        conn.commit()
        conn.close()
        #flash('Maintenance record deleted.', 'success')
        return redirect(url_for('service'))

    # ====================== EXPANDED PAGES ======================
    @app.route('/onboard', methods=['GET', 'POST'])
    @login_required
    @boat_required
    def onboard():
        boat_id = session['current_boat_id']
        conn = get_boat_db(boat_id)

        if request.method == 'POST':
            new_item = request.form.get('new_item', '').strip()
            category = request.form.get('category', 'Other')
            if new_item:
                conn.execute("INSERT INTO onboard_items (name, category) VALUES (?, ?)", 
                           (new_item, category))
                conn.commit()

        items = conn.execute("SELECT * FROM onboard_items ORDER BY category, name").fetchall()
        categories = sorted({item['category'] for item in items if item['category']})
        conn.close()

        return render_template('onboard.html', onboard_items=items, categories=categories)

    @app.route('/delete_onboard/<int:item_id>', methods=['POST'])
    @login_required
    @boat_required
    def delete_onboard(item_id):
        boat_id = session['current_boat_id']
        conn = get_boat_db(boat_id)
        conn.execute("DELETE FROM onboard_items WHERE id=?", (item_id,))
        conn.commit()
        conn.close()
        #flash('Item deleted successfully.', 'success')
        return redirect(url_for('onboard'))


#========================= Passengers ==================

    @app.route('/passengers', methods=['GET', 'POST'])
    @login_required
    @boat_required
    def passengers():
        boat_id = session['current_boat_id']
        conn = get_boat_db(boat_id)
        current_trip = conn.execute("SELECT * FROM trips WHERE end_time IS NULL ORDER BY id DESC LIMIT 1").fetchone()

        if request.method == 'POST':
            if 'add_master' in request.form:
                name = request.form.get('name', '').strip()
                if name:
                    conn.execute("INSERT OR IGNORE INTO passengers_master (name) VALUES (?)", (name,))
                    conn.commit()

            elif 'add_to_trip' in request.form and current_trip:
                pid = request.form.get('passenger_id')
                if pid:
                    conn.execute("INSERT OR IGNORE INTO trip_passengers (trip_id, passenger_id) VALUES (?, ?)",
                               (current_trip['id'], pid))
                    conn.commit()

            elif 'delete_master' in request.form:
                pid = request.form.get('passenger_id')
                if pid:
                    conn.execute("DELETE FROM passengers_master WHERE id=?", (pid,))
                    conn.execute("DELETE FROM trip_passengers WHERE passenger_id=?", (pid,))
                    conn.commit()
                    #flash('Passenger deleted from master list.', 'success')

        master_list = conn.execute("SELECT * FROM passengers_master ORDER BY name").fetchall()
        current_passengers = []

        if current_trip:
            current_passengers = conn.execute("""
                SELECT pm.* FROM passengers_master pm
                JOIN trip_passengers tp ON tp.passenger_id = pm.id
                WHERE tp.trip_id = ? ORDER BY pm.name
            """, (current_trip['id'],)).fetchall()

        conn.close()
        return render_template('passengers.html', 
                               master_list=master_list, 
                               current_trip=current_trip,
                               current_passengers=current_passengers)

#======================== TIPS ===========================
    @app.route('/tips', methods=['GET', 'POST'])
    @login_required
    @boat_required
    def tips():
        boat_id = session['current_boat_id']
        conn = get_boat_db(boat_id)

        if request.method == 'POST':
            # === DELETE TIP ===
            if request.form.get('delete_tip'):
                tip_id = request.form.get('tip_id')
                if tip_id:
                    conn.execute("DELETE FROM tips WHERE id=?", (tip_id,))
                    conn.execute("DELETE FROM tip_files WHERE tip_id=?", (tip_id,))
                    conn.commit()
                    #flash('✅ Tip deleted successfully!', 'success')
                    conn.close()
                    return redirect(url_for('tips'))

            # === EDIT TIP ===
            elif request.form.get('tip_id') and request.form.get('title'):
                tip_id = request.form.get('tip_id')
                title = request.form.get('title', '').strip()
                category = request.form.get('category', 'Other')
                content = request.form.get('content', '').strip()

                conn.execute("""
                    UPDATE tips 
                    SET title=?, category=?, content=?
                    WHERE id=?
                """, (title, category, content, tip_id))

                # Handle new images during edit
                if 'files' in request.files:
                    for file in request.files.getlist('files'):
                        if file and file.filename and allowed_file(file.filename):
                            filename = secure_filename(file.filename)
                            tip_upload_dir = os.path.join('static', 'uploads', f'boat_{boat_id}', 'tips')
                            stored = save_upload(file, tip_upload_dir, filename)
                            conn.execute("""
                                INSERT INTO tip_files (tip_id, file_path, file_type)
                                VALUES (?, ?, ?)
                            """, (tip_id, f'uploads/boat_{boat_id}/tips/{stored}', 
                                  stored.rsplit('.', 1)[-1].lower()))

                conn.commit()
                #flash('✅ Tip updated successfully!', 'success')
                conn.close()
                return redirect(url_for('tips'))

            # === ADD NEW TIP ===
            elif 'add_tip' in request.form:
                title = request.form.get('title', '').strip()
                category = request.form.get('category', 'Other')
                content = request.form.get('content', '').strip()

                if title:
                    conn.execute("""
                        INSERT INTO tips (title, category, content)
                        VALUES (?, ?, ?)
                    """, (title, category, content))
                    tip_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

                    if 'files' in request.files:
                        for file in request.files.getlist('files'):
                            if file and file.filename and allowed_file(file.filename):
                                filename = secure_filename(file.filename)
                                tip_upload_dir = os.path.join('static', 'uploads', f'boat_{boat_id}', 'tips')
                                stored = save_upload(file, tip_upload_dir, filename)
                                conn.execute("""
                                    INSERT INTO tip_files (tip_id, file_path, file_type)
                                    VALUES (?, ?, ?)
                                """, (tip_id, f'uploads/boat_{boat_id}/tips/{stored}', 
                                      stored.rsplit('.', 1)[-1].lower()))

                    conn.commit()
                    #flash('✅ Tip added successfully!', 'success')

            conn.close()
            return redirect(url_for('tips'))

        # GET request
        tips_list = conn.execute("SELECT * FROM tips ORDER BY category, created_at DESC").fetchall()
        
        tip_files = {}
        for tip in tips_list:
            files = conn.execute("SELECT * FROM tip_files WHERE tip_id=? ORDER BY uploaded_at", 
                               (tip['id'],)).fetchall()
            tip_files[tip['id']] = files

        categories = sorted({t['category'] for t in tips_list if t['category']})
        conn.close()

        return render_template('tips.html', 
                               tips=tips_list, 
                               categories=categories, 
                               tip_files=tip_files)

    @app.route('/tips/delete_file/<int:file_id>', methods=['POST'])
    @login_required
    @boat_required
    def delete_tip_file(file_id):
        boat_id = session['current_boat_id']
        conn = get_boat_db(boat_id)

    # Get file info
        file_row = conn.execute("SELECT * FROM tip_files WHERE id=?", (file_id,)).fetchone()
        if file_row:
        # Delete physical file
            file_path = os.path.join('static', file_row['file_path'])
            if os.path.exists(file_path):
                os.remove(file_path)

        # Delete from database
            conn.execute("DELETE FROM tip_files WHERE id=?", (file_id,))
            conn.commit()
           # flash('Image deleted', 'success')

        conn.close()
        return redirect(url_for('tips'))

# ============================ INFO =============================
    @app.route('/info', methods=['GET', 'POST'])
    @login_required
    @boat_required
    def info():
        boat_id = session['current_boat_id']
        conn = get_boat_db(boat_id)

        if request.method == 'POST':
            sensor_enabled = 1 if request.form.get('sensor_enabled') == '1' else 0

            conn.execute("""
                UPDATE boat_settings
                SET boat_name=?,
                    captain_name=?,
                    boat_number=?,
                    home_port=?,
                    registration=?,
                    boat_type=?,
                    build_year=?,
                    length=?,
                    width=?,
                    draft=?,
                    displacement=?,
                    engine=?,
                    sail_type=?,
                    notes=?,
                    sensor_enabled=?
                WHERE id = 1
            """, (
                request.form.get('boat_name'),
                request.form.get('captain_name'),
                request.form.get('boat_number'),
                request.form.get('home_port'),
                request.form.get('registration'),
                request.form.get('boat_type'),
                request.form.get('build_year'),
                request.form.get('length'),
                request.form.get('width'),
                request.form.get('draft'),
                request.form.get('displacement'),
                request.form.get('engine'),
                request.form.get('sail_type'),
                request.form.get('notes'),
                sensor_enabled
            ))
            conn.commit()
            flash('Boat information saved successfully!', 'success')
        settings = conn.execute("SELECT * FROM boat_settings WHERE id=1").fetchone()
        conn.close()
        return render_template('info.html', settings=settings)

#===================== Public ============
    @app.route('/public/<slug>')
    def public_boat(slug):
        # Find boat by slug
        main_conn = get_main_db()
        boats = main_conn.execute("SELECT id FROM boats").fetchall()
        main_conn.close()

        boat_id = None
        for b in boats:
            c = get_boat_db(b["id"])
            row = c.execute("SELECT public_slug FROM boat_settings WHERE id=1").fetchone()
            c.close()
            if row and row['public_slug'] == slug:
                boat_id = b["id"]
                break

        if not boat_id:
            return "Boat not found", 404

        conn = get_boat_db(boat_id)
        settings = conn.execute("SELECT * FROM boat_settings WHERE id=1").fetchone()
        if not settings or not settings['is_public']:
            conn.close()
            return "This boat is not public", 404

        data = {'settings': settings, 'boat_id': boat_id}

        if settings['public_main']:
            data['images'] = conn.execute("SELECT * FROM boat_images ORDER BY uploaded_at DESC").fetchall()

        if settings['public_tips']:
            tips = conn.execute("SELECT * FROM tips ORDER BY created_at DESC").fetchall()
            tip_files = {}
            for tip in tips:
                files = conn.execute("SELECT * FROM tip_files WHERE tip_id=?", (tip['id'],)).fetchall()
                tip_files[tip['id']] = files
            data['tips'] = tips
            data['tip_files'] = tip_files

        if settings['public_trips']:
            data['trips'] = conn.execute("""
                SELECT *, (julianday(COALESCE(end_time, 'now')) - julianday(start_time)) * 24 as duration_hours
                FROM trips WHERE end_time IS NOT NULL ORDER BY start_time DESC
            """).fetchall()

        if settings['public_onboard']:
            data['onboard_items'] = conn.execute("SELECT * FROM onboard_items ORDER BY category, name").fetchall()

        conn.close()

        lang = request.args.get('lang', 'en')
        if lang not in ['en', 'fi', 'sv', 'ru', 'de']:
            lang = 'en'
        data['lang'] = lang

        return "This page has been removed.", 404
#====================== Toggle_public ================
    @app.route('/admin/boats/toggle_public/<int:boat_id>', methods=['POST'])
    @login_required
    def toggle_public(boat_id):
        if session.get('role') != 'admin':
            flash('Access denied.', 'danger')
            return redirect(url_for('admin_boats'))

        conn = get_main_db()
        boat = conn.execute("SELECT journal_public FROM boats WHERE id=?", (boat_id,)).fetchone()
        if not boat:
            conn.close()
            flash('Boat not found.', 'danger')
            return redirect(url_for('admin_boats'))

        new_value = 0 if boat['journal_public'] else 1
        conn.execute("UPDATE boats SET journal_public=? WHERE id=?", (new_value, boat_id))
        conn.commit()
        conn.close()

        flash(f'Public journal {"enabled" if new_value else "disabled"}.', 'success')
        return redirect(url_for('admin_boats'))


#==============================================
    @app.route('/journal/settings', methods=['GET', 'POST'])
    @login_required
    @boat_required
    def journal_settings():
        boat_id = session['current_boat_id']
        conn = get_main_db()

        if request.method == 'POST':
            title = request.form.get('journal_title', '').strip() or 'Journal'
            public = 1 if request.form.get('journal_public') else 0
            conn.execute("UPDATE boats SET journal_title=?, journal_public=? WHERE id=?",
                         (title, public, boat_id))
            conn.commit()
            conn.close()
            return redirect(url_for('journal'))

        boat = conn.execute("SELECT journal_title, journal_public FROM boats WHERE id=?", (boat_id,)).fetchone()
        conn.close()
        return render_template('journal_settings.html',
                               journal_title=boat['journal_title'] if boat else 'Journal',
                               journal_public=boat['journal_public'] if boat else 0)


#==================================================
    @app.route('/journal/<int:trip_id>', methods=['GET', 'POST'])
    @login_required
    @boat_required
    def journal_post(trip_id):
        boat_id = session['current_boat_id']
        conn = get_boat_db(boat_id)
        trip = conn.execute("SELECT * FROM trips WHERE id=?", (trip_id,)).fetchone()
        if not trip:
            conn.close()
            return redirect(url_for('journal'))

        if request.method == 'POST':
            # Save draft or publish the journal post
            if 'save_journal' in request.form:
                is_published = 1 if request.form.get('is_published') else 0
                cover_image = request.form.get('cover_image') or None
                published_at = now_hki().isoformat() if is_published else None
                conn.execute("""
                    UPDATE trips SET is_published=?, cover_image=?, published_at=?
                    WHERE id=?
                """, (is_published, cover_image, published_at, trip_id))
                conn.commit()
                flash('Saved', 'success')
                return redirect(url_for('journal_post', trip_id=trip_id))

            # Owner comments are stored already approved
            if trip['allow_comments']:
                author = request.form.get('author_name', '').strip()[:80]
                content = request.form.get('content', '').strip()[:2000]
                if author and content:
                    conn.execute("""
                        INSERT INTO trip_comments (trip_id, author_name, content, approved)
                        VALUES (?, ?, ?, 1)
                    """, (trip_id, author, content))
                    conn.commit()
                return redirect(url_for('journal_post', trip_id=trip_id))

        trip = dict(trip)
        trip['images'] = conn.execute(
            "SELECT * FROM trip_images WHERE trip_id=? ORDER BY id", (trip_id,)
        ).fetchall()
        comments = conn.execute(
            "SELECT * FROM trip_comments WHERE trip_id=? ORDER BY created_at", (trip_id,)
        ).fetchall()
        conn.close()
        return render_template('journal_post.html', trip=trip, comments=comments)
#=========================================
    @app.route('/journal/<int:trip_id>/edit', methods=['GET', 'POST'])
    @login_required
    @boat_required
    def edit_trip(trip_id):
        boat_id = session['current_boat_id']
        conn = get_boat_db(boat_id)

        if request.method == 'POST':
            title = request.form.get('title', '').strip()
            start_location = request.form.get('start_location', '')
            finish_location = request.form.get('finish_location', '')
            notes = request.form.get('notes', '').strip()
            is_public = 1 if request.form.get('is_public') else 0
            allow_comments = 1 if request.form.get('allow_comments') else 0

            conn.execute("""
                UPDATE trips
                SET title=?, start_location=?, finish_location=?, notes=?, is_public=?, allow_comments=?
                WHERE id=?
            """, (title, start_location, finish_location, notes, is_public, allow_comments, trip_id))

            # Delete selected images
            for img_id in request.form.getlist('delete_images'):
                conn.execute("DELETE FROM trip_images WHERE id=? AND trip_id=?", (img_id, trip_id))

        # Upload new images
            if 'images' in request.files:
                upload_dir = os.path.join('static', 'uploads', f'boat_{boat_id}', 'trips')
                for file in request.files.getlist('images'):
                    if file and file.filename and allowed_file(file.filename):
                        filename = secure_filename(file.filename)
                        stored = save_upload(file, upload_dir, filename)
                        conn.execute("INSERT INTO trip_images (trip_id, image_path) VALUES (?, ?)",
                                     (trip_id, f'uploads/boat_{boat_id}/trips/{stored}'))

            conn.commit()
            conn.close()
            return redirect(url_for('journal_post', trip_id=trip_id))

        trip = conn.execute("SELECT * FROM trips WHERE id=?", (trip_id,)).fetchone()
        images = conn.execute("SELECT * FROM trip_images WHERE trip_id=? ORDER BY id", (trip_id,)).fetchall()
        conn.close()

        trip = dict(trip) if trip else None
        return render_template('edit_trip.html', trip=trip, images=images)

#================================
    @app.route('/journal/new', methods=['GET', 'POST'])
    @login_required
    @boat_required
    def add_trip_manual():
        boat_id = session['current_boat_id']
        conn = get_boat_db(boat_id)

        if request.method == 'POST':
            title = request.form.get('title', '').strip() or 'Untitled'
            start_location = request.form.get('start_location', '')
            finish_location = request.form.get('finish_location', '')
            start_time = request.form.get('start_time')
            end_time = request.form.get('end_time')
            notes = request.form.get('notes', '').strip()
            is_public = 1 if request.form.get('is_public') else 0
            allow_comments = 1 if request.form.get('allow_comments') else 0

            conn.execute("""
                INSERT INTO trips (title, start_location, finish_location, start_time, end_time, notes, is_public, allow_comments)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (title, start_location, finish_location, start_time, end_time, notes, is_public, allow_comments))
            trip_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

            # Upload images
            if 'images' in request.files:
                upload_dir = os.path.join('static', 'uploads', f'boat_{boat_id}', 'trips')
                for file in request.files.getlist('images'):
                    if file and file.filename and allowed_file(file.filename):
                        filename = secure_filename(file.filename)
                        stored = save_upload(file, upload_dir, filename)
                        conn.execute("INSERT INTO trip_images (trip_id, image_path) VALUES (?, ?)",
                                     (trip_id, f'uploads/boat_{boat_id}/trips/{stored}'))

            conn.commit()
            conn.close()
            return redirect(url_for('journal'))

        conn.close()
        return render_template('add_trip_manual.html')

#======================================
    @app.route('/<boat_slug>/journal')
    @app.route('/<boat_slug>/journal/')
    def public_journal(boat_slug):
        conn = get_main_db()
        boat = conn.execute("""
            SELECT id, journal_public, journal_title, name
            FROM boats
            WHERE LOWER(REPLACE(name, ' ', '-')) = ?
        """, (boat_slug.lower(),)).fetchone()
        conn.close()

        if not boat or not boat['journal_public']:
            return "Journal is not public", 404

        boat_id = boat['id']
        bconn = get_boat_db(boat_id)
        trips = bconn.execute("""
            SELECT *, (julianday(COALESCE(end_time, 'now')) - julianday(start_time)) * 24 as duration_hours
            FROM trips
            WHERE is_public = 1
            ORDER BY start_time DESC
        """).fetchall()

        trip_list = []
        for trip in trips:
            t = dict(trip)
            t['images'] = bconn.execute(
                "SELECT * FROM trip_images WHERE trip_id=? ORDER BY uploaded_at",
                (trip['id'],)
            ).fetchall()
            trip_list.append(t)
        bconn.close()

        return render_template('journal_public.html',
                               trips=trip_list,
                               journal_title=boat['journal_title'] or boat['name'],
                               boat_name=boat['name'],
                               boat_slug=boat_slug)
#==============================================
    @app.route('/<boat_slug>/journal/<int:trip_id>', methods=['GET', 'POST'])
    @app.route('/<boat_slug>/journal/<int:trip_id>/', methods=['GET', 'POST'])
    def public_journal_post_by_slug(boat_slug, trip_id):
        main = get_main_db()
        boats = main.execute("SELECT id, journal_public, name FROM boats WHERE journal_public=1").fetchall()
        main.close()

        boat = None
        for b in boats:
            if b['name'].replace(' ', '-').lower() == boat_slug.lower():
                boat = b
                break

        if not boat:
            return "Not found", 404

        boat_id = boat['id']
        conn = get_boat_db(boat_id)
        trip = conn.execute("SELECT * FROM trips WHERE id=? AND is_public=1", (trip_id,)).fetchone()
        if not trip:
            conn.close()
            return "Not found", 404

    # +1 view
        conn.execute("UPDATE trips SET views = views + 1 WHERE id=?", (trip_id,))
        conn.commit()

        if request.method == 'POST' and trip['allow_comments']:
            author = request.form.get('author_name', '').strip()[:80]
            content = request.form.get('content', '').strip()[:2000]
            if author and content:
                conn.execute(
                    "INSERT INTO trip_comments (trip_id, author_name, content, approved) VALUES (?, ?, ?, 0)",
                    (trip_id, author, content)
                )
                conn.commit()
            conn.close()
            return redirect(url_for('public_journal_post_by_slug', boat_slug=boat_slug, trip_id=trip_id, pending=1))

        trip = dict(trip)
        trip['images'] = conn.execute(
            "SELECT * FROM trip_images WHERE trip_id=? ORDER BY id",
            (trip_id,)
        ).fetchall()
        comments = conn.execute(
            "SELECT * FROM trip_comments WHERE trip_id=? AND approved=1 ORDER BY created_at",
            (trip_id,)
        ).fetchall()
        conn.close()

        return render_template(
            'journal_post_public.html',
            trip=trip,
            comments=comments,
            boat_slug=boat_slug,
            boat_name=boat['name']
        )
#===================================================
    @app.route('/journal/save/<int:trip_id>', methods=['POST'])
    @login_required
    @boat_required
    def save_journal(trip_id):
        boat_id = session['current_boat_id']
        conn = get_boat_db(boat_id)
        is_published = 1 if request.form.get('publish') else 0
        cover = request.form.get('cover_image')
        published_at = now_hki().isoformat() if is_published else None

        conn.execute("""
            UPDATE trips 
            SET is_published=?, cover_image=?, published_at=?
            WHERE id=?
        """, (is_published, cover, published_at, trip_id))
        conn.commit()
        conn.close()
        flash('Saved', 'success')
        return redirect(url_for('edit_trip', trip_id=trip_id))

#=====================================
    @app.route('/journal/comment/<int:comment_id>/approve', methods=['POST'])
    @login_required
    @boat_required
    def approve_comment(comment_id):
        boat_id = session['current_boat_id']
        conn = get_boat_db(boat_id)
        row = conn.execute("SELECT trip_id FROM trip_comments WHERE id=?", (comment_id,)).fetchone()
        if row:
            conn.execute("UPDATE trip_comments SET approved=1 WHERE id=?", (comment_id,))
            conn.commit()
        conn.close()
        if not row:
            return redirect(url_for('journal'))
        return redirect(url_for('journal_post', trip_id=row['trip_id']))

    @app.route('/journal/comment/<int:comment_id>/delete', methods=['POST'])
    @login_required
    @boat_required
    def delete_comment(comment_id):
        boat_id = session['current_boat_id']
        conn = get_boat_db(boat_id)
        row = conn.execute("SELECT trip_id FROM trip_comments WHERE id=?", (comment_id,)).fetchone()
        if row:
            conn.execute("DELETE FROM trip_comments WHERE id=?", (comment_id,))
            conn.commit()
        conn.close()
        if not row:
            return redirect(url_for('journal'))
        return redirect(url_for('journal_post', trip_id=row['trip_id']))

    @app.route('/trip/<int:trip_id>/toggle_public', methods=['POST'])
    @login_required
    @boat_required
    def toggle_trip_public(trip_id):
        boat_id = session['current_boat_id']
        conn = get_boat_db(boat_id)
        current = conn.execute("SELECT is_public FROM trips WHERE id=?", (trip_id,)).fetchone()
        if current:
            new_val = 0 if current['is_public'] else 1
            conn.execute("UPDATE trips SET is_public=? WHERE id=?", (new_val, trip_id))
            conn.commit()
            #flash('Post visibility updated.', 'success')
        conn.close()
        return redirect(request.referrer or url_for('history'))


    @app.route('/trip/<int:trip_id>/toggle_comments', methods=['POST'])
    @login_required
    @boat_required
    def toggle_trip_comments(trip_id):
        boat_id = session['current_boat_id']
        conn = get_boat_db(boat_id)
        current = conn.execute("SELECT allow_comments FROM trips WHERE id=?", (trip_id,)).fetchone()
        if current:
            new_val = 0 if current['allow_comments'] else 1
            conn.execute("UPDATE trips SET allow_comments=? WHERE id=?", (new_val, trip_id))
            conn.commit()
            #flash('Comments setting updated.', 'success')
        conn.close()
        return redirect(request.referrer or url_for('history'))

#=================================================
    @app.route('/trip/<int:trip_id>/set_public', methods=['POST'])
    @login_required
    @boat_required
    def set_trip_public(trip_id):
        boat_id = session['current_boat_id']
        is_public = 1 if request.form.get('is_public') else 0

        conn = get_boat_db(boat_id)
        conn.execute("UPDATE trips SET is_public=? WHERE id=?", (is_public, trip_id))
        conn.commit()
        conn.close()
        #flash('Visibility updated.', 'success')
        return redirect(request.referrer or url_for('history'))

#====================== DELETE TRIP ======================
    @app.route('/history/delete/<int:trip_id>', methods=['POST'])
    @login_required
    @boat_required
    def delete_trip(trip_id):
        boat_id = session['current_boat_id']
        conn = get_boat_db(boat_id)
        try:
            conn.execute("DELETE FROM trip_passengers WHERE trip_id = ?", (trip_id,))
            try:
                conn.execute("DELETE FROM trip_images WHERE trip_id = ?", (trip_id,))
            except:
                pass
            conn.execute("DELETE FROM trips WHERE id = ?", (trip_id,))
            conn.commit()
            #flash('Trip deleted.', 'success')
        except Exception as e:
            conn.rollback()
            #flash(f'Error: {e}', 'danger')
        finally:
            conn.close()
        return redirect(url_for('journal'))

#=============================================
    @app.route('/journal')
    @login_required
    @boat_required
    def journal():
        boat_id = session['current_boat_id']
        conn = get_boat_db(boat_id)
        main = get_main_db()
        boat = main.execute(
            "SELECT journal_title, journal_public, name FROM boats WHERE id=?",
            (boat_id,)
        ).fetchone()
        main.close()

        journal_title = boat['journal_title'] if boat and boat['journal_title'] else session.get('current_boat_name', 'Journal')
        is_public_journal = bool(boat and boat['journal_public'])
        boat_name = boat['name'] if boat and boat['name'] else session.get('current_boat_name', '')

        trips = conn.execute("""
            SELECT *, (julianday(COALESCE(end_time, 'now')) - julianday(start_time)) * 24 as duration_hours
            FROM trips ORDER BY start_time DESC
        """).fetchall()
        trip_list = []
        for trip in trips:
            t = dict(trip)
            t['images'] = conn.execute(
                "SELECT * FROM trip_images WHERE trip_id=? ORDER BY uploaded_at",
                (trip['id'],)
            ).fetchall()
            trip_list.append(t)
        conn.close()

        return render_template('journal.html',
                               trips=trip_list,
                               journal_title=journal_title,
                               is_public_journal=is_public_journal,
                               boat_name=boat_name)

    @app.route('/toggle_journal_public', methods=['POST'])
    @login_required
    @boat_required
    def toggle_journal_public():
        boat_id = session['current_boat_id']
        conn = get_main_db()
        boat = conn.execute("SELECT journal_public FROM boats WHERE id=?", (boat_id,)).fetchone()
        new_value = 0 if (boat and boat['journal_public']) else 1
        conn.execute("UPDATE boats SET journal_public=? WHERE id=?", (new_value, boat_id))
        conn.commit()
        conn.close()
        #flash(f'Journal is now {"public" if new_value else "private"}.', 'success')
        return redirect(request.referrer or url_for('journal'))

    @app.route('/update_journal_title', methods=['POST'])
    @login_required
    @boat_required
    def update_journal_title():
        boat_id = session['current_boat_id']
        title = request.form.get('journal_title', '').strip()
        if title:
            conn = get_main_db()
            conn.execute("UPDATE boats SET journal_title=? WHERE id=?", (title, boat_id))
            conn.commit()
            conn.close()
            #flash('Journal name updated.', 'success')
        return redirect(url_for('journal'))
#===========================================
    @app.route('/<boat_slug>/journal/<int:trip_id>')
    def public_journal_post(boat_slug, trip_id):
        conn = get_main_db()
        boat = conn.execute("""
            SELECT id, journal_public FROM boats
            WHERE LOWER(REPLACE(name, ' ', '-')) = ?
        """, (boat_slug.lower(),)).fetchone()
        conn.close()

        if not boat or not boat['journal_public']:
            return "Journal is not public", 404



#________________________________________
    return
