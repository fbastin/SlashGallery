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
                is_public INTEGER DEFAULT 1,
                phorum_message_id INTEGER
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
                'path': row['file_path'] if not os.path.isabs(row['file_path']) else os.path.relpath(row['file_path'], self.photo_base_dir),
                'lat': row['latitude'],
                'lng': row['longitude'],
                'name': row['file_name']
            })
        conn.close()
        return results

    def get_summarized_timeline(self):
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

    def get_all_images(self, is_admin=False, user_tag=None, filter_tag=None):
        conn = self.get_conn()
        cursor = conn.cursor()
        privacy_clause = self._get_privacy_clause(is_admin, user_tag)
        
        sql = f"SELECT DISTINCT i.file_path FROM images i LEFT JOIN tags t ON i.id = t.image_id WHERE ({privacy_clause})"
        params = []
        
        if filter_tag:
            sql += " AND i.id IN (SELECT image_id FROM tags WHERE tag_name = ?)"
            params.append(filter_tag.lower())
            
        sql += " ORDER BY i.id DESC"
        cursor.execute(sql, params)
        results = []
        for row in cursor.fetchall():
            fp = row['file_path']
            if os.path.isabs(fp):
                fp = os.path.relpath(fp, self.photo_base_dir)
            results.append({'path': fp})
        conn.close()
        return results

    def get_by_message_id(self, message_id):
        conn = self.get_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT file_path FROM images WHERE phorum_message_id = ?", (message_id,))
        results = []
        for row in cursor.fetchall():
            results.append({
                'path': row['file_path'] if not os.path.isabs(row['file_path']) else os.path.relpath(row['file_path'], self.photo_base_dir)
            })
        conn.close()
        return results

    def search(self, query_str, is_admin=False, user_tag=None, filter_tag=None):
        conn = self.get_conn()
        cursor = conn.cursor()
        keywords = query_str.split()
        privacy_clause = self._get_privacy_clause(is_admin, user_tag)
        
        sql = f"SELECT DISTINCT i.file_path, i.latitude, i.longitude, i.date_taken FROM images i LEFT JOIN tags t ON i.id = t.image_id WHERE ({privacy_clause})"
        params = []
        
        if filter_tag:
            sql += " AND i.id IN (SELECT image_id FROM tags WHERE tag_name = ?)"
            params.append(filter_tag.lower())

        if keywords:
            conditions = []
            for kw in keywords:
                kw_pattern = f"%{kw}%"
                conditions.append("(i.file_path LIKE ? OR t.tag_name LIKE ?)")
                params.extend([kw_pattern, kw_pattern])
            sql += " AND (" + " AND ".join(conditions) + ")"
            
        sql += " LIMIT 500"
        cursor.execute(sql, params)
        results = []
        for row in cursor.fetchall():
            results.append({
                'path': row['file_path'] if not os.path.isabs(row['file_path']) else os.path.relpath(row['file_path'], self.photo_base_dir),
                'lat': row['latitude'],
                'lng': row['longitude']
            })
        conn.close()
        return results

    def get_batch_metadata(self, file_paths):
        conn = self.get_conn()
        cursor = conn.cursor()
        if not file_paths: return {'tags': {}, 'meta': {}}

        placeholders = ', '.join(['?'] * len(file_paths))
        sql_tags = f"SELECT i.file_path, t.tag_name, t.source FROM tags t JOIN images i ON t.image_id = i.id WHERE i.file_path IN ({placeholders})"
        cursor.execute(sql_tags, file_paths)
        tags_results = {}
        for row in cursor.fetchall():
            fp = row['file_path']
            if fp not in tags_results: tags_results[fp] = []
            tags_results[fp].append({'tag_name': row['tag_name'], 'source': row['source']})

        sql_coords = f"SELECT file_path, latitude, longitude, date_taken, is_public FROM images WHERE file_path IN ({placeholders})"
        cursor.execute(sql_coords, file_paths)
        meta_results = {}
        for row in cursor.fetchall():
            meta_results[row['file_path']] = {'lat': row['latitude'], 'lng': row['longitude'], 'date': row['date_taken'], 'is_public': bool(row['is_public'])}
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
        conn = self.get_conn()
        cursor = conn.cursor()
        try:
            cursor.execute("DELETE FROM tags WHERE image_id IN (SELECT id FROM images WHERE file_path = ?) AND tag_name = ?", (rel_path, tag_name.lower().strip()))
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
            cursor.execute("SELECT id FROM images WHERE file_path = ?", (rel_path,))
            row = cursor.fetchone()
            if not row:
                if os.path.exists(full_path):
                    stats = os.stat(full_path)
                    cursor.execute(
                        "INSERT INTO images (file_path, file_name, date_added, file_size) VALUES (?, ?, ?, ?)",
                        (rel_path, os.path.basename(rel_path), datetime.now(), stats.st_size)
                    )
                    image_id = cursor.lastrowid
                else:
                    return {"success": False, "error": f"File not found: {rel_path}"}
            else:
                image_id = row['id']
            
            cursor.execute("INSERT OR IGNORE INTO tags (image_id, tag_name, source) VALUES (?, ?, ?)", (image_id, tag_name.lower().strip(), source))
            conn.commit()
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}
        finally:
            conn.close()

    def set_message_id(self, rel_path, message_id):
        conn = self.get_conn()
        cursor = conn.cursor()
        try:
            cursor.execute("UPDATE images SET phorum_message_id = ? WHERE file_path = ?", (message_id, rel_path))
            conn.commit()
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}
        finally:
            conn.close()

    def delete_by_message_id(self, message_id):
        conn = self.get_conn()
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT file_path FROM images WHERE phorum_message_id = ?", (message_id,))
            rows = cursor.fetchall()
            for row in rows:
                self.delete_image(row['file_path'])
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}
        finally:
            conn.close()

    def update_location(self, rel_path, lat, lng):
        conn = self.get_conn()
        cursor = conn.cursor()
        try:
            cursor.execute("UPDATE images SET latitude = ?, longitude = ? WHERE file_path = ?", (lat, lng, rel_path))
            conn.commit()
            return True
        except: return False
        finally: conn.close()

    def set_public(self, rel_path, is_public):
        conn = self.get_conn()
        cursor = conn.cursor()
        try:
            cursor.execute("UPDATE images SET is_public = ? WHERE file_path = ?", (1 if is_public else 0, rel_path))
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
            cursor.execute("SELECT id, phorum_message_id FROM images WHERE file_path = ?", (rel_path,))
            row = cursor.fetchone()
            if row:
                image_id = row['id']
                msg_id = row['phorum_message_id']
                cursor.execute("DELETE FROM tags WHERE image_id = ?", (image_id,))
                cursor.execute("DELETE FROM images WHERE id = ?", (image_id,))
                conn.commit()
                if not msg_id and os.path.exists(full_path):
                    os.remove(full_path)
                    thumb = os.path.join(self.photo_base_dir, 'thumbs', rel_path)
                    if os.path.exists(thumb):
                        os.remove(thumb)
            return {"success": True, "file_deleted": not bool(row and row['phorum_message_id'])}
        except Exception as e:
            return {"success": False, "error": str(e)}
        finally:
            conn.close()
