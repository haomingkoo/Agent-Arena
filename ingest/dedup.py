"""
Content-based deduplication for discovered skills.

Three levels:
  1. Exact URL match
  2. Content hash (SHA-256 of normalized content)
  3. Fuzzy similarity (word trigram Jaccard)
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field

from evaluate.rubric import ParsedSkill


@dataclass
class DeduplicatedSkill:
    """A skill with its duplicates grouped together."""
    primary: ParsedSkill              # best version (most stars/installs)
    duplicates: list[ParsedSkill] = field(default_factory=list)
    content_hash: str = ""


def content_hash(text: str) -> str:
    """SHA-256 of whitespace-normalized, lowercased content."""
    normalized = " ".join(text.lower().split())
    return hashlib.sha256(normalized.encode()).hexdigest()


def word_trigrams(text: str) -> set[tuple[str, ...]]:
    """Extract word-level trigrams for fuzzy matching."""
    words = text.lower().split()
    if len(words) < 3:
        return {tuple(words)} if words else set()
    return {tuple(words[i:i + 3]) for i in range(len(words) - 2)}


def jaccard_similarity(a: set, b: set) -> float:
    """Jaccard index between two sets."""
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def _pick_primary(skills: list[ParsedSkill]) -> tuple[ParsedSkill, list[ParsedSkill]]:
    """Pick the best version from a group of duplicates.

    Selects the skill with highest (github_stars + install_count).
    Returns (primary, remaining_duplicates).
    """
    ranked = sorted(
        skills,
        key=lambda s: s.github_stars + s.install_count,
        reverse=True,
    )
    return ranked[0], ranked[1:]


def deduplicate(
    skills: list[ParsedSkill],
    similarity_threshold: float = 0.85,
) -> list[DeduplicatedSkill]:
    """Group skills by content hash (exact dupes), then fuzzy-match remaining.

    For each group, pick the version with highest (github_stars + install_count)
    as primary.

    Args:
        skills: List of parsed skills to deduplicate.
        similarity_threshold: Jaccard threshold for fuzzy matching (default 0.85).

    Returns:
        List of DeduplicatedSkill, each containing a primary and its duplicates.
    """
    if not skills:
        return []

    # ── Stage 1: Exact URL dedup ───────────────────────────────────────────
    seen_urls: dict[str, int] = {}  # url -> index in url_deduped
    url_deduped: list[list[ParsedSkill]] = []

    for skill in skills:
        url = skill.source_url
        if url and url in seen_urls:
            url_deduped[seen_urls[url]].append(skill)
        else:
            idx = len(url_deduped)
            url_deduped.append([skill])
            if url:
                seen_urls[url] = idx

    # Flatten: pick one representative per URL group
    url_primaries: list[ParsedSkill] = []
    url_dupes: dict[int, list[ParsedSkill]] = {}
    for idx, group in enumerate(url_deduped):
        primary, dupes = _pick_primary(group)
        url_primaries.append(primary)
        if dupes:
            url_dupes[idx] = dupes

    # ── Stage 2: Content hash dedup ────────────────────────────────────────
    hash_groups: dict[str, list[tuple[int, ParsedSkill]]] = {}  # hash -> [(original_idx, skill)]

    for idx, skill in enumerate(url_primaries):
        h = content_hash(skill.raw_content)
        hash_groups.setdefault(h, []).append((idx, skill))

    # Build intermediate list: one representative per hash group
    hash_primaries: list[tuple[ParsedSkill, list[ParsedSkill], str]] = []
    consumed: set[int] = set()

    for h, group in hash_groups.items():
        all_skills_in_group = [s for _, s in group]
        # Also gather URL-level dupes for these skills
        for orig_idx, _ in group:
            all_skills_in_group.extend(url_dupes.get(orig_idx, []))
            consumed.add(orig_idx)

        primary, dupes = _pick_primary(all_skills_in_group)
        hash_primaries.append((primary, dupes, h))

    # ── Stage 3: Fuzzy similarity dedup ────────────────────────────────────
    # Compute trigrams for each hash-deduped primary
    trigram_cache: list[set[tuple[str, ...]]] = [
        word_trigrams(primary.raw_content) for primary, _, _ in hash_primaries
    ]

    merged: list[bool] = [False] * len(hash_primaries)
    results: list[DeduplicatedSkill] = []

    for i in range(len(hash_primaries)):
        if merged[i]:
            continue

        primary_i, dupes_i, hash_i = hash_primaries[i]
        cluster_skills = [primary_i] + dupes_i

        # Find fuzzy matches
        for j in range(i + 1, len(hash_primaries)):
            if merged[j]:
                continue
            sim = jaccard_similarity(trigram_cache[i], trigram_cache[j])
            if sim >= similarity_threshold:
                merged[j] = True
                primary_j, dupes_j, _ = hash_primaries[j]
                cluster_skills.append(primary_j)
                cluster_skills.extend(dupes_j)

        # Pick final primary from the full cluster
        final_primary, final_dupes = _pick_primary(cluster_skills)
        results.append(DeduplicatedSkill(
            primary=final_primary,
            duplicates=final_dupes,
            content_hash=hash_i,
        ))

    return results
