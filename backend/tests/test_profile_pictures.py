"""Real-JWT picture tests with disposable SQLite accounts and private temporary files."""

from dataclasses import replace
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image, PngImagePlugin
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

import test_privacy
from app.models.user import User
from app.services import profile_image_storage as storage


def picture(fmt="PNG", size=(800, 400)):
    output = io.BytesIO()
    image = Image.new("RGB", size, "red")
    info = PngImagePlugin.PngInfo()
    info.add_text("private-location", "must be stripped")
    image.save(output, format=fmt, **({"pnginfo": info} if fmt == "PNG" else {}))
    return output.getvalue()


class PictureTests(unittest.TestCase):
    auth = test_privacy.PrivacyTests.auth

    def setUp(self):
        test_privacy.PrivacyTests.setUp(self)
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.storage_patch = patch.object(storage, "settings", replace(storage.settings, profile_image_dir=str(self.root)))
        self.storage_patch.start()

    def tearDown(self):
        self.storage_patch.stop()
        self.temp.cleanup()
        test_privacy.PrivacyTests.tearDown(self)

    def upload(self, uid=1, content=None, mime="image/png", path="/users/me/picture"):
        return self.client.post(path, headers={**self.auth(uid), "Content-Type": mime}, content=picture() if content is None else content)

    def test_all_roles_upload_replace_remove_and_private_retrieval(self):
        for uid in (1, 2, 3):
            with self.subTest(uid=uid):
                r = self.upload(uid)
                self.assertEqual(r.status_code, 200)
                first = r.json()["profile_image"]
                self.assertTrue(storage.valid_key(first))
                with Session(self.engine) as db:
                    self.assertEqual(db.get(User, uid).profile_image, first)
                self.assertEqual((self.root / first).stat().st_mode & 0o777, 0o600)
                r = self.client.get("/users/me/picture", headers=self.auth(uid))
                self.assertEqual(r.status_code, 200)
                self.assertEqual(r.headers["content-type"], "image/png")
                self.assertEqual(r.headers["cache-control"], "no-store")
                self.assertEqual(r.headers["x-content-type-options"], "nosniff")
                with Image.open(io.BytesIO(r.content)) as image:
                    self.assertEqual(image.size, (512, 256))
                    self.assertEqual(image.info, {})
                self.assertEqual(self.client.get(f"/users/{uid}/picture").status_code, 404)
                r = self.upload(uid, picture("JPEG"), "image/jpeg")
                self.assertEqual(r.status_code, 200)
                second = r.json()["profile_image"]
                self.assertNotEqual(first, second)
                self.assertFalse((self.root / first).exists())
                self.assertTrue((self.root / second).exists())
                r = self.client.delete("/users/me/picture", headers=self.auth(uid))
                self.assertEqual(r.status_code, 200)
                self.assertIsNone(r.json()["profile_image"])
                self.assertFalse((self.root / second).exists())
                self.assertEqual(self.client.get("/users/me/picture", headers=self.auth(uid)).status_code, 404)
                self.assertEqual(self.client.delete("/users/me/picture", headers=self.auth(uid)).status_code, 200)

    def test_visibility_admin_and_response_filtering(self):
        for uid in (1, 2, 3):
            self.assertEqual(self.upload(uid).status_code, 200)
            # Simulate legacy public JSON for Admin: serving must still deny access.
            with Session(self.engine) as db:
                db.get(User, uid).privacy_preferences = {"profile_visibility": "public"}
                db.commit()
            r = self.client.get(f"/users/{uid}/picture")
            self.assertEqual(r.status_code, 404 if uid == 3 else 200)
            self.assertEqual(r.headers["cache-control"], "no-store")
            if uid != 3:
                body = self.client.get(f"/users/{uid}/public-profile").json()
                self.assertEqual(set(body), {"name", "profile_image"})
                self.assertTrue(storage.valid_key(body["profile_image"]))
                self.client.patch("/users/me/privacy", headers=self.auth(uid), json={"profile_visibility": "private"})
                self.assertEqual(self.client.get(f"/users/{uid}/picture").status_code, 404)

    def test_unauthenticated_and_cross_account_access(self):
        self.assertEqual(self.upload(2).status_code, 200)
        for method in ("get", "post", "delete"):
            r = getattr(self.client, method)("/users/me/picture")
            self.assertEqual(r.status_code, 401)
            self.assertEqual(r.headers["x-content-type-options"], "nosniff")
        self.assertEqual(self.client.get("/users/2/picture", headers=self.auth(1)).status_code, 404)
        with Session(self.engine) as db:
            before = db.get(User, 2).profile_image
        self.assertEqual(self.upload(path="/users/me/picture?user_id=2").status_code, 200)
        self.assertEqual(self.client.delete("/users/me/picture?user_id=2", headers=self.auth(1)).status_code, 200)
        with Session(self.engine) as db:
            self.assertEqual(db.get(User, 2).profile_image, before)
        self.assertEqual(self.upload(path="/users/2/picture").status_code, 405)

    def test_malformed_formats_and_animation(self):
        for data, mime, status in ((b"", "image/png", 422), (b"broken", "image/jpeg", 422),
                                   (b"<svg/>", "image/svg+xml", 415), (b"<svg/>", "image/png", 422),
                                   (picture("GIF"), "image/png", 422), (picture()[:50], "image/png", 422),
                                   (b"https://example.com/image.png", "image/png", 422)):
            self.assertEqual(self.upload(content=data, mime=mime).status_code, status)
        output = io.BytesIO()
        Image.new("RGB", (8, 8), "red").save(output, format="PNG", save_all=True,
                                             append_images=[Image.new("RGB", (8, 8), "blue")], duration=100)
        self.assertEqual(self.upload(content=output.getvalue()).status_code, 422)
        self.assertEqual(list(self.root.iterdir()), [])

    def test_size_and_pixel_limits(self):
        self.assertEqual(self.upload(content=b"x" * (storage.MAX_UPLOAD + 1)).status_code, 413)
        self.assertEqual(self.upload(content=picture(size=(4001, 4000))).status_code, 422)
        self.assertEqual(list(self.root.iterdir()), [])

    def test_chunked_limit_without_content_length(self):
        from fastapi import HTTPException
        from starlette.requests import Request
        from app.routers.users import upload_picture
        import asyncio
        calls = []
        async def receive():
            calls.append(1)
            return {"type": "http.request", "body": b"x" * (1024 * 1024), "more_body": True}
        request = Request({"type": "http", "headers": [(b"content-type", b"image/png")], "method": "POST"}, receive)
        with self.assertRaises(HTTPException) as caught:
            asyncio.run(upload_picture(request, user=None, db=None))
        self.assertEqual(caught.exception.status_code, 413)
        self.assertEqual(len(calls), 6)

    def test_paths_symlinks_and_no_raw_key_serving(self):
        outside = self.root / "sentinel"
        outside.write_bytes(b"private")
        for key in ("../sentinel", str(outside), "https://example.com/image.png"):
            with Session(self.engine) as db:
                db.get(User, 1).profile_image = key
                db.get(User, 1).privacy_preferences = {"profile_visibility": "public"}
                db.commit()
            self.assertIsNone(self.client.get("/users/1/public-profile").json()["profile_image"])
            self.assertEqual(self.client.get("/users/me/picture", headers=self.auth(1)).status_code, 404)
            self.assertEqual(self.client.delete("/users/me/picture", headers=self.auth(1)).status_code, 200)
            self.assertEqual(outside.read_bytes(), b"private")
        key = "a" * 64 + ".png"
        (self.root / key).symlink_to(outside)
        with Session(self.engine) as db:
            db.get(User, 1).profile_image = key
            db.commit()
        self.assertEqual(self.client.get("/users/me/picture", headers=self.auth(1)).status_code, 404)
        self.assertEqual(self.client.get('/' + key).status_code, 404)

    def test_storage_failure_and_database_rollback(self):
        first = self.upload().json()["profile_image"]
        with patch.object(storage, "write_image", side_effect=OSError("private path")):
            r = self.upload()
        self.assertEqual(r.status_code, 503)
        self.assertNotIn("private path", r.text)
        with patch.object(Session, "commit", side_effect=SQLAlchemyError("uncertain commit")):
            r = self.upload()
        self.assertEqual(r.status_code, 503)
        with Session(self.engine) as db:
            self.assertEqual(db.get(User, 1).profile_image, first)
        self.assertTrue((self.root / first).exists())
        self.assertEqual(self.client.get("/users/me/picture", headers=self.auth(1)).status_code, 200)

    def test_cleanup_failure_does_not_undo_commit(self):
        first = self.upload().json()["profile_image"]
        with patch.object(storage, "delete_image", side_effect=OSError("cannot delete")):
            r = self.upload()
        self.assertEqual(r.status_code, 200)
        self.assertNotEqual(r.json()["profile_image"], first)
        self.assertEqual(self.client.get("/users/me/picture", headers=self.auth(1)).status_code, 200)

    def test_failed_write_and_flush_leave_existing_reference_intact(self):
        first = self.upload().json()["profile_image"]
        before = set(self.root.iterdir())
        with patch.object(storage.os, "fsync", side_effect=OSError("disk failure")):
            self.assertEqual(self.upload().status_code, 503)
        self.assertEqual(set(self.root.iterdir()), before)
        with patch.object(Session, "flush", side_effect=SQLAlchemyError("flush failure")):
            self.assertEqual(self.upload().status_code, 503)
        self.assertEqual(set(self.root.iterdir()), before)
        with Session(self.engine) as db:
            self.assertEqual(db.get(User, 1).profile_image, first)

    def test_replacement_reloads_stale_identity_before_cleanup(self):
        from app.services.profile_image_service import change_picture
        first = self.upload().json()["profile_image"]
        with Session(self.engine, expire_on_commit=False) as stale_db:
            stale_user = stale_db.get(User, 1)
            # End the read transaction but retain the earlier identity-map snapshot.
            stale_db.commit()
            second = self.upload().json()["profile_image"]
            self.assertEqual(stale_user.profile_image, first)
            third = change_picture(stale_db, stale_user, picture())["profile_image"]
        self.assertNotEqual(second, third)
        self.assertFalse((self.root / second).exists())
        self.assertTrue((self.root / third).exists())
        with Session(self.engine) as db:
            self.assertEqual(db.get(User, 1).profile_image, third)
