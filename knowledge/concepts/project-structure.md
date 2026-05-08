---
title: "Project Structure & Tech Stack"
aliases: [project-structure, tech-stack, directory-layout, file-map]
tags: [architecture, infrastructure, reference]
sources:
  - "CLAUDE.md (migrated 2026-04-14)"
created: 2026-04-14
updated: 2026-04-14
---

## Tech Stack

| Компонент       | Технология                       | Назначение                                        |
| --------------- | -------------------------------- | ------------------------------------------------- |
| Оркестрация     | n8n (self-hosted)                | Workflow, Telegram routing, AI                    |
| База данных     | Supabase (PostgreSQL 17.6)       | Всё: users, food logs, gamification, translations |
| Background Jobs | Python + APScheduler 3.10        | Cron: mana, streak, leagues, reminders            |
| Webhooks        | Python + FastAPI 0.115 + Uvicorn | Stripe/TON payment webhooks                       |
| HTTP Client     | httpx 0.27                       | Async запросы к Supabase REST + Telegram API      |
| Payments        | Stripe SDK 11.0                  | Подписки, checkout, webhooks                      |
| Deploy          | systemd + rsync                  | 2 сервиса: noms-cron, noms-webhooks               |
| Сервер          | VPS (89.167.86.20)               | Linux, user: taskbot                              |

## Directory Layout

> Python-код лежит прямо в корне NOMS/ (зеркало структуры VPS `/home/taskbot/noms/`).

```
NOMS/
├── main.py                         # APScheduler entry point (UTC)
├── config.py                       # Env vars + rate limiting config
├── webhook_server.py               # FastAPI: Stripe webhooks + checkout
├── supabase_client.py              # Async httpx wrapper для Supabase
├── telegram_client.py              # Async Bot API с rate limiting
├── requirements.txt
├── noms-cron.service               # systemd unit (APScheduler)
├── noms-webhooks.service           # systemd unit (FastAPI)
├── deploy.sh                       # Скрипт деплоя на VPS (rsync)
├── crons/
│   ├── base.py                     # BaseCron abstract class
│   ├── mana_reset.py               # Hourly: mana regen + daily counters
│   ├── streak_checker.py           # Hourly: streak freeze/break
│   ├── league_cycle.py             # Monday 12:00 UTC: rankings
│   ├── referral_unlock.py          # Hourly: escrow unlock
│   ├── reminders.py                # Hourly: 7 типов напоминаний
│   ├── subscription_lifecycle.py   # Daily: expiry check
│   └── ton_payment_checker.py      # Every 5 min: TON blockchain poll
├── utils/
│   └── timezone_helpers.py
│
├── n8n_workflows/                  # n8n workflow JSONs (архивные)
├── n8n_code_nodes/                 # JS code nodes для n8n
│   ├── dispatcher_route_classifier_v1.6.js  # Главный роутер
│   ├── onboarding_engine.js        # 8-step регистрация
│   ├── response_builder.js         # Форматирование ответов
│   ├── dispatcher_payment_nodes.js # Payment routing
│   └── after_lang_builder.js       # Post-language selection
│
├── migrations/                     # SQL миграции (001-062+)
├── Master Blueprint 3.0.md         # Основной PRD
├── claude-memory-compiler/         # Knowledge Base (concepts, daily logs)
└── deploy.sh                       # Скрипт деплоя
```
