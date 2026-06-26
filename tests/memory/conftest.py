"""
Pre-stub packages that pull in a native gRPC DLL blocked by Windows Application
Control policies, so test collection succeeds on restricted Windows machines.
This conftest is executed by pytest before any module-level imports in test files.
"""

import sys
from unittest.mock import MagicMock

if sys.platform == "win32":
    _stub = MagicMock()

    # Stub qdrant_client and its sub-packages before they are imported.
    # mem0/configs/vector_stores/qdrant.py does `from qdrant_client import QdrantClient`
    # which triggers qdrant_client's __init__ which pulls in grpc (native DLL, blocked).
    _qdrant_packages = [
        "qdrant_client",
        "qdrant_client.async_qdrant_client",
        "qdrant_client.async_qdrant_remote",
        "qdrant_client.connection",
        "qdrant_client.grpc",
        "qdrant_client.grpc.collections_pb2",
        "qdrant_client.grpc.collections_pb2_grpc",
        "qdrant_client.grpc.collections_service_pb2_grpc",
        "qdrant_client.grpc.points_pb2",
        "qdrant_client.grpc.points_pb2_grpc",
        "qdrant_client.grpc.points_service_pb2_grpc",
        "qdrant_client.grpc.snapshots_service_pb2_grpc",
        "qdrant_client.grpc.qdrant_pb2_grpc",
        "qdrant_client.http",
        "qdrant_client.http.api",
        "qdrant_client.http.models",
        "qdrant_client.models",
        "qdrant_client.qdrant_remote",
    ]
    for _name in _qdrant_packages:
        sys.modules.setdefault(_name, _stub)

    # Also stub grpc itself to be safe.
    _grpc_packages = [
        "grpc",
        "grpc._channel",
        "grpc._compression",
        "grpc._cython",
        "grpc._cython.cygrpc",
        "grpc._interceptor",
        "grpc._utilities",
        "grpc.experimental",
        "grpc.aio",
    ]
    for _name in _grpc_packages:
        sys.modules.setdefault(_name, _stub)
