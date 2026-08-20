"""Matricules vigiles en roulement (RLT-XXX)."""

from __future__ import annotations

import re

from accounts.models import User

STANDARD_ROULEMENT_USERNAME = re.compile(r"^RLT-\d{3}$", re.IGNORECASE)


def is_standard_roulement_username(value: str | None) -> bool:
    return bool(value and STANDARD_ROULEMENT_USERNAME.match(value.strip()))


def generate_roulement_username() -> str:
    max_num = 0
    for value in User.objects.filter(role=User.Role.VIGILE).values_list("username", flat=True):
        if value and value.upper().startswith("RLT-"):
            suffix = value[4:]
            if suffix.isdigit():
                max_num = max(max_num, int(suffix))
    return f"RLT-{max_num + 1:03d}"
