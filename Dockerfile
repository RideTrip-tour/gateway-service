# Используем официальный образ Nginx в качестве базового
FROM nginx:alpine

# Устанавливаем необходимые пакеты (curl, certbot, bash)
RUN apk update && \
    apk add --no-cache bash certbot nginx-utils curl

# Скачиваем nginx-prometheus-exporter
RUN curl -LO https://github.com/nginxinc/nginx-prometheus-exporter/releases/download/v0.10.0/nginx-prometheus-exporter-0.10.0-linux-amd64.tar.gz \
    && tar -xvzf nginx-prometheus-exporter-0.10.0-linux-amd64.tar.gz \
    && mv nginx-prometheus-exporter-0.10.0-linux-amd64/nginx-prometheus-exporter /usr/local/bin/

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
COPY ./scripts/ssl_serts.sh /ssl_serts.sh
RUN chmod +x /ssl_serts.sh

# Скрипт для запуска
COPY ./scripts/start.sh /start.sh
RUN chmod +x /start.sh

# Открываем порты для HTTP и HTTPS
EXPOSE 80 443

# Запуск контейнера
ENTRYPOINT ["/ssl_serts.sh"]
CMD ["/start.sh"]
