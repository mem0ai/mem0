"""Regression tests for the shared spaCy model loader.

`mem0.utils.spacy_models` promises graceful degradation: when a model cannot be
obtained the getters return ``None`` and latch ``_load_failed_*`` so later calls
do not retry. All three guards are ``except Exception``, which cannot catch the
``SystemExit`` that spaCy's download helper raises when it gives up, so the host
process exits instead of degrading and the latch is never set.
"""

import sys
import types

import pytest

from mem0.utils import spacy_models


def _install_fake_spacy(monkeypatch, *, download_error):
    """Put a minimal `spacy` package in sys.modules whose download() fails.

    Only the external dependency is faked; the code under test
    (`spacy_models._ensure_model_available` and the two getters) runs for real.
    """
    spacy = types.ModuleType("spacy")
    spacy_util = types.ModuleType("spacy.util")
    spacy_cli = types.ModuleType("spacy.cli")

    # Force the download branch: the model is reported as not installed.
    spacy_util.is_package = lambda name: False

    def download(model, *args, **kwargs):
        raise download_error

    spacy_cli.download = download
    spacy.load = lambda *args, **kwargs: object()
    spacy.util = spacy_util
    spacy.cli = spacy_cli

    monkeypatch.setitem(sys.modules, "spacy", spacy)
    monkeypatch.setitem(sys.modules, "spacy.util", spacy_util)
    monkeypatch.setitem(sys.modules, "spacy.cli", spacy_cli)


@pytest.fixture(autouse=True)
def clean_loader_state():
    fields = ("_nlp_full", "_nlp_lemma", "_load_failed_full", "_load_failed_lemma")
    saved = {f: getattr(spacy_models, f) for f in fields}
    for f in fields:
        setattr(spacy_models, f, None if f.startswith("_nlp") else False)
    yield
    for f, v in saved.items():
        setattr(spacy_models, f, v)


def test_download_failure_that_raises_exception_degrades_as_documented(monkeypatch):
    """Control: the already-handled shape must keep working after any change."""
    _install_fake_spacy(monkeypatch, download_error=OSError("no network"))

    assert spacy_models.get_nlp_lemma() is None
    assert spacy_models._load_failed_lemma is True

    assert spacy_models.get_nlp_full() is None
    assert spacy_models._load_failed_full is True


@pytest.mark.parametrize("getter", ["get_nlp_full", "get_nlp_lemma"])
def test_download_termination_does_not_escape_the_loader(monkeypatch, getter):
    """spaCy's download() exits the process on failure; the loader must not die with it."""
    # `wasabi.msg.fail(..., exits=1)` and spaCy's `run_command()` both end in
    # sys.exit(), which is a BaseException and therefore skips `except Exception`.
    _install_fake_spacy(monkeypatch, download_error=SystemExit(1))

    result = getattr(spacy_models, getter)()

    assert result is None
    latch = "_load_failed_full" if getter == "get_nlp_full" else "_load_failed_lemma"
    assert getattr(spacy_models, latch) is True


@pytest.mark.parametrize("getter_name", ["get_nlp_full", "get_nlp_lemma"])
def test_latched_loader_stops_retrying_after_download_termination(monkeypatch, getter_name):
    """A failed download must be remembered, not retried on every add()/search()."""
    calls = []
    spacy = types.ModuleType("spacy")
    spacy_util = types.ModuleType("spacy.util")
    spacy_cli = types.ModuleType("spacy.cli")

    def download(model, *args, **kwargs):
        calls.append(model)
        raise SystemExit(1)

    spacy_util.is_package = lambda name: False
    spacy_cli.download = download
    spacy.load = lambda *args, **kwargs: object()
    spacy.util = spacy_util
    spacy.cli = spacy_cli
    monkeypatch.setitem(sys.modules, "spacy", spacy)
    monkeypatch.setitem(sys.modules, "spacy.util", spacy_util)
    monkeypatch.setitem(sys.modules, "spacy.cli", spacy_cli)

    getter = getattr(spacy_models, getter_name)
    first = getter()
    second = getter()

    assert first is None
    assert second is None
    assert len(calls) == 1
