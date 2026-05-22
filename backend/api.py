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

    if action == "get_summarized_timeline":
        print(json.dumps(db.get_summarized_timeline()))
    elif action == "get_photos_by_date":
        date = sys.argv[4] if len(sys.argv) > 4 else ""
        print(json.dumps(db.get_photos_by_date(date)))
    elif action == "get_geolocated":
        print(json.dumps(db.get_geolocated()))
    elif action == "get_all_tags":
        print(json.dumps(db.get_all_tags()))
    elif action == "search":
        query = sys.argv[4] if len(sys.argv) > 4 else ""
        print(json.dumps(db.search(query)))
    elif action == "get_batch_metadata":
        paths = json.loads(sys.argv[4]) if len(sys.argv) > 4 else []
        print(json.dumps(db.get_batch_metadata(paths)))
    elif action == "add_tag":
        path = sys.argv[4]
        tag = sys.argv[5]
        print(json.dumps(db.add_tag(path, tag)))
    elif action == "delete_tag":
        path = sys.argv[4]
        tag = sys.argv[5]
        print(json.dumps(db.delete_tag(path, tag)))
    elif action == "update_location":
        path = sys.argv[4]
        lat = float(sys.argv[5]) if sys.argv[5] != 'null' else None
        lng = float(sys.argv[6]) if sys.argv[6] != 'null' else None
        # Need to add update_location to GalleryDB class in db_helper.py
        # For now I will just call it if available or print error
        if hasattr(db, 'update_location'):
            print(json.dumps(db.update_location(path, lat, lng)))
        else:
            print(json.dumps({"success": False, "error": "Method not implemented in DB helper"}))
    else:
        print(json.dumps({"success": False, "error": "Unknown action"}))

if __name__ == "__main__":
    handle_api()
