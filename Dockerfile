# Используем официальный образ Nginx в качестве базового
FROM nginx:alpine

# Устанавливаем необходимые пакеты (curl, certbot, bash)
RUN apk update && \
    apk add --no-cache bash certbot nginx-utils curl

# Копируем конфигурацию Nginx в контейнер
COPY nginx.conf /etc/nginx/nginx.conf

# Создаем директорию для кеша и назначаем нужные права
RUN mkdir -p /var/cache/nginx/bot_cache && \
    chown -R nginx:nginx /var/cache/nginx

# Копируем .env файл в контейнер
COPY .env /root/.env

# Создаем директории для хранения сертификатов, если их еще нет
RUN mkdir -p /etc/letsencrypt /var/lib/letsencrypt

# Устанавливаем скрипт для получения сертификатов при запуске контейнера
COPY ./scripts/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Открываем порты для HTTP и HTTPS
EXPOSE 80 443

# Запуск контейнера
ENTRYPOINT ["/entrypoint.sh"]
CMD ["nginx", "-g", "daemon off;"]
