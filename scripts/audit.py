"""
Audit the knowledge base for cleanup candidates — deterministic, no LLM, $0.

Complements lint.py. Where lint checks structural health (broken links, missing
backlinks), audit hunts for *redundancy and decay* so the KB stays navigable as
it grows faster than anyone can read it:

  - merge candidates  pairs of concepts with high lexical overlap (SHORTLIST only —
                      see the honesty note below)
  - orphans           concepts absent from index.md AND with zero inbound wikilinks
  - stale             concepts whose effective date is older than --stale-days (default 60),
                      flagged harder when tagged with a superseded tech stack (n8n/legacy)
  - domain map        every concept grouped by its frontmatter tags, sorted newest-first,
                      so an agent resolving a contradiction knows which file is authoritative

## Honesty note on merge candidates

Lexical overlap (shared words / 2-grams) cannot reliably tell a *duplicate* from
two articles that simply share a topic's vocabulary. On a curated KB the real
duplicates have usually already been merged, so the surviving signal is weak and
noisy. This script therefore emits merge candidates as a *recall-oriented
shortlist* — a short list to eyeball, NOT a verdict. The kb-close skill decides
auto-merge vs. propose by actually *reading* each candidate pair; a raw score
must never trigger an unattended merge, or two distinct articles that merely
share words could be destroyed.

It NEVER edits or deletes anything. It reads the KB and writes two reports:
  reports/audit-YYYY-MM-DD.md    human-readable
  reports/audit-YYYY-MM-DD.json  machine-readable, consumed by the kb-close skill

Usage:
    uv run python scripts/audit.py
    uv run python scripts/audit.py --stale-days 90 --dup-threshold 0.45 --max-candidates 15
    uv run python scripts/audit.py --json-only
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from datetime import date, datetime
from pathlib import Path

from config import CONCEPTS_DIR, INDEX_FILE, REPORTS_DIR, today_iso
from utils import extract_wikilinks, list_wiki_articles

# Tech stacks the project has migrated away from. A concept tagged with these is
# more likely to be superseded — surfaced as a stronger staleness signal so the
# agent revisits it even if its date is recent (a tag can outlive a rewrite).
SUPERSEDED_TAGS = {"n8n", "legacy-n8n", "n8n-migration", "legacy"}

# Status markers already present in the KB. A concept the team has *already*
# triaged (legacy/superseded/duplicate/stale banner) is not a fresh finding, so
# we down-rank it rather than re-reporting noise every run.
TRIAGED_MARKERS = ("🏛", "💤", "status: superseded", "status: legacy",
                   "status: outdated", "status: duplicate", "OUTDATED")

# Tiny Russian+English stopword set. We only need to strip the highest-frequency
# glue words so that lexical overlap reflects topical vocabulary, not grammar.
STOPWORDS = set(
    "и в во не на что он но за то же ты к у из за по о от так вот для как а бы или это "
    "эта этот эти те все уже да нет если мы вы они их его ее там тут чтобы при над под "
    "без про между быть был была было были есть это того этого чем тем когда где".split()
) | set("the a an and or of to in for on is are be was were this that with as by it".split())


# ── Frontmatter + dates ────────────────────────────────────────────────

def parse_frontmatter(text: str) -> dict:
    """Extract a shallow YAML-ish frontmatter block. Good enough for our fields
    (title, tags, created, updated, status); we don't need a full YAML parser."""
    if not text.startswith("---"):
        return {}
    end = text.find("\n---", 3)
    if end == -1:
        return {}
    meta: dict = {}
    for line in text[3:end].splitlines():
        m = re.match(r"^(\w+):\s*(.*)$", line)
        if not m:
            continue
        key, val = m.group(1), m.group(2).strip()
        if val.startswith("[") and val.endswith("]"):
            val = [v.strip().strip('"\'') for v in val[1:-1].split(",") if v.strip()]
        else:
            val = val.strip('"\'')
        meta[key] = val
    return meta


def git_last_date(path: Path) -> str | None:
    """Last commit date (YYYY-MM-DD) for a file, or None if not tracked."""
    try:
        out = subprocess.run(
            ["git", "log", "-1", "--format=%cs", "--", str(path)],
            cwd=path.parent, capture_output=True, text=True, timeout=10,
        )
        return out.stdout.strip() or None
    except Exception:
        return None


def effective_date(path: Path, meta: dict) -> tuple[str, str]:
    """Best-known 'last touched' date and where it came from. Frontmatter is
    authoritative; we fall back to git, then filesystem mtime, so concepts that
    predate the frontmatter convention still get a real age."""
    for key in ("updated", "created"):
        val = meta.get(key)
        if isinstance(val, str) and re.match(r"\d{4}-\d{2}-\d{2}", val):
            return val[:10], f"frontmatter:{key}"
    g = git_last_date(path)
    if g:
        return g, "git"
    return datetime.fromtimestamp(path.stat().st_mtime).strftime("%Y-%m-%d"), "mtime"


def days_since(iso_date: str) -> int:
    try:
        return (date.today() - date.fromisoformat(iso_date)).days
    except ValueError:
        return 0


# ── Lexical overlap (merge-candidate shortlist) ────────────────────────

def tokenize_body(text: str) -> list[str]:
    """Lowercase word tokens from the article body, frontmatter and code/links
    stripped so overlap reflects prose, not shared boilerplate or paths."""
    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end != -1:
            text = text[end + 4:]
    text = re.sub(r"```.*?```", " ", text, flags=re.DOTALL)
    text = re.sub(r"\[\[[^\]]+\]\]", " ", text)
    text = re.sub(r"[^\w\s]", " ", text.lower())
    return text.split()


def sig_words(tokens: list[str]) -> set[str]:
    """Significant words: length > 3 and not a stopword. Filtering grammar glue
    keeps overlap focused on a concept's actual vocabulary."""
    return {w for w in tokens if len(w) > 3 and w not in STOPWORDS}


def bigrams(tokens: list[str]) -> set[str]:
    """Adjacent word pairs — a coarse phrase signal. Two files sharing many
    2-grams are more likely genuinely redundant than ones sharing loose words."""
    return {f"{tokens[i]} {tokens[i + 1]}" for i in range(len(tokens) - 1)}


def containment(a: set[str], b: set[str]) -> float:
    """|A∩B| / min(|A|,|B|): how much of the *smaller* set the larger absorbs —
    the right shape for 'most of one file already lives in the other'."""
    if not a or not b:
        return 0.0
    return len(a & b) / min(len(a), len(b))


# ── Load + checks ──────────────────────────────────────────────────────

def load_concepts() -> list[dict]:
    concepts = []
    for path in list_wiki_articles():
        if path.parent != CONCEPTS_DIR:
            continue
        text = path.read_text(encoding="utf-8")
        meta = parse_frontmatter(text)
        eff_date, date_src = effective_date(path, meta)
        tags = meta.get("tags", [])
        if isinstance(tags, str):
            tags = [tags]
        tokens = tokenize_body(text)
        head = text[:400]
        concepts.append({
            "file": f"concepts/{path.name}",
            "name": path.stem,
            "tags": tags,
            "date": eff_date,
            "date_source": date_src,
            "age_days": days_since(eff_date),
            "triaged": any(m in head or m in str(meta.get("status", "")) for m in TRIAGED_MARKERS),
            "words": sig_words(tokens),
            "bigrams": bigrams(tokens),
            "links": [l for l in extract_wikilinks(text) if not l.startswith("daily/")],
        })
    return concepts


def find_merge_candidates(concepts: list[dict], word_thr: float,
                          bigram_floor: float, max_candidates: int) -> list[dict]:
    """Recall-oriented shortlist. A pair qualifies when word-overlap clears
    word_thr AND 2-gram overlap clears bigram_floor (the precision gate that
    kills pure-vocabulary coincidences). Ranked by the product of the two and
    capped, because this is a list to eyeball, not an exhaustive verdict."""
    rows = []
    for i in range(len(concepts)):
        for j in range(i + 1, len(concepts)):
            a, b = concepts[i], concepts[j]
            wc = containment(a["words"], b["words"])
            gc = containment(a["bigrams"], b["bigrams"])
            if wc < word_thr or gc < bigram_floor:
                continue
            if a["date"] != b["date"]:
                canonical, redundant = (a, b) if a["date"] >= b["date"] else (b, a)
            else:
                canonical, redundant = (a, b) if len(a["words"]) >= len(b["words"]) else (b, a)
            rows.append({
                "redundant": redundant["file"],
                "canonical": canonical["file"],
                "word_overlap": round(wc, 3),
                "bigram_overlap": round(gc, 3),
                "score": round(wc * gc, 3),
                "hint": f"if truly redundant, fold {redundant['name']} into the newer "
                        f"{canonical['name']} ({canonical['date']}) and archive the original",
            })
    rows.sort(key=lambda r: r["score"], reverse=True)
    return rows[:max_candidates]


def find_orphans(concepts: list[dict]) -> list[dict]:
    index_text = INDEX_FILE.read_text(encoding="utf-8") if INDEX_FILE.exists() else ""
    inbound: dict[str, int] = {}
    for c in concepts:
        for link in c["links"]:
            inbound[link] = inbound.get(link, 0) + 1
    orphans = []
    for c in concepts:
        link_target = c["file"].replace(".md", "")
        in_index = link_target in index_text or c["name"] in index_text
        if not in_index and inbound.get(link_target, 0) == 0:
            orphans.append({
                "file": c["file"],
                "reason": "not in index.md AND zero inbound links — invisible to other agents",
            })
    return orphans


def find_stale(concepts: list[dict], stale_days: int) -> list[dict]:
    stale = []
    for c in concepts:
        if c["triaged"]:
            continue  # already banner-flagged; not a fresh finding
        superseded_tag = sorted(set(c["tags"]) & SUPERSEDED_TAGS)
        old = c["age_days"] >= stale_days
        if not old and not superseded_tag:
            continue
        bits = []
        if old:
            bits.append(f"{c['age_days']}d old (date {c['date']} via {c['date_source']})")
        if superseded_tag:
            bits.append(f"tagged superseded stack: {', '.join(superseded_tag)}")
        stale.append({
            "file": c["file"],
            "age_days": c["age_days"],
            "tags": c["tags"],
            "reason": "; ".join(bits),
            "severity": "high" if (old and superseded_tag) else "warning",
        })
    stale.sort(key=lambda s: s["age_days"], reverse=True)
    return stale


def group_domains(concepts: list[dict]) -> dict[str, list[dict]]:
    domains: dict[str, list[dict]] = {}
    for c in concepts:
        for tag in (c["tags"] or ["(untagged)"]):
            domains.setdefault(tag, []).append({"file": c["file"], "date": c["date"]})
    for files in domains.values():
        files.sort(key=lambda f: f["date"], reverse=True)  # newest = authoritative first
    return dict(sorted(domains.items(), key=lambda kv: len(kv[1]), reverse=True))


# ── Reporting ──────────────────────────────────────────────────────────

def build_report(data: dict) -> str:
    L = [f"# KB Audit — {today_iso()}", ""]
    L += [f"**Concepts scanned:** {data['scanned']}  |  "
          f"merge candidates: {len(data['merge_candidates'])}  |  "
          f"orphans: {len(data['orphans'])}  |  "
          f"stale: {len(data['stale'])}", ""]

    L += ["## Merge candidates — LEXICAL SHORTLIST, verify by reading", "",
          "> Same-topic articles appear here too. These are NOT confirmed duplicates. "
          "Open both files before merging; never merge on the score alone.", ""]
    if data["merge_candidates"]:
        for d in data["merge_candidates"]:
            L.append(f"- `{d['redundant']}` ~ `{d['canonical']}` "
                     f"(words {d['word_overlap']}, 2-grams {d['bigram_overlap']}) — {d['hint']}")
    else:
        L.append("_none above threshold_")

    L += ["", "## Orphans (invisible to other agents)", ""]
    L += [f"- `{o['file']}` — {o['reason']}" for o in data["orphans"]] or ["_none_"]

    L += ["", "## Stale / superseded-stack", ""]
    L += [f"- **[{s['severity']}]** `{s['file']}` — {s['reason']}" for s in data["stale"]] or ["_none_"]

    L += ["", "## Domain map (newest first = authoritative on conflict)", ""]
    for domain, files in data["domains"].items():
        if len(files) < 2:
            continue
        newest = files[0]
        L.append(f"- **{domain}** ({len(files)}): authoritative `{newest['file']}` ({newest['date']})")
    L.append("")
    return "\n".join(L)


def main() -> int:
    p = argparse.ArgumentParser(description="Audit the knowledge base for cleanup candidates")
    p.add_argument("--stale-days", type=int, default=60)
    p.add_argument("--dup-threshold", type=float, default=0.45,
                   help="min significant-word containment to shortlist a pair")
    p.add_argument("--bigram-floor", type=float, default=0.12,
                   help="min 2-gram containment (precision gate against shared-vocabulary noise)")
    p.add_argument("--max-candidates", type=int, default=15)
    p.add_argument("--json-only", action="store_true")
    args = p.parse_args()

    print("Loading concepts...")
    concepts = load_concepts()
    print(f"  {len(concepts)} concepts")

    print("Finding merge candidates...")
    candidates = find_merge_candidates(concepts, args.dup_threshold, args.bigram_floor, args.max_candidates)
    print(f"  {len(candidates)} candidate pairs (shortlist)")

    print("Finding orphans...")
    orphans = find_orphans(concepts)
    print(f"  {len(orphans)} orphans")

    print(f"Finding stale (>{args.stale_days}d)...")
    stale = find_stale(concepts, args.stale_days)
    print(f"  {len(stale)} stale")

    data = {
        "date": today_iso(),
        "scanned": len(concepts),
        "params": {"stale_days": args.stale_days, "dup_threshold": args.dup_threshold,
                   "bigram_floor": args.bigram_floor, "max_candidates": args.max_candidates},
        "merge_candidates": candidates,
        "orphans": orphans,
        "stale": stale,
        "domains": group_domains(concepts),
    }

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    json_path = REPORTS_DIR / f"audit-{today_iso()}.json"
    json_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nJSON: {json_path}")

    if not args.json_only:
        md_path = REPORTS_DIR / f"audit-{today_iso()}.md"
        md_path.write_text(build_report(data), encoding="utf-8")
        print(f"Report: {md_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
