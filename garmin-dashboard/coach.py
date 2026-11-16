"""Legge l'Excel del coach e salva il piano in data/coach/plan.json.

Uso:  python coach.py percorso/Programmazione.xlsx
Serve openpyxl (pip install openpyxl). Il piano resta in data/ (privato).
"""
import datetime as dt
import json
import os
import re
import sys

import openpyxl

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "data", "coach", "plan.json")
DAYS = ["Lunedì", "Martedì", "Mercoledì", "Giovedì", "Venerdì", "Sabato", "Domenica"]
MESI = {"gennaio": 1, "febbraio": 2, "marzo": 3, "aprile": 4, "maggio": 5, "giugno": 6, "luglio": 7,
        "agosto": 8, "settembre": 9, "ottobre": 10, "novembre": 11, "dicembre": 12}
EMPTY = {"", "—", "-", "–"}


def txt(c):
    return "" if c is None else str(c).strip()


def week_start(label):
    """'16–22 novembre 2026' oppure '30 novembre – 6 dicembre 2026' -> data del lunedi'."""
    m = re.match(r"\s*(\d{1,2})\s*(?:([a-zà]+)\s*)?[–-]\s*\d{1,2}\s+([a-zà]+)\s+(\d{4})", label.lower())
    if not m:
        return None
    day, mon1, mon2, year = int(m.group(1)), m.group(2), m.group(3), int(m.group(4))
    month = MESI.get(mon1 or mon2)
    if not month:
        return None
    if mon1 and MESI.get(mon1) == 12 and MESI.get(mon2) == 1:
        year -= 1
    return dt.date(year, month, day)


def parse_grid(rows, i):
    """rows[i] e' l'intestazione 'Fascia oraria | Lunedi' ...'. Ritorna blocchi per giorno."""
    slots = []
    j = i + 1
    while j < len(rows) and re.match(r"^\d{1,2}[:.]\d{2}|^Dopo", txt(rows[j][0])):
        slots.append(rows[j])
        j += 1
    days = []
    for d in range(7):
        blocks, cur = [], None
        for r in slots:
            cell = txt(r[d + 1]) if len(r) > d + 1 else ""
            slot = txt(r[0])
            if cell in EMPTY:
                if cur:
                    blocks.append(cur)
                    cur = None
                continue
            if cur is None:
                cur = {"start": slot.split("–")[0].split("-")[0].strip(), "slot": slot, "text": [cell]}
            else:
                if cell not in cur["text"]:
                    cur["text"].append(cell)
                cur["slot"] = cur["slot"].split("–")[0] + "–" + slot.split("–")[-1]
        if cur:
            blocks.append(cur)
        for b in blocks:
            b["text"] = " ".join(b["text"])
            codes = re.findall(r"\b([NBC]\d)\b", b["text"])
            b["codes"] = codes
        days.append(blocks)
    return days, j


def library(wb):
    """Testo delle sedute N1, B2, C3... dai fogli Nuoto/Bici/Corsa."""
    lib = {}
    for ws in wb.worksheets:
        name = ws.title.lower()
        if not any(k in name for k in ("nuoto", "bici", "corsa")):
            continue
        cur = None
        for row in ws.iter_rows(values_only=True):
            a, b = txt(row[0]) if row else "", txt(row[1]) if len(row) > 1 else ""
            m = re.match(r"^([NBC]\d)\s*:?\s*$", a)
            if m:
                cur = m.group(1)
                lib[cur] = []
                continue
            if cur and (a or b):
                lib[cur].append((a + ("  ·  " + b if b else "")).strip())
    return lib


def main():
    if len(sys.argv) < 2:
        sys.exit("Uso: python coach.py Programmazione.xlsx")
    wb = openpyxl.load_workbook(sys.argv[1], data_only=True)
    weeks = []
    for ws in wb.worksheets:
        if "programma" not in ws.title.lower():
            continue
        rows = [list(r) for r in ws.iter_rows(values_only=True)]
        label, note = None, ""
        i = 0
        while i < len(rows):
            first = txt(rows[i][0])
            if first.lower().startswith("fascia oraria") and label:
                days, i = parse_grid(rows, i)
                ws0 = week_start(label)
                if ws0:
                    weeks.append({"label": label, "start": ws0.isoformat(), "note": note, "days": days})
                label = None
                continue
            if week_start(first.split("|")[0]):
                parts = [p.strip() for p in first.split("|")]
                label = parts[0]
                note = " ".join(p for p in parts[1:] if p) or " ".join(txt(c) for c in rows[i][1:] if txt(c) not in ("", "|"))
            i += 1
    plan = {"weeks": weeks, "library": library(wb), "source": os.path.basename(sys.argv[1]),
            "imported": dt.datetime.now().isoformat(timespec="minutes")}
    # tengo le settimane gia' importate da file precedenti
    old = {}
    if os.path.exists(OUT):
        with open(OUT, encoding="utf-8") as f:
            prev = json.load(f)
        old = {w["start"]: w for w in prev.get("weeks", [])}
        plan["library"] = {**prev.get("library", {}), **plan["library"]}
    for w in weeks:
        old[w["start"]] = w
    plan["weeks"] = sorted(old.values(), key=lambda w: w["start"])
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(plan, f, ensure_ascii=False, indent=1)
    print("Piano del coach salvato: %d settimane, %d sedute in libreria" % (len(plan["weeks"]), len(plan["library"])))
    for w in weeks:
        n = sum(len(d) for d in w["days"])
        print("  %s (dal %s): %d sedute" % (w["label"], w["start"], n))


if __name__ == "__main__":
    main()
