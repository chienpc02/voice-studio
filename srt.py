"""Đọc file phụ đề SRT/VTT thành danh sách câu thoại."""
import re

_TIME = re.compile(r"^(?:(\d+):)?(\d+):(\d+)(?:[.,](\d+))?$")


def _ms(s: str):
    m = _TIME.match(s.strip())
    if not m:
        return None
    h, mi, se, fr = int(m[1] or 0), int(m[2]), int(m[3]), m[4] or "0"
    return round((h * 3600 + mi * 60 + se + float("0." + fr)) * 1000)


def parse(text: str):
    text = text.replace("﻿", "").replace("\r", "")
    cues = []
    for block in re.split(r"\n{2,}", text):
        lines = [l for l in block.split("\n") if l.strip()]
        ti = next((i for i, l in enumerate(lines) if "-->" in l), -1)
        if ti < 0:
            continue
        a, b = lines[ti].split("-->", 1)
        start, end = _ms(a), _ms(b.strip().split()[0] if b.strip() else "")
        if start is None or end is None:
            continue
        body = "\n".join(lines[ti + 1:])
        body = re.sub(r"<[^>]+>", "", body)
        body = re.sub(r"\{\\[^}]*\}", "", body)
        body = re.sub(r"^\s*[-–]\s*", "", body, flags=re.M)
        body = body.replace("&nbsp;", " ").replace("&amp;", "&").strip()
        if body:
            cues.append({"start": start, "end": end, "text": " ".join(body.split())})
    cues.sort(key=lambda c: c["start"])
    return cues
