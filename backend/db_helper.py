import sqlite3
import sys
import json
import os
from datetime import datetime

DB_PATH = '/home/bastin/Cloud/Photos/photo_catalog.db'
PHOTO_BASE_DIR = '/home/bastin/Cloud/Photos'

def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def get_all_geolocated():
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT file_path, latitude, longitude, file_name 
        FROM images 
        WHERE latitude IS NOT NULL AND longitude IS NOT NULL
    """)
    results = []
    for row in cursor.fetchall():
        results.append({
            'path': row['file_path'][len(PHOTO_BASE_DIR)+1:],
            'lat': row['latitude'],
            'lng': row['longitude'],
            'name': row['file_name']
        })
    conn.close()
    return results

def get_summarized_timeline():
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT date(COALESCE(date_taken, date_added)) as day, COUNT(*) as count 
        FROM images 
        GROUP BY day 
        ORDER BY day DESC
    """)
    results = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return results

def get_photos_by_date(day_str):
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT file_path, latitude, longitude, date_taken 
        FROM images 
        WHERE date(COALESCE(date_taken, date_added)) = ?
        LIMIT 1000
    """, (day_str,))
    results = []
    for row in cursor.fetchall():
        results.append({
            'path': row['file_path'][len(PHOTO_BASE_DIR)+1:],
            'lat': row['latitude'],
            'lng': row['longitude']
        })
    conn.close()
    return results

def search(query_str):
    conn = get_conn()
    cursor = conn.cursor()
    keywords = query_str.split()
    if not keywords: return []
    sql = "SELECT DISTINCT i.file_path, i.latitude, i.longitude, i.date_taken FROM images i LEFT JOIN tags t ON i.id = t.image_id WHERE "
    conditions = []
    params = []
    for kw in keywords:
        kw_pattern = f"%{kw}%"
        conditions.append("(i.file_path LIKE ? OR t.tag_name LIKE ?)")
        params.extend([kw_pattern, kw_pattern])
    sql += " AND ".join(conditions) + " LIMIT 500"
    cursor.execute(sql, params)
    results = []
    for row in cursor.fetchall():
        results.append({
            'path': row['file_path'][len(PHOTO_BASE_DIR)+1:],
            'lat': row['latitude'],
            'lng': row['longitude']
        })
    conn.close()
    return results

def get_batch_metadata(file_paths):
    conn = get_conn()
    cursor = conn.cursor()
    full_paths = [os.path.join(PHOTO_BASE_DIR, p) for p in file_paths]
    placeholders = ', '.join(['?'] * len(full_paths))
    sql_tags = f"SELECT i.file_path, t.tag_name, t.source FROM tags t JOIN images i ON t.image_id = i.id WHERE i.file_path IN ({placeholders})"
    cursor.execute(sql_tags, full_paths)
    tags_results = {}
    for row in cursor.fetchall():
        rel_path = row['file_path'][len(PHOTO_BASE_DIR)+1:]
        if rel_path not in tags_results: tags_results[rel_path] = []
        tags_results[rel_path].append({'tag_name': row['tag_name'], 'source': row['source']})
    sql_coords = f"SELECT file_path, latitude, longitude, date_taken FROM images WHERE file_path IN ({placeholders})"
    cursor.execute(sql_coords, full_paths)
    meta_results = {}
    for row in cursor.fetchall():
        rel_path = row['file_path'][len(PHOTO_BASE_DIR)+1:]
        meta_results[rel_path] = {'lat': row['latitude'], 'lng': row['longitude'], 'date': row['date_taken']}
    conn.close()
    return {'tags': tags_results, 'meta': meta_results}

def get_all_tags():
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("SELECT tag_name, COUNT(*) as count FROM tags GROUP BY tag_name ORDER BY count DESC, tag_name ASC")
    results = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return results

def add_tag(file_path, tag_name, source='manual'):
    full_path = os.path.join(PHOTO_BASE_DIR, file_path)
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM images WHERE file_path = ?", (full_path,))
    row = cursor.fetchone()
    if not row:
        if os.path.exists(full_path):
            stats = os.stat(full_path)
            cursor.execute(
                "INSERT INTO images (file_path, file_name, date_added, file_size) VALUES (?, ?, ?, ?)",
                (full_path, os.path.basename(full_path), datetime.now(), stats.st_size)
            )
            image_id = cursor.lastrowid
        else: return False
    else: image_id = row['id']
    try:
        cursor.execute("INSERT INTO tags (image_id, tag_name, source) VALUES (?, ?, ?)", (image_id, tag_name.lower().strip(), source))
        conn.commit()
        return True
    except: return False
    finally: conn.close()

def delete_tag(file_path, tag_name):
    full_path = os.path.join(PHOTO_BASE_DIR, file_path)
    conn = get_conn()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM tags WHERE image_id IN (SELECT id FROM images WHERE file_path = ?) AND tag_name = ?", (full_path, tag_name.lower().strip()))
        conn.commit()
        return True
    except: return False
    finally: conn.close()

def update_location(rel_path, lat, lng):
    full_path = os.path.join(PHOTO_BASE_DIR, rel_path)
    conn = get_conn()
    cursor = conn.cursor()
    try:
        cursor.execute("UPDATE images SET latitude = ?, longitude = ? WHERE file_path = ?", (lat, lng, full_path))
        conn.commit()
        return True
    except: return False
    finally: conn.close()

if __name__ == "__main__":
    if len(sys.argv) < 2: sys.exit(1)
    action = sys.argv[1]
    if action == "search": print(json.dumps(search(" ".join(sys.argv[2:]))))
    elif action == "get_all_tags": print(json.dumps(get_all_tags()))
    elif action == "get_summarized_timeline": print(json.dumps(get_summarized_timeline()))
    elif action == "get_photos_by_date": print(json.dumps(get_photos_by_date(sys.argv[2])))
    elif action == "get_geolocated": print(json.dumps(get_all_geolocated()))
    elif action == "get_batch_metadata": print(json.dumps(get_batch_metadata(json.loads(sys.argv[2]))))
    elif action == "update_location": print(json.dumps(update_location(sys.argv[2], float(sys.argv[3]) if sys.argv[3] != 'null' else None, float(sys.argv[4]) if sys.argv[4] != 'null' else None)))
    elif action == "add_tag": print(json.dumps(add_tag(sys.argv[2], sys.argv[3])))
    elif action == "delete_tag": print(json.dumps(delete_tag(sys.argv[2], sys.argv[3])))
