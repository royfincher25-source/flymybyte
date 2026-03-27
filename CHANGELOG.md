# Changelog

Все значимые изменения в проекте будут документироваться в этом файле.

## [1.6.6] - 2026-03-23

### ✨ Новое

#### DNS-обход AI-доменов
Новая функция для обхода региональных блокировок AI-сервисов Google через подмену DNS.

**Поддерживаемые сервисы:**
- Google AI Studio (aistudio.google.com)
- Gemini (gemini.google.com)
- Google Colab (colab.research.google.com)
- Kaggle (kaggle.com)
- Google DeepMind
- TensorFlow
- и другие

**Принцип работы:**
1. DNS-запросы к AI-доменам направляются через VPN DNS (порт 40500)
2. VPN резолвит домены через внешний DNS (8.8.8.8)
3. Сервис видит IP VPN, а не реальный регион пользователя

**Новые файлы:**
- `core/dns_spoofing.py` — модуль DNS-обхода AI-доменов
- `templates/dns_spoofing.html` — веб-интерфейс управления
- `resources/lists/unblock-ai-domains.txt` — готовый список AI-доменов
- `resources/config/unblock-ai.dnsmasq.template` — шаблон конфигурации dnsmasq
- `docs/DNS_SPOOFING_DESIGN.md` — дизайн-документ архитектуры
- `docs/DNS_SPOOFING_INSTRUCTION.md` — инструкция пользователя
- `tests/test_dns_spoofing.py` — unit-тесты

**Обновлённые файлы:**
- `routes.py` — добавлено 8 API endpoints для управления DNS-обходом
- `resources/scripts/unblock_dnsmasq.sh` — генерация конфигурации для AI-доменов
- `templates/service.html` — добавлена карточка "DNS-обход AI"
- `README.md` — добавлена документация по DNS-обходу
- `docs/OBSIDIAN_INSTRUCTION.md` — полная документация Obsidian
- `VERSION` — обновлена версия до 1.6.6

**API Endpoints:**
- `GET /dns-spoofing` — страница управления
- `GET /dns-spoofing/status` — статус DNS-обхода
- `POST /dns-spoofing/apply` — применить конфигурацию
- `POST /dns-spoofing/disable` — выключить DNS-обход
- `GET /dns-spoofing/domains` — получить список доменов
- `POST /dns-spoofing/domains` — сохранить список доменов
- `GET /dns-spoofing/preset` — загрузить готовый список
- `POST /dns-spoofing/test` — тестировать разрешение домена
- `GET /dns-spoofing/logs` — получить логи

**Веб-интерфейс:**
- Страница `/dns-spoofing` с полным управлением
- Статус DNS-обхода (Активен/Выключен)
- Список AI-доменов с возможностью редактирования
- Кнопка загрузки готового списка
- Тестирование разрешения доменов
- Просмотр логов применения конфигурации

**Документация:**
- `docs/DNS_SPOOFING_DESIGN.md` — архитектурное описание
- `docs/DNS_SPOOFING_INSTRUCTION.md` — руководство пользователя
- `README.md` — обновлено с описанием новой функции
- `OBSIDIAN_INSTRUCTION.md` — обновлена полная документация

### 🔧 Технические детали

**Модуль dns_spoofing.py:**
- Singleton pattern для потокобезопасности
- Валидация доменов (проверка формата, длины)
- Фильтрация IP-адресов
- Atomic write конфигурации (через .tmp файл)
- Интеграция с dnsmasq (перезапуск через init script)
- Тестирование разрешения доменов через nslookup

**Конфигурация dnsmasq:**
```conf
# AI Domains DNS Spoofing
address=/aistudio.google.com/127.0.0.1#40500
server=/aistudio.google.com/127.0.0.1#40500
```

**Зависимости:**
- Python 3.8+
- dnsmasq (установлен по умолчанию)
- VPN с DNSPort (Shadowsocks/Xray/Tor)

### 📝 Документация

**Новые документы:**
- `docs/DNS_SPOOFING_DESIGN.md` — дизайн-документ
- `docs/DNS_SPOOFING_INSTRUCTION.md` — инструкция пользователя

**Обновлённые документы:**
- `README.md` — добавлен раздел "DNS-обход AI-доменов"
- `docs/OBSIDIAN_INSTRUCTION.md` — обновлена версия до 1.2.0
- `VERSION` — 1.6.6

### 🧪 Тесты

**Новые тесты:**
- `tests/test_dns_spoofing.py` — unit-тесты модуля DNS-обхода

**Категории тестов:**
- DomainValidation — валидация доменов
- ConfigGeneration — генерация конфигурации dnsmasq
- ConfigWrite — запись конфигурации
- Status — статус DNS-обхода
- DomainLoading — загрузка списка доменов
- ModuleFunctions — тестирование функций модуля

### 🎯 Быстрый старт

**Через веб-интерфейс:**
1. Откройте `http://192.168.1.1:8080`
2. Перейдите в **Сервис** → **DNS-обход AI** → **Настроить**
3. Нажмите **Загрузить готовый список**
4. Нажмите **Применить**
5. Проверьте статус: должен быть "✅ Активен"

**Через SSH:**
```bash
# 1. Подключитесь к роутеру
ssh root@192.168.1.1 -p 222

# 2. Скачайте список AI-доменов
curl -sL -o /opt/etc/unblock/ai-domains.txt \
  https://raw.githubusercontent.com/royfincher25-source/flymybyte/master/src/web_ui/resources/lists/unblock-ai-domains.txt

# 3. Примените конфигурацию
sh /opt/etc/web_ui/resources/scripts/unblock_dnsmasq.sh

# 4. Проверьте конфигурацию
cat /opt/etc/unblock-ai.dnsmasq
```

### ⚠️ Важные замечания

**Требования:**
- Настроенный VPN (Shadowsocks, Xray, Tor) с DNSPort (порт 40500)
- Установленный dnsmasq
- Python 3.8+

**Безопасность:**
- DNS-запросы идут через VPN DNS, что скрывает регион
- Atomic write предотвращает повреждение конфигурации
- Валидация доменов защищает от некорректных записей

**Производительность:**
- Память: ~1MB (dnsmasq + кэш)
- CPU: минимальное (только при старте)
- Место: ~50KB (конфигурация)

---

## [1.6.5] - 2026-03-20

### Предыдущая версия

См. историю коммитов для деталей.

---

## Формат

Этот проект следует [Semantic Versioning](https://semver.org/lang/ru/):
- **MAJOR** — обратно несовместимые изменения
- **MINOR** — новые функции, обратно совместимые
- **PATCH** — исправления ошибок, обратно совместимые

Формат: `[MAJOR.MINOR.PATCH] - YYYY-MM-DD`

### Типы изменений

- **✨ Новое** — новые функции
- **🔧 Изменено** — изменения в существующем функционале
- **🐛 Исправлено** — исправления ошибок
- **📝 Документация** — изменения в документации
- **🧪 Тесты** — новые или обновлённые тесты
- **⚠️ Важно** — критические изменения, требующие внимания
