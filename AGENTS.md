# AGENTS.md — telegram-catalog

Тестовое задание: микросервис каталога товаров с Telegram Mini App.
Стек: Next.js (App Router) + TypeScript, FastAPI, aiogram 3, PostgreSQL, MinIO.
Код пишется вручную. Запрещены LLM/AI-вызовы, AI-библиотеки и сгенерированный код.

## Компоненты

- **api** — FastAPI + SQLAlchemy 2 async + Alembic + Pydantic v2; владеет PostgreSQL и MinIO.
- **bot** — aiogram 3 + aiohttp (webhook); только Telegram-логика, ходит в API.
- **web** — Next.js App Router; страница «Каталог» и Telegram Mini App.
- **db / minio** — инфраструктура docker/podman compose.

## Структура

```
api/    — приложение, миграции, тесты
bot/    — webhook-сервер, handlers, клиент API
web/    — src/app, src/components, src/lib
deploy/ — initdb и конфиги инфраструктуры
```

## Правила

1. **Stateless.** Никаких локальных файлов, in-memory сессий и состояния между запросами.
   Данные — PostgreSQL, файлы — MinIO. Сценарии проектируются в рамках одного update
   Telegram; для многошаговых сценариев — FSM storage в PostgreSQL, не в памяти.
   В проде бот работает через webhook; polling — только локальная отладка.
2. HTTP-клиенты и подключения не хранят пользовательские данные; кэши только неизменяемые.
3. Секреты — только в `.env`; `.env` не коммитить, токены не логировать.
4. Ошибки API — `{"detail": "..."}`; коды 400/401/404/413/415/422/500/503.
5. SQL — только через SQLAlchemy, схема — только через Alembic.
6. Валидация файлов — на API (размер, MIME, magic bytes).
7. Идентификаторы — `BIGINT GENERATED ALWAYS AS IDENTITY`; время — `timestamptz`, в API ISO 8601 UTC.
8. Фронтенд — чистая семантика, без UI-фреймворков и сложных стилей.
9. Комментарии и docstring — на русском, только по делу; код и имена — на английском.
10. Репозиторий публичный: не добавлять токены, личные чаты и скриншоты с персональными данными.
11. Не менять CI, деплой и учётные данные без явной просьбы.
12. Не коммитить и не пушить без явной просьбы.
13. После изменений — самопроверка: тесты, ruff, web typecheck/lint/build.

## Команды

Этап 5 (без бота, webhook ещё не настроен):

```bash
podman compose up --build -d db minio-perms minio minio-init migrate api web
podman compose --profile test run --build --rm api-tests
podman compose --profile test run --build --rm bot-tests
podman compose --profile test run --build --rm api-tests ruff check .
podman compose --profile test run --build --rm bot-tests ruff check .
cd web && npm run typecheck && npm run lint && npm run build
```

Полный стек (после настройки `TELEGRAM_WEBHOOK_URL`/`WEBAPP_URL`, этап 6):

```bash
podman compose up --build -d
```

## Проверка stateless

```bash
podman compose up -d --scale api=2 --scale bot=2
```

`TELEGRAM_WEBHOOK_URL` и `TELEGRAM_WEBHOOK_SECRET` обязательны для webhook-режима
(в том числе с одной репликой). Polling нельзя масштабировать.
