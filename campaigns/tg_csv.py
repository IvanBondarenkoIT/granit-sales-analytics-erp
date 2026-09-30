"""Parse Telegram-bot user export: card number + phone (local only; do not commit files)."""
from __future__ import annotations

import csv
import io
import re
from pathlib import Path
from typing import IO

from campaigns.excel import CampaignRow, normalize_phone

CARD_RE = re.compile(r"^\d{13}$")


def _read_text(source: str | Path | IO[bytes] | IO[str]) -> str:
    if isinstance(source, (str, Path)):
        return Path(source).read_text(encoding="utf-8-sig")
    data = source.read()
    if isinstance(data, bytes):
        return data.decode("utf-8-sig")
    return data.lstrip("\ufeff")


def parse_tg_users_csv(source: str | Path | IO[bytes] | IO[str]) -> list[CampaignRow]:
    """Rows are ``card,phone``; header optional; ``;`` also accepted as delimiter."""
    text = _read_text(source)
    first = text.splitlines()[0] if text else ""
    delimiter = ";" if first.count(";") > first.count(",") else ","
    seen: set[str] = set()
    out: list[CampaignRow] = []
    for row in csv.reader(io.StringIO(text), delimiter=delimiter):
        if not row:
            continue
        card = row[0].strip()
        if not CARD_RE.match(card) or card in seen:
            continue
        seen.add(card)
        phone = normalize_phone(row[1]) if len(row) > 1 else ""
        out.append(CampaignRow(granit_client_id=None, phone=phone, card_number=card))
    return out
