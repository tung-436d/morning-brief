import base64
import hashlib
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from push_image import send_image

WEBHOOK = 'https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=test'


class ImageTests(unittest.TestCase):
    def test_payload_and_response(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'test.png'
            path.write_bytes(b'image-data')
            with patch('push_image.http_post_json', return_value='{"errcode":0}') as post:
                send_image(path, WEBHOOK)
                payload = post.call_args.args[1]
                self.assertEqual(payload['msgtype'], 'image')
                self.assertEqual(base64.b64decode(payload['image']['base64']), b'image-data')
                self.assertEqual(payload['image']['md5'], hashlib.md5(b'image-data').hexdigest())
            for response in ('{}', '{"errcode":40058}', '{"errcode":false}'):
                with patch('push_image.http_post_json', return_value=response):
                    with self.assertRaises(RuntimeError):
                        send_image(path, WEBHOOK)

    def test_rejects_oversized_image_before_network(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'large.png'
            path.write_bytes(b'x' * (2 * 1024 * 1024 + 1))
            with patch('push_image.http_post_json') as post:
                with self.assertRaises(ValueError):
                    send_image(path, WEBHOOK)
                post.assert_not_called()

    def test_invalid_destination(self):
        with self.assertRaises(ValueError):
            send_image('unused.png', 'https://example.com?key=test')
