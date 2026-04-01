# DNS Spoofing для обхода региональных блокировок AI-сервисов

**Дата:** 23 марта 2026 г.  
**Версия:** 1.0  
**Статус:** В разработке

---

## 1. Проблема

### 1.1. Описание
AI-сервисы Google (aistudio.google.com, gemini.google.com, colab.research.google.com) определяют регион пользователя по:
- DNS-запросам (резолв доменов через локальные DNS)
- IP-адресу исходящего соединения
- HTTP-заголовкам (Accept-Language,_timezone)

При обнаружении региона РФ/РК доступ блокируется на уровне:
- **DNS-level:** Возврат NXDOMAIN или неправильного IP
- **HTTP-level:** 403 Forbidden или редирект на заглушку

### 1.2. Текущее состояние
Проект flymybyte уже реализует:
- ✅ Маршрутизацию через VPN (Shadowsocks, Tor, VLESS, Trojan)
- ✅ DNS-мониторинг и автопереключение
- ✅ Разрешение доменов через ipset

**Недостаток:** DNS-запросы к AI-доменам всё ещё могут уходить через локальные DNS, что позволяет определить регион.

---

## 2. Решение

### 2.1. Архитектура

```
┌─────────────────────────────────────────────────────────────────┐
│                    Пользователь (браузер)                       │
└─────────────────────────────────────────────────────────────────┘
                              │
                              │ DNS запрос: aistudio.google.com
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    dnsmasq (роутер Keenetic)                     │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │  /opt/etc/unblock-ai.dnsmasq                              │  │
│  │  server=/aistudio.google.com/127.0.0.1#40500             │  │
│  └───────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              │ DNS запрос через VPN DNS
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│              Shadowsocks / Xray / Tor (VPN DNSPort)             │
│                    Порт 40500 (DNS-over-TCP)                     │
└─────────────────────────────────────────────────────────────────┘
                              │
                              │ Запрос через VPN канал
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Внешний DNS (8.8.8.8)                         │
│                    Возвращает правильный IP                      │
└─────────────────────────────────────────────────────────────────┘
```

### 2.2. Компоненты

| Компонент | Файл | Назначение |
|-----------|------|------------|
| **DNS Spoofing Module** | `core/dns_spoofing.py` | Генерация конфигурации dnsmasq |
| **AI Domains List** | `resources/lists/unblock-ai-domains.txt` | Список доменов для обхода |
| **dnsmasq Config** | `/opt/etc/unblock-ai.dnsmasq` | Правила для dnsmasq |
| **Web UI** | `templates/dns_spoofing.html` | Управление через веб-интерфейс |
| **Routes** | `routes.py` | API endpoints |

---

## 3. Технические детали

### 3.1. Конфигурация dnsmasq

Файл: `/opt/etc/unblock-ai.dnsmasq`

```conf
# AI Domains DNS Spoofing
# Все DNS-запросы к AI-доменам направляются через VPN DNS (порт 40500)

# Google AI Studio
server=/aistudio.google.com/127.0.0.1#40500

# Gemini
server=/gemini.google.com/127.0.0.1#40500

# Google Colab
server=/colab.research.google.com/127.0.0.1#40500

# Kaggle
server=/kaggle.com/127.0.0.1#40500
```

### 3.2. Интеграция с VPN

#### Shadowsocks
```json
{
  "dns": "8.8.8.8",
  "dns_port": 40500
}
```

#### Xray (VLESS)
```json
{
  "dns": {
    "servers": [
      {
        "address": "8.8.8.8",
        "port": 40500
      }
    ]
  }
}
```

#### Tor
```conf
DNSPort 127.0.0.1:40500
```

### 3.3. Алгоритм работы

1. **Инициализация:**
   - Загрузка списка AI-доменов из `unblock-ai-domains.txt`
   - Генерация конфигурации `/opt/etc/unblock-ai.dnsmasq`
   - Перезапуск dnsmasq

2. **DNS-запрос:**
   - Пользователь запрашивает `aistudio.google.com`
   - dnsmasq проверяет правила в `unblock-ai.dnsmasq`
   - Запрос перенаправляется на `127.0.0.1:40500` (VPN DNSPort)
   - VPN резолвит домен через внешний DNS
   - Возвращается правильный IP

3. **HTTP-запрос:**
   - Браузер подключается к полученному IP
   - Трафик маршрутизируется через VPN (ipset + iptables)
   - Сервис видит IP VPN, а не реальный регион

---

## 4. Реализация

### 4.1. Модуль dns_spoofing.py

```python
"""
DNS Spoofing Module - AI Domain Bypass

Generates dnsmasq configuration for routing AI domain DNS queries through VPN.
"""

AI_DOMAINS_LIST = '/opt/etc/unblock/ai-domains.txt'
DNSMASQ_AI_CONFIG = '/opt/etc/unblock-ai.dnsmasq'
VPN_DNS_PORT = 40500

def load_ai_domains() -> List[str]:
    """Load AI domains from list file"""
    ...

def generate_dnsmasq_config(domains: List[str]) -> str:
    """Generate dnsmasq configuration for AI domains"""
    ...

def apply_config() -> Tuple[bool, str]:
    """Apply dnsmasq configuration and restart"""
    ...

def get_status() -> Dict[str, Any]:
    """Get current spoofing status"""
    ...
```

### 4.2. Обновление unblock_dnsmasq.sh

Добавить секцию для AI-доменов:

```bash
# AI Domains DNS Spoofing
if [ -f "/opt/etc/unblock/ai-domains.txt" ]; then
    echo "# AI Domains" >> /opt/etc/unblock-ai.dnsmasq
    while read -r domain; do
        [ -z "$domain" ] && continue
        [ "${domain:0:1}" = "#" ] && continue
        echo "server=/$domain/127.0.0.1#$VPN_DNS_PORT" >> /opt/etc/unblock-ai.dnsmasq
    done < /opt/etc/unblock/ai-domains.txt
fi
```

### 4.3. Веб-интерфейс

#### Страница `/dns-spoofing`
- Список AI-доменов с чекбоксами
- Кнопка "Включить/Выключить"
- Статус: "Активен" / "Выключен"
- Логи применения конфигурации

#### API Endpoints
| Endpoint | Method | Описание |
|----------|--------|----------|
| `/dns-spoofing` | GET | Страница управления |
| `/dns-spoofing/apply` | POST | Применить конфигурацию |
| `/dns-spoofing/disable` | POST | Выключить DNS-обход |
| `/dns-spoofing/status` | GET | Текущий статус |

---

## 5. Тестирование

### 5.1. Проверка DNS

```bash
# Через dnsmasq
dig @192.168.1.1 aistudio.google.com

# Ожидается: IP через VPN
```

### 5.2. Проверка маршрутизации

```bash
# Проверка ipset
ipset list unblocksh | grep aistudio

# Проверка iptables
iptables-save -t nat | grep 1082
```

### 5.3. Проверка доступности

```bash
# Через curl с прокси
curl -x socks5h://127.0.0.1:1082 https://aistudio.google.com

# Ожидается: 200 OK
```

---

## 6. Безопасность

### 6.1. Риски
- **DNS leak:** Если VPN DNS недоступен, запросы могут уйти через локальный DNS
- **MitM:** Подмена DNS-ответов злоумышленником

### 6.2. Защита
- ✅ Проверка доступности VPN DNS перед применением
- ✅ Graceful fallback при ошибке
- ✅ Логирование всех изменений
- ✅ Валидация доменов (только буквенные)

---

## 7. Производительность

### 7.1. Ресурсы
| Параметр | Значение |
|----------|----------|
| Память | ~1MB (dnsmasq + кэш) |
| CPU | Минимальное (только при старте) |
| Место | ~50KB (конфиг) |

### 7.2. Оптимизация для KN-1212
- Кэширование DNS-ответов (1536 записей)
- Lazy loading конфигурации
- Минимальное количество перезапусков dnsmasq

---

## 8. Зависимости

### 8.1. Обязательные
- ✅ dnsmasq (установлен по умолчанию)
- ✅ Shadowsocks/Xray/Tor с DNSPort
- ✅ Python 3.8+

### 8.2. Опциональные
- ⚠️ DNS-over-TLS (DoT) для дополнительной защиты
- ⚠️ Split-horizon DNS для сложных сценариев

---

## 9. Критерии завершения

- ✅ Список AI-доменов создан
- ✅ Модуль dns_spoofing.py реализован
- ✅ Конфигурация dnsmasq генерируется
- ✅ Веб-интерфейс управления
- ✅ Тесты проходят
- ✅ Документация готова

---

## 10. Приложения

### A. Список AI-доменов
См. `resources/lists/unblock-ai-domains.txt`

### B. Пример конфигурации
См. `resources/config/unblock-ai.dnsmasq.template`

### C. Скрипт проверки
См. `scripts/check_dns_spoofing.sh`
