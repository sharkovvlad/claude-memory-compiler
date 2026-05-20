# systemd drop-in override pattern для persistent service config changes

> **Lesson date:** 2026-05-20 (food log Python cutover, PR C iteration v2).
> **Trigger:** main unit file (`/etc/systemd/system/X.service`) revertнулся после моего sed edit. Какой-то process (deploy.sh? cron? unknown) переписал.

## TL;DR

Для **persistent** изменений в systemd service config — используй **drop-in override** в директории `/etc/systemd/system/X.service.d/`, не edit'ь main unit. Override **survives** main unit revert / rsync / deploy.

## Pattern

```bash
mkdir -p /etc/systemd/system/<service>.service.d
cat > /etc/systemd/system/<service>.service.d/override.conf <<EOF
[Service]
ExecStart=
ExecStart=<new command with full path and args>
EOF
systemctl daemon-reload
systemctl restart <service>
```

**Critical:** empty `ExecStart=` clears the previous one, second `ExecStart=` provides new value. Без empty line systemd **concatenates** (running both), что обычно ломает service.

## Verify

```bash
systemctl cat <service>
# Shows main unit + drop-in override, в порядке overlay
```

```bash
systemctl show <service> -p ExecStart
# Shows effective ExecStart (post-override)
```

## When to use

✅ **Use drop-in override:**
- Bind address changes (`--host`)
- Env vars / EnvironmentFile additions
- Resource limits (LimitNOFILE, etc.)
- User/Group changes
- Any config that auto-deploy / rsync / parallel-agent edits might overwrite

❌ **NOT for:**
- Whole unit replacement (use full unit file).
- Adding new dependencies (Wants= / After=) — может interfere with main unit's logic.

## NOMS use case

webhook_server.py:
- **Main unit** (`/etc/systemd/system/noms-webhooks.service`): `--host 127.0.0.1 --port 8443` (loopback only, для Caddy edge). Этот unit потенциально editable by deploy.sh-related restart cycle.
- **Drop-in** (`/etc/systemd/system/noms-webhooks.service.d/override.conf`): `--host 0.0.0.0 --port 8443 --proxy-headers --forwarded-allow-ips="127.0.0.1"` (required for n8n container access via Docker bridge gateway 172.18.0.1).
- External port 8443 blocked by Hetzner Cloud Firewall → 0.0.0.0 bind безопасен.

## Diagnostic story

Initial fix: I edited main unit via `sed`, set `--host 0.0.0.0`, restarted. Worked. 5 minutes later — service restarted **by something else**, unit reverted, bind back to 127.0.0.1. Lost the fix.

Drop-in override **persisted** through subsequent restarts. Verified via:
```bash
systemctl restart noms-webhooks
ss -tlnp | grep 8443  # 0.0.0.0:8443 ✅ persistent
```

## Caveat: deploy.sh awareness

If deploy.sh rsyncs /etc/systemd/system/ from git (which would be unusual), drop-in override could be wiped. NOMS не делает этого (systemd configs are host state, не в git). Verify before relying на drop-in для critical services.

## Связано

- [[concepts/docker-bridge-networking-pattern]] — почему нужен 0.0.0.0 bind в первую очередь.
- [[concepts/release-protocol]] — auto-deploy через GitHub Actions, rsync scope.
- [[daily/2026-05-20]] — PR C iteration v2 chronology.
