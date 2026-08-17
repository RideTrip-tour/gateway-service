
# Аутентификация Admin Service при обращении к Gateway

## Назначение

Admin Service — отдельное приложение, которое предоставляет административный интерфейс и выполняет операции с сущностями через Gateway.

Admin Service **не обращается непосредственно к микросервисам**. Все запросы проходят через Gateway:

```text
┌──────────────┐
│ Admin Service│
│    Django    │
└──────┬───────┘
       │
       │ HTTPS
       │ authenticated request
       ▼
┌──────────────┐
│   Gateway    │
└──────┬───────┘
       │
       ▼
┌─────────────────────┐
│ Microservice        │
│ location/profile/...│
└─────────────────────┘
```

Gateway должен убедиться, что запрос действительно отправлен доверенным Admin Service, а также определить пользователя, от имени которого выполняется операция.

---

# 1. HTTP-запрос

Каждый запрос Admin Service к Gateway должен содержать следующие HTTP headers:

| Header            | Обязательный | Назначение                        |
| ----------------- | -----------: | --------------------------------- |
| `X-Service-ID`    |           Да | Идентификатор сервиса             |
| `X-Service-Token` |           Да | Секретный токен сервиса           |
| `X-User-Context`  |           Да | JWT пользователя                  |
| `X-Timestamp`     |           Да | Unix timestamp создания запроса   |
| `X-Nonce`         |           Да | Уникальный идентификатор запроса  |
| `X-Signature`     |           Да | Криптографическая подпись запроса |

Пример:

```http
POST /api/admin/locations?country=ru HTTP/1.1
Host: gateway.example.com
X-Service-ID: admin-service
X-Service-Token: <service-token>
X-User-Context: <user-jwt>
X-Timestamp: 1786960000
X-Nonce: d3f8a7c2...
X-Signature: <base64-signature>
Content-Type: application/json

{"name":"Москва"}
```


# 3. `X-Service-ID`

Идентификатор сервиса:

```http
X-Service-ID: admin
```

Значение должно быть заранее зарегистрировано в Gateway.

Например:

```python
SERVICE_PUBLIC_KEYS = {
    "admin": "...",
}
```

`X-Service-ID` **не является секретом**.

Он только сообщает Gateway:

> «Я являюсь `admin-service`, используй для проверки моей подписи соответствующий public key».

Gateway не должен доверять `X-Service-ID` без проверки подписи.

---

# 4. `X-Service-Token`

Секретный токен Admin Service:

```http
X-Service-Token: <service-token>
```

> `X-Service-Token` и приватный ключ — секреты Admin Service.

---

# 5. `X-User-Context`

`X-User-Context` содержит JWT пользователя, от имени которого выполняется операция.

Например:

```http
X-User-Context: eyJhbGciOiJSUzI1NiIs...
```

Gateway самостоятельно проверяет этот JWT.

Admin Service **не должен изменять или пересобирать JWT**.

Если текущий пользователь — пользователь с ID `123`, в header передаётся JWT этого пользователя.

---

# 6. `X-Timestamp`

Содержит Unix timestamp момента создания запроса в секундах:

```http
X-Timestamp: 1786960000
```

Пример на Python:

```python
import time

timestamp = str(int(time.time()))
```

Gateway принимает запрос, если его timestamp отличается от текущего времени не более чем на **30 секунд**.

---

# 7. `X-Nonce`

`X-Nonce` — случайная уникальная строка, создаваемая для **каждого запроса**.

Например:

```http
X-Nonce: d3f8a7c2e91f...
```

На Python:

```python
import secrets

nonce = secrets.token_urlsafe(32)
```

Один nonce нельзя использовать повторно.

Gateway хранит использованные nonce ограниченное время и отклоняет повторный запрос:

```text
first request
    nonce = abc123
        ↓
       OK

second request
    nonce = abc123
        ↓
       401 Request replay detected
```

---

# 8. `X-Signature`

`X-Signature` содержит Ed25519-подпись запроса.

Подпись создаётся **приватным ключом Admin Service**.

Gateway имеет соответствующий **public key**.

```text
Admin Service
     │
     │ private key
     ▼
   sign()
     │
     ▼
X-Signature
     │
     ▼
   Gateway
     │
     │ public key
     ▼
  verify()
```

Приватный ключ **никогда не передаётся Gateway**.

---

# 9. Что именно подписывается

Подписывается следующая последовательность:

```text
service_id
method
path
query
timestamp
nonce
body_hash
user_context
```

Значения соединяются символом перевода строки `\n`.

Например:

```text
admin-service
POST
/api/admin/locations
country=ru
1786960000
d3f8a7c2
a8f5f167...
eyJhbGciOiJSUzI1NiIs...
```

Важно: порядок полей менять нельзя.

---

# 10. `body_hash`

Перед формированием подписи вычисляется SHA-256 от **исходного HTTP body**.

Например:

```python
import hashlib

body = b'{"name":"Москва"}'

body_hash = hashlib.sha256(body).hexdigest()
```

Полученная строка:

```text
a8f5f167...
```

используется при формировании подписи.

Важно:

> Подписывать нужно именно те bytes, которые будут отправлены в HTTP body.

Нельзя сначала подписать:

```json
{"name": "Москва"}
```

а затем отправить:

```json
{"name":"Москва"}
```

если используемая сериализация приводит к другому набору bytes.

---

# 11. Формирование signing message

На стороне Admin Service должна быть реализована функция:

```python
def build_signing_message(
    service_id: str,
    method: str,
    path: str,
    query: str,
    timestamp: str,
    nonce: str,
    body_hash: str,
    user_context: str,
) -> bytes:
    parts = [
        service_id,
        method,
        path,
        query,
        timestamp,
        nonce,
        body_hash,
        user_context,
    ]

    return "\n".join(parts).encode("utf-8")
```

Например:

```python
message = build_signing_message(
    service_id="admin-service",
    method="POST",
    path="/api/admin/locations",
    query="country=ru",
    timestamp="1786960000",
    nonce="d3f8a7c2",
    body_hash="a8f5f167...",
    user_context="eyJhbGciOi...",
)
```

---

# 12. Создание подписи

Используется Ed25519.

Python:

```python
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
)

signature = private_key.sign(message)
```

Полученный результат нужно передать в Base64:

```python
import base64

signature_header = base64.b64encode(signature).decode("ascii")
```

И передать:

```http
X-Signature: <signature_header>
```

---

# 13. Полный пример на Python

Пример реализации клиента:

```python
import base64
import hashlib
import secrets
import time

from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
)


def build_signing_message(
    service_id: str,
    method: str,
    path: str,
    query: str,
    timestamp: str,
    nonce: str,
    body_hash: str,
    user_context: str,
) -> bytes:
    parts = [
        service_id,
        method,
        path,
        query,
        timestamp,
        nonce,
        body_hash,
        user_context,
    ]

    return "\n".join(parts).encode("utf-8")


def sign_request(
    *,
    private_key: Ed25519PrivateKey,
    service_id: str,
    service_token: str,
    method: str,
    path: str,
    query: str,
    body: bytes,
    user_context: str,
) -> dict[str, str]:

    timestamp = str(int(time.time()))
    nonce = secrets.token_urlsafe(32)

    body_hash = hashlib.sha256(body).hexdigest()

    message = build_signing_message(
        service_id=service_id,
        method=method,
        path=path,
        query=query,
        timestamp=timestamp,
        nonce=nonce,
        body_hash=body_hash,
        user_context=user_context,
    )

    signature = private_key.sign(message)

    return {
        "X-Service-ID": service_id,
        "X-Service-Token": service_token,
        "X-User-Context": user_context,
        "X-Timestamp": timestamp,
        "X-Nonce": nonce,
        "X-Signature": base64.b64encode(signature).decode("ascii"),
    }
```

Использование:

```python
body = b'{"name":"Москва"}'

headers = sign_request(
    private_key=private_key,
    service_id="admin-service",
    service_token=service_token,
    method="POST",
    path="/api/admin/locations",
    query="country=ru",
    body=body,
    user_context=user_jwt,
)

response = await client.post(
    "https://gateway.example.com/api/admin/locations?country=ru",
    content=body,
    headers=headers,
)
```

---

# 14. Важное правило: URL должен соответствовать подписи

Если подписывается:

```text
path = /api/admin/locations
query = country=ru
```

то запрос должен быть отправлен именно как:

```text
/api/admin/locations?country=ru
```

Нельзя подписать:

```text
/api/admin/locations?country=ru
```

а отправить:

```text
/api/admin/locations?country=en
```

Gateway обнаружит изменение при проверке подписи.

---

# 15. Что проверяет Gateway

При получении запроса Gateway выполняет проверки:

```text
1. Все необходимые headers присутствуют
       ↓
2. X-Service-ID известен
       ↓
3. Получен public key этого сервиса
       ↓
4. Подпись корректна
       ↓
5. Timestamp не старше 30 секунд
       ↓
6. Nonce ещё не использовался
       ↓
7. X-User-Context содержит корректный JWT
       ↓
8. Запрос разрешён
```

При успешной проверке Gateway устанавливает:

```python
request.state.user
request.state.client_type
```

Для Admin Service:

```python
request.state.client_type == "admin"
```

---

# 16. Что нужно предоставить Admin Service

Для подключения Admin Service Gateway должен предоставить:

```text
SERVICE_ID
SERVICE_TOKEN
PRIVATE_KEY
GATEWAY_URL
```

При этом:

```text
SERVICE_ID       → можно передавать в запросе
SERVICE_TOKEN    → секрет
PRIVATE_KEY      → секрет
```

Gateway должен знать:

```text
SERVICE_ID
PUBLIC_KEY
```

Приватный ключ Admin Service **никогда не должен попадать в Gateway**.

---

## Коротко

Для каждого запроса Admin Service делает:

```text
                    HTTP request
                         │
        ┌────────────────┴────────────────┐
        │                                 │
   обычные данные                    security data
        │                                 │
   HTTP method                       service_id
   URL/path                          service_token
   query                             user_context
   body                              timestamp
                                     nonce
                                     signature
```

А подпись строится:

```text
service_id
    +
method
    +
path
    +
query
    +
timestamp
    +
nonce
    +
SHA256(body)
    +
user_context
        │
        ▼
   Ed25519.sign()
        │
        ▼
   X-Signature
```

