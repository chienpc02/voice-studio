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


_END = re.compile(r'[.!?…。！？]["”’)\]]*$')


def merge(cues, max_gap=800, soft_ms=3000, soft_chars=60, hard_ms=12000, hard_chars=220):
    """Gộp các dòng phụ đề bị cắt vụn thành câu trọn vẹn để giọng đọc tự nhiên hơn.

    Cắt câu khi: khoảng lặng giữa hai dòng lớn, câu gộp quá dài, hoặc dòng hiện tại đã
    kết thúc bằng dấu câu và đủ dài (soft_ms / soft_chars)."""
    out, cur = [], None
    for c in cues:
        if cur is None:
            cur = dict(c)
            continue
        gap = c["start"] - cur["end"]
        too_long = (c["end"] - cur["start"] > hard_ms) or (len(cur["text"]) + 1 + len(c["text"]) > hard_chars)
        ended = bool(_END.search(cur["text"])) and (cur["end"] - cur["start"] >= soft_ms or len(cur["text"]) >= soft_chars)
        if gap > max_gap or too_long or ended:
            out.append(cur)
            cur = dict(c)
        else:
            cur["end"] = c["end"]
            cur["text"] = cur["text"] + " " + c["text"]
    if cur:
        out.append(cur)
    return out
