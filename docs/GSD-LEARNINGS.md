# GSD Learnings — Система самообучения агента

## Обзор

GSD включает встроенную систему **learnings** для накопления и повторного использования знаний между сессиями и проектами.

## Как это работает

### Хранилище

- **Расположение:** `~/.gsd/knowledge/`
- **Формат:** Каждый learning — отдельный JSON файл
- **Дедупликация:** SHA-256 хэш контента + проект — идентичные записи не дублируются

### Структура записи

```json
{
  "id": "l1234abcd-5678efgh",
  "source_project": "FlyMyByte",
  "date": "2026-04-13T12:00:00.000Z",
  "context": "ipset troubleshooting",
  "learning": "Домены в bypass файлах не добавляются в ipset напрямую — они обрабатываются dnsmasq через ipset=/domain/ipset_name директивы...",
  "tags": ["ipset", "dnsmasq", "bypass", "troubleshooting"],
  "content_hash": "a1b2c3d4..."
}
```

## Команды

### Просмотр всех learnings

```bash
gsd-tools learnings list
```

### Поиск по тегу

```bash
gsd-tools learnings query --tag ipset
gsd-tools learnings query --tag dnsmasq
```

### Копирование из проекта

```bash
gsd-tools learnings copy
```

Копирует все секции из `.planning/LEARNINGS.md` текущего проекта в глобальное хранилище.

### Удаление старых

```bash
gsd-tools learnings prune --older-than 90d
```

Удаляет записи старше 90 дней.

### Удалить конкретную запись

```bash
gsd-tools learnings delete <id>
```

## Создание LEARNINGS.md

В каждой фазе можно создать файл `.planning/phases/XX-LEARNINGS.md`:

```markdown
## Диагностика ipset bypass

При анализе проблемы с пустым ipset обнаружено:
- Домены из vless.txt не добавляются в ipset напрямую
- Dnsmasq обрабатывает их через ipset=/domain/ipset_name
- Для работы нужно чтобы клиент сделал DNS запрос

## Полезные команды

ssh root@192.168.1.1 -p 222 "ipset -L unblockvless | grep -c '^[0-9]'"
```

**Формат:**
- `## Заголовок` — создаёт новый learning
- Тело после заголовка — содержимое learning
- Теги автоматически извлекаются из слов заголовка (>2 символов)

## Интеграция с workflow

При выполнении фазы (`/gsd-execute-phase`):

1. Шаг `auto_copy_learnings` запускается после завершения фазы
2. Читает `.planning/phases/*-LEARNINGS.md`
3. Копирует все секции в `~/.gsd/knowledge/`
4. Дедупликация происходит автоматически

## Пример использования

### Сессия 1: Диагностика проблемы

1. Обнаружил что ipset показывает 0 записей
2. Проверил код, нашёл что домены пропускаются в resolve_domains_for_ipset()
3. Зафиксировал в LEARNINGS.md

### Сессия 2: Продолжение

1. Запустил `gsd-tools learnings query --tag ipset`
2. Получил сохранённые знания о том как работает bypass
3. Не нужно заново разбираться в коде

## Конфигурация

Включено по умолчанию. Для отключения:

```bash
gsd-tools config-set features.global_learnings false
```

## Переносимость

Знания хранятся в `~/.gsd/knowledge/` — переносятся между машинами при синхронизации папки home.