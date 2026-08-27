import sqlite3
import os
from datetime import date, datetime

# Python 3.12 deprecated the implicit sqlite3 datetime adapter; register an
# explicit ISO-8601 adapter so writes are deterministic and warning-free.
sqlite3.register_adapter(datetime, lambda dt: dt.isoformat(sep=' '))
sqlite3.register_adapter(date, lambda d: d.isoformat())

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
        # Albums: user-defined collections not tied to the filesystem layout.
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS albums (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                description TEXT,
                created_at DATETIME,
                updated_at DATETIME
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS album_images (
                album_id INTEGER,
                image_id INTEGER,
                position INTEGER DEFAULT 0,
                added_at DATETIME,
                PRIMARY KEY (album_id, image_id),
                FOREIGN KEY (album_id) REFERENCES albums (id) ON DELETE CASCADE,
                FOREIGN KEY (image_id) REFERENCES images (id) ON DELETE CASCADE
            )
        """)
        # Migration : licence définie par le propriétaire (domaine public, CC,
        # tous droits réservés). NULL = non défini (photo membre par défaut).
        cursor.execute("PRAGMA table_info(images)")
        cols = [r[1] for r in cursor.fetchall()]
        if 'license' not in cols:
            cursor.execute("ALTER TABLE images ADD COLUMN license TEXT")
        conn.commit()
        conn.close()

    def get_conn(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def resolve_under_base(self, rel_path):
        """Resolve a (possibly relative) path and verify it stays inside photo_base_dir.

        Returns (resolved_full_path, normalized_rel_path) on success, (None, None) if
        the path escapes the base directory. Does not require the file to exist."""
        base = self.photo_base_dir
        candidate = os.path.normpath(os.path.join(base, rel_path))
        if not candidate.startswith(base + os.sep) and candidate != base:
            return None, None
        return candidate, os.path.relpath(candidate, base)

    def _get_privacy_clause(self, is_admin, user_tag):
        if is_admin:
            return "1=1", ()
        if user_tag:
            return (
                "(i.is_public = 1 OR i.id IN (SELECT image_id FROM tags WHERE tag_name = ?))",
                (user_tag.lower(),)
            )
        return "i.is_public = 1", ()

    def get_geolocated(self, is_admin=False, user_tag=None):
        conn = self.get_conn()
        cursor = conn.cursor()
        clause, params = self._get_privacy_clause(is_admin, user_tag)
        cursor.execute(f"""
            SELECT i.file_path, i.latitude, i.longitude, i.file_name 
            FROM images i
            WHERE i.latitude IS NOT NULL AND i.longitude IS NOT NULL AND {clause}
        """, params)
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
        privacy_clause, params = self._get_privacy_clause(is_admin, user_tag)
        
        sql = f"SELECT DISTINCT i.file_path FROM images i LEFT JOIN tags t ON i.id = t.image_id WHERE ({privacy_clause})"
        
        if filter_tag:
            sql += " AND i.id IN (SELECT image_id FROM tags WHERE tag_name = ?)"
            params = params + (filter_tag.lower(),)
            
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
        privacy_clause, params = self._get_privacy_clause(is_admin, user_tag)
        
        sql = f"SELECT DISTINCT i.file_path, i.latitude, i.longitude, i.date_taken FROM images i LEFT JOIN tags t ON i.id = t.image_id WHERE ({privacy_clause})"
        
        if filter_tag:
            sql += " AND i.id IN (SELECT image_id FROM tags WHERE tag_name = ?)"
            params = params + (filter_tag.lower(),)

        if keywords:
            conditions = []
            for kw in keywords:
                kw_pattern = f"%{kw}%"
                conditions.append("(i.file_path LIKE ? OR t.tag_name LIKE ?)")
                params = params + (kw_pattern, kw_pattern)
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

        sql_coords = f"SELECT file_path, latitude, longitude, date_taken, is_public, license FROM images WHERE file_path IN ({placeholders})"
        cursor.execute(sql_coords, file_paths)
        meta_results = {}
        for row in cursor.fetchall():
            meta_results[row['file_path']] = {'lat': row['latitude'], 'lng': row['longitude'], 'date': row['date_taken'], 'is_public': bool(row['is_public']), 'license': row['license']}
        conn.close()
        return {'tags': tags_results, 'meta': meta_results}

    def get_all_tags(self, is_admin=False, user_tag=None):
        conn = self.get_conn()
        cursor = conn.cursor()
        clause, params = self._get_privacy_clause(is_admin, user_tag)
        cursor.execute(f"SELECT tag_name, COUNT(*) as count FROM tags t JOIN images i ON t.image_id = i.id WHERE {clause} GROUP BY tag_name ORDER BY count DESC, tag_name ASC", params)
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
        full_path, _ = self.resolve_under_base(rel_path)
        if full_path is None:
            return {"success": False, "error": f"Invalid path: {rel_path}"}
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
        except Exception:
            return False
        finally:
            conn.close()

    def set_license(self, rel_path, license_code):
        conn = self.get_conn()
        cursor = conn.cursor()
        try:
            cursor.execute("UPDATE images SET license = ? WHERE file_path = ?", (license_code or None, rel_path))
            conn.commit()
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}
        finally:
            conn.close()

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
        full_path, _ = self.resolve_under_base(rel_path)
        if full_path is None:
            return {"success": False, "error": f"Invalid path: {rel_path}"}
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

    def _get_or_create_image_id(self, cursor, rel_path):
        """Return the image id for rel_path, creating a DB row (without tags) if
        the file exists on disk. Returns None if the file is missing/invalid."""
        full_path, _ = self.resolve_under_base(rel_path)
        if full_path is None:
            return None
        cursor.execute("SELECT id FROM images WHERE file_path = ?", (rel_path,))
        row = cursor.fetchone()
        if row:
            return row['id']
        if not os.path.exists(full_path):
            return None
        stats = os.stat(full_path)
        cursor.execute(
            "INSERT INTO images (file_path, file_name, date_added, file_size) VALUES (?, ?, ?, ?)",
            (rel_path, os.path.basename(rel_path), datetime.now(), stats.st_size)
        )
        return cursor.lastrowid

    def get_random_images(self, limit=24, is_admin=False, user_tag=None):
        """Return a random sample of accessible images (privacy-aware)."""
        limit = max(1, min(int(limit), 500))
        conn = self.get_conn()
        cursor = conn.cursor()
        clause, params = self._get_privacy_clause(is_admin, user_tag)
        cursor.execute(
            f"SELECT i.file_path FROM images i WHERE {clause} ORDER BY RANDOM() LIMIT ?",
            params + (limit,)
        )
        results = []
        for row in cursor.fetchall():
            fp = row['file_path']
            if os.path.isabs(fp):
                fp = os.path.relpath(fp, self.photo_base_dir)
            results.append({'path': fp})
        conn.close()
        return results

    def get_album_folder_cover(self, folder_rel_path, is_admin=False, user_tag=None):
        """Pick a single random image inside a folder (a directory-style album)
        to use as its cover. Prefers images already indexed in the DB (privacy-
        aware), falling back to a direct directory scan if none are indexed."""
        full_dir, _ = self.resolve_under_base(folder_rel_path)
        if full_dir is None or not os.path.isdir(full_dir):
            return None

        conn = self.get_conn()
        cursor = conn.cursor()
        clause, params = self._get_privacy_clause(is_admin, user_tag)
        prefix = folder_rel_path.rstrip(os.sep) + os.sep
        cursor.execute(
            f"SELECT i.file_path FROM images i WHERE {clause} AND i.file_path LIKE ? AND i.file_path NOT LIKE ? ORDER BY RANDOM() LIMIT 1",
            params + (prefix + '%', prefix + '%' + os.sep + '%')
        )
        row = cursor.fetchone()
        conn.close()

        if row:
            fp = row['file_path']
            if os.path.isabs(fp):
                return {'path': os.path.relpath(fp, self.photo_base_dir)}
            return {'path': fp}

        # Fallback: scan the directory directly for an image file.
        import random
        allowed = ('.jpg', '.jpeg', '.png', '.gif', '.webp')
        subdirs = []
        images = []
        for item in os.listdir(full_dir):
            item_path = os.path.join(full_dir, item)
            if os.path.isdir(item_path):
                subdirs.append(item_path)
            elif item.lower().endswith(allowed):
                images.append(item)

        # Include images nested in direct subfolders for a nicer cover.
        for sub in subdirs:
            for item in os.listdir(sub):
                if item.lower().endswith(allowed):
                    images.append(os.path.join(sub, item))

        if not images:
            return None

        rel = os.path.relpath(full_dir, self.photo_base_dir)
        chosen = images[random.randrange(len(images))]
        chosen_rel = os.path.join(rel, chosen) if not os.path.isabs(chosen) else chosen
        return {'path': chosen_rel}

    def create_album(self, name, description=''):
        name = (name or '').strip()
        if not name:
            return {"success": False, "error": "Album name is required"}
        conn = self.get_conn()
        cursor = conn.cursor()
        try:
            now = datetime.now()
            cursor.execute(
                "INSERT INTO albums (name, description, created_at, updated_at) VALUES (?, ?, ?, ?)",
                (name, description or '', now, now)
            )
            conn.commit()
            return {"success": True, "album_id": cursor.lastrowid}
        except Exception as e:
            return {"success": False, "error": str(e)}
        finally:
            conn.close()

    def list_albums(self, is_admin=False, user_tag=None):
        """List albums with a photo count (privacy-aware count)."""
        conn = self.get_conn()
        cursor = conn.cursor()
        clause, params = self._get_privacy_clause(is_admin, user_tag)
        cursor.execute(f"""
            SELECT a.id, a.name, a.description, a.created_at, a.updated_at,
                   COUNT(CASE WHEN i.file_path IS NOT NULL THEN 1 END) as image_count
            FROM albums a
            LEFT JOIN album_images ai ON ai.album_id = a.id
            LEFT JOIN images i ON i.id = ai.image_id AND ({clause})
            GROUP BY a.id
            ORDER BY a.updated_at DESC
        """, params)
        results = []
        for row in cursor.fetchall():
            results.append({
                'album_id': row['id'],
                'name': row['name'],
                'description': row['description'],
                'created_at': row['created_at'],
                'updated_at': row['updated_at'],
                'image_count': row['image_count'],
            })
        conn.close()
        return results

    def get_album(self, album_id, is_admin=False, user_tag=None):
        """Return album metadata and its images (privacy-aware)."""
        conn = self.get_conn()
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT id, name, description, created_at FROM albums WHERE id = ?", (album_id,))
            album = cursor.fetchone()
            if not album:
                return {"success": False, "error": "Album not found"}

            clause, params = self._get_privacy_clause(is_admin, user_tag)
            cursor.execute(f"""
                SELECT i.file_path
                FROM album_images ai
                JOIN images i ON i.id = ai.image_id
                WHERE ai.album_id = ? AND ({clause})
                ORDER BY ai.position ASC, ai.added_at ASC
            """, (album_id,) + params)
            images = []
            for row in cursor.fetchall():
                fp = row['file_path']
                if os.path.isabs(fp):
                    fp = os.path.relpath(fp, self.photo_base_dir)
                images.append({'path': fp})
            return {
                'success': True,
                'album_id': album['id'],
                'name': album['name'],
                'description': album['description'],
                'created_at': album['created_at'],
                'images': images,
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
        finally:
            conn.close()

    def add_image_to_album(self, album_id, rel_path):
        conn = self.get_conn()
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT id FROM albums WHERE id = ?", (album_id,))
            if not cursor.fetchone():
                return {"success": False, "error": "Album not found"}

            image_id = self._get_or_create_image_id(cursor, rel_path)
            if image_id is None:
                return {"success": False, "error": f"Invalid or missing file: {rel_path}"}

            pos = cursor.execute(
                "SELECT COALESCE(MAX(position), -1) + 1 FROM album_images WHERE album_id = ?",
                (album_id,)
            ).fetchone()[0]
            cursor.execute(
                "INSERT OR IGNORE INTO album_images (album_id, image_id, position, added_at) VALUES (?, ?, ?, ?)",
                (album_id, image_id, pos, datetime.now())
            )
            cursor.execute("UPDATE albums SET updated_at = ? WHERE id = ?", (datetime.now(), album_id))
            conn.commit()
            return {"success": True, "album_id": album_id}
        except Exception as e:
            return {"success": False, "error": str(e)}
        finally:
            conn.close()

    def remove_image_from_album(self, album_id, rel_path):
        conn = self.get_conn()
        cursor = conn.cursor()
        try:
            cursor.execute(
                "DELETE FROM album_images WHERE album_id = ? AND image_id IN (SELECT id FROM images WHERE file_path = ?)",
                (album_id, rel_path)
            )
            cursor.execute("UPDATE albums SET updated_at = ? WHERE id = ?", (datetime.now(), album_id))
            conn.commit()
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}
        finally:
            conn.close()

    def delete_album(self, album_id):
        conn = self.get_conn()
        cursor = conn.cursor()
        try:
            cursor.execute("DELETE FROM albums WHERE id = ?", (album_id,))
            conn.commit()
            return {"success": True, "deleted": cursor.rowcount > 0}
        except Exception as e:
            return {"success": False, "error": str(e)}
        finally:
            conn.close()
