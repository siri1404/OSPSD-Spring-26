import pytest
from cloud_storage_client_api.di import get_client

def test_get_client_raises_when_not_injected() -> None:
    with pytest.raises(RuntimeError):
        get_client()
