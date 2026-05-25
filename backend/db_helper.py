import sqlite3
import os
from datetime import datetime

class GalleryDB:
    def __init__(self, db_path, photo_base_dir):
        self.db_path = db_path
        self.photo_base_dir = os.path.normpath(photo_base_dir)
        self._ensure_db()

    def _ensure_db(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS images (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_path TEXT UNIQUE,
                file_name TEXT,
                date_added DATETIME,
                date_taken DATETIME,
                file_size INTEGER,
                latitude REAL,
                longitude REAL,
                is_public INTEGER DEFAULT 1
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tags (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                image_id INTEGER,
                tag_name TEXT,
                source TEXT,
                FOREIGN KEY (image_id) REFERENCES images (id),
                UNIQUE(image_id, tag_name, source)
            )
        """)
        conn.commit()
        conn.close()

    def get_conn(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _get_privacy_clause(self, is_admin, user_tag):
        if is_admin:
            return "1=1"
        if user_tag:
            return f"(i.is_public = 1 OR i.id IN (SELECT image_id FROM tags WHERE tag_name = '{user_tag.lower()}'))"
        return "i.is_public = 1"

    def get_geolocated(self, is_admin=False, user_tag=None):
        conn = self.get_conn()
        cursor = conn.cursor()
        clause = self._get_privacy_clause(is_admin, user_tag)
        cursor.execute(f"""
            SELECT i.file_path, i.latitude, i.longitude, i.file_name 
            FROM images i
            WHERE i.latitude IS NOT NULL AND i.longitude IS NOT NULL AND {clause}
        """)
        results = []
        for row in cursor.fetchall():
            results.append({
                'path': os.path.relpath(os.path.normpath(row['file_path']), os.path.normpath(self.photo_base_dir)),
                'lat': row['latitude'],
                'lng': row['longitude'],
                'name': row['file_name']
            })
        conn.close()
        return results

    def get_summarized_timeline(self):
        # Timeline remains public for now or filtered? User didn't specify. 
        # Let's keep it simple and filter it too if needed, but usually timeline is a summary.
        conn = self.get_conn()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT date(COALESCE(date_taken, date_added)) as day, COUNT(*) as count 
            FROM images 
            WHERE is_public = 1
            GROUP BY day 
            ORDER BY day DESC
        """)
        results = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return results

    def get_all_images(self, is_admin=False, user_tag=None):
        conn = self.get_conn()
        cursor = conn.cursor()
        clause = self._get_privacy_clause(is_admin, user_tag)
        cursor.execute(f"SELECT file_path FROM images i WHERE {clause} ORDER BY id DESC")
        results = []
        for row in cursor.fetchall():
            results.append({
                'path': os.path.relpath(os.path.normpath(row['file_path']), os.path.normpath(self.photo_base_dir))
            })
        conn.close()
        return results

    def search(self, query_str, is_admin=False, user_tag=None):
        conn = self.get_conn()
        cursor = conn.cursor()
        keywords = query_str.split()
        if not keywords: return []
        clause = self._get_privacy_clause(is_admin, user_tag)
        sql = f"SELECT DISTINCT i.file_path, i.latitude, i.longitude, i.date_taken FROM images i LEFT JOIN tags t ON i.id = t.image_id WHERE ({clause}) AND "
        conditions = []
        params = []
        for kw in keywords:
            kw_pattern = f"%{kw}%"
            conditions.append("(i.file_path LIKE ? OR t.tag_name LIKE ?)")
            params.extend([kw_pattern, kw_pattern])
        sql += "(" + " AND ".join(conditions) + ") LIMIT 500"
        cursor.execute(sql, params)
        results = []
        for row in cursor.fetchall():
            results.append({
                'path': os.path.relpath(os.path.normpath(row['file_path']), os.path.normpath(self.photo_base_dir)),
                'lat': row['latitude'],
                'lng': row['longitude']
            })
        conn.close()
        return results

    def get_batch_metadata(self, file_paths):
        conn = self.get_conn()
        cursor = conn.cursor()
        full_paths = [os.path.normpath(os.path.join(self.photo_base_dir, p)) for p in file_paths]
        if not full_paths: return {'tags': {}, 'meta': {}}
        
        placeholders = ', '.join(['?'] * len(full_paths))
        sql_tags = f"SELECT i.file_path, t.tag_name, t.source FROM tags t JOIN images i ON t.image_id = i.id WHERE i.file_path IN ({placeholders})"
        cursor.execute(sql_tags, full_paths)
        tags_results = {}
        norm_base = os.path.normpath(self.photo_base_dir)
        for row in cursor.fetchall():
            rel_path = os.path.relpath(os.path.normpath(row['file_path']), norm_base)
            if rel_path not in tags_results: tags_results[rel_path] = []
            tags_results[rel_path].append({'tag_name': row['tag_name'], 'source': row['source']})
            
        sql_coords = f"SELECT file_path, latitude, longitude, date_taken, is_public FROM images WHERE file_path IN ({placeholders})"
        cursor.execute(sql_coords, full_paths)
        meta_results = {}
        for row in cursor.fetchall():
            rel_path = os.path.relpath(os.path.normpath(row['file_path']), norm_base)
            meta_results[rel_path] = {'lat': row['latitude'], 'lng': row['longitude'], 'date': row['date_taken'], 'is_public': bool(row['is_public'])}
        conn.close()
        return {'tags': tags_results, 'meta': meta_results}

    def get_all_tags(self, is_admin=False, user_tag=None):
        conn = self.get_conn()
        cursor = conn.cursor()
        clause = self._get_privacy_clause(is_admin, user_tag)
        cursor.execute(f"SELECT tag_name, COUNT(*) as count FROM tags t JOIN images i ON t.image_id = i.id WHERE {clause} GROUP BY tag_name ORDER BY count DESC, tag_name ASC")
        results = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return results

    def delete_tag(self, rel_path, tag_name):
        full_path = os.path.normpath(os.path.join(self.photo_base_dir, rel_path))
        conn = self.get_conn()
        cursor = conn.cursor()
        try:
            cursor.execute("DELETE FROM tags WHERE image_id IN (SELECT id FROM images WHERE file_path = ?) AND tag_name = ?", (full_path, tag_name.lower().strip()))
            conn.commit()
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}
        finally:
            conn.close()

    def add_tag(self, rel_path, tag_name, source='manual'):
        full_path = os.path.normpath(os.path.join(self.photo_base_dir, rel_path))
        conn = self.get_conn()
        cursor = conn.cursor()
        try:
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
                else: 
                    return {"success": False, "error": f"File not found on disk: {full_path}"}
            else: 
                image_id = row['id']
            
            cursor.execute("INSERT INTO tags (image_id, tag_name, source) VALUES (?, ?, ?)", (image_id, tag_name.lower().strip(), source))
            conn.commit()
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}
        finally:
            conn.close()

    def update_location(self, rel_path, lat, lng):
        full_path = os.path.normpath(os.path.join(self.photo_base_dir, rel_path))
        conn = self.get_conn()
        cursor = conn.cursor()
        try:
            cursor.execute("UPDATE images SET latitude = ?, longitude = ? WHERE file_path = ?", (lat, lng, full_path))
            conn.commit()
            return True
        except: return False
        finally: conn.close()

    def set_public(self, rel_path, is_public):
        full_path = os.path.normpath(os.path.join(self.photo_base_dir, rel_path))
        conn = self.get_conn()
        cursor = conn.cursor()
        try:
            cursor.execute("UPDATE images SET is_public = ? WHERE file_path = ?", (1 if is_public else 0, full_path))
            conn.commit()
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}
        finally:
            conn.close()

    def delete_image(self, rel_path):
        full_path = os.path.normpath(os.path.join(self.photo_base_dir, rel_path))
        conn = self.get_conn()
        cursor = conn.cursor()
        try:
            # Get ID first
            cursor.execute("SELECT id FROM images WHERE file_path = ?", (full_path,))
            row = cursor.fetchone()
            if row:
                image_id = row['id']
                cursor.execute("DELETE FROM tags WHERE image_id = ?", (image_id,))
                cursor.execute("DELETE FROM images WHERE id = ?", (image_id,))
                conn.commit()
            
            # Remove file from disk
            if os.path.exists(full_path):
                os.remove(full_path)
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}
        finally:
            conn.close()
