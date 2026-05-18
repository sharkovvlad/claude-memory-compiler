# NLM Sync Infrastructure — NOMS

## Блокнот

**NOMS Supabase Data** — единый RAG-блокнот для всего стека NOMS.
- ID: `fa75f4de-96c2-4dc0-bc9d-0bf07bd992f5`
- Лимит: 300 источников (NotebookLM Pro)
- Текущий размер: ~212 источников

## 3 слоя

### Слой 1 — Supabase DB (ежедневно 02:05)

**Scheduled task:** `~/.claude/scheduled-tasks/noms-supabase-sync/SKILL.md`
**Ручная команда:** `/nlm-noms`

Экспортирует все публичные таблицы + RPC-функции через `supabase_source.py`.
Источники: `{tablename}_{date}.md` (без специального префикса).
Логика обновления: удаляет источники с именем текущей таблицы → загружает новые.

### Слой 2 — n8n Workflows (каждые 2 дня 02:00)

**Scheduled task:** `~/.claude/scheduled-tasks/noms-n8n-backup/SKILL.md`

**Архитектура:**
1. `n8n_backup.py --force` — SSH tunnel Mac→VPS:5678 → скачивает все воркфлоу в `json архив/n8n_YYYY.MM.DD/`
2. `n8n_to_markdown.py --active-only` — конвертирует активные воркфлоу в Markdown
3. Удаляет все `n8n_*` источники из NLM → загружает новые

**Конфигурация SSH:**
- `.env`: `N8N_SSH_HOST=root@89.167.86.20`
- API key получается с VPS: `grep ^N8N_TARGET_API_KEY= /home/noms/n8n/compose/.env`
- Туннель: `local:15678 → VPS:127.0.0.1:5678`

Источники: `n8n_{workflow_name}_{date}.md` + `n8n_index_{date}.md`.

**n8n Архив-папки:** воркфлоу с `folderId != null` — в папке. `/api/v1/folders` возвращает 404 (CE-версия не поддерживает). Фильтрация архивных воркфлоу: деактивировать перед перемещением в "Архив" → `--active-only` исключит их автоматически.

### Слой 3 — Python/JS Код (ежедневно 03:00)

**Scheduled task:** `~/.claude/scheduled-tasks/noms-code-sync/SKILL.md`
**Ручная команда:** `/nlm-noms-code`

Инкрементальный синк: SHA-256 манифест `.nlm_code_manifest.json`.
Сканирует: `**/*.py`, `n8n_code/**/*.js`, `n8n_code_nodes/**/*.js`, `CLAUDE.md`.
Исключения: `.venv`, `__pycache__`, `_archive`, `json архив`, `Дизайн`, `.git`, `.obsidian`.
Оборачивает `.py`/`.js` в `.md` перед загрузкой (NLM отклоняет raw code).

**⚠️ Важно:** перед синком выполняется `git pull origin main --ff-only` — код берётся с **локального диска**, который должен совпадать с GitHub main.

Источники: `code_py_{stem}_{date}.py`, `code_js_{stem}_{date}.js`, `code_docs_CLAUDE_{date}.md`, `code_index_{date}.md`.

## Полный сброс и перезагрузка

При накоплении мусора (старые ручные загрузки, дубли):
```python
# Удалить все источники
notebooklm source list -n <NB_ID> --json | python3 -c "..."
# Сбросить manifest
rm /Users/vladislav/Documents/NOMS/.nlm_code_manifest.json
# Запустить все 3 синка: /nlm-noms, noms-n8n-backup, /nlm-noms-code
```

## NLM Сессия

**Проблема:** Google-куки протухают (~1 неделя). `auth check --json` говорит OK но реальные запросы падают с редиректом.
**Диагностика:** `notebooklm source list -n <NB_ID> --json` — если ошибка "Authentication expired" → сессия мертва.
**Лечение (только интерактивно):**
```bash
pkill -f "Google Chrome for Testing"  # убить если завис
source .venv/bin/activate && notebooklm login
# → откроется браузер → залогиниться → нажать ENTER → проверить дату storage_state.json
```

## Ключевые файлы

| Файл | Описание |
|---|---|
| `NOMS/scripts/n8n_backup.py` | SSH tunnel backup, `--force` флаг |
| `NOMS/scripts/n8n_to_markdown.py` | n8n JSON → Markdown конвертер |
| `NOMS/scripts/code_to_nlm.py` | Инкрементальный code sync |
| `NOMS/.nlm_code_manifest.json` | SHA-256 манифест для инкрементального синка |
| `NotebookLM+Claude/plugins/notebooklm-rag/scripts/supabase_source.py` | Supabase export |
| `NotebookLM+Claude/plugins/notebooklm-rag/scripts/nlm.py` | Batch upload + wait |
| `NotebookLM+Claude/plugins/notebooklm-rag/config/notebooks.json` | Реестр блокнотов |
