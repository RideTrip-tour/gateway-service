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

В middleware, dependency или endpoint можно читать данные так:

```python
from fastapi import Request


def get_user(request: Request):
    return getattr(request.state, "user", None)
```

Если нужен только идентификатор пользователя, gateway сам передаёт его в заголовке:

```http
X-User-ID: <user_id>
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
- нужен доступ к более полному payload через `request.state.user`.
