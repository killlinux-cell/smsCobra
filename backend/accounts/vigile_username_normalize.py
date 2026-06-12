"""Normalisation ponctuelle des identifiants vigiles (VIR-XXX)."""

from __future__ import annotations

import re
from dataclasses import dataclass

STANDARD_VIGILE_USERNAME = re.compile(r"^VIR-\d{3}$", re.IGNORECASE)
NUMERIC_USERNAME = re.compile(r"^\d+$")
TEMP_USERNAME_PREFIX = "__vig_norm_"


def is_standard_vigile_username(username: str) -> bool:
    return bool(STANDARD_VIGILE_USERNAME.match((username or "").strip()))


def preferred_vigile_username(username: str) -> str | None:
    """
    Retourne le VIR-XXX cible pour un identifiant saisi manuellement.
    None si déjà au format standard.
    """
    raw = (username or "").strip()
    if not raw or is_standard_vigile_username(raw):
        return None
    if NUMERIC_USERNAME.match(raw):
        return f"VIR-{int(raw):03d}"
    return None


def _max_vir_number(usernames: set[str]) -> int:
    max_num = 0
    for username in usernames:
        if not username:
            continue
        match = STANDARD_VIGILE_USERNAME.match(username.strip())
        if match:
            max_num = max(max_num, int(username.split("-", 1)[1]))
    return max_num


def next_free_vigile_username(taken: set[str], start: int = 1) -> str:
    num = max(0, start - 1)
    while True:
        num += 1
        candidate = f"VIR-{num:03d}"
        if candidate.lower() not in taken:
            return candidate


def temp_vigile_username(user_id: int) -> str:
    return f"{TEMP_USERNAME_PREFIX}{user_id}__"


@dataclass(frozen=True)
class VigileUsernameChange:
    user_id: int
    old_username: str
    new_username: str
    reason: str


def plan_vigile_username_normalizations(
    vigiles: list[tuple[int, str]],
    *,
    reserved_usernames: set[str] | None = None,
) -> tuple[list[VigileUsernameChange], list[str]]:
    """
    vigiles: vigiles hors format VIR-XXX a normaliser (id, username).
    reserved_usernames: tous les identifiants deja en base (minuscules).
    """
    taken: set[str] = set(reserved_usernames or [])
    taken.update((username or "").lower() for _, username in vigiles)
    changes: list[VigileUsernameChange] = []
    warnings: list[str] = []

    max_vir_num = _max_vir_number(taken)

    pending: list[tuple[int, str, str | None]] = []
    for user_id, username in vigiles:
        preferred = preferred_vigile_username(username)
        if preferred is None:
            if is_standard_vigile_username(username):
                continue
            pending.append((user_id, username, None))
        else:
            pending.append((user_id, username, preferred))

    def sort_key(item: tuple[int, str, str | None]) -> tuple[int, int, str]:
        _uid, old, preferred = item
        if preferred and preferred.upper().startswith("VIR-"):
            return (0, int(preferred[4:]), old.lower())
        return (1, 10**9, old.lower())

    pending.sort(key=sort_key)

    for user_id, old_username, preferred in pending:
        target = preferred
        reason = "numerique -> VIR-XXX"
        if target is None:
            target = next_free_vigile_username(taken, start=max_vir_num + 1)
            reason = "identifiant libre -> prochain VIR-XXX disponible"
            max_vir_num = max(max_vir_num, int(target[4:]))
        elif target.lower() in taken and target.lower() != old_username.lower():
            warnings.append(
                f"#{user_id} {old_username!r} : {target} deja pris — "
                f"attribution du prochain numero libre."
            )
            target = next_free_vigile_username(taken, start=1)
            reason = "conflit -> prochain VIR-XXX disponible"
            max_vir_num = max(max_vir_num, int(target[4:]))

        if target.lower() == old_username.lower():
            continue

        changes.append(
            VigileUsernameChange(
                user_id=user_id,
                old_username=old_username,
                new_username=target,
                reason=reason,
            )
        )
        taken.add(target.lower())

    return changes, warnings
