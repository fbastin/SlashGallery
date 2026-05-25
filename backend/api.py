import sys
import json
import os
from db_helper import GalleryDB
from PIL import Image

def generate_thumbnail(img_path, base_dir, size=(400, 400)):
    try:
        full_path = os.path.join(base_dir, img_path)
        thumb_dir = os.path.join(base_dir, 'thumbs')
        if not os.path.exists(thumb_dir):
            os.makedirs(thumb_dir, exist_ok=True)
        
        thumb_path = os.path.join(thumb_dir, img_path)
        
        # Ensure subdirectories in thumbs exist
        os.makedirs(os.path.dirname(thumb_path), exist_ok=True)

        if os.path.exists(thumb_path) and os.path.getmtime(thumb_path) > os.path.getmtime(full_path):
            return {"success": True, "path": img_path, "status": "exists"}

        with Image.open(full_path) as img:
            # Handle orientation if present
            try:
                from PIL import ImageOps
                img = ImageOps.exif_transpose(img)
            except: pass
            
            img.thumbnail(size)
            # Save as WebP if possible, or same format
            img.save(thumb_path, optimize=True, quality=85)
            
        return {"success": True, "path": img_path}
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
        msg_id = int(sys.argv[6])
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
        path = sys.argv[6]
        msg_id = int(sys.argv[7])
        print(json.dumps(db.set_message_id(path, msg_id)))
    elif action == "delete_by_message_id":
        msg_id = int(sys.argv[6])
        print(json.dumps(db.delete_by_message_id(msg_id)))
    elif action == "set_public":
        path = sys.argv[6]
        is_public = sys.argv[7].lower() == 'true'
        print(json.dumps(db.set_public(path, is_public)))
    elif action == "delete_image":
        path = sys.argv[6]
        res = db.delete_image(path)
        # Also delete thumbnail
        thumb_path = os.path.join(photo_base_dir, 'thumbs', path)
        if os.path.exists(thumb_path):
            os.remove(thumb_path)
        print(json.dumps(res))
    elif action == "generate_thumbnail":
        path = sys.argv[6]
        print(json.dumps(generate_thumbnail(path, photo_base_dir)))
    else:
        print(json.dumps({"success": False, "error": f"Unknown action: {action}"}))

if __name__ == "__main__":
    handle_api()
