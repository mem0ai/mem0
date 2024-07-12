import tempfile

import pytest

from embedchain.loaders.xml import XmlLoader

# Taken from https://github.com/langchain-ai/langchain/blob/master/libs/langchain/tests/integration_tests/examples/factbook.xml
SAMPLE_XML = """<?xml version="1.0" encoding="UTF-8"?>
<factbook>
  <country>
    <name>United States</name>
    <capital>Washington, DC</capital>
    <leader>Joe Biden</leader>
    <sport>Baseball</sport>
  </country>
  <country>
    <name>Canada</name>
    <capital>Ottawa</capital>
    <leader>Justin Trudeau</leader>
    <sport>Hockey</sport>
  </country>
  <country>
    <name>France</name>
    <capital>Paris</capital>
    <leader>Emmanuel Macron</leader>
    <sport>Soccer</sport>
  </country>
  <country>
    <name>Trinidad &amp; Tobado</name>
    <capital>Port of Spain</capital>
    <leader>Keith Rowley</leader>
    <sport>Track &amp; Field</sport>
  </country>
</factbook>"""


@pytest.mark.parametrize("xml", [SAMPLE_XML])
def test_load_data(xml: str):
    """
    Test XML loader

    Tests that XML file is loaded, metadata is correct and content is correct
    """
    # Creating temporary XML file
    with tempfile.NamedTemporaryFile(mode="w+") as tmpfile:
        tmpfile.write(xml)

        tmpfile.seek(0)
        filename = tmpfile.name

        # Loading CSV using XmlLoader
        loader = XmlLoader()
        result = loader.load_data(filename)
        data = result["data"]

        # Assertions
        assert len(data) == 1
        assert "United States Washington, DC Joe Biden" in data[0]["content"]
        assert "Canada Ottawa Justin Trudeau" in data[0]["content"]
        assert "France Paris Emmanuel Macron" in data[0]["content"]
        assert "Trinidad & Tobado Port of Spain Keith Rowley" in data[0]["content"]
        assert data[0]["meta_data"]["url"] == filename
