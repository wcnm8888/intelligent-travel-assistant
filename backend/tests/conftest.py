"""Global offline-safety boundary for the backend test suite."""

from __future__ import annotations

import os
import socket
from collections.abc import Generator
from ipaddress import ip_address
from typing import Any

import pytest

# This module is loaded before test modules.  Selecting test composition here
# prevents importing the application composition root from consulting the local
# developer dotenv file.
os.environ["APP_ENV"] = "test"

_PROVIDER_ENVIRONMENT = (
    "DEEPSEEK_API_KEY",
    "AMAP_API_KEY",
    "QWEATHER_API_HOST",
    "QWEATHER_PROJECT_ID",
    "QWEATHER_CREDENTIAL_ID",
    "QWEATHER_PRIVATE_KEY_PATH",
)

for _variable in _PROVIDER_ENVIRONMENT:
    os.environ.pop(_variable, None)


@pytest.fixture(autouse=True)
def deny_real_network(monkeypatch: pytest.MonkeyPatch) -> Generator[None]:
    """Allow local test plumbing but fail every non-loopback connection."""

    original_create_connection = socket.create_connection
    original_connect = socket.socket.connect

    def is_loopback(address: object) -> bool:
        if not isinstance(address, tuple) or not address:
            return False
        host = address[0]
        if not isinstance(host, str):
            return False
        if host == "localhost":
            return True
        try:
            return ip_address(host).is_loopback
        except ValueError:
            return False

    def guarded_create_connection(address: Any, *args: Any, **kwargs: Any) -> Any:
        if not is_loopback(address):
            raise AssertionError("real_network_disabled_in_tests")
        return original_create_connection(address, *args, **kwargs)

    def guarded_connect(instance: socket.socket, address: Any) -> Any:
        if not is_loopback(address):
            raise AssertionError("real_network_disabled_in_tests")
        return original_connect(instance, address)

    monkeypatch.setattr(socket, "create_connection", guarded_create_connection)
    monkeypatch.setattr(socket.socket, "connect", guarded_connect)
    yield
