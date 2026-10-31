"""Disposable SQLite and private temporary storage; production engine is blocked."""
import io
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch
import unittest
from PIL import Image
from sqlalchemy.orm import Session
import test_owner_onboarding
from app.services import profile_image_storage as storage

class StudioPhotoTests(unittest.TestCase):
    auth = test_owner_onboarding.OnboardingTests.auth
    def setUp(self):
        test_owner_onboarding.OnboardingTests.setUp(self)
        self.directory = TemporaryDirectory()
        self.settings = patch.object(storage, 'settings', SimpleNamespace(profile_image_dir=self.directory.name))
        self.settings.start()
        self.assertEqual(self.client.put('/owner/studio', headers=self.headers, json=self.body).status_code, 200)
    def tearDown(self):
        self.settings.stop(); self.directory.cleanup()
        test_owner_onboarding.OnboardingTests.tearDown(self)
    def image(self, format='PNG'):
        output = io.BytesIO(); Image.new('RGB', (700, 400), 'blue').save(output, format=format)
        return output.getvalue()
    def upload(self, content=None, mime='image/png', headers=None):
        return self.client.post('/owner/studio/photo', content=self.image() if content is None else content,
            headers={**(self.headers if headers is None else headers), 'Content-Type': mime})
    def test_upload_replace_remove_and_details_preserve(self):
        for format, mime in [('JPEG','image/jpeg'), ('PNG','image/png'), ('WEBP','image/webp')]:
            r = self.upload(self.image(format), mime); self.assertEqual(r.status_code, 200, r.text)
            image = self.client.get('/owner/studio/photo', headers=self.headers)
            self.assertEqual(image.status_code, 200)
            self.assertEqual(image.headers['content-type'], 'image/png')
            self.assertEqual(image.headers['cache-control'], 'no-store')
            self.assertEqual(image.headers['x-content-type-options'], 'nosniff')
            with Image.open(io.BytesIO(image.content)) as decoded:
                self.assertLessEqual(max(decoded.size), 512); self.assertFalse(decoded.info)
            self.assertEqual(len(list(Path(self.directory.name).iterdir())), 1)
        self.client.put('/owner/studio', headers=self.headers, json={**self.body, 'studio_name':'Updated'})
        self.assertEqual(self.client.get('/owner/studio/photo', headers=self.headers).status_code, 200)
        self.assertEqual(self.client.delete('/owner/studio/photo', headers=self.headers).status_code, 200)
        self.assertEqual(self.client.get('/owner/studio/photo', headers=self.headers).status_code, 404)
        self.assertEqual(list(Path(self.directory.name).iterdir()), [])
    def test_owner_scope_and_protected_fields(self):
        for headers, code in [({},401),(self.auth(1),403),(self.auth(3),403)]:
            self.assertEqual(self.upload(headers=headers).status_code, code)
            self.assertEqual(self.client.get('/owner/studio/photo', headers=headers).status_code, code)
            self.assertEqual(self.client.delete('/owner/studio/photo', headers=headers).status_code, code)
        self.assertEqual(self.upload().status_code,200)
        self.assertEqual(self.client.get('/owner/studio/photo',headers=self.auth(4)).status_code,409)
        self.assertEqual(self.client.get('/owner/studio/photo?user_id=2',headers=self.auth(4)).status_code,422)
        self.assertEqual(self.client.put('/owner/studio',headers=self.headers,json={**self.body,'studio_photo':'../../etc/passwd'}).status_code,422)
    def test_malformed_oversized_and_animated(self):
        self.assertEqual(self.upload(b'not an image').status_code,422)
        self.assertEqual(self.upload(b'<svg/>','image/svg+xml').status_code,415)
        self.assertEqual(self.upload(b'x'*(5*1024*1024+1)).status_code,413)
        output=io.BytesIO(); Image.new('RGB',(10,10)).save(output,format='PNG',save_all=True,append_images=[Image.new('RGB',(10,10),'red')])
        self.assertEqual(self.upload(output.getvalue()).status_code,422)
        self.assertEqual(list(Path(self.directory.name).iterdir()),[])
    def test_unmigrated_profile_is_compatible(self):
        # DDL exclusively on fixture SQLite, never MySQL.
        with self.engine.begin() as connection:
            connection.exec_driver_sql('ALTER TABLE UserProfile DROP COLUMN studio_photo')
        self.assertEqual(self.client.get('/owner/studio/photo-status',headers=self.headers).json(),{'available':False,'has_photo':False})
        self.assertEqual(self.upload().status_code,503)
        self.assertEqual(self.client.get('/owner/onboarding',headers=self.headers).status_code,200)
        self.assertEqual(self.client.put('/owner/studio',headers=self.auth(4),json=self.body).status_code,200)
        self.assertEqual(list(Path(self.directory.name).iterdir()),[])
    def test_failed_flush_preserves_old_photo(self):
        self.assertEqual(self.upload().status_code,200)
        previous=set(Path(self.directory.name).iterdir())
        from sqlalchemy.exc import SQLAlchemyError
        with patch.object(Session,'flush',side_effect=SQLAlchemyError('private')):
            self.assertEqual(self.upload().status_code,503)
        self.assertEqual(set(Path(self.directory.name).iterdir()),previous)
        self.assertEqual(self.client.get('/owner/studio/photo',headers=self.headers).status_code,200)
    def test_decoded_limit_and_unsafe_reference(self):
        with patch.object(storage, 'MAX_PIXELS', 100):
            self.assertEqual(self.upload().status_code, 422)
        from app.models.profile import UserProfile
        from sqlalchemy import select
        with Session(self.engine) as db:
            profile = db.scalar(select(UserProfile).where(UserProfile.user_id == 2))
            profile.studio_photo = '../../etc/passwd'
            db.commit()
        self.assertEqual(self.client.get('/owner/studio/photo', headers=self.headers).status_code, 404)
        self.assertEqual(list(Path(self.directory.name).iterdir()), [])
