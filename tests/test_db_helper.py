import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

from db_helper import GalleryDB


class GalleryDBTestBase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.base = self._tmp.name
        self.db_path = os.path.join(self.base, 'test.db')
        self.db = GalleryDB(self.db_path, self.base)

        # A couple of known images (one public, one private)
        self.pub = 'photos/pub.jpg'
        self.priv = 'photos/priv.jpg'
        os.makedirs(os.path.join(self.base, 'photos'), exist_ok=True)
        for rel in (self.pub, self.priv):
            with open(os.path.join(self.base, rel), 'w') as f:
                f.write('x')

        self._add(self.pub, public=True)
        self._add(self.priv, public=False)
        # Give the private image a tag matching the default member tag
        self.db.add_tag(self.priv, 'shared')

    def tearDown(self):
        self._tmp.cleanup()

    def _add(self, rel, public):
        cursor = self.db.get_conn().cursor()
        cursor.execute(
            "INSERT INTO images (file_path, file_name, date_added, is_public) "
            "VALUES (?, ?, datetime('now'), ?)",
            (rel, os.path.basename(rel), 1 if public else 0),
        )
        cursor.connection.commit()
        cursor.connection.close()


class PrivacyTests(GalleryDBTestBase):
    def test_non_admin_sees_only_public(self):
        results = self.db.get_all_images(is_admin=False, user_tag=None)
        paths = [r['path'] for r in results]
        self.assertIn(self.pub, paths)
        self.assertNotIn(self.priv, paths)

    def test_admin_sees_everything(self):
        results = self.db.get_all_images(is_admin=True)
        paths = [r['path'] for r in results]
        self.assertIn(self.pub, paths)
        self.assertIn(self.priv, paths)

    def test_member_sees_tagged_private(self):
        results = self.db.get_all_images(is_admin=False, user_tag='shared')
        paths = [r['path'] for r in results]
        self.assertIn(self.pub, paths)
        self.assertIn(self.priv, paths)

    def test_sql_injection_in_user_tag_is_safe(self):
        # Malicious user_tag must not alter the query result or error out.
        evil = "x' OR '1'='1"
        results = self.db.get_all_images(is_admin=False, user_tag=evil)
        # It should not leak the private image.
        paths = [r['path'] for r in results]
        self.assertNotIn(self.priv, paths)


class PathTraversalTests(GalleryDBTestBase):
    def test_resolve_under_base_blocks_escape(self):
        full, rel = self.db.resolve_under_base('../outside.jpg')
        self.assertIsNone(full)
        self.assertIsNone(rel)

    def test_resolve_under_base_allows_inside(self):
        full, rel = self.db.resolve_under_base(self.pub)
        self.assertIsNotNone(full)
        self.assertEqual(rel, self.pub)

    def test_add_tag_rejects_traversal(self):
        res = self.db.add_tag('../../etc/passwd', 'evil')
        self.assertFalse(res['success'])
        self.assertIn('Invalid path', res['error'])

    def test_delete_image_rejects_traversal(self):
        res = self.db.delete_image('../../etc/passwd')
        self.assertFalse(res['success'])


class PhotosByDateTests(GalleryDBTestBase):
    """`get_photos_by_date` : cette methode manquait, et `api.py` renvoyait alors
    `[false, "Unknown action: …"]` — un tableau, qu'un appelant parcourt comme une
    liste de chemins. Ces tests verrouillent ce qui compte : la meme regle de date que
    `get_summarized_timeline`, et la meme clause de confidentialite que le reste."""

    def _set_dates(self, rel, taken=None, added=None):
        conn = self.db.get_conn()
        cur = conn.cursor()
        cur.execute("UPDATE images SET date_taken = ?, date_added = COALESCE(?, date_added) "
                    "WHERE file_path = ?", (taken, added, rel))
        conn.commit()
        conn.close()

    def test_non_admin_sees_only_public_on_that_day(self):
        self._set_dates(self.pub, taken='2024-05-01 10:00:00')
        self._set_dates(self.priv, taken='2024-05-01 11:00:00')
        paths = [r['path'] for r in self.db.get_photos_by_date('2024-05-01')]
        self.assertIn(self.pub, paths)
        self.assertNotIn(self.priv, paths)

    def test_admin_sees_private_too(self):
        self._set_dates(self.pub, taken='2024-05-01 10:00:00')
        self._set_dates(self.priv, taken='2024-05-01 11:00:00')
        paths = [r['path'] for r in self.db.get_photos_by_date('2024-05-01', is_admin=True)]
        self.assertIn(self.priv, paths)

    def test_falls_back_to_date_added(self):
        """date_taken NULL : c'est date_added qui fait foi, comme dans la chronologie."""
        self._set_dates(self.pub, taken=None, added='2024-06-02 08:00:00')
        paths = [r['path'] for r in self.db.get_photos_by_date('2024-06-02')]
        self.assertIn(self.pub, paths)

    def test_other_days_are_excluded(self):
        self._set_dates(self.pub, taken='2024-05-01 10:00:00')
        self.assertEqual(self.db.get_photos_by_date('2024-05-02'), [])

    def test_agrees_with_summarized_timeline(self):
        """Le compte du jour et la liste du jour doivent parler de la meme chose."""
        self._set_dates(self.pub, taken='2024-07-03 09:00:00')
        self._set_dates(self.priv, taken='2024-07-03 09:30:00')
        compte = {e['day']: e['count'] for e in self.db.get_summarized_timeline()}
        liste = self.db.get_photos_by_date('2024-07-03')
        self.assertEqual(compte.get('2024-07-03'), len(liste))

    def test_sql_injection_in_user_tag_is_safe(self):
        self._set_dates(self.pub, taken='2024-05-01 10:00:00')
        self._set_dates(self.priv, taken='2024-05-01 11:00:00')
        paths = [r['path'] for r in
                 self.db.get_photos_by_date("2024-05-01", user_tag="x' OR '1'='1")]
        self.assertNotIn(self.priv, paths)


class PathCanonicalisationTests(GalleryDBTestBase):
    """`file_path` est UNIQUE, mais deux ECRITURES du meme fichier sont deux chaines
    differentes : `photos/x.jpg` et `/base/photos/x.jpg` passent toutes deux la
    contrainte. Constate en production : deux photos indexees deux fois, la seconde
    ligne sans la licence ni l'etiquette de proprietaire de la premiere — la galerie
    affichait la meme image deux fois, dont une sans attribution."""

    def _count(self, rel):
        conn = self.db.get_conn()
        n = conn.execute("SELECT COUNT(*) FROM images WHERE file_name = ?",
                         (os.path.basename(rel),)).fetchone()[0]
        conn.close()
        return n

    def test_absolute_path_does_not_create_a_second_row(self):
        avant = self._count(self.pub)
        self.db.add_tag(os.path.join(self.base, self.pub), 'depuis-un-chemin-absolu')
        self.assertEqual(self._count(self.pub), avant,
                         "un chemin absolu a cree une seconde ligne pour le meme fichier")

    def test_tag_added_by_absolute_path_lands_on_the_same_image(self):
        self.db.add_tag(os.path.join(self.base, self.pub), 'marqueur')
        meta = self.db.get_batch_metadata([self.pub])
        noms = [t['tag_name'] for t in meta['tags'].get(self.pub, [])]
        self.assertIn('marqueur', noms)

    def test_dotted_path_is_canonicalised(self):
        avant = self._count(self.pub)
        self.db.add_tag('photos/../photos/pub.jpg', 'chemin-detourne')
        self.assertEqual(self._count(self.pub), avant)

    def test_set_public_accepts_an_absolute_path(self):
        """Sans normalisation, l'UPDATE ne touchait AUCUNE ligne et echouait en silence."""
        self.db.set_public(os.path.join(self.base, self.pub), False)
        conn = self.db.get_conn()
        val = conn.execute("SELECT is_public FROM images WHERE file_path = ?",
                           (self.pub,)).fetchone()[0]
        conn.close()
        self.assertEqual(val, 0)

    def test_escaping_the_base_is_refused(self):
        self.assertIsNone(self.db.canonical_rel('../../etc/passwd'))


class SearchTests(GalleryDBTestBase):
    def test_search_matches_tag_and_path(self):
        # Search by tag name
        by_tag = self.db.search('shared', is_admin=True)
        self.assertTrue(any(r['path'] == self.priv for r in by_tag))
        # Search by file name
        by_name = self.db.search('pub', is_admin=True)
        self.assertTrue(any(r['path'] == self.pub for r in by_name))


class RandomTests(GalleryDBTestBase):
    def test_random_returns_requested_number_of_public_images(self):
        results = self.db.get_random_images(limit=3, is_admin=False, user_tag=None)
        # Deterministic: only public image exists in this dataset.
        self.assertLessEqual(len(results), 3)
        for r in results:
            self.assertIn('path', r)

    def test_random_admin_sees_private_too(self):
        results = self.db.get_random_images(limit=100, is_admin=True)
        self.assertEqual(len(results), 2)
        paths = {r['path'] for r in results}
        self.assertEqual(paths, {self.pub, self.priv})

    def test_random_limit_is_clamped(self):
        # Deterministic: negative/zero limits are clamped up (min 1) and never error.
        self.assertGreaterEqual(len(self.db.get_random_images(limit=-5, is_admin=True)), 1)
        self.assertGreaterEqual(len(self.db.get_random_images(limit=0, is_admin=True)), 1)


class FolderCoverTests(GalleryDBTestBase):
    def test_cover_from_indexed_public_image(self):
        # The db has two indexed images under 'photos/'; non-admin should get a public one.
        cover = self.db.get_album_folder_cover('photos', is_admin=False, user_tag=None)
        self.assertIsNotNone(cover)
        # Deterministic: the private image is not public, so a non-admin must not see it.
        self.assertNotEqual(cover['path'], self.priv)
        self.assertIn('path', cover)

    def test_cover_returns_none_for_missing_folder(self):
        self.assertIsNone(self.db.get_album_folder_cover('does-not-exist', is_admin=True))

    def test_cover_falls_back_to_scan(self):
        # A folder with a file on disk but no DB row should still yield a cover.
        empty = 'photos/raw'
        os.makedirs(os.path.join(self.base, empty), exist_ok=True)
        with open(os.path.join(self.base, empty, 'pic.png'), 'w') as f:
            f.write('x')
        cover = self.db.get_album_folder_cover(empty, is_admin=True)
        self.assertIsNotNone(cover)
        self.assertTrue(cover['path'].startswith(empty))


class AlbumTests(GalleryDBTestBase):
    def _create_album(self, name, description=''):
        return self.db.create_album(name, description)['album_id']

    def test_create_album_requires_name(self):
        res = self.db.create_album('  ')
        self.assertFalse(res['success'])

    def test_album_lifecycle(self):
        album_id = self._create_album('Voyage', 'Souvenirs')

        # Adding an image that exists creates the album membership.
        self.assertTrue(self.db.add_image_to_album(album_id, self.pub)['success'])
        self.assertTrue(self.db.add_image_to_album(album_id, self.priv)['success'])
        # Adding the same image twice is idempotent.
        self.assertTrue(self.db.add_image_to_album(album_id, self.pub)['success'])

        albums = self.db.list_albums(is_admin=True)
        self.assertEqual(len(albums), 1)
        self.assertEqual(albums[0]['name'], 'Voyage')
        self.assertEqual(albums[0]['image_count'], 2)

        album = self.db.get_album(album_id, is_admin=True)
        self.assertTrue(album['success'])
        self.assertEqual(len(album['images']), 2)

        # Removing one image leaves the other.
        self.assertTrue(self.db.remove_image_from_album(album_id, self.pub)['success'])
        album = self.db.get_album(album_id, is_admin=True)
        self.assertEqual([img['path'] for img in album['images']], [self.priv])

        # Deleting the album removes it.
        self.assertTrue(self.db.delete_album(album_id)['success'])
        self.assertEqual(self.db.list_albums(is_admin=True), [])

    def test_album_privacy_filters_images(self):
        album_id = self._create_album('Mixed')
        self.db.add_image_to_album(album_id, self.pub)
        self.db.add_image_to_album(album_id, self.priv)

        # Non-admin (no tag) should only see the public image.
        album = self.db.get_album(album_id, is_admin=False, user_tag=None)
        self.assertEqual([img['path'] for img in album['images']], [self.pub])
        # Image_count for non-admin should reflect only accessible images.
        albums = self.db.list_albums(is_admin=False, user_tag=None)
        self.assertEqual(albums[0]['image_count'], 1)

    def test_add_image_rejects_traversal(self):
        album_id = self._create_album('Safe')
        res = self.db.add_image_to_album(album_id, '../../etc/passwd')
        self.assertFalse(res['success'])


if __name__ == '__main__':
    unittest.main()
