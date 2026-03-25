# Инструкция по ручному обновлению flymybyte на роутере

## Проблема
Кнопка "Обновить" в веб-интерфейсе не работает из-за:
1. Неправильного указания репозитория (используется неверное имя репозитория)
2. Неправильной ветки (используется `main` вместо `master`)
3. Остаточных ссылок на удаленные файлы `bot3` (Telegram-бот)

## Решение

### Вариант 1: Исправление на существующей установке (быстрое)

1. Подключитесь к роутеру по SSH:
   ```bash
   ssh root@192.168.1.1
   ```

2. Скачайте и запустите скрипт исправления:
   ```bash
   cd /tmp
   curl -sL -o fix_bot3.sh "https://raw.githubusercontent.com/royfincher25-source/flymybyte/master/fix_bot3_references.sh"
   chmod +x fix_bot3.sh
   ./fix_bot3.sh
   ```

3. Проверьте логи:
   ```bash
   tail -f /opt/var/log/web_ui.log
   ```

4. Попробуйте кнопку "Обновить" в веб-интерфейсе.

### Вариант 2: Полное обновление файлов

1. **Подключитесь к роутеру по SSH:**
   ```bash
   ssh root@192.168.1.1
   ```

2. **Создайте резервную копию:**
   ```bash
   mkdir -p /opt/root/backup
   tar -czf /opt/root/backup/web_ui_backup_$(date +%Y%m%d_%H%M%S).tar.gz /opt/etc/web_ui
   ```

3. **Остановите веб-интерфейс:**
   ```bash
   /opt/etc/init.d/S99web_ui stop
   ```

4. **Скачайте обновленные файлы:**
   ```bash
   cd /tmp
   rm -rf update_web_ui
   mkdir update_web_ui
   cd update_web_ui
   
   # Основные файлы
   curl -sL -o app.py "https://raw.githubusercontent.com/royfincher25-source/flymybyte/master/src/web_ui/app.py"
   curl -sL -o routes.py "https://raw.githubusercontent.com/royfincher25-source/flymybyte/master/src/web_ui/routes.py"
   curl -sL -o env_parser.py "https://raw.githubusercontent.com/royfincher25-source/flymybyte/master/src/web_ui/env_parser.py"
   curl -sL -o requirements.txt "https://raw.githubusercontent.com/royfincher25-source/flymybyte/master/src/web_ui/requirements.txt"
   curl -sL -o .env.example "https://raw.githubusercontent.com/royfincher25-source/flymybyte/master/src/web_ui/.env.example"
   
   # Core файлы
   mkdir -p core
   cd core
   for file in __init__.py app_config.py utils.py services.py ipset_manager.py list_catalog.py dns_manager.py dns_monitor.py dns_resolver.py web_config.py; do
       curl -sL -o "$file" "https://raw.githubusercontent.com/royfincher25-source/flymybyte/master/src/web_ui/core/$file"
   done
   cd ..
   
   # Шаблоны
   mkdir -p templates
   cd templates
   for file in base.html login.html index.html keys.html bypass.html install.html stats.html service.html updates.html bypass_view.html bypass_add.html bypass_remove.html bypass_catalog.html key_generic.html backup.html dns_monitor.html logs.html; do
       curl -sL -o "$file" "https://raw.githubusercontent.com/royfincher25-source/flymybyte/master/src/web_ui/templates/$file"
   done
   cd ..
   
   # Статика и скрипты
   mkdir -p static scripts resources/scripts
   curl -sL -o static/style.css "https://raw.githubusercontent.com/royfincher25-source/flymybyte/master/src/web_ui/static/style.css"
   curl -sL -o scripts/script.sh "https://raw.githubusercontent.com/royfincher25-source/flymybyte/master/src/web_ui/scripts/script.sh"
   chmod 755 scripts/script.sh
   
   # Ресурсы
   cd resources/scripts
   for script in unblock_ipset.sh unblock_dnsmasq.sh unblock_update.sh 100-redirect.sh 100-ipset.sh 100-unblock-vpn.sh 100-unblock-vpn-v4.sh S99unblock S99web_ui keensnap.sh; do
       curl -sL -o "$script" "https://raw.githubusercontent.com/royfincher25-source/flymybyte/master/src/web_ui/resources/scripts/$script"
       chmod 755 "$script"
   done
   cd ../..
   
   # Конфиги
   mkdir -p resources/config
   curl -sL -o resources/config/dnsmasq.conf "https://raw.githubusercontent.com/royfincher25-source/flymybyte/master/src/web_ui/resources/config/dnsmasq.conf"
   curl -sL -o resources/config/crontab "https://raw.githubusercontent.com/royfincher25-source/flymybyte/master/src/web_ui/resources/config/crontab"
   
   # VERSION
   curl -sL -o VERSION "https://raw.githubusercontent.com/royfincher25-source/flymybyte/master/VERSION"
   ```

5. **Замените файлы:**
   ```bash
   rm -rf /opt/etc/web_ui/*
   cp -r /tmp/update_web_ui/* /opt/etc/web_ui/
   
   # Установите права
   chmod -R 755 /opt/etc/web_ui/scripts/
   chmod -R 755 /opt/etc/web_ui/resources/scripts/
   chmod 644 /opt/etc/web_ui/*.py
   chmod 644 /opt/etc/web_ui/core/*.py
   ```

6. **Установите зависимости:**
   ```bash
   cd /opt/etc/web_ui
   opkg update
   opkg install python3-pip
   pip3 install -r requirements.txt
   ```

7. **Запустите веб-интерфейс:**
   ```bash
   /opt/etc/init.d/S99web_ui start
   ```

8. **Проверьте логи:**
   ```bash
   tail -f /opt/var/log/web_ui.log
   ```

9. **Очистите временные файлы:**
   ```bash
   rm -rf /tmp/update_web_ui
   ```

## Проверка

1. Откройте веб-интерфейс: `http://192.168.1.1:8080`
2. Нажмите кнопку "Обновить"
3. Теперь она должна работать без ошибок

## Примечания

- Ветка `master` используется вместо `main`, так как это ветка по умолчанию в репозитории
- Репозиторий `FlyMyByte` (с подчёркиванием) правильный, а не `FlyMyByte` (с дефисом)
- Все ссылки на файлы `bot3` (Telegram-бот) удалены
- Обновление через веб-интерфейс теперь будет работать корректно