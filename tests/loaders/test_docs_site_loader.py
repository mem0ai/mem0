import pytest
import responses
from bs4 import BeautifulSoup


@pytest.mark.parametrize(
    "ignored_tag",
    [
        "<nav>This is a navigation bar.</nav>",
        "<aside>This is an aside.</aside>",
        "<form>This is a form.</form>",
        "<header>This is a header.</header>",
        "<noscript>This is a noscript.</noscript>",
        "<svg>This is an SVG.</svg>",
        "<canvas>This is a canvas.</canvas>",
        "<footer>This is a footer.</footer>",
        "<script>This is a script.</script>",
        "<style>This is a style.</style>",
    ],
    ids=["nav", "aside", "form", "header", "noscript", "svg", "canvas", "footer", "script", "style"],
)
@pytest.mark.parametrize(
    "selectee",
    [
        """
<article class="bd-article">
    <h2>Article Title</h2>
    <p>Article content goes here.</p>
</article>
""",
        """
<article role="main">
    <h2>Main Article Title</h2>
    <p>Main article content goes here.</p>
</article>
""",
        """
<div class="md-content">
    <h2>Markdown Content</h2>
    <p>Markdown content goes here.</p>
</div>
""",
        """
<div role="main">
    <h2>Main Content</h2>
    <p>Main content goes here.</p>
</div>
""",
        """
<div class="container">
    <h2>Container</h2>
    <p>Container content goes here.</p>
</div>
        """,
        """
<div class="section">
    <h2>Section</h2>
    <p>Section content goes here.</p>
</div>
        """,
        """
<article>
    <h2>Generic Article</h2>
    <p>Generic article content goes here.</p>
</article>
        """,
        """
<main>
    <h2>Main Content</h2>
    <p>Main content goes here.</p>
</main>
""",
    ],
    ids=[
        "article.bd-article",
        'article[role="main"]',
        "div.md-content",
        'div[role="main"]',
        "div.container",
        "div.section",
        "article",
        "main",
    ],
)
def test_load_data_gets_by_selectors_and_ignored_tags(selectee, ignored_tag, loader, mocked_responses, mocker):
    child_url = "https://docs.embedchain.ai/quickstart"
    html_body = """
<!DOCTYPE html>
<html lang="en">
<body>
    {ignored_tag}
    {selectee}
</body>
</html>
"""
    html_body = html_body.format(selectee=selectee, ignored_tag=ignored_tag)
    mocked_responses.get(child_url, body=html_body, status=200, content_type="text/html")

    url = "https://docs.embedchain.ai/"
    html_body = """
<!DOCTYPE html>
<html lang="en">
<body>
    <li><a href="/quickstart">Quickstart</a></li>
</body>
</html>
"""
    mocked_responses.get(url, body=html_body, status=200, content_type="text/html")

    mock_sha256 = mocker.patch("embedchain.loaders.docs_site_loader.hashlib.sha256")
    doc_id = "mocked_hash"
    mock_sha256.return_value.hexdigest.return_value = doc_id

    result = loader.load_data(url)
    selector_soup = BeautifulSoup(selectee, "html.parser")
    soup = BeautifulSoup(selector_soup.get_text(), "html.parser")
    expected_content = next(soup.stripped_strings).replace("\n", " ")
    assert result["doc_id"] == doc_id
    assert result["data"] == [
        {
            "content": expected_content,
            "meta_data": {"url": "https://docs.embedchain.ai/quickstart"},
        }
    ]


def test_load_data_gets_child_links_recursively(loader, mocked_responses, mocker):
    child_url = "https://docs.embedchain.ai/quickstart"
    html_body = """
<!DOCTYPE html>
<html lang="en">
<body>
    <li><a href="/">..</a></li>
    <li><a href="/quickstart">.</a></li>
</body>
</html>
"""
    mocked_responses.get(child_url, body=html_body, status=200, content_type="text/html")

    child_url = "https://docs.embedchain.ai/introduction"
    html_body = """
<!DOCTYPE html>
<html lang="en">
<body>
    <li><a href="/">..</a></li>
    <li><a href="/introduction">.</a></li>
</body>
</html>
"""
    mocked_responses.get(child_url, body=html_body, status=200, content_type="text/html")

    url = "https://docs.embedchain.ai/"
    html_body = """
<!DOCTYPE html>
<html lang="en">
<body>
    <li><a href="/quickstart">Quickstart</a></li>
    <li><a href="/introduction">Introduction</a></li>
</body>
</html>
"""
    mocked_responses.get(url, body=html_body, status=200, content_type="text/html")

    mock_sha256 = mocker.patch("embedchain.loaders.docs_site_loader.hashlib.sha256")
    doc_id = "mocked_hash"
    mock_sha256.return_value.hexdigest.return_value = doc_id

    result = loader.load_data(url)
    assert result["doc_id"] == doc_id
    expected_data = [
        {"content": "..\n.", "meta_data": {"url": "https://docs.embedchain.ai/quickstart"}},
        {"content": "..\n.", "meta_data": {"url": "https://docs.embedchain.ai/introduction"}},
    ]
    assert all(item in expected_data for item in result["data"])


# TODO: Add tests for failure cases.


@pytest.fixture
def loader():
    from embedchain.loaders.docs_site_loader import DocsSiteLoader

    return DocsSiteLoader()


@pytest.fixture
def mocked_responses():
    with responses.RequestsMock() as rsps:
        yield rsps
