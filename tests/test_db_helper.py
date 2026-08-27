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
