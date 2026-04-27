"""Curated ATT&CK ID aliases for historically renumbered equivalent techniques.

Only include pairs we have manually verified as semantically equivalent for this
benchmark. Do not treat same-name IDs as equivalent by default.
"""

from __future__ import annotations


_ALIAS_GROUPS: tuple[tuple[str, ...], ...] = (
    # Credentials from Web Browsers
    ("T1503", "T1555.003"),
    # Disk Content Wipe
    ("T1488", "T1561.001"),
    # SIP and Trust Provider Hijacking
    ("T1198", "T1553.003"),
    # Extra Window Memory Injection
    ("T1181", "T1055.011"),
    # Mshta
    ("T1170", "T1218.005"),
)


ATTACK_ID_ALIAS_MAP: dict[str, str] = {}
for group in _ALIAS_GROUPS:
    canonical = group[-1]
    for attack_id in group:
        ATTACK_ID_ALIAS_MAP[attack_id.upper()] = canonical.upper()


def canonicalize_attack_id(attack_id: str | None) -> str:
    normalized = str(attack_id or "").strip().upper()
    if not normalized:
        return ""
    return ATTACK_ID_ALIAS_MAP.get(normalized, normalized)


def canonicalize_attack_ids(attack_ids: list[str] | tuple[str, ...] | set[str]) -> list[str]:
    return [canonicalize_attack_id(attack_id) for attack_id in attack_ids if canonicalize_attack_id(attack_id)]
