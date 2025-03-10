#!/bin/bash

# Загружаем переменные из .env
if [ -f /root/.env ]; then
  export $(cat /root/.env | grep -v '^#' | xargs)
else
  echo ".env file not found!"
  exit 1
fi

# Перенаправление HTTP на HTTPS (первоначальная настройка)
nginx -s reload

# Получаем SSL-сертификаты с использованием Certbot (если они еще не получены)
if [ ! -f /etc/letsencrypt/live/$DOMAIN_FOR_SSL/fullchain.pem ]; then
    echo "Получаем SSL сертификаты для $DOMAIN с Let's Encrypt..."
    certbot --nginx -d $DOMAIN_FOR_SSL -d www.$DOMAIN_FOR_SSL --agree-tos --non-interactive --email $EMAIL_FOR_SSL
else
    echo "SSL сертификаты для $DOMAIN_FOR_SSL уже существуют!"
fi

# Запускаем Nginx после получения сертификатов
nginx -g "daemon off;"

# Регулярно обновляем сертификаты (каждое первое число месяца)
echo "0 0 1 * * certbot renew --quiet && nginx -s reload" | crontab -
