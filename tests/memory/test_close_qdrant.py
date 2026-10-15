from unittest.mock import Mock

from mem0.memory.main import Memory, _close_owned_vector_store


def _memStub(db=None, vector_store=None):
    m = Memory.__new__(Memory)
    m.db = db
    m.vector_store = vector_store
    return m


def test_close_closes_owned_local_client():
    client = Mock()
    vs = Mock()
    vs.is_local = True
    vs.client = client
    _memStub(db=None, vector_store=vs).close()
    client.close.assert_called_once_with()


def test_close_leaves_caller_supplied_client_open():
    client = Mock()
    vs = Mock()
    vs.is_local = False
    vs.client = client
    _memStub(db=None, vector_store=vs).close()
    client.close.assert_not_called()


def test_close_repeated_is_safe():
    client = Mock()
    vs = Mock()
    vs.is_local = True
    vs.client = client
    m = _memStub(db=None, vector_store=vs)
    m.close()
    m.close()
    assert client.close.call_count == 2  # Mock never raises; real clients guarded by try/except


def test_close_without_vector_store_ok():
    _memStub(db=None, vector_store=None).close()
    m = Memory.__new__(Memory)
    m.db = Mock()
    # no vector_store attribute at all
    if hasattr(m, "vector_store"):
        delattr(m, "vector_store")
    m.close()
    m.db.close.assert_called_once_with()


def test_close_error_suppressed():
    client = Mock()
    client.close.side_effect = RuntimeError("already closed")
    vs = Mock()
    vs.is_local = True
    vs.client = client
    _memStub(db=None, vector_store=vs).close()  # must not raise


def test_helper_no_close_method_ok():
    vs = Mock(spec=[])
    _close_owned_vector_store(vs)  # must not raise
