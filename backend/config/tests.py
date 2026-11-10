from pathlib import Path
from tempfile import TemporaryDirectory

from django.test import SimpleTestCase, override_settings


class CampusEntryTests(SimpleTestCase):
    def test_frontend_is_served_without_requiring_a_login_token(self):
        with TemporaryDirectory() as folder:
            page = Path(folder) / "index.html"
            page.write_text("<!DOCTYPE html><title>QUALT</title>", encoding="utf-8")
            with override_settings(FRONTEND_INDEX_PATH=page):
                response = self.client.get("/")
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response["Content-Type"], "text/html; charset=utf-8")
                self.assertIn(b"QUALT", b"".join(response.streaming_content))

    def test_a_missing_frontend_file_returns_not_found(self):
        with override_settings(FRONTEND_INDEX_PATH=Path("/missing-qualt-frontend/index.html")):
            self.assertEqual(self.client.get("/").status_code, 404)
