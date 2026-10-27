import importlib.util
import sys
import unittest
from datetime import UTC, datetime
from pathlib import Path

TESTS = Path(__file__).resolve().parent
PARSER_PATH = TESTS.parent / "custom_components" / "actus_ville" / "parser.py"


def _load_parser():
    # Importing the package would require Home Assistant; the parser only needs the stdlib.
    spec = importlib.util.spec_from_file_location("actus_ville_parser", PARSER_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


parser = _load_parser()

KEYWORDS = ["coupure", "interruption", "panne", "enedis", "électricité", "eau potable"]


class ParseRssTest(unittest.TestCase):
    def setUp(self):
        raw = (TESTS / "fixtures" / "rss_app_exemple.xml").read_bytes()
        self.posts = parser.parse_feed(raw, KEYWORDS)

    def test_sorted_newest_first_undated_last(self):
        self.assertEqual(
            [post.link for post in self.posts],
            [
                "https://www.facebook.com/villedelyon/posts/1004",
                "https://www.facebook.com/villedelyon/posts/1003",
                "https://www.facebook.com/villedelyon/posts/1002",
                None,
            ],
        )

    def test_dates_are_utc(self):
        self.assertEqual(self.posts[0].published, datetime(2026, 10, 26, 16, 5, tzinfo=UTC))
        self.assertIsNone(self.posts[3].published)

    def test_html_becomes_plain_text_with_line_breaks(self):
        self.assertEqual(
            self.posts[0].text,
            "⚠️ COUPURES D'EAU mardi 27 octobre de 8h à 12h\n"
            "Travaux sur le réseau d'eau potable, rue du Commerce.",
        )
        self.assertEqual(
            self.posts[1].text,
            "Fête de la châtaigne ce week-end !\n"
            "Rendez-vous sur la place, programme sur le panneau d'affichage & sur PanneauPocket.",
        )

    def test_images_from_media_then_inline_img(self):
        self.assertEqual(self.posts[0].image, "https://example.org/travaux.jpg")
        self.assertEqual(self.posts[1].image, "https://example.org/chataigne.jpg")
        self.assertIsNone(self.posts[2].image)

    def test_ids_from_guid_or_digest(self):
        self.assertEqual(self.posts[0].id, "post-1004")
        self.assertEqual(len(self.posts[3].id), 16)
        raw = (TESTS / "fixtures" / "rss_app_exemple.xml").read_bytes()
        self.assertEqual(parser.parse_feed(raw)[3].id, self.posts[3].id)

    def test_keywords_flag_important_posts(self):
        self.assertEqual(self.posts[0].keywords, ["coupure", "eau potable"])
        self.assertTrue(self.posts[0].important)
        self.assertEqual(self.posts[1].keywords, [])
        self.assertFalse(self.posts[1].important)
        self.assertEqual(self.posts[2].keywords, ["interruption", "enedis", "électricité"])

    def test_as_dict(self):
        self.assertEqual(
            self.posts[0].as_dict(),
            {
                "id": "post-1004",
                "date": "2026-10-26T16:05:00+00:00",
                "text": self.posts[0].text,
                "link": "https://www.facebook.com/villedelyon/posts/1004",
                "image": "https://example.org/travaux.jpg",
                "important": True,
                "keywords": ["coupure", "eau potable"],
            },
        )


class ParseAtomTest(unittest.TestCase):
    def test_atom_entry(self):
        raw = b"""<?xml version="1.0" encoding="utf-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <title>Exemple</title>
  <entry>
    <id>urn:post:1</id>
    <title>Alerte canicule</title>
    <link rel="alternate" href="https://example.org/1"/>
    <updated>2026-07-01T09:00:00Z</updated>
    <summary type="html">&lt;p&gt;Vigilance orange canicule.&lt;/p&gt;</summary>
  </entry>
</feed>"""
        [post] = parser.parse_feed(raw, ["canicule"])
        self.assertEqual(post.id, "urn:post:1")
        self.assertEqual(post.link, "https://example.org/1")
        self.assertEqual(post.published, datetime(2026, 7, 1, 9, 0, tzinfo=UTC))
        self.assertEqual(post.text, "Vigilance orange canicule.")
        self.assertEqual(post.keywords, ["canicule"])


class FeedErrorTest(unittest.TestCase):
    def test_not_xml(self):
        with self.assertRaises(parser.FeedError):
            parser.parse_feed(b"Service unavailable")

    def test_html_page(self):
        with self.assertRaises(parser.FeedError):
            parser.parse_feed(b"<html><body>Not found</body></html>")


class FindKeywordsTest(unittest.TestCase):
    def test_whole_words_only(self):
        self.assertEqual(parser.find_keywords("Le nouveau bureau", ["eau"]), [])
        self.assertEqual(parser.find_keywords("Panneau d'affichage", ["panne"]), [])
        self.assertEqual(parser.find_keywords("Panne de courant", ["panne"]), ["panne"])

    def test_plural_case_and_accents(self):
        self.assertEqual(parser.find_keywords("Les EAUX montent", ["eau"]), ["eau"])
        self.assertEqual(parser.find_keywords("coupures prévues", ["Coupure"]), ["Coupure"])
        self.assertEqual(parser.find_keywords("ELECTRICITE", ["électricité"]), ["électricité"])

    def test_blank_keywords_ignored(self):
        self.assertEqual(parser.find_keywords("texte", ["", "   "]), [])


class TruncationTest(unittest.TestCase):
    def test_long_text_truncated(self):
        post = parser.Post(
            id="x", title="", text="a" * 1500, link=None, image=None, published=None
        )
        text = post.as_dict()["text"]
        self.assertEqual(len(text), parser.MAX_TEXT_LENGTH + 1)
        self.assertTrue(text.endswith("…"))


if __name__ == "__main__":
    unittest.main()
