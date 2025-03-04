#!/bin/bash

# Запускаем nginx
nginx -g 'daemon off;' &

# Запускаем nginx-prometheus-exporter
nginx-prometheus-exporter -nginx.scrape-uri=http://localhost:8080/stub_status

# Ожидаем завершения процессов
wait
