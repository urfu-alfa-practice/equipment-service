from datetime import UTC, datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import create_app


def test_complete_ticket_lifecycle(client: TestClient, ticket_data: dict[str, str]) -> None:
    assert client.get("/api/tickets").json() == []
    before = datetime.now(UTC)
    response = client.post("/api/tickets", json=ticket_data)
    assert response.status_code == 201
    ticket = response.json()
    assert ticket.items() >= ticket_data.items()
    assert ticket["status"] == "new"
    created_at = datetime.fromisoformat(ticket["created_at"])
    assert created_at.tzinfo is not None
    assert before <= created_at <= datetime.now(UTC)
    location = response.headers["location"]
    assert client.get(location).json() == ticket

    # Включая повторное сохранение и возврат закрытой заявки в работу.
    for new_status in ("in_progress", "in_progress", "closed", "in_progress"):
        response = client.patch(f"{location}/status", json={"status": new_status})
        assert response.status_code == 200
        updated = response.json()
        assert updated == {**ticket, "status": new_status}
        assert client.get(location).json() == updated
    assert client.get("/api/tickets").json() == [updated]


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"equipment": "Прибор"},
        {"equipment": "", "description": "Проблема"},
        {"equipment": " \t\n", "description": "Проблема"},
        {"equipment": "Прибор", "description": " \n "},
        {"equipment": "x" * 121, "description": "Проблема"},
        {"equipment": "Прибор", "description": "x" * 2001},
        {"equipment": 123, "description": "Проблема"},
        {"equipment": "Прибор", "description": "Проблема", "status": "closed"},
        {"equipment": "Прибор", "description": "Проблема", "id": 42},
    ],
)
def test_invalid_ticket_is_not_saved(client: TestClient, payload: dict) -> None:
    response = client.post("/api/tickets", json=payload)
    assert response.status_code == 422
    assert "detail" in response.json()
    assert client.get("/api/tickets").json() == []


def test_text_boundaries_and_whitespace(client: TestClient) -> None:
    response = client.post("/api/tickets", json={"equipment": "x" * 120, "description": "я" * 2000})
    assert response.status_code == 201
    response = client.post(
        "/api/tickets", json={"equipment": "  Прибор \n", "description": "  Строка 1\nСтрока 2  "}
    )
    assert response.json()["equipment"] == "Прибор"
    assert response.json()["description"] == "Строка 1\nСтрока 2"


@pytest.mark.parametrize("payload", [{"status": "unknown"}, {}, {"status": "closed", "id": 7}])
def test_invalid_status_does_not_change_ticket(
    client: TestClient, ticket_data: dict[str, str], payload: dict
) -> None:
    ticket = client.post("/api/tickets", json=ticket_data).json()
    url = f"/api/tickets/{ticket['id']}"
    assert client.patch(f"{url}/status", json=payload).status_code == 422
    assert client.get(url).json() == ticket


def test_missing_ticket(client: TestClient) -> None:
    assert client.get("/api/tickets/999").status_code == 404
    response = client.patch("/api/tickets/999/status", json={"status": "closed"})
    assert response.status_code == 404
    assert response.json() == {"detail": "Заявка не найдена"}


def test_database_survives_app_restart(tmp_path: Path, ticket_data: dict[str, str]) -> None:
    path = tmp_path / "nested" / "tickets.sqlite3"
    with TestClient(create_app(path), base_url="http://127.0.0.1") as first:
        ticket = first.post("/api/tickets", json=ticket_data).json()
        url = f"/api/tickets/{ticket['id']}/status"
        saved = first.patch(url, json={"status": "closed"}).json()
    with TestClient(create_app(path), base_url="http://127.0.0.1") as second:
        assert second.get("/api/tickets").json() == [saved]


def test_sql_like_text_is_stored_as_text(client: TestClient) -> None:
    equipment = "'); DROP TABLE tickets; --"
    response = client.post(
        "/api/tickets", json={"equipment": equipment, "description": "Проверка текста"}
    )
    assert response.status_code == 201
    assert client.get("/api/tickets").json()[0]["equipment"] == equipment


def test_api_schema_is_available(client: TestClient) -> None:
    assert client.get("/docs").status_code == 200
    schema = client.get("/openapi.json").json()
    assert "/api/tickets" in schema["paths"]
    assert "/tickets" not in schema["paths"]


@pytest.mark.parametrize("ticket_id", ["not-a-number", "0", "-1", str(2**63)])
def test_invalid_ticket_number_is_rejected(client: TestClient, ticket_id: str) -> None:
    assert client.get(f"/api/tickets/{ticket_id}").status_code == 422
    response = client.patch(f"/api/tickets/{ticket_id}/status", json={"status": "closed"})
    assert response.status_code == 422
