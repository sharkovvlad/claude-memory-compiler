---
title: "XP & Gamification Model"
aliases: [xp, gamification, economy]
tags: [gamification, core]
sources:
  - "daily/2026-04-08.md"
  - "daily/2026-04-10.md"
created: 2026-04-08
updated: 2026-04-14
---

# XP & Gamification Model

Three-tier economy: XP (social, weekly reset) + NomsCoins (persistent currency) + Mana (energy limiter).

## Key Points

- Text log=15XP, Photo/Voice=10XP, Fasting=15XP (soft cap 6 logs/day, 7+ = 0 XP)
- Day Closed (3+ logs)=50XP, Streak Keep=10XP/day, Quest=20XP
- Correction bonus=+5XP (max 3/day), Share=30XP (1/week)
- 8 Leagues: Onion > Pickle > Avocado > Chili > Tofu > Sashimi > Truffle > Lotus
- 60 levels + Prestige (5000XP per star after lvl 60)
- Free: 2 mana/day (regen 1/12h), Premium: 500+
- 6 gamification tables: xp_events, coin_transactions, levels_config, leagues, league_groups, league_memberships
- Key RPCs: log_meal_transaction, grant_xp, grant_nomscoins, spend_nomscoins, check_and_deduct_mana

## Related Concepts

- [[concepts/noms-architecture]]
- [[concepts/user-preferences]]
