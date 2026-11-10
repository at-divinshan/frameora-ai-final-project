"""Pixel-level checks, no network, database or original-file writes."""
from io import BytesIO
from pathlib import Path
import unittest
from unittest.mock import patch
from PIL import Image, ImageChops, ImageStat
from fastapi import HTTPException
from starlette.routing import Mount
from app.main import app
from app.services import shared_preview as preview

class SharedPreviewTests(unittest.TestCase):
    def raw(self, image):
        out=BytesIO();image.save(out,format='PNG');return out.getvalue()

    def test_logo_is_approved_asset_and_positions_are_deterministic(self):
        original=Path(__file__).resolve().parents[2]/'frontend/public/images/logo/logo-icon.png'
        self.assertEqual(preview.LOGO_PATH.read_bytes(),original.read_bytes())
        positions={preview.logo_position((960,720),(100,60),bytes([i])) for i in range(3)}
        self.assertEqual(len(positions),3)
        for x,y in positions:
            self.assertGreaterEqual(x,0);self.assertLessEqual(x+100,960)
            self.assertGreater(y,600);self.assertLessEqual(y+60,720)
        raw=self.raw(Image.new('RGB',(1600,1200),'navy'))
        first=preview.preview_bytes(raw)
        self.assertEqual(first,preview.preview_bytes(raw))
        output=Image.open(BytesIO(first));self.assertEqual(output.size,(960,720))
        self.assertGreater(sum(ImageStat.Stat(output.crop((0,600,960,720))).var),1)
        self.assertLess(sum(ImageStat.Stat(output.crop((0,0,960,500))).var),1)

    def test_blur_is_mild_and_original_bytes_unchanged(self):
        image=Image.new('RGB',(500,400))
        for x in range(500):
            for y in range(400):image.putpixel((x,y),(255,255,255) if (x//8+y//8)%2 else (0,0,0))
        raw=self.raw(image);before=bytes(raw)
        blurred=Image.open(BytesIO(preview.preview_bytes(raw)))
        with patch.object(preview,'PREVIEW_BLUR_RADIUS',0):
            sharp=Image.open(BytesIO(preview.preview_bytes(raw)))
        region=(0,0,500,280)
        self.assertIsNotNone(ImageChops.difference(blurred.crop(region),sharp.crop(region)).getbbox())
        b=ImageStat.Stat(blurred.crop(region)).var[0];s=ImageStat.Stat(sharp.crop(region)).var[0]
        self.assertLess(b,s);self.assertGreater(b,s*.5)
        self.assertEqual(raw,before)

    def test_missing_logo_fails_closed_and_no_static_mount_exposes_originals(self):
        with patch.object(preview,'LOGO_PATH',Path('/not-present-frameora-logo')):
            with self.assertRaises(HTTPException):preview.preview_bytes(self.raw(Image.new('RGB',(80,60))))
        self.assertFalse(any(isinstance(route,Mount) for route in app.routes))
