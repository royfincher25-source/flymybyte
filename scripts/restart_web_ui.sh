#!/bin/sh
# Скрипт очистки кэша, логов и перезапуска web_ui
# Запускать НАПРЯМУЮ на роутере (в Entware)!
# Использование: sh /opt/root/restart_web_ui.sh

echo "============================================================"
echo "Очистка кэша, логов и перезапуск web_ui"
echo "============================================================"
echo ""

echo '[1/4] Остановка web_ui...'
/opt/etc/init.d/S99web_ui stop

echo '[2/4] Очистка кэша Python...'
rm -rf /opt/root/web_ui/src/web_ui/__pycache__
rm -rf /opt/root/web_ui/src/web_ui/core/__pycache__

echo '[3/4] Очистка логов...'
echo '' > /opt/var/log/web_ui.log

echo '[4/4] Запуск web_ui...'
/opt/etc/init.d/S99web_ui start

echo ''
echo '============================================================'
echo 'Готово! Web UI перезапущен с чистой конфигурацией'
echo '============================================================'
echo ''
echo 'Последние строки лога:'
tail -10 /opt/var/log/web_ui.log
