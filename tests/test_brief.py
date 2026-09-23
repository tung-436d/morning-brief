from datetime import datetime, timedelta
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from collect_news import CST, parse_feed
from cloud_brief import ensure_fresh
from push_brief import push_qmsg, split_text, confirm_qmsg, QmsgContentRejected


class BriefTests(unittest.TestCase):
    def test_rss_filters_old_and_undated(self):
        now = datetime(2026, 9, 24, 7, 40, tzinfo=CST)
        rss = b'''<rss><channel>
        <item><title>Fresh &amp; useful</title><pubDate>Wed, 23 Sep 2026 20:00:00 +0800</pubDate></item>
        <item><title>Old</title><pubDate>Tue, 22 Sep 2026 20:00:00 +0800</pubDate></item>
        <item><title>No date</title></item></channel></rss>'''
        self.assertEqual([x['title'] for x in parse_feed(rss, now)], ['Fresh & useful'])

    def test_atom(self):
        now = datetime(2026, 9, 24, 7, 40, tzinfo=CST)
        atom = b'''<feed xmlns="http://www.w3.org/2005/Atom"><entry><title>News</title>
        <updated>2026-09-23T22:00:00Z</updated><link href="https://example.com/a"/></entry></feed>'''
        self.assertEqual(parse_feed(atom, now)[0]['url'], 'https://example.com/a')

    def test_chunk_limit(self):
        text = 'x' * 2000 + '\n' + 'y' * 1000
        chunks = split_text(text, 950)
        self.assertTrue(all(len(x) <= 950 for x in chunks))
        self.assertEqual(''.join(chunks).replace('\n', ''), text.replace('\n', ''))

    def test_qmsg_rejects_ambiguous_success(self):
        for response in ('<html>error</html>', '{}', '[]', '{"success":false}'):
            with self.subTest(response=response), patch('push_brief.http_post_form', return_value=response):
                with self.assertRaises(RuntimeError):
                    push_qmsg('test', {'key': 'test'})

    def test_qmsg_success(self):
        with patch('push_brief.http_post_form', return_value='{"success":true,"data":42}') as post, patch('push_brief.confirm_qmsg') as confirm:
            push_qmsg('test', {'key': 'test', 'qq': '123'})
            self.assertEqual(post.call_args.args[1], {'msg': 'test', 'qq': '123'})
            confirm.assert_called_once_with('test', 42)

    def test_async_rejection_is_failure(self):
        with patch('push_brief.http_post_form', return_value='{"success":true,"data":2}'), patch('push_brief.time.sleep'):
            with self.assertRaises(QmsgContentRejected):
                confirm_qmsg('test', 42)

    def test_pending_then_success(self):
        with patch('push_brief.http_post_form', side_effect=['{"success":true,"data":0}', '{"success":true,"data":1}']), patch('push_brief.time.sleep'):
            confirm_qmsg('test', 42)

    def test_pending_timeout_is_not_success(self):
        with patch('push_brief.http_post_form', return_value='{"success":true,"data":0}'), patch('push_brief.time.sleep'):
            with self.assertRaises(RuntimeError):
                confirm_qmsg('test', 42, attempts=2)

    def test_stale_artifact_recollected(self):
        with tempfile.TemporaryDirectory() as tmp, patch('cloud_brief.collect') as collect:
            directory = Path(tmp)
            yesterday = datetime.now(CST) - timedelta(days=1)
            (directory / 'brief.json').write_text(json.dumps({'date': yesterday.date().isoformat(), 'generated_at': yesterday.isoformat()}))
            (directory / 'brief.txt').write_text('old')
            ensure_fresh(directory)
            collect.assert_called_once_with(directory)


if __name__ == '__main__':
    unittest.main()
