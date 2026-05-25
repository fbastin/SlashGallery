import sys
import json
import os
from db_helper import GalleryDB

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
    elif action == "get_photos_by_date":
        date = sys.argv[6] if len(sys.argv) > 6 else ""
        print(json.dumps(db.get_photos_by_date(date)))
    elif action == "get_geolocated":
        print(json.dumps(db.get_geolocated(is_admin, user_tag)))
    elif action == "get_all_tags":
        print(json.dumps(db.get_all_tags(is_admin, user_tag)))
    elif action == "get_all_images":
        print(json.dumps(db.get_all_images(is_admin, user_tag)))
    elif action == "search":
        query = sys.argv[6] if len(sys.argv) > 6 else ""
        print(json.dumps(db.search(query, is_admin, user_tag)))
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
    elif action == "update_location":
        path = sys.argv[6]
        lat = float(sys.argv[7]) if sys.argv[7] != 'null' else None
        lng = float(sys.argv[8]) if sys.argv[8] != 'null' else None
        print(json.dumps(db.update_location(path, lat, lng)))
    elif action == "set_public":
        path = sys.argv[6]
        is_public = sys.argv[7].lower() == 'true'
        print(json.dumps(db.set_public(path, is_public)))
    elif action == "delete_image":
        path = sys.argv[6]
        print(json.dumps(db.delete_image(path)))
    else:
        print(json.dumps({"success": False, "error": f"Unknown action: {action}"}))

if __name__ == "__main__":
    handle_api()
