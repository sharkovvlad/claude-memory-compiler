---
title: "Worktree vs main-clone — Edit по absolute path в неправильное место"
aliases: [worktree-edit-confusion, edit-path-trap, main-clone-vs-worktree]
tags: [process, git, worktree, gotcha, agent-discipline]
sources:
  - "daily/2026-06-08.md"
created: 2026-06-08
updated: 2026-06-08
---

# Worktree vs main-clone — Edit по absolute path в неправильное место

Агенты работают в git worktree (например `/Users/vladislav/Documents/NOMS/.claude/worktrees/dreamy-tharp-ab88d9/`), а не в основном клоне (`/Users/vladislav/Documents/NOMS/`). Это два **разных рабочих дерева**, шарят `.git/` базу, но имеют **независимые** наборы файлов и checkout'ов разных веток.

Тонкий gotcha: при использовании `Edit` / `Write` / `Read` инструментов агент может ошибочно указать **absolute path в основной клон** вместо worktree. Тесты всё равно пройдут (если запускаются из основного клона), но `git status` в worktree покажет **чистый state** — и агент не поймёт, что его правки лежат в чужом месте.

## Когда случается

- Bash-вызовы по умолчанию стартуют в **worktree** (cwd подтверждается харнессом), но если агент пишет явный `cd /Users/vladislav/Documents/NOMS &&`, он уходит в **основной клон**.
- `Edit` / `Write` принимают **absolute path**. Если агент пишет `/Users/vladislav/Documents/NOMS/services/foo.py` (без `.claude/worktrees/<name>/`), правка попадает в **основной клон**.
- Pytest, запущенный из основного клона, прочитает правки оттуда и зелёный тест ничего не докажет про worktree.

## Симптомы

```
worktree$ git status
On branch claude/dreamy-tharp-ab88d9
nothing to commit, working tree clean   ← должны быть мои правки!

worktree$ ls untracked-file-i-just-wrote.py
ls: untracked-file-i-just-wrote.py: No such file or directory  ← но я только что Write'нул!

# А в основном клоне:
main-clone$ git status
On branch claude/regional-eval-2026-06-08   ← чужая ветка!
Changes not staged for commit:
  modified: services/foo.py
  modified: tests/test_foo.py
Untracked: tests/test_foo_new.py
```

## Защитные правила

1. **`Edit` / `Write` всегда по worktree path.** Перед записью сверь начало пути с `system-reminder` working directory.
2. **`Bash` без явного `cd`** — он сам стартует в worktree. `cd /Users/vladislav/Documents/NOMS && ...` уводит в основной клон. Используй редко, только когда действительно нужен основной клон (например `gh pr merge` локально падает с `'main' is already used by worktree at ...` — тогда merge через GitHub API из основного клона).
3. **Sanity-check перед commit:** `git status` в worktree должен показать **все** твои изменения. Если показывает «clean» — правки ушли мимо.
4. **Восстановление, если попал:** скопировать файлы из основного клона в worktree (`cp /main-clone/path/file worktree/path/file`), откатить основной клон (`git checkout -- file`, `rm` untracked). Коммитить из worktree.

## Why this trap exists

- Документация Claude Code описывает worktree как «изолированная копия», и агенты подсознательно ожидают, что absolute path-ы будут как-то магически переадресовываться. Это не так — absolute path = absolute path, файловая система не знает про worktree.
- Тесты в основном клоне проходят, потому что **там тоже есть правка**. Зелёный pytest не доказывает, что правка в правильном месте.

## Live incident — 2026-06-08

В сессии PR #375 (sage payload-meta) агент писал правки в `services/sage.py` и `tests/services/test_sage.py` по path `/Users/vladislav/Documents/NOMS/services/sage.py` — это основной клон, не worktree. Миграцию `migrations/496_*.sql` написал в worktree path. Поймал на этапе `git status` (worktree был чист, кроме одной миграции). Перенёс файлы через `cp` + откатил основной клон через `git checkout --`. Чисто.

**Хорошая практика:** перед любым `Edit`/`Write` свериться с system-reminder «Working directory: /…/worktrees/<name>/», и **префикс path начинать с этого пути**, а не с `/Users/vladislav/Documents/NOMS/`.

## Related Concepts

- [[concepts/release-protocol]] — почему `./deploy.sh` ТОЛЬКО из основного клона из чистого main (rsync race)
- [[concepts/migration-collision-guard]] — параллельная работа в worktree'ах
