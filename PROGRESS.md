# PROGRESS — telegram-catalog

Состояние на 2026-10-22. Файл нужен для продолжения работы после перезапуска/новой сессии.
Секреты сюда не записывать (BOT_TOKEN, ADMIN_IDS, пароли, API_INTERNAL_TOKEN).

## Статус этапов

| Этап | Содержание | Статус |
|---|---|---|
| 0 | Каркас репозитория, .env/.env.example, .gitignore, AGENTS.md, README | принят |
| 1 | Ядро API: config, images, storage, model, Alembic 0001 | принят |
| 2 | API endpoints + тесты | принят (APPROVE) |
| 3 | Telegram-бот aiogram 3 + идемпотентность | принят (APPROVE) |
| 4 | Next.js каталог + TMA | принят (APPROVE после исправлений) |
| 5 | Инфраструктура compose, Dockerfiles, миграции, MinIO init | принят (APPROVE) |
| 6 | Публичный HTTPS, webhook, реальная проверка TMA | принят: `/start`, TMA, фото и файл проверены пользователем |
| 7 | Финальное ревью, полный прогон, push в GitHub | в работе: код готов, остались финальный прогон и push |

## Текущее состояние кода

- Репозиторий: `D:\OpenCode\telegram-catalog`, git есть, коммитов нет, remote не настроен.
  Всё untracked: `.gitignore`, `.env.example`, `.gitattributes`, `.dockerignore`, `AGENTS.md`,
  `README.md`, `PROGRESS.md`, `compose.yaml`, `api/`, `bot/`, `web/`, `deploy/`.
  `.env` игнорируется.
- GitHub: публичный `bellk76/telegram-catalog`. Git identity локально: `bellk76` /
  `299753221+bellk76@users.noreply.github.com`. Коммит/push — только этап 7.
- Архитектура: один публичный origin — web. `/api/*` → API, `/telegram/*` → бот.
  API и MinIO наружу не публикуются. Изображения API проксирует из MinIO.
- Этап 6: публичный HTTPS через SSH-туннель localhost.run
  (`ssh -R 80:127.0.0.1:3000 nokey@localhost.run`). Cloudflare quick tunnel
  в этой сети нестабилен (530/520, обрывы control stream); Serveo тоже истекает.
  Бот зарегистрировал webhook, `getWebhookInfo` OK, POST с неверным секретом → 401,
  с верным → 200. Пользователь нажал Start: `/start`, TMA, стили, фотографии
  и добавление товара фото+подпись проверены в Telegram Desktop.
- Telegram DNS `149.154.166.110` недоступен; в compose у bot `extra_hosts`
  `api.telegram.org:149.154.167.220` через `TELEGRAM_API_IP` (default).
  `getMe`, `setWebhook` и `getFile` через этот IP работают.
- Добавлена отправка изображения файлом (JPEG/PNG/WebP): бот скачивает документ
  и передаёт оригинал в API. Проверено: файл 2000×1500 JPEG 437 КБ сохранён
  без сжатия (id=8), изображение отдаётся с `image/jpeg`. Обычное фото Telegram
  по-прежнему приходит сжатым (~1280 px).

### API (`api/`)

- Python 3.12, venv: `api/.venv`. FastAPI + SQLAlchemy 2 async + asyncpg + Alembic + minio.
- Модель `Product`: BIGINT identity, title 200, image_key unique, image_content_type,
  image_size, `idempotency_key` (String(128), unique, nullable), created_at timestamptz.
- Миграции: `0001_products`, `0002_idempotency_key`.
- Endpoints:
  - `GET /health` — 200/503 (БД).
  - `GET /ready` — 200/503 (БД + bucket MinIO), используется healthcheck'ом.
  - `POST /api/products` — multipart `title` + `image`, `X-Internal-Token`,
    опционально `X-Idempotency-Key`; 201/400/401/404/413/415/422/500/503.
  - `GET /api/products?limit&offset` — limit 1..100, offset 0..1_000_000.
  - `GET /api/products/{id}/image` — поток из MinIO.
- Идемпотентность: pre-check; при гонке `IntegrityError` → rollback → проверка
  наличия `Product` по `image_key`; удаление только если БД подтвердила отсутствие.
  При неизвестном состоянии объект сохраняется (orphan безопаснее потери). Replay 201.
- Ошибки БД → 503; прочие SQLAlchemyError → 500 + лог. CORS для GET/POST и заголовков.
- Middleware ограничивает Content-Length для POST. Пул БД настраивается
  `DB_POOL_SIZE`/`DB_MAX_OVERFLOW` (default 5/10).
- Тесты: **37 passed**, ruff чисто (host и контейнер), включая `/ready` (ok/storage/БД),
  безопасную очистку после неоднозначного commit.
  Host: `TEST_DATABASE_URL=...catalog_test` на `localhost:5433`.
- Alembic check на `catalog_migrate`: `No new upgrade operations detected`.

### Бот (`bot/`)

- aiogram 3.31.0, venv `bot/.venv`, aiohttp webhook, httpx-клиент API, pydantic-settings.
- `/start`: «У меня есть товар» + web_app кнопка «Каталог».
- Админ (ADMIN_IDS) отправляет фото + подпись или image-документ (JPEG/PNG/WebP)
  + подпись: ключ `tg:{chat_id}:{message_id}`, обработка 413/415/422/401/403/503;
  для документов MIME проверяется до скачивания, окончательно — на API по magic bytes.
- Webhook: `POST /telegram/webhook`, secret compare_digest, fail-closed при пустом секрете,
  JSON-only, тело <= 64 KiB, `feed_webhook_update` ожидается в обработчике
  (идемпотентность защищает от повторов Telegram).
- Режимы: `webhook` (default) / `polling` только при `ALLOW_POLLING=true`.
- URL: `WEBAPP_URL` — https (локально http://localhost/127.0.0.1);
  `TELEGRAM_WEBHOOK_URL` — строго `https://<host>/telegram/webhook`.
- Тесты: **56 passed**, ruff чисто (host и контейнер). `PYTHONPATH=/app` в test-образе.
  Покрыты фото, image-документы (JPEG/PNG/WebP), неверный MIME, превышение размера
  до скачивания, отсутствие подписи, не-админ и ошибка скачивания.

### Web (`web/`)

- Next.js 15.5.28 + React 19.3.1 + TypeScript, oxlint. Node 22 в образе.
- `src/app/page.tsx`: SSR `force-dynamic`, h1 «Каталог», grid, empty state,
  пагинация по 100 (`?page=`, ссылки Назад/Вперёд), строгий разбор номера страницы.
- `loading.tsx`, `error.tsx` (retry), `RefreshButton`, `lib/api.ts` (fetch no-store, timeout 5 с).
- TMA: `telegram-web-app.js` через `next/script` `afterInteractive`;
  `TelegramBootstrap` ретраит init до 10 с, ставит ready/expand, слушает themeChanged
  и выставляет CSS-переменные; prepaint-скрипт убран.
- `next.config.mjs`: `output: "standalone"`, images unoptimized,
  rewrites `/api/:path*` → `${API_INTERNAL_URL}` и `/telegram/:path*` → `${BOT_INTERNAL_URL}`.
  `API_INTERNAL_URL` — build-time rewrites + runtime SSR; `BOT_INTERNAL_URL` — только
  build-time rewrites. После изменения обоих нужен `--build`.
- `postbuild` = `scripts/prepare-standalone.mjs` (копирует static/public для `npm start`).
- `package.json`: `overrides.postcss=^8.5.31` (закрыт high advisory); `npm audit --omit=dev`
  — 0 vulnerabilities.
- Проверки: typecheck, lint (0/0), build, `npm start` — успешно.

### Инфраструктура (этап 5)

- `compose.yaml` (project `telegram-catalog`): `db`, `minio-perms`, `minio`, `minio-init`,
  `migrate`, `api`, `web`, `bot`, `api-tests`, `bot-tests` (профиль `test`).
- Порты: web `127.0.0.1:3000`; db `127.0.0.1:5433`.
  API, bot и MinIO без host-портов — доступны только в compose-сети.
- `db`: postgres:16-alpine, healthcheck `pg_isready -h 127.0.0.1 -U ... -d ...`
  (+start_period), volume, initdb создаёт `${POSTGRES_DB}_test` и `_migrate`.
- `deploy/initdb/01-databases.sh` — создание тестовой и migrate-БД.
- `minio-perms`: root с `cap_drop: ALL` + `CHOWN/DAC_OVERRIDE`, no-new-privileges,
  `chown -R 100:101 /data`; MinIO работает uid 100/gid 101.
- `minio-init`: ждёт alias/ready, создаёт bucket `product-images`, app user;
  policy пересоздаётся при каждом запуске (detach/remove/create/attach) и проверяется
  через `mc admin user info | grep catalog-policy`; ошибки не маскируются.
- `migrate`: one-shot `alembic upgrade head`; получает только DATABASE_URL,
  alembic читает его напрямую из env (без полного Settings).
- Compose env: для migrate/api/bot явные allowlist-переменные (не `env_file` целиком),
  `${VAR:?}` для обязательных, `CORS_ORIGINS` — JSON-строка.
- Dockerfiles: api/bot python:3.12-slim, non-root, venv; web multi-stage standalone,
  non-root nextjs; отдельные `api/Dockerfile.test`, `bot/Dockerfile.test` (dev deps),
  чтобы `target: test` не перетирал runtime-образы.
- MinIO: официальные `minio/minio`/`minio/mc` недоступны (404/401), используются
  pinned-зеркала `docker.io/alpine/minio:RELEASE.2025-10-15T17-29-55Z` и
  `docker.io/rancher/mirrored-minio-mc:RELEASE.2023-06-28T21-54-17Z`.
- Проверено: `compose config` OK; api×2/web/db/minio healthy; миграции применились;
  MinIO non-root; `api-tests` **37 passed**, `bot-tests` **56 passed**, ruff OK;
  `minio-init` успешно перезапускается (policy пересоздаётся), `/ready` 200;
  товар создан через web (`POST /api/products` → 201, id=2; replay → 201, тот же id);
  image 200 `image/png`; `/` 200 с товаром; 2 строки в БД и 2 объекта в MinIO;
  `/telegram/webhook` проксируется (этап 6: работает через бот и туннель).
- Bot в compose работает: webhook зарегистрирован, healthcheck healthy; ручной `/start`
  и TMA ждут пользователя (см. этап 6).

## Окружение и ограничения

- Windows, PowerShell 5.1. Podman 5.8.3 (WSL machine, 3 CPU, **2 GiB RAM**), `podman compose`
  использует docker-compose.exe 5.5.1. Docker Desktop daemon не запущен.
- Host Python 3.12.10, Node 24.21.0, npm 11.x, gh авторизован как `bellk76`.
- Порт 5432 занят PostgreSQL 17 → БД на **5433**.
- Тестовая БД host: контейнер `catalog-test-db` (postgres:16-alpine), сейчас Exited.
  Не запускать одновременно с compose-БД. Старый `geo-db` не запускать.
- `cloudflared` установлен (2026.10.3), но quick tunnel в этой сети постоянно рвёт
  control stream; Serveo истекает через 10–25 минут. Используется localhost.run
  (SSH-процесс), но и он может умереть через несколько минут. При смене URL обновить
  `.env`, пересоздать bot/api и перезапустить web; входящие update Telegram
  доставит после восстановления webhook.
- `C:\temp\opencode` — временные файлы.
- Podman 2 GiB может не хватить для Next build; при OOM:
  `podman machine set --memory 4096` (перезапуск machine).

## Текущий `.env` (значения секретов не фиксировать)

- `WEBAPP_URL=https://<ephemeral>.lhr.life/` — публичный HTTPS (localhost.run),
  URL временный, в документации не фиксируется.
- `TELEGRAM_WEBHOOK_URL=https://<ephemeral>.lhr.life/telegram/webhook`;
  `BOT_MODE=webhook`, `ALLOW_POLLING=false`; `CORS_ORIGINS` — этот origin.
- `BOT_INTERNAL_URL` в `.env` не задан, compose default `http://bot:8080`.
- `TELEGRAM_API_IP` в `.env` не задан; compose default `149.154.167.220`.
- `TELEGRAM_WEBHOOK_SECRET`, `BOT_TOKEN`, `ADMIN_IDS`, `API_INTERNAL_TOKEN`,
  пароли PostgreSQL/MinIO — только в `.env`; не логировать и не выводить в чат.

## Следующие шаги

1. **Этап 7 — финал (в работе):**
   - API/бот тесты, ruff, web typecheck/lint/build, compose smoke.
   - Финализировать README/PROGRESS; временный tunnel URL не коммитить.
   - git add/commit, remote, push в `https://github.com/bellk76/telegram-catalog`.
2. **Если туннель отвалился:**
   - перезапустить SSH-туннель, обновить URL в `.env`;
   - `podman compose up -d --force-recreate --scale api=2 api bot`, `podman compose restart web`;
   - проверить `getWebhookInfo` и отправить пользователю новую кнопку.
3. Скриншот для README: `docs/screenshots/catalog.png` (локальный web, без туннеля).

## Известные отложенные мелочи

- Идемпотентный replay отвечает 201 (а не 200 + флаг replay); для бота приемлемо.
- Полный GC осиротевших объектов MinIO не реализован; при неизвестном исходе commit
  объект намеренно сохраняется (orphan безопаснее потери изображения).
- Один туннель/один origin: web — точка отказа для webhook; API/бот внутри сети.
- Бесплатные туннели (localhost.run/Serveo/Cloudflare quick) живут минуты и рвутся;
  для продакшена нужен постоянный домен/HTTPS. Telegram повторно доставляет update
  после восстановления webhook.
- Обычное фото Telegram сжимает (~1280 px); оригинал сохраняется только при
  отправке изображения файлом. Лимит API — 5 МБ.
- `TELEGRAM_API_IP` — вынужденный обход блокировки DNS api.telegram.org в этой сети.
