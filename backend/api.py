import sys
import json
import os
from db_helper import GalleryDB
from PIL import Image, ImageOps

def _safe_int(value, default=None):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default

def _safe_join(base_dir, rel_path):
    candidate = os.path.normpath(os.path.join(base_dir, rel_path))
    base = os.path.normpath(base_dir)
    if not candidate.startswith(base + os.sep) and candidate != base:
        return None
    return candidate

def generate_thumbnail(img_path, base_dir, size=(400, 400)):
    full_path = _safe_join(base_dir, img_path)
    if full_path is None:
        return {"success": False, "error": f"Invalid path: {img_path}"}

    thumb_dir = os.path.join(base_dir, 'thumbs')
    os.makedirs(thumb_dir, exist_ok=True)
    thumb_path = os.path.join(thumb_dir, img_path)

    try:
        os.makedirs(os.path.dirname(thumb_path), exist_ok=True)

        if os.path.exists(thumb_path) and os.path.getmtime(thumb_path) > os.path.getmtime(full_path):
            return {"success": True, "path": img_path, "status": "exists"}

        with Image.open(full_path) as img:
            img = ImageOps.exif_transpose(img)
            img.thumbnail(size)
            thumb_path = os.path.splitext(thumb_path)[0] + '.webp'
            img.save(thumb_path, 'WEBP', optimize=True, quality=85)

        return {"success": True, "path": os.path.splitext(img_path)[0] + '.webp'}
    except Exception as e:
        return {"success": False, "error": str(e)}

# This serves as the main Python entry point for the PHP library
def handle_api():
    if len(sys.argv) < 4:
        print(json.dumps({"success": False, "error": "Insufficient arguments"}))
        return

    action = sys.argv[1]
    db_path = sys.argv[2]
    photo_base_dir = sys.argv[3]
    
    db = GalleryDB(db_path, photo_base_dir)

    # Optional security context passed from PHP
    is_admin = sys.argv[4].lower() == 'true' if len(sys.argv) > 4 else False
    user_tag = sys.argv[5] if len(sys.argv) > 5 and sys.argv[5] != 'null' else None

    if action == "get_summarized_timeline":
        print(json.dumps(db.get_summarized_timeline()))
    elif action == "get_geolocated":
        print(json.dumps(db.get_geolocated(is_admin, user_tag)))
    elif action == "get_all_tags":
        print(json.dumps(db.get_all_tags(is_admin, user_tag)))
    elif action == "get_all_images":
        filter_tag = sys.argv[6] if len(sys.argv) > 6 and sys.argv[6] != 'null' else None
        print(json.dumps(db.get_all_images(is_admin, user_tag, filter_tag)))
    elif action == "get_by_message_id":
        msg_id = _safe_int(sys.argv[6] if len(sys.argv) > 6 else None)
        if msg_id is None:
            print(json.dumps({"success": False, "error": "Invalid message id"}))
            return
        print(json.dumps(db.get_by_message_id(msg_id)))
    elif action == "search":
        filter_tag = sys.argv[6] if len(sys.argv) > 6 and sys.argv[6] != 'null' else None
        query = sys.argv[7] if len(sys.argv) > 7 else ""
        print(json.dumps(db.search(query, is_admin, user_tag, filter_tag)))
    elif action == "get_batch_metadata":
        paths = json.loads(sys.argv[6]) if len(sys.argv) > 6 else []
        print(json.dumps(db.get_batch_metadata(paths)))
    elif action == "add_tag":
        path = sys.argv[6]
        tag = sys.argv[7]
        print(json.dumps(db.add_tag(path, tag)))
    elif action == "delete_tag":
        path = sys.argv[6]
        tag = sys.argv[7]
        print(json.dumps(db.delete_tag(path, tag)))
    elif action == "set_message_id":
        if not is_admin:
            print(json.dumps({"success": False, "error": "Admin required"}))
            return
        path = sys.argv[6]
        msg_id = _safe_int(sys.argv[7] if len(sys.argv) > 7 else None)
        if msg_id is None:
            print(json.dumps({"success": False, "error": "Invalid message id"}))
            return
        print(json.dumps(db.set_message_id(path, msg_id)))
    elif action == "delete_by_message_id":
        if not is_admin:
            print(json.dumps({"success": False, "error": "Admin required"}))
            return
        msg_id = _safe_int(sys.argv[6] if len(sys.argv) > 6 else None)
        if msg_id is None:
            print(json.dumps({"success": False, "error": "Invalid message id"}))
            return
        print(json.dumps(db.delete_by_message_id(msg_id)))
    elif action == "set_public":
        path = sys.argv[6]
        is_public = sys.argv[7].lower() == 'true'
        if not is_admin:
            print(json.dumps({"success": False, "error": "Admin required"}))
            return
        print(json.dumps(db.set_public(path, is_public)))
    elif action == "set_license":
        path = sys.argv[6]
        license_code = sys.argv[7] if len(sys.argv) > 7 else ''
        if not is_admin:
            print(json.dumps({"success": False, "error": "Admin required"}))
            return
        print(json.dumps(db.set_license(path, license_code)))
    elif action == "delete_image":
        if not is_admin:
            print(json.dumps({"success": False, "error": "Admin required"}))
            return
        path = sys.argv[6]
        res = db.delete_image(path)
        # Also delete thumbnail (both legacy extension and WebP)
        thumb_dir = os.path.join(photo_base_dir, 'thumbs')
        base = os.path.splitext(path)[0]
        for candidate in (base + '.webp', path):
            thumb_path = _safe_join(thumb_dir, candidate)
            if thumb_path and os.path.exists(thumb_path):
                try:
                    os.remove(thumb_path)
                except OSError:
                    pass
        print(json.dumps(res))
    elif action == "generate_thumbnail":
        path = sys.argv[6]
        print(json.dumps(generate_thumbnail(path, photo_base_dir)))
    elif action == "get_random_images":
        limit = _safe_int(sys.argv[6] if len(sys.argv) > 6 else None, 24)
        print(json.dumps(db.get_random_images(limit, is_admin, user_tag)))
    elif action == "get_album_folder_cover":
        folder = sys.argv[6] if len(sys.argv) > 6 else ''
        print(json.dumps(db.get_album_folder_cover(folder, is_admin, user_tag)))
    elif action == "create_album":
        name = sys.argv[6] if len(sys.argv) > 6 else ''
        description = sys.argv[7] if len(sys.argv) > 7 else ''
        print(json.dumps(db.create_album(name, description)))
    elif action == "list_albums":
        print(json.dumps(db.list_albums(is_admin, user_tag)))
    elif action == "get_album":
        album_id = _safe_int(sys.argv[6] if len(sys.argv) > 6 else None)
        if album_id is None:
            print(json.dumps({"success": False, "error": "Invalid album id"}))
            return
        print(json.dumps(db.get_album(album_id, is_admin, user_tag)))
    elif action == "add_image_to_album":
        album_id = _safe_int(sys.argv[6] if len(sys.argv) > 6 else None)
        path = sys.argv[7] if len(sys.argv) > 7 else ''
        if album_id is None:
            print(json.dumps({"success": False, "error": "Invalid album id"}))
            return
        print(json.dumps(db.add_image_to_album(album_id, path)))
    elif action == "remove_image_from_album":
        album_id = _safe_int(sys.argv[6] if len(sys.argv) > 6 else None)
        path = sys.argv[7] if len(sys.argv) > 7 else ''
        if album_id is None:
            print(json.dumps({"success": False, "error": "Invalid album id"}))
            return
        print(json.dumps(db.remove_image_from_album(album_id, path)))
    elif action == "delete_album":
        if not is_admin:
            print(json.dumps({"success": False, "error": "Admin required"}))
            return
        album_id = _safe_int(sys.argv[6] if len(sys.argv) > 6 else None)
        if album_id is None:
            print(json.dumps({"success": False, "error": "Invalid album id"}))
            return
        print(json.dumps(db.delete_album(album_id)))
    else:
        print(json.dumps({"success": False, "error": f"Unknown action: {action}"}))

if __name__ == "__main__":
    handle_api()
