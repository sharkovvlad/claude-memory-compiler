# Hybrid Modal Routing Pattern (async overlay modal)

> Created 2026-05-24 from Phase 3c stress UX (mig 317) implementation.

## Problem

`save_via_callback=TRUE` headless pipeline calls the save_rpc inside SQL `process_user_input`, but Python never sees the RPC return value. You get clean headless navigation, but **you cannot react to safety gate outputs** (e.g., `show_modal=TRUE`, `reason='rpp_guard_active'`).

This matters when:
- A button triggers a potentially dangerous modifier (stress=high, dose-tracking, etc.)
- Clinical safety gates can return `show_modal=TRUE` signalling the caller to show an escalation message
- The user still needs to navigate forward (not blocked) — just gets an additional overlay

## Solution: Hybrid routing

One button in the screen bypasses `save_via_callback` and goes to a dedicated Python handler.

### DB button meta

```sql
-- Buttons that can trigger safety escalation: NO save_via_callback
-- (Python handler reads show_modal AFTER calling save_rpc directly)
INSERT INTO public.ui_screen_buttons ... VALUES (
    'stress_checkin', 2, 0, 'stress_checkin.button_high', 'cmd_stress_high',
    jsonb_build_object(
        'save_rpc',      'set_user_stress_label',
        'save_value',    'high',
        'target_screen', 'my_plan'
        -- ← NO 'save_via_callback': True
    )
);
```

### Router

The callback MUST be in `PROFILE_V5_CALLBACKS` in `dispatcher/router.py` → `target="menu_v3"` → Python handler. Without this, section 4l routes `cmd_*` to `target="menu"` → legacy n8n, bypassing the Python handler entirely.

```python
PROFILE_V5_CALLBACKS: frozenset[str] = frozenset({
    # ...existing...
    # mig 317: all stress buttons → menu_v3 (Python)
    "cmd_stress_none", "cmd_stress_moderate", "cmd_stress_high",
})
```

### Python handler (handlers/menu_v3.py)

Pattern: dispatch guard BEFORE the main `dispatch_with_render` call.

```python
# In handle_menu_v3(), before the main dispatch_with_render call:
if (decision.callback_data == "cmd_stress_high"
        or decision.synth_callback == "cmd_stress_high"):
    return await _handle_stress_high(ctx, decision, rpc_caller)
```

### _handle_stress_high implementation

```python
async def _handle_stress_high(ctx, decision, rpc_caller) -> ResponseEnvelope:
    items_pre = []
    # 1. Answer callback immediately to clear Telegram spinner
    if decision.callback_query_id:
        items_pre.append(OutboundItem(
            strategy="answer_callback_only",
            chat_id=ctx.telegram_id,
            callback_query_id=decision.callback_query_id,
        ))

    # 2. Call save_rpc directly → read show_modal
    save_result = await rpc_caller("set_user_stress_label",
        {"p_telegram_id": ctx.telegram_id, "p_value": "high"})
    save_result = (save_result[0] if isinstance(save_result, list) and save_result
                   else save_result or {})

    # 3. Navigate to my_plan via dispatch_with_render
    #    (no save_via_callback on button → SQL skips save_rpc, just navigates)
    rpc_nav = await rpc_caller("dispatch_with_render", {
        "p_telegram_id": ctx.telegram_id,
        "p_action_type": "callback",
        "p_payload": {"callback_data": "cmd_stress_high"},
        "p_cb_context": {"is_inline": True},
        "p_skip_debounce": True,    # already answered callback above
    })
    rpc_nav = (rpc_nav[0] if isinstance(rpc_nav, list) and rpc_nav else rpc_nav or {})

    # Build navigation envelope (my_plan), without re-answering callback
    nav_decision = SimpleNamespace(**{k: getattr(decision, k)
                                      for k in vars(decision)
                                      if not k.startswith("__")},
                                   callback_query_id=None)
    envelope = await _envelope_from_rpc_result(rpc_nav, ctx, nav_decision, rpc_caller)
    envelope.items = items_pre + envelope.items

    # 4. Append clinical modal overlay AFTER my_plan (async overlay)
    if save_result.get("show_modal"):
        reason = save_result.get("reason", "")
        modal_key = ("modifier.suppressed.rpp_guard"
                     if reason == "rpp_guard_active"
                     else "modifier.suppressed.teen_stress")
        fallback = "⚠️ Please speak with a healthcare professional."
        modal_text = _lookup_translation(ctx, modal_key) or fallback
        envelope.items.append(OutboundItem(
            strategy="send_new",
            chat_id=ctx.telegram_id,
            text=modal_text,
            parse_mode="HTML",
        ))
    return envelope
```

## Why not block navigation?

Clinical guidance decision: even when safety gate fires, the user has already recorded their stress (lifestyle log written unconditionally before gate). Blocking navigation would strand them. **Async overlay = they see my_plan + get additional clinical message.** This is the pattern for all Phase 3 safety modals.

## Call order matters

1. `answer_callback_query` — FIRST (clears spinner, Telegram 30s timeout)
2. `set_user_stress_label` — second (save + gate check)
3. `dispatch_with_render` — third (navigate to my_plan)
4. Modal overlay — appended last (rendered after navigation items)

## When to use this pattern

Use hybrid routing whenever:
- A button click can produce a safety gate output (`show_modal`, `show_supportive_banner`) that Python must react to
- The RPC has 3+ args (can't use `save_via_callback` 2-arg contract)
- The user must still navigate forward (overlay, not blocker)

Use `save_via_callback=TRUE` headless when:
- RPC is 2-arg `(p_telegram_id, p_value)` format
- No Python-readable output needed
- Pure navigation + save, no conditional overlays

## Isolation: simultaneous safe buttons

Other buttons on the same screen can still use `save_via_callback=TRUE`. Example:
- `cmd_stress_none` → save_via_callback=TRUE (headless, no modal risk)
- `cmd_stress_moderate` → save_via_callback=TRUE (headless)
- `cmd_stress_high` → hybrid Python handler (modal risk)

## Reference implementation

`handlers/menu_v3.py` → `_handle_stress_high` (mig 317, 2026-05-24)
`migrations/317_stress_modifier_ux.sql` → Section 5 ui_screen_buttons
`dispatcher/router.py` → PROFILE_V5_CALLBACKS stress entries

## Test pattern

```python
# T5 in test_phase3c_stress_ux.py: RPP gate
def test_T5_rpp_gate_cachexia(db_conn):
    _set_cachexia(cur)
    _set_premium(cur, True)
    result = _apply(cur, "stress", "high")
    assert result.get("show_modal") is True
    assert result.get("reason") == "rpp_guard_active"
    # lifestyle log still written (unconditional, before gate)
    m = _metrics(cur)
    assert m["stress_label_qualitative"] == "high"
```
