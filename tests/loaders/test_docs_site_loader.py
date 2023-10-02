"""
<!DOCTYPE html>
<html>
<head>
    <title>My Page</title>
    <style>
        /* Style for the body */
        body {
            background-color: #f2f2f2;
            font-family: Arial, sans-serif;
        }

        /* Style for the header */
        header {
            background-color: #333;
            color: #fff;
            padding: 10px;
            text-align: center;
        }

        /* Style for the main content */
        main {
            margin: 20px;
            padding: 20px;
            background-color: #fff;
            box-shadow: 0px 0px 10px #ccc;
        }

        /* Style for the footer */
        footer {
            background-color: #333;
            color: #fff;
            padding: 10px;
            text-align: center;
        }
    </style>
</head>
<body>
    <header>
        <h1>My Page</h1>
    </header>
    <main>
        <article class="bd-article">
            <h2>Article Title</h2>
            <p>Article content goes here.</p>
        </article>
        <article role="main">
            <h2>Main Article Title</h2>
            <p>Main article content goes here.</p>
        </article>
        <div class="md-content">
            <h2>Markdown Content</h2>
            <p>Markdown content goes here.</p>
        </div>
        <div role="main">
            <h2>Main Content</h2>
            <p>Main content goes here.</p>
        </div>
        <div class="container">
            <h2>Container</h2>
            <p>Container content goes here.</p>
        </div>
        <div class="section">
            <h2>Section</h2>
            <p>Section content goes here.</p>
        </div>
        <article>
            <h2>Generic Article</h2>
            <p>Generic article content goes here.</p>
        </article>
        <main>
            <h2>Main Content</h2>
            <p>Main content goes here.</p>
        </main>
    </main>
    <footer>
        <p>Copyright © 2021 My Page</p>
    </footer>
</body>
</html>
"""

from pprint import pprint

import pytest
import responses


def test_load_data(loader, mocked_responses):
    child_url = "https://docs.embedchain.ai/quickstart"
    html_body = """
<!DOCTYPE html>
<html lang="en">
<body>
    <header>
        <h1>Quick Start</h1>
    </header>
    <main>
    <li><a href="/">..</a></li>
    <li><a href="/quickstart">.</a></li>
    <nav>This is a navigation bar.</nav>
    <aside>This is an aside.</aside>
    <form>This is a form.</form>
    <header>This is a header.</header>
    <noscript>This is a noscript.</noscript>
    <svg>This is an SVG.</svg>
    <canvas>This is a canvas.</canvas>
    <footer>This is a footer.</footer>
    <script>This is a script.</script>
    <style>This is a style.</style>
    </main>
    <footer>
        <p>Copyright © 2023 Quick Start</p>
    </footer>
</body>
</html>
"""
    mocked_responses.get(child_url, body=html_body, status=200, content_type="text/html")

    child_url = "https://docs.embedchain.ai/introduction"
    html_body = """
<!DOCTYPE html>
<html lang="en">
<body>
    <header>
        <h1>Introduction</h1>
    </header>
    <main>
        <li><a href="/">..</a></li>
        <li><a href="/introduction">.</a></li>
        <article class="bd-article">
            <h2>Article Title</h2>
            <p>Article content goes here.</p>
        </article>
        <article role="main">
            <h2>Main Article Title</h2>
            <p>Main article content goes here.</p>
        </article>
        <div class="md-content">
            <h2>Markdown Content</h2>
            <p>Markdown content goes here.</p>
        </div>
        <div role="main">
            <h2>Main Content</h2>
            <p>Main content goes here.</p>
        </div>
        <div class="container">
            <h2>Container</h2>
            <p>Container content goes here.</p>
        </div>
        <div class="section">
            <h2>Section</h2>
            <p>Section content goes here.</p>
        </div>
        <article>
            <h2>Generic Article</h2>
            <p>Generic article content goes here.</p>
        </article>
        <main>
            <h2>Main Content</h2>
            <p>Main content goes here.</p>
        </main>
    </main>
    <footer>
        <p>Copyright © 2023 Introduction</p>
    </footer>
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

    result = loader.load_data(url)
    pprint(result)
    assert result == {"doc_id": "", "data": []}


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
    assert result == {
        "doc_id": doc_id,
        "data": [
            {"content": "..\n.", "meta_data": {"url": "https://docs.embedchain.ai/quickstart"}},
            {"content": "..\n.", "meta_data": {"url": "https://docs.embedchain.ai/introduction"}},
        ],
    }


@pytest.fixture
def loader():
    from embedchain.loaders.docs_site_loader import DocsSiteLoader

    return DocsSiteLoader()


@pytest.fixture
def mocked_responses():
    with responses.RequestsMock() as rsps:
        yield rsps
