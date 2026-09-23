import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from wecom_app import send_app_image, upload_image, WeComError

CFG = {'corpid': 'corp', 'corpsecret': 'secret', 'agentid': '1000002', 'touser': 'test-user'}


class AppTests(unittest.TestCase):
    def test_upload_multipart(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'test.png'
            path.write_bytes(b'png-test-data')
            with patch('wecom_app.request_api', return_value={'media_id': 'media'}) as api:
                self.assertEqual(upload_image('token', path), 'media')
                self.assertIn(b'name="media"', api.call_args.args[2])
                self.assertIn(b'png-test-data', api.call_args.args[2])

    def test_send_uses_only_named_recipient(self):
        with patch('wecom_app.get_token', return_value='token'), patch('wecom_app.check_agent'), patch('wecom_app.upload_image', return_value='media'), patch('wecom_app.request_api', return_value={'errcode': 0, 'msgid': 'id'}) as api:
            result = send_app_image('unused', CFG)
            payload = json.loads(api.call_args.args[2])
            self.assertEqual(payload['touser'], 'test-user')
            self.assertEqual(payload['image']['media_id'], 'media')
            self.assertEqual(payload['agentid'], 1000002)
            self.assertEqual(result['status'], 'api_success')

    def test_invalid_user_does_not_report_success(self):
        with patch('wecom_app.get_token', return_value='token'), patch('wecom_app.check_agent'), patch('wecom_app.upload_image', return_value='media'), patch('wecom_app.request_api', return_value={'errcode': 0, 'invaliduser': 'test-user'}):
            with self.assertRaises(WeComError):
                send_app_image('unused', CFG)

    def test_no_default_broadcast(self):
        with patch('wecom_app.get_token', return_value='token'), patch('wecom_app.check_agent'), patch('wecom_app.upload_image') as upload:
            with self.assertRaises(WeComError):
                send_app_image('unused', {**CFG, 'touser': ''})
            upload.assert_not_called()
