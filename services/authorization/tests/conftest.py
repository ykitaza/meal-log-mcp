import pytest


@pytest.fixture
def anyio_backend():
    """@pytest.mark.anyio の非同期テストを asyncio で動かす。"""
    return "asyncio"
