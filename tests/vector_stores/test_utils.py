from types import SimpleNamespace

import pytest

from mem0.vector_stores.utils import normalize_list_result


def test_normalize_list_result_supported_shapes():
    rows = [SimpleNamespace(id="one"), SimpleNamespace(id="two")]

    assert normalize_list_result(None) == []
    assert normalize_list_result([]) == []
    assert normalize_list_result(()) == []
    assert normalize_list_result(rows) == rows
    assert normalize_list_result([rows]) == rows
    assert normalize_list_result((rows, None)) == rows
    assert normalize_list_result((tuple(rows), "next")) == rows


@pytest.mark.parametrize("result", [{}, "rows", 1, (SimpleNamespace(id="one"), None), ([1], None, "extra")])
def test_normalize_list_result_rejects_malformed_shapes(result):
    with pytest.raises(TypeError, match="vector-store list result"):
        normalize_list_result(result)
