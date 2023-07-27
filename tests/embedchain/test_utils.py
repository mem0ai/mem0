import unittest

from embedchain.utils import detect_datatype


class TestApp(unittest.TestCase):
    """Test that the datatype detection is working, based on the input."""

    def test_detect_datatype_youtube(self):
        self.assertEqual(detect_datatype("https://www.youtube.com/watch?v=dQw4w9WgXcQ"), "youtube_video")
        self.assertEqual(detect_datatype("https://m.youtube.com/watch?v=dQw4w9WgXcQ"), "youtube_video")
        self.assertEqual(detect_datatype("https://www.youtube-nocookie.com/watch?v=dQw4w9WgXcQ"), "youtube_video")
        self.assertEqual(detect_datatype("https://vid.plus/watch?v=dQw4w9WgXcQ"), "youtube_video")

    def test_detect_datatype_short_youtube(self):
        self.assertEqual(detect_datatype("https://youtu.be/dQw4w9WgXcQ"), "youtube_video")

    def test_detect_datatype_pdf(self):
        self.assertEqual(detect_datatype("https://www.example.com/document.pdf"), "pdf_file")

    def test_detect_datatype_xml(self):
        self.assertEqual(detect_datatype("https://www.example.com/sitemap.xml"), "sitemap")

    def test_detect_datatype_docx(self):
        self.assertEqual(detect_datatype("https://www.example.com/document.docx"), "docx")

    def test_detect_datatype_docs_site(self):
        self.assertEqual(detect_datatype("https://docs.example.com"), "docs_site")

    def test_detect_datatype_docs_in_path(self):
        self.assertEqual(detect_datatype("https://www.example.com/docs/index.html"), "docs_site")

    def test_detect_datatype_web_page(self):
        self.assertEqual(detect_datatype("https://www.example.com"), "web_page")

    def test_detect_datatype_invalid_url(self):
        self.assertEqual(detect_datatype("not a url"), "text")

    def test_detect_datatype_qna_pair(self):
        self.assertEqual(detect_datatype(("Question?", "Answer.")), "qna_pair")

    def test_detect_datatype_text(self):
        self.assertEqual(detect_datatype("Just some text."), "text")


if __name__ == "__main__":
    unittest.main()
