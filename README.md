# Gateway Service

Gateway Service принимает входящие запросы и проксирует их в микросервисы проекта `trip-constructor`.

Его основная задача - единая точка входа для API, проверка JWT и перенос контекста пользователя в downstream-сервисы.

## Что делает gateway

- проксирует запросы в `auth`, `plans`, `locations`, `users`, `activities`, `routes`, `departure`, `pricing`, `pdf` и `bot` сервисы;
- проверяет access token до проксирования;
- сохраняет данные пользователя в `request.state.user`;
- добавляет `X-User-ID` в исходящий запрос к микросервису;
- отдаёт публичные маршруты без аутентификации;
- ограничивает частоту запросов.

## Как передаётся пользовательский контекст

После успешной проверки JWT middleware кладёт decoded payload в `request.state.user`.

Дальше proxy слой:

- читает `request.state.user`;
- достаёт идентификатор пользователя из `user_id`, `sub` или `id`;
- добавляет его в заголовок `X-User-ID`.

Если downstream-сервису нужен весь контекст пользователя, gateway также добавляет `X-User-Claims` (base64url(JSON payload)).
Downstream-сервис может восстановить `request.state.user` из этого заголовка в своём middleware или dependency.

Подробное описание находится в отдельном документе:

- [`docs/request-context.md`](docs/request-context.md)

## Маршрутизация

Gateway проксирует запросы по префиксу пути:

- `/auth/*` -> `auth-service`
- `/plans/*` -> `plans-service`
- `/locations/*` -> `locations-service`
- `/users/*` -> `users-service`
- `/activities/*` -> `activities-service`
- `/routes/*` -> `routes-service`
- `/departure/*` -> `departure-service`
- `/pricing/*` -> `pricing-service`
- `/pdf/*` -> `pdf-service`
- `/bot/*` -> `bot-service`

## Конфигурация

Основные настройки задаются через `.env`:

- `REDIS_URL`
- `REDIS_TTL`
- `RATE_LIMIT`
- `PROXY_TIMEOUT`
- `CACHE_ENABLED`
- `RESPONSE_CACHE_TTL`
- `CACHEABLE_PATHS`
- `PUBLIC_PATHS`
- `SERVICE_MAP`

`PUBLIC_PATHS`, `CACHEABLE_PATHS` и `SERVICE_MAP` должны быть валидными JSON-строками.

Response cache применяется только для публичных `GET`/`HEAD` запросов без cookies,
`Authorization`, `X-User-ID` и `X-User-Claims`, и только для путей из `CACHEABLE_PATHS`.
По умолчанию кешируются публичные справочные маршруты `/api/locations` и
`/api/references`.

## Запуск

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload
```

## Документация

- [`docs/request-context.md`](docs/request-context.md) - передача данных пользователя через `X-User-ID` / `X-User-Claims`;
- [`app/middleware/auth.py`](app/middleware/auth.py) - JWT middleware;
- [`app/services/proxy.py`](app/services/proxy.py) - проксирование и заголовки контекста пользователя.
