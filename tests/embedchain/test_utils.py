import tempfile
import unittest
from unittest.mock import patch

from embedchain.models.data_type import DataType
from embedchain.utils.misc import detect_datatype


class TestApp(unittest.TestCase):
    """Test that the datatype detection is working, based on the input."""

    def test_detect_datatype_youtube(self):
        self.assertEqual(detect_datatype("https://www.youtube.com/watch?v=dQw4w9WgXcQ"), DataType.YOUTUBE_VIDEO)
        self.assertEqual(detect_datatype("https://m.youtube.com/watch?v=dQw4w9WgXcQ"), DataType.YOUTUBE_VIDEO)
        self.assertEqual(
            detect_datatype("https://www.youtube-nocookie.com/watch?v=dQw4w9WgXcQ"), DataType.YOUTUBE_VIDEO
        )
        self.assertEqual(detect_datatype("https://vid.plus/watch?v=dQw4w9WgXcQ"), DataType.YOUTUBE_VIDEO)
        self.assertEqual(detect_datatype("https://youtu.be/dQw4w9WgXcQ"), DataType.YOUTUBE_VIDEO)

    def test_detect_datatype_local_file(self):
        self.assertEqual(detect_datatype("file:///home/user/file.txt"), DataType.WEB_PAGE)

    def test_detect_datatype_pdf(self):
        self.assertEqual(detect_datatype("https://www.example.com/document.pdf"), DataType.PDF_FILE)

    def test_detect_datatype_local_pdf(self):
        self.assertEqual(detect_datatype("file:///home/user/document.pdf"), DataType.PDF_FILE)

    def test_detect_datatype_xml(self):
        self.assertEqual(detect_datatype("https://www.example.com/sitemap.xml"), DataType.SITEMAP)

    def test_detect_datatype_local_xml(self):
        self.assertEqual(detect_datatype("file:///home/user/sitemap.xml"), DataType.SITEMAP)

    def test_detect_datatype_docx(self):
        self.assertEqual(detect_datatype("https://www.example.com/document.docx"), DataType.DOCX)

    def test_detect_datatype_local_docx(self):
        self.assertEqual(detect_datatype("file:///home/user/document.docx"), DataType.DOCX)

    def test_detect_data_type_json(self):
        self.assertEqual(detect_datatype("https://www.example.com/data.json"), DataType.JSON)

    def test_detect_data_type_local_json(self):
        self.assertEqual(detect_datatype("file:///home/user/data.json"), DataType.JSON)

    @patch("os.path.isfile")
    def test_detect_datatype_regular_filesystem_docx(self, mock_isfile):
        with tempfile.NamedTemporaryFile(suffix=".docx", delete=True) as tmp:
            mock_isfile.return_value = True
            self.assertEqual(detect_datatype(tmp.name), DataType.DOCX)

    def test_detect_datatype_docs_site(self):
        self.assertEqual(detect_datatype("https://docs.example.com"), DataType.DOCS_SITE)

    def test_detect_datatype_docs_sitein_path(self):
        self.assertEqual(detect_datatype("https://www.example.com/docs/index.html"), DataType.DOCS_SITE)
        self.assertNotEqual(detect_datatype("file:///var/www/docs/index.html"), DataType.DOCS_SITE)  # NOT equal

    def test_detect_datatype_web_page(self):
        self.assertEqual(detect_datatype("https://nav.al/agi"), DataType.WEB_PAGE)

    def test_detect_datatype_invalid_url(self):
        self.assertEqual(detect_datatype("not a url"), DataType.TEXT)

    def test_detect_datatype_qna_pair(self):
        self.assertEqual(
            detect_datatype(("Question?", "Answer. Content of the string is irrelevant.")), DataType.QNA_PAIR
        )  #

    def test_detect_datatype_qna_pair_types(self):
        """Test that a QnA pair needs to be a tuple of length two, and both items have to be strings."""
        with self.assertRaises(TypeError):
            self.assertNotEqual(
                detect_datatype(("How many planets are in our solar system?", 8)), DataType.QNA_PAIR
            )  # NOT equal

    def test_detect_datatype_text(self):
        self.assertEqual(detect_datatype("Just some text."), DataType.TEXT)

    def test_detect_datatype_non_string_error(self):
        """Test type error if the value passed is not a string, and not a valid non-string data_type"""
        with self.assertRaises(TypeError):
            detect_datatype(["foo", "bar"])

    @patch("os.path.isfile")
    def test_detect_datatype_regular_filesystem_file_txt(self, mock_isfile):
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=True) as tmp:
            mock_isfile.return_value = True
            self.assertEqual(detect_datatype(tmp.name), DataType.TEXT_FILE)

    def test_detect_datatype_regular_filesystem_no_file(self):
        """Test that if a filepath is not actually an existing file, it is not handled as a file path."""
        self.assertEqual(detect_datatype("/var/not-an-existing-file.txt"), DataType.TEXT)

    def test_doc_examples_quickstart(self):
        """Test examples used in the documentation."""
        self.assertEqual(detect_datatype("https://en.wikipedia.org/wiki/Elon_Musk"), DataType.WEB_PAGE)
        self.assertEqual(detect_datatype("https://www.tesla.com/elon-musk"), DataType.WEB_PAGE)

    def test_doc_examples_introduction(self):
        """Test examples used in the documentation."""
        self.assertEqual(detect_datatype("https://www.youtube.com/watch?v=3qHkcs3kG44"), DataType.YOUTUBE_VIDEO)
        self.assertEqual(
            detect_datatype(
                "https://navalmanack.s3.amazonaws.com/Eric-Jorgenson_The-Almanack-of-Naval-Ravikant_Final.pdf"
            ),
            DataType.PDF_FILE,
        )
        self.assertEqual(detect_datatype("https://nav.al/feedback"), DataType.WEB_PAGE)

    def test_doc_examples_app_types(self):
        """Test examples used in the documentation."""
        self.assertEqual(detect_datatype("https://www.youtube.com/watch?v=Ff4fRgnuFgQ"), DataType.YOUTUBE_VIDEO)
        self.assertEqual(detect_datatype("https://en.wikipedia.org/wiki/Mark_Zuckerberg"), DataType.WEB_PAGE)

    def test_doc_examples_configuration(self):
        """Test examples used in the documentation."""
        import subprocess
        import sys

        subprocess.check_call([sys.executable, "-m", "pip", "install", "wikipedia"])
        import wikipedia

        page = wikipedia.page("Albert Einstein")
        # TODO: Add a wikipedia type, so wikipedia is a dependency and we don't need this slow test.
        # (timings: import: 1.4s, fetch wiki: 0.7s)
        self.assertEqual(detect_datatype(page.content), DataType.TEXT)


if __name__ == "__main__":
    unittest.main()
