import tempfile
import unittest
from unittest.mock import patch

from embedchain.utils import detect_datatype


class TestApp(unittest.TestCase):
    """Test that the datatype detection is working, based on the input."""

    def test_detect_datatype_youtube(self):
        self.assertEqual(detect_datatype("https://www.youtube.com/watch?v=dQw4w9WgXcQ"), "youtube_video")
        self.assertEqual(detect_datatype("https://m.youtube.com/watch?v=dQw4w9WgXcQ"), "youtube_video")
        self.assertEqual(detect_datatype("https://www.youtube-nocookie.com/watch?v=dQw4w9WgXcQ"), "youtube_video")
        self.assertEqual(detect_datatype("https://vid.plus/watch?v=dQw4w9WgXcQ"), "youtube_video")
        self.assertEqual(detect_datatype("https://youtu.be/dQw4w9WgXcQ"), "youtube_video")

    def test_detect_datatype_local_file(self):
        self.assertEqual(detect_datatype("file:///home/user/file.txt"), "web_page")

    def test_detect_datatype_pdf(self):
        self.assertEqual(detect_datatype("https://www.example.com/document.pdf"), "pdf_file")

    def test_detect_datatype_local_pdf(self):
        self.assertEqual(detect_datatype("file:///home/user/document.pdf"), "pdf_file")

    def test_detect_datatype_xml(self):
        self.assertEqual(detect_datatype("https://www.example.com/sitemap.xml"), "sitemap")

    def test_detect_datatype_local_xml(self):
        self.assertEqual(detect_datatype("file:///home/user/sitemap.xml"), "sitemap")

    def test_detect_datatype_docx(self):
        self.assertEqual(detect_datatype("https://www.example.com/document.docx"), "docx")

    def test_detect_datatype_local_docx(self):
        self.assertEqual(detect_datatype("file:///home/user/document.docx"), "docx")

    @patch("os.path.isfile")
    def test_detect_datatype_regular_filesystem_docx(self, mock_isfile):
        with tempfile.NamedTemporaryFile(suffix=".docx", delete=True) as tmp:
            mock_isfile.return_value = True
            self.assertEqual(detect_datatype(tmp.name), "docx")

    def test_detect_datatype_docs_site(self):
        self.assertEqual(detect_datatype("https://docs.example.com"), "docs_site")

    def test_detect_datatype_docs_sitein_path(self):
        self.assertEqual(detect_datatype("https://www.example.com/docs/index.html"), "docs_site")
        self.assertNotEqual(detect_datatype("file:///var/www/docs/index.html"), "docs_site")  # NOT equal

    def test_detect_datatype_web_page(self):
        self.assertEqual(detect_datatype("https://www.example.com"), "web_page")

    def test_detect_datatype_invalid_url(self):
        self.assertEqual(detect_datatype("not a url"), "text")

    def test_detect_datatype_qna_pair(self):
        self.assertEqual(detect_datatype(("Question?", "Answer.")), "qna_pair")

    def test_detect_datatype_text(self):
        self.assertEqual(detect_datatype("Just some text."), "text")

    @patch("os.path.isfile")
    def test_detect_datatype_regular_filesystem_file_not_detected(self, mock_isfile):
        """Test error if a valid file is referenced, but it isn't a valid data_type"""
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=True) as tmp:
            mock_isfile.return_value = True
            with self.assertRaises(ValueError):
                detect_datatype(tmp.name)

    def test_detect_datatype_regular_filesystem_no_file(self):
        """Test that if a filepath is not actually an existing file, it is not handled as a file path."""
        self.assertEqual(detect_datatype("/var/not-an-existing-file.txt"), "text")


if __name__ == "__main__":
    unittest.main()
