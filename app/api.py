"""JSON API. Те же модели и хранилище, что и у HTML-интерфейса."""

from fastapi import APIRouter, Response, status

from app.models import Ticket, TicketCreate, TicketId, TicketStatusUpdate
from app.repository import TicketRepository


def create_api_router(repository: TicketRepository) -> APIRouter:
    router = APIRouter(prefix="/api/tickets", tags=["Заявки"])

    @router.get("", summary="Список заявок")
    def list_tickets() -> list[Ticket]:
        return repository.list_all()

    @router.post("", status_code=status.HTTP_201_CREATED, summary="Создать заявку")
    def create_ticket(data: TicketCreate, response: Response) -> Ticket:
        ticket = repository.create(data)
        response.headers["Location"] = f"/api/tickets/{ticket.id}"
        return ticket

    @router.get(
        "/{ticket_id}", summary="Получить заявку", responses={404: {"description": "Не найдена"}}
    )
    def get_ticket(ticket_id: TicketId) -> Ticket:
        return repository.get(ticket_id)

    @router.patch(
        "/{ticket_id}/status",
        summary="Изменить статус",
        responses={404: {"description": "Не найдена"}},
    )
    def update_status(ticket_id: TicketId, data: TicketStatusUpdate) -> Ticket:
        return repository.update_status(ticket_id, data.status)

    return router
