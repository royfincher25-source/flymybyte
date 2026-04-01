# Инструкция по DNS-обходу AI-доменов

**Дата:** 23 марта 2026 г.  
**Версия:** 1.0

---

## 1. Назначение

DNS-обход AI-доменов предназначен для обхода региональных блокировок AI-сервисов Google:
- Google AI Studio (aistudio.google.com)
- Gemini (gemini.google.com)
- Google Colab (colab.research.google.com)
- Kaggle (kaggle.com)
- и других

**Принцип работы:** DNS-запросы к указанным доменам направляются через VPN DNS (порт 40500), что скрывает ваш реальный регион от AI-сервисов.

---

## 2. Быстрый старт

### 2.1. Через веб-интерфейс (рекомендуется)

1. Откройте веб-интерфейс: `http://192.168.1.1:8080`
2. Перейдите в **Сервис** → **DNS-обход AI** → **Настроить**
3. Нажмите **Загрузить готовый список**
4. Нажмите **Применить**
5. Проверьте статус: должен быть "✅ Активен"

### 2.2. Через SSH (альтернативный)

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

---

## 3. Настройка

### 3.1. Добавление доменов

#### Через веб-интерфейс:

1. Откройте `/dns-spoofing`
2. В поле "Домены для обхода" введите домены (по одному в строке):
   ```
   aistudio.google.com
   gemini.google.com
   colab.research.google.com
   ```
3. Нажмите **Сохранить**
4. Нажмите **Применить**

#### Вручную:

```bash
# 1. Откройте файл списка
nano /opt/etc/unblock/ai-domains.txt

# 2. Добавьте домены (по одному в строке)
aistudio.google.com
gemini.google.com
colab.research.google.com

# 3. Сохраните (Ctrl+O, Enter, Ctrl+X)

# 4. Примените
sh /opt/etc/web_ui/resources/scripts/unblock_dnsmasq.sh
```

### 3.2. Wildcard домены

Поддерживаются wildcard домены вида `*.example.com`:

```
*.google.com
*.googleusercontent.com
```

При применении wildcard автоматически преобразуется в базовый домен (`google.com`).

---

## 4. Проверка работы

### 4.1. Через веб-интерфейс

1. Откройте `/dns-spoofing`
2. В секции "Тестирование DNS" введите домен (например, `aistudio.google.com`)
3. Нажмите **Тест**
4. Проверьте результат:
   - ✅ **Разрешён** — показаны IP адреса
   - ❌ **Ошибка** — проблема с разрешением

### 4.2. Через SSH

```bash
# 1. Проверьте конфигурацию dnsmasq
cat /opt/etc/unblock-ai.dnsmasq

# Ожидается:
# address=/aistudio.google.com/127.0.0.1#40500
# server=/aistudio.google.com/127.0.0.1#40500

# 2. Проверьте разрешение домена
nslookup aistudio.google.com 192.168.1.1

# Ожидается: IP адрес (не блокируемый)

# 3. Проверьте логи
tail -50 /opt/var/log/unblock_dnsmasq.log
```

### 4.3. Проверка доступности AI-сервисов

```bash
# 1. Через curl с прокси
curl -x socks5h://127.0.0.1:1082 https://aistudio.google.com

# Ожидается: 200 OK или редирект

# 2. Через браузер
# Откройте https://aistudio.google.com
# Должен открыться без ошибки региона
```

---

## 5. Управление

### 5.1. Включение

**Веб-интерфейс:**
1. `/dns-spoofing` → **Применить**

**SSH:**
```bash
sh /opt/etc/web_ui/resources/scripts/unblock_dnsmasq.sh
```

### 5.2. Выключение

**Веб-интерфейс:**
1. `/dns-spoofing` → **Выключить**

**SSH:**
```bash
rm /opt/etc/unblock-ai.dnsmasq
/opt/etc/init.d/S56dnsmasq restart
```

### 5.3. Обновление списка доменов

**Веб-интерфейс:**
1. `/dns-spoofing` → **Загрузить готовый список** → **Сохранить** → **Применить**

**SSH:**
```bash
curl -sL -o /opt/etc/unblock/ai-domains.txt \
  https://raw.githubusercontent.com/royfincher25-source/flymybyte/master/src/web_ui/resources/lists/unblock-ai-domains.txt
sh /opt/etc/web_ui/resources/scripts/unblock_dnsmasq.sh
```

---

## 6. Troubleshooting

### 6.1. DNS-обход не включается

**Проблема:** Статус "❌ Выключен" после применения

**Решение:**
```bash
# 1. Проверьте наличие списка доменов
ls -la /opt/etc/unblock/ai-domains.txt

# 2. Проверьте dnsmasq
ps | grep dnsmasq
# Ожидается: процесс запущен

# 3. Перезапустите dnsmasq
/opt/etc/init.d/S56dnsmasq restart

# 4. Проверьте логи
tail -50 /opt/var/log/unblock_dnsmasq.log
```

### 6.2. Домены не разрешаются

**Проблема:** Тест DNS показывает ошибку

**Решение:**
```bash
# 1. Проверьте конфигурацию
cat /opt/etc/unblock-ai.dnsmasq

# 2. Проверьте VPN DNS (порт 40500)
netstat -tlnp | grep 40500

# 3. Проверьте Shadowsocks/Xray/Tor
ps | grep -E "ss-redir|xray|tor"

# 4. Перезапустите VPN сервис
# Для Shadowsocks:
/opt/etc/init.d/S22shadowsocks restart
```

### 6.3. AI-сервисы всё ещё блокируют

**Проблема:** Доступ есть, но сервис определяет регион

**Решение:**
1. **Очистите кэш DNS в браузере:**
   - Chrome: `chrome://net-internals/#dns` → Clear host cache
   - Firefox: `about:networking#dns` → Clear DNS Cache

2. **Перезапустите браузер**

3. **Проверьте IP VPN:**
   ```bash
   curl -x socks5h://127.0.0.1:1082 https://api.ipify.org
   # Ожидается: IP другой страны
   ```

4. **Проверьте маршрутизацию:**
   ```bash
   # Проверьте ipset
   ipset list unblocksh
   
   # Проверьте iptables
   iptables-save -t nat | grep 1082
   ```

### 6.4. dnsmasq не запускается

**Проблема:** Ошибка при перезапуске dnsmasq

**Решение:**
```bash
# 1. Проверьте конфигурацию на ошибки
dnsmasq --test --conf-file=/opt/etc/dnsmasq.conf

# 2. Проверьте логи
logread | grep dnsmasq

# 3. Временно отключите AI конфиг
mv /opt/etc/unblock-ai.dnsmasq /opt/etc/unblock-ai.dnsmasq.bak
/opt/etc/init.d/S56dnsmasq restart

# 4. Если запустился — проблема в AI конфиге
cat /opt/etc/unblock-ai.dnsmasq.bak
# Проверьте на неправильные домены
```

---

## 7. Логи

### 7.1. Просмотр логов

**Веб-интерфейс:**
1. `/dns-spoofing` → секция "Логи" → **Обновить логи**

**SSH:**
```bash
# Последние 50 строк
tail -50 /opt/var/log/unblock_dnsmasq.log

# В реальном времени
tail -f /opt/var/log/unblock_dnsmasq.log

# Поиск ошибок
grep -i error /opt/var/log/unblock_dnsmasq.log
```

### 7.2. Уровень логирования

По умолчанию логируются:
- ✅ Применение конфигурации
- ✅ Перезапуск dnsmasq
- ⚠️ Ошибки валидации доменов
- ⚠️ Ошибки перезапуска dnsmasq

---

## 8. Производительность

### 8.1. Ресурсы

| Параметр | Значение |
|----------|----------|
| Память | ~1MB (dnsmasq + кэш) |
| CPU | Минимальное (только при старте) |
| Место | ~50KB (конфиг) |
| DNS кэш | 1536 записей |

### 8.2. Оптимизация для KN-1212

- ✅ Кэширование DNS-ответов
- ✅ Lazy loading конфигурации
- ✅ Минимальное количество перезапусков

---

## 9. Безопасность

### 9.1. Риски

| Риск | Описание | Защита |
|------|----------|--------|
| **DNS leak** | Если VPN DNS недоступен, запросы уходят через локальный DNS | Проверка доступности VPN DNS перед применением |
| **MitM** | Подмена DNS-ответов злоумышленником | Валидация доменов, логирование изменений |
| **Конфигурация** | Повреждение файла конфигурации | Atomic write через .tmp файл |

### 9.2. Рекомендации

1. **Регулярно обновляйте список доменов**
2. **Проверяйте логи после применения**
3. **Используйте готовые списки из репозитория**

---

## 10. Список AI-доменов

### 10.1. Базовый список

```
# Google AI Studio
aistudio.google.com

# Gemini
gemini.google.com

# Google Colab
colab.research.google.com
colab.google.com

# Kaggle
kaggle.com
kaggleusercontent.com

# Google DeepMind
deepmind.google
deepmind.com

# Google Cloud AI
cloud.google.com
console.cloud.google.com

# TensorFlow
tensorflow.org

# Google AI
ai.google.com

# Google APIs
generativelanguage.googleapis.com
ml.googleapis.com

# Google Research
research.google.com

# Google Notebooks
notebooks.googleusercontent.com

# Google Script
script.google.com
```

### 10.2. Обновление списка

Список обновляется в репозитории:
- Файл: `src/web_ui/resources/lists/unblock-ai-domains.txt`
- URL: https://github.com/royfincher25-source/flymybyte

---

## 11. Поддержка

### 11.1. Документация

- Дизайн-документ: `docs/DNS_SPOOFING_DESIGN.md`
- README: `README.md`

### 11.2. Проблемы и предложения

https://github.com/royfincher25-source/flymybyte/issues

---

## 12. FAQ

### Q: Чем DNS-обход отличается от обычного обхода через VPN?

**A:** DNS-обход маршрутизирует только DNS-запросы через VPN DNS, тогда как обычный обход маршрутизирует весь трафик через VPN. DNS-обход легче и быстрее, но работает только для обхода DNS-блокировок.

### Q: Можно ли использовать DNS-обход без VPN?

**A:** Нет, DNS-обход требует настроенный VPN (Shadowsocks, Xray, Tor) с DNSPort (порт 40500).

### Q: Как часто обновлять список доменов?

**A:** По мере необходимости. Если AI-сервисы начинают блокировать — обновите список.

### Q: Влияет ли DNS-обход на скорость доступа?

**A:** Минимально. DNS-запросы идут через VPN DNS, что добавляет ~10-50ms к разрешению домена. Кэширование dnsmasq компенсирует задержку.

### Q: Можно ли добавить свои домены?

**A:** Да, через веб-интерфейс или вручную в файл `/opt/etc/unblock/ai-domains.txt`.
