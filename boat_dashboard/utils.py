from models import get_boat_db
import os
from PIL import Image, ImageOps

IMAGE_EXTS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
MAX_IMAGE_SIDE = 1600


def get_motor_hours_formatted(boat_id):
    try:
        conn = get_boat_db(boat_id)
        row = conn.execute("SELECT total_motor_hours FROM status WHERE id=1").fetchone()
        conn.close()
        hours = row['total_motor_hours'] if row and row['total_motor_hours'] is not None else 0.0
        return round(hours, 2)
    except:
        return 0.0


def save_upload(file_storage, directory, filename, max_side=MAX_IMAGE_SIDE):
    """Save an upload. Photos are resized (longest side max_side) and stored as JPEG.
    PDFs, GPX and other allowed files are saved unchanged.
    Returns the filename that was written.
    """
    os.makedirs(directory, exist_ok=True)
    filename = os.path.basename(filename) or 'upload'
    ext = filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''
    stem = filename.rsplit('.', 1)[0] if '.' in filename else filename

    if ext not in IMAGE_EXTS:
        stored = _unique_name(directory, filename)
        file_storage.save(os.path.join(directory, stored))
        return stored

    try:
        img = Image.open(file_storage.stream)
        img = ImageOps.exif_transpose(img)
        if ext == 'gif' and getattr(img, 'is_animated', False):
            file_storage.stream.seek(0)
            stored = _unique_name(directory, filename)
            file_storage.save(os.path.join(directory, stored))
            return stored

        if max(img.size) > max_side:
            img.thumbnail((max_side, max_side), Image.Resampling.LANCZOS)

        if ext == 'png' and img.mode in ('RGBA', 'LA'):
            stored = _unique_name(directory, stem + '.png')
            img.save(os.path.join(directory, stored), 'PNG', optimize=True)
            return stored

        if img.mode != 'RGB':
            img = img.convert('RGB')
        stored = _unique_name(directory, stem + '.jpg')
        img.save(os.path.join(directory, stored), 'JPEG', quality=82, optimize=True)
        return stored
    except Exception:
        try:
            file_storage.stream.seek(0)
        except Exception:
            pass
        stored = _unique_name(directory, filename)
        file_storage.save(os.path.join(directory, stored))
        return stored


def _unique_name(directory, filename):
    candidate = filename
    stem, dot, ext = filename.rpartition('.')
    if not dot:
        stem, ext = filename, ''
    n = 1
    while os.path.exists(os.path.join(directory, candidate)):
        suffix = f'_{n}'
        candidate = f'{stem}{suffix}.{ext}' if ext else f'{stem}{suffix}'
        n += 1
    return candidate
