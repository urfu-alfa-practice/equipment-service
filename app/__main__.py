"""Запуск: python -m app [--demo] [--port 8000]."""

import argparse

import uvicorn

from app.main import create_app


def main() -> None:
    parser = argparse.ArgumentParser(description="Заявки на обслуживание оборудования")
    parser.add_argument("--demo", action="store_true", help="добавить примеры в пустую базу")
    parser.add_argument("--port", type=int, default=8000, help="порт сервера (по умолчанию 8000)")
    args = parser.parse_args()
    uvicorn.run(create_app(demo=args.demo), host="127.0.0.1", port=args.port)


if __name__ == "__main__":
    main()
