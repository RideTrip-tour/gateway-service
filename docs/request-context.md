# Request Context

Этот документ описывает, как gateway сохраняет данные пользователя и как downstream-сервисы могут их использовать.

## Что делает middleware

Функция `jwt_middleware`:

1. пропускает публичные пути и документацию;
2. читает `access_token` из cookies;
3. валидирует JWT через `validate_jwt`;
4. сохраняет decoded payload в `request.state.user`.

## Где лежат данные пользователя

Основной контракт:

```python
request.state.user
```

Это словарь с данными, которые вернул `validate_jwt`.

## Как достать данные в другом сервисе

Gateway передаёт пользовательский контекст в downstream-сервисы через HTTP-заголовки.

Если нужен только идентификатор пользователя, gateway добавляет:

```http
X-User-ID: <user_id>
```

Если нужен полный payload, gateway добавляет:

```http
X-User-Claims: <base64url(JSON payload)>
```

Downstream-сервис должен восстановить `request.state.user` из `X-User-Claims` (в своём middleware/dependency),
а дальше использовать как обычно:

```python
from fastapi import Request


def get_user(request: Request):
    return getattr(request.state, "user", None)
```

## Откуда берётся `X-User-ID`

Proxy слой пытается взять идентификатор из одного из полей:

- `user_id`
- `sub`
- `id`

Если идентификатор найден, он добавляется в `X-User-ID`.

## Когда это полезно

- микросервису нужно знать, кто сделал запрос;
- сервис не хочет самостоятельно разбирать JWT;
- сервису достаточно получить ID пользователя из заголовка;
- нужен доступ к более полному payload через `X-User-Claims` и локальный `request.state.user`.
