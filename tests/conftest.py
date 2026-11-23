from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import create_app


@pytest.fixture
def client(tmp_path: Path) -> Iterator[TestClient]:
    app = create_app(tmp_path / "tickets.sqlite3")
    with TestClient(app, base_url="http://127.0.0.1") as test_client:
        yield test_client


@pytest.fixture
def ticket_data() -> dict[str, str]:
    return {
        "equipment": "Осциллограф · Э-204",
        "description": "Не отображается сигнал на втором канале.",
    }
