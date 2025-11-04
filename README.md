# Техническое задание на разработку `gateway-service`

## 1. Функциональные требования

### 1.1 Маршрутизация запросов
- Проксирование HTTP-запросов к микросервисам:

```
/auth/* → auth-service
/plans/* → plans-service
/locations/* → locations-service
/users/* → users-service 
/activities/* → activities-service
/routes/* → routes-service
/departure/* → departure-service
/pricing/* → pricing-service 
/pdf/* → pdf-service
/bot/* → bot-service 
```

- Поддержка динамического добавления маршрутов
- Кэширование ответов (TTL 5 мин)

### 1.2 Аутентификация и авторизация
- Валидация JWT через интеграцию с `auth-service`:
```json
POST /auth/validate
{"token": "JWT"}
```

- Кэширование результатов валидации (Redis)

Заголовки:
```
Authorization: Bearer <JWT>

X-User-ID (после аутентификации)
```

### 1.3 Безопасность
Rate limiting:

100 RPM для авторизованных

10 RPM для анонимных

Защита от DDoS

## 2. Технические требования
### 2.1 Стек технологий

Язык - Python (FastAPI)
Кэш -	Redis
API Gateway	- NGINX
Мониторинг	- Prometheus + Grafana
Логирование	- Loki

### 2.2 Конфигурация

Настройки приложения загружаются из переменных окружения и файла `.env`.

**Пример файла `.env`:**

```dotenv
# URL для подключения к Redis (включая пароль, если он есть)
REDIS_URL="redis://default:your_password@127.0.0.1:6379/0"

# Время жизни записей в кеше Redis в секундах
REDIS_TTL=300

# Ограничение количества запросов в минуту
RATE_LIMIT=100

# Публичные пути, не требующие аутентификации (формат: JSON-массив в виде строки)
PUBLIC_PATHS='["/health","/auth/login","/auth/register","/docs","/openapi.json","/redoc"]'

# Карта маршрутизации от префикса пути к URL микросервиса (формат: JSON-объект в виде строки)
SERVICE_MAP='{"auth": "http://127.0.0.1:8001/api", "plans": "http://127.0.0.1:8002/api"}'
```

**Важно:** Значения для `PUBLIC_PATHS` и `SERVICE_MAP` должны быть валидными JSON-строками, заключенными в одинарные кавычки.

## 3. Требования к инфраструктуре
### 3.1 Kubernetes

```yaml
deployment:
  replicas: 2
  probes:
    liveness: /health
    readiness: /health
  resources:
    requests:
      cpu: 100m
      memory: 128Mi
    limits:
      cpu: 500m
      memory: 512Mi
```

## 4. Этапы разработки
1. Проектирование (3 дня)

- Схема маршрутизации

- API контракты

2. Реализация (10 дней)

- Базовый функционал

- Интеграции

3. Тестирование (5 дней)

- Юнит-тесты

- Нагрузочное тестирование

5. Критерии приемки
- 100% покрытие тестами критического функционала

- Задержка < 100ms на 95% запросов

- Отсутствие 5xx ошибок в продакшене
