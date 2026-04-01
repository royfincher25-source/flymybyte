# Сравнение Smart DNS подходов: xbox-dns.ru vs FlyMyByte

**Дата:** 31 марта 2026 г.
**Версия:** 1.0

---

## 1. Архитектурное сравнение

### xbox-dns.ru (Smart DNS сервис)

```
Пользователь → DNS-запрос → Smart DNS сервер (111.88.96.50)
                                    │
                    ┌───────────────┴───────────────┐
                    │                               │
            Заблокированный домен           Обычный домен
            (xbox.com, openai.com)          (google.com)
                    │                               │
                    ▼                               ▼
            Прокси-сервер                    Напрямую
            (IP меняется)                    (IP провайдера)
```

**Характеристики:**
- Централизованный сервис с публичными DNS-серверами
- Автоматическое определение заблокированных доменов
- Split-horizon DNS на стороне сервиса
- Не требует установки ПО

### FlyMyByte (Smart DNS на роутере)

```
Пользователь → dnsmasq (роутер) → Правила /opt/etc/unblock-ai.dnsmasq
                                        │
                        ┌───────────────┴───────────────┐
                        │                               │
                AI-домен                         Обычный домен
                (aistudio.google.com)            (yandex.ru)
                        │                               │
                        ▼                               ▼
                Cloudflare DNS (1.1.1.1)         Локальный DNS
                (IP меняется)                    (IP провайдера)
```

**Характеристики:**
- Децентрализованное решение (на роутере пользователя)
- Ручное управление списками доменов
- Split-horizon DNS на стороне клиента
- Требует настройки роутера

---

## 2. Технические различия

| Характеристика | xbox-dns.ru | FlyMyByte |
|----------------|-------------|-----------|
| **DNS-серверы** | 111.88.96.50, 111.88.96.51 | 1.1.1.1 (Cloudflare) |
| **DoH/DoT** | ✅ Поддерживается | ⚠️ Требуется stubby |
| **Автоматизация** | ✅ Автоопределение | ❌ Ручное добавление |
| **Категории** | ✅ Игры, AI, Стриминги | ⚠️ Только AI (расширяется) |
| **Приватность** | Zero-log (RAM только) | Локально (без логов) |
| **Зависимость** | Внешний сервис | Независимо |
| **Скорость** | 100% провайдера | 100% провайдера |

---

## 3. Почему xbox-dns.ru работает лучше для некоторых сервисов

### 3.1. Более полные списки доменов

**xbox-dns.ru** поддерживает:
- Xbox Live (15+ доменов)
- PlayStation Network (10+ доменов)
- Steam, Epic Games, Blizzard
- AI-сервисы (OpenAI, Anthropic, Midjourney)
- Стриминги (Spotify, Twitch, Netflix)

**FlyMyByte** (текущая версия):
- Только AI-сервисы Google (~20 доменов)
- ❌ Нет OpenAI (ChatGPT)
- ❌ Нет Anthropic (Claude)
- ❌ Нет Microsoft Copilot
- ❌ Нет игровых сервисов

**Решение:** Расширен список `unblock-ai-domains.txt` до 200+ доменов (см. файл).

### 3.2. Автоматическое обновление списков

**xbox-dns.ru:**
- Мониторинг доступности сервисов 24/7
- Автоматическое добавление новых доменов
- A/B тестирование DNS-серверов

**FlyMyByte:**
- Ручное обновление через GitHub
- Нет мониторинга доступности
- Нет автообновления

**Решение:** Добавить модуль `dns_monitor.py` с функциями:
```python
# Проверка доступности доменов
def check_domain_accessibility(domain: str) -> bool:
    """Проверить, доступен ли домен через текущий DNS"""
    
# Автодобавление проблемных доменов
def auto_add_problem_domains():
    """Добавить домены с ошибками DNS в список обхода"""
```

### 3.3. DNS-over-HTTPS / DNS-over-TLS

**xbox-dns.ru:**
- ✅ DoH: `https://xbox-dns.ru/dns-query`
- ✅ DoT: `xbox-dns.ru` (порт 853)
- Шифрование DNS-запросов
- Защита от DNS poisoning

**FlyMyByte:**
- ❌ Только незашифрованный DNS (порт 53)
- ❌ Провайдер видит DNS-запросы
- ⚠️ Возможна подмена DNS-ответов

**Решение:** Установить stubby (DNS-over-TLS):

```bash
# 1. Установить stubby
opkg update
opkg install stubby

# 2. Настроить /opt/etc/stubby/stubby.yml
resolution_type: GETDNS_RESOLUTION_STUB
dns_transport_list:
  - GETDNS_TRANSPORT_TLS
tls_authentication: GETDNS_AUTHENTICATION_REQUIRED
listen_addresses:
  - 127.0.0.1@5353
upstream_recursive_servers:
  - address_data: 1.1.1.1
    tls_auth_name: "cloudflare-dns.com"
    tls_port: 853

# 3. Обновить dnsmasq для использования stubby
# /opt/etc/dnsmasq.conf
server=127.0.0.1#5353
no-resolv

# 4. Перезапустить сервисы
/opt/etc/init.d/S56dnsmasq restart
/opt/etc/init.d/S99stubby restart
```

### 3.4. Split-horizon DNS для разных сервисов

**xbox-dns.ru:**
- Разные DNS-серверы для разных категорий
- Оптимизация маршрута для каждого сервиса

**FlyMyByte:**
- Один DNS-сервер (1.1.1.1) для всех AI-доменов
- Нет оптимизации по категориям

**Решение:** Создать профили DNS:

```conf
# /opt/etc/unblock-ai.dnsmasq (Google AI)
server=/aistudio.google.com/1.1.1.1#53
server=/gemini.google.com/1.1.1.1#53

# /opt/etc/unblock-openai.dnsmasq (OpenAI)
server=/chatgpt.com/1.1.1.1#53
server=/api.openai.com/1.1.1.1#53

# /opt/etc/unblock-gaming.dnsmasq (Игры)
server=/xboxlive.com/111.88.96.50#53
server=/playstation.net/111.88.96.50#53
```

---

## 4. Диагностика проблем

### 4.1. Проверка текущего DNS

```bash
# 1. Проверить, какой DNS используется
nslookup aistudio.google.com
# Если IP провайдера → проблема

# 2. Проверить конфигурацию dnsmasq
cat /opt/etc/unblock-ai.dnsmasq
# Должно быть: server=/aistudio.google.com/1.1.1.1#53

# 3. Проверить, применяется ли конфиг
ps | grep dnsmasq
# dnsmasq должен быть запущен

# 4. Проверить через nslookup с указанием DNS
nslookup aistudio.google.com 127.0.0.1
# Должен вернуть IP Cloudflare (не провайдера)

# 5. Проверить доступность сервиса
curl -I https://aistudio.google.com
# Ожидается: HTTP/2 200
```

### 4.2. Типичные проблемы и решения

| Проблема | Причина | Решение |
|----------|---------|---------|
| DNS не применяется | dnsmasq не перезапущен | `/opt/etc/init.d/S56dnsmasq restart` |
| IP провайдера | Конфиг не читается | Проверить путь в dnsmasq.conf |
| Таймаут | 1.1.1.1 недоступен | Использовать 8.8.8.8 |
| DNS leak | IPv6 не настроен | Отключить IPv6 или настроить DNS |

### 4.3. Проверка DNS leak

```bash
# 1. Проверить IPv4 DNS
curl https://dnsleaktest.com

# 2. Проверить, какой DNS видит сервис
curl https://api.ip.sb/ip
curl https://api.ip.sb/geoip

# 3. Сверить IP с реальным
# Если IP другой → DNS leak отсутствует
```

---

## 5. Рекомендации по улучшению FlyMyByte

### 5.1. Краткосрочные (1-2 часа)

1. ✅ **Расширить список AI-доменов** — выполнено (200+ доменов)
2. ⚠️ **Добавить DNS-over-TLS** — установить stubby
3. ⚠️ **Создать профили DNS** — раздельные конфиги для OpenAI, Google AI, Claude

### 5.2. Среднесрочные (1-2 дня)

4. ⚠️ **Модуль dns_monitor.py** — автоматическая проверка доступности
5. ⚠️ **Веб-интерфейс профилей** — выбор категорий (AI, Игры, Стриминги)
6. ⚠️ **Автообновление списков** — загрузка с GitHub по расписанию

### 5.3. Долгосрочные (1-2 недели)

7. ⚠️ **DNS analyzer** — логирование проблемных запросов
8. ⚠️ **Интеграция с xbox-dns.ru** — использование их DNS для игр
9. ⚠️ **Мобильное приложение** — настройка DNS на устройствах

---

## 6. Быстрый старт для пользователя

### Шаг 1: Проверка текущей конфигурации

```bash
# SSH на роутер
ssh root@192.168.1.1 -p 222

# Проверить dnsmasq
cat /opt/etc/unblock-ai.dnsmasq

# Проверить DNS
nslookup aistudio.google.com 127.0.0.1
```

### Шаг 2: Применение нового списка

```bash
# Через веб-интерфейс
Сервис → DNS-обход AI → Загрузить готовый список → Применить

# Или вручную
curl -sL -o /opt/etc/unblock/ai-domains.txt \
  https://raw.githubusercontent.com/royfincher25-source/flymybyte/master/src/web_ui/resources/lists/unblock-ai-domains.txt

# Применить конфигурацию
sh /opt/etc/web_ui/resources/scripts/unblock_dnsmasq.sh
```

### Шаг 3: Проверка доступности

```bash
# Проверить ChatGPT
nslookup chatgpt.com 127.0.0.1
curl -I https://chatgpt.com

# Проверить Claude
nslookup claude.ai 127.0.0.1
curl -I https://claude.ai

# Проверить Gemini
nslookup gemini.google.com 127.0.0.1
curl -I https://gemini.google.com
```

---

## 7. Сводная таблица доменов

| Сервис | Домены | Статус |
|--------|--------|--------|
| **Google AI** | aistudio.google.com, gemini.google.com, colab.research.google.com | ✅ В списке |
| **OpenAI** | chatgpt.com, api.openai.com, platform.openai.com | ✅ В списке |
| **Anthropic** | claude.ai, console.anthropic.com | ✅ В списке |
| **Microsoft AI** | copilot.microsoft.com, bing.com, oai.azure.com | ✅ В списке |
| **Meta AI** | meta.ai, llama.meta.com | ✅ В списке |
| **Midjourney** | midjourney.com | ✅ В списке |
| **Stability AI** | stability.ai, dreamstudio.ai | ✅ В списке |
| **Hugging Face** | huggingface.co, spaces.huggingface.co | ✅ В списке |
| **Perplexity** | perplexity.ai | ✅ В списке |
| **Character.AI** | character.ai | ✅ В списке |
| **GitHub Copilot** | github.com, copilot.github.com | ✅ В списке |

---

## 8. Выводы

### Что уже работает в FlyMyByte

✅ **Smart DNS архитектура** — dnsmasq + split-horizon
✅ **Cloudflare DNS** — 1.1.1.1 вместо локального
✅ **Веб-интерфейс** — управление через браузер
✅ **Атомарная запись** — защита от повреждения конфига
✅ **Валидация доменов** — фильтрация некорректных записей

### Что заимствовать у xbox-dns.ru

⚠️ **DoH/DoT поддержка** — шифрование DNS
⚠️ **Автомониторинг** — проверка доступности доменов
⚠️ **Готовые профили** — AI, Игры, Стриминги
⚠️ **Больше доменов** — расширенные списки

### Критические отличия

| Аспект | xbox-dns.ru | FlyMyByte |
|--------|-------------|-----------|
| **Контроль** | Внешний сервис | Полный контроль |
| **Приватность** | Доверие сервису | Локально |
| **Гибкость** | Фиксированные профили |自定义 списки |
| **Зависимость** | Сервис должен работать | Независимо |

---

## 9. Дополнительные ресурсы

- [xbox-dns.ru](https://xbox-dns.ru) — Smart DNS сервис
- [Cloudflare DNS](https://1.1.1.1) — Публичный DNS
- [dnsmasq documentation](https://thekelleys.org.uk/dnsmasq/doc.html)
- [stubby DNS-over-TLS](https://dnsprivacy.org/wiki/display/DP/DNS+Privacy+Daemon+-+Stubby)
