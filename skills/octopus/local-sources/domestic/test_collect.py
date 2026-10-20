"""Regression checks for material daily-brief data-quality guarantees."""
import unittest

from collect import parse_feed, plain

XML = b"""<rss><channel><item><title>AI launch</title>
<link>https://example.org/article</link><pubDate>Tue, 20 Oct 2026 08:00:00 +0800</pubDate>
<description>AI news</description></item></channel></rss>"""


class CandidateTests(unittest.TestCase):
    def candidate(self, semantics, xml=XML):
        return parse_feed(xml, {"id": "test", "name": "test", "date_semantics": semantics},
                          "2026-10-20T10:00:00+08:00", ["AI"])[0]

    def test_hotlist_date_is_not_a_news_publication_date(self):
        self.assertIsNone(self.candidate("hotlist_observation")["published_at"])

    def test_question_creation_is_separate_from_news_date(self):
        item = self.candidate("question_created")
        self.assertIsNone(item["published_at"])
        self.assertEqual(item["question_created_at"], "2026-10-20T08:00:00+08:00")

    def test_wechat_generator_date_must_be_verified(self):
        item = self.candidate("article_date_unverified")
        self.assertIsNone(item["published_at"])
        self.assertIsNotNone(item["unverified_feed_date"])

    def test_real_video_timestamp_preserved_and_missing_stays_missing(self):
        self.assertEqual(self.candidate("video_published")["published_at"], "2026-10-20T08:00:00+08:00")
        self.assertIsNone(self.candidate("video_published", XML.replace(
            b"<pubDate>Tue, 20 Oct 2026 08:00:00 +0800</pubDate>", b""))["published_at"])

    def test_script_and_style_content_do_not_enter_candidates(self):
        self.assertEqual(plain("<p>Hello</p><script>bad()</script><style>hide{}</style><p>AI</p>"), "Hello AI")


if __name__ == "__main__":
    unittest.main()
