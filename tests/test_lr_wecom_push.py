import base64
import hashlib
import tempfile
import unittest
from pathlib import Path

from lr.wecom_push import image_message


class ImageMessageTest(unittest.TestCase):
    def test_builds_wecom_base64_image_payload(self) -> None:
        content = b"fake png bytes"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "kanban.png"
            path.write_bytes(content)

            payload = image_message(path)

        self.assertEqual(payload["msgtype"], "image")
        self.assertEqual(
            payload["image"]["base64"],
            base64.b64encode(content).decode("ascii"),
        )
        self.assertEqual(payload["image"]["md5"], hashlib.md5(content).hexdigest())


if __name__ == "__main__":
    unittest.main()
