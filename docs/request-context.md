# Request Context

Этот документ описывает, как gateway сохраняет данные пользователя и как downstream-сервисы могут их использовать.

## Что делает middleware

Функция `jwt_middleware`:

1. пропускает публичные пути и документацию;
2. читает `access_token` из cookies;
3. валидирует JWT через `validate_jwt`;
4. сохраняет decoded payload в `request.state.user`.
5. сохраняет исочник запроса в `request.state.client_type`.

## Что лежит в client_type

В client_type лежит название сервиса, который отправил запрос.

- `user`: Запрос на прямую из клиента
- `<name>`: Запрос от сервиса по внутренней сети
- `admin`: Запрос из админ контура (получает доступ к админ части сервисов)

## Как отправить запрос из сервиса

Запрос должен иметь headers: 
- `X-Service-ID`: название сервиса
- `X-User-Context`: jwt c данными пользователя, может протухнуть, при каждом запросе кодировать новый.
- `X-Service-Token`: Уникальный токен сервиса. При добавлени нового сервиса, токен нужно добавить в Settings.service_tokens. Ключ название сервиса: значение токен.

## Как отправить подписанный запрос из admin_service
- [`./request-from-admin-service.md`](./request-from-admin-service.md)


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


