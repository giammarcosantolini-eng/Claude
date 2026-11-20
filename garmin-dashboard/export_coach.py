"""Esporta una settimana del piano Jesolo nel formato Excel del coach.

Uso:  python export_coach.py 2026-11-30 [percorso_excel_coach]
Parte dall'Excel originale del coach (stessi fogli, stili, larghezze) e sostituisce:
  - il foglio "Programma ..." con la settimana scelta (stessa griglia a fasce orarie)
  - i fogli 03 Nuoto, 04 Bici, 05 Corsa con le sedute di quella settimana
Il file finisce in exports/ (privato, fuori da git).
"""
import copy
import datetime as dt
import json
import os
import re
import sys

import openpyxl

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_SRC = os.path.join(HERE, "data", "coach", "coach_template.xlsx")
MESI = ["gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno", "luglio", "agosto", "settembre",
        "ottobre", "novembre", "dicembre"]
MESI_T = [m.capitalize() for m in MESI]
SLOTS = [("06:45–08:00", 0, 8 * 60), ("08:00–08:45", 8 * 60, 8 * 60 + 45), ("08:45–12:00", 8 * 60 + 45, 12 * 60),
         ("12:00–14:00", 12 * 60, 14 * 60), ("14:00–18:00", 14 * 60, 18 * 60), ("18:00–19:00", 18 * 60, 19 * 60),
         ("19:00–20:15", 19 * 60, 20 * 60 + 15), ("20:15–20:30", 20 * 60 + 15, 20 * 60 + 30), ("Dopo le 20:30", 20 * 60 + 30, 24 * 60)]
SPORT_NAME = {"swim": "Nuoto", "bike": "Bike", "run": "Corsa", "gym": "Preparazione", "race": "Gara"}
PREFIX = {"swim": "N", "bike": "B", "run": "C"}


def hm(x):
    h, m = x.split(":")
    return int(h) * 60 + int(m)


def week_label(ws):
    we = ws + dt.timedelta(days=6)
    if ws.month == we.month:
        return "%d–%d %s %d" % (ws.day, we.day, MESI[we.month - 1], we.year)
    return "%d %s – %d %s %d" % (ws.day, MESI[ws.month - 1], we.day, MESI[we.month - 1], we.year)


def load_week(start):
    html = open(os.path.join(HERE, "season.html"), encoding="utf-8").read()
    data = json.loads(re.search(r"const D=(\{.*?\});\n", html, re.S).group(1))
    for w in data["weeks"]:
        if w["start"] == start:
            return w
    sys.exit("Settimana %s non trovata nel piano" % start)


def target_of(step):
    """Estrae il riferimento (zona, passo, watt, battito) da mettere nella colonna B, come fa il coach."""
    pats = [r"(A1|A2|B1|B2|C1|C2|ritmo gara)\s*\d:\d\d–\d:\d\d/100", r"\d:\d\d–\d:\d\d/100",
            r"\d{2,3}–\d{2,3} W(?: \([^)]*\))?", r"\d{2,3} W", r"\d:\d\d–\d:\d\d/km(?: \(FC [^)]*\))?",
            r"\d:\d\d/km", r"FC [\d\-– ]+"]
    for p in pats:
        m = re.search(p, step)
        if m:
            return m.group(0)
    return ""


def style_like(dst, src):
    dst.font = copy.copy(src.font)
    dst.fill = copy.copy(src.fill)
    dst.border = copy.copy(src.border)
    dst.alignment = copy.copy(src.alignment)
    dst.number_format = src.number_format


def main():
    start = sys.argv[1] if len(sys.argv) > 1 else None
    src = sys.argv[2] if len(sys.argv) > 2 else DEFAULT_SRC
    w = load_week(start)
    ws0 = dt.date.fromisoformat(start)
    wb = openpyxl.load_workbook(src)

    # ---------------- codici delle sedute (N1, B1, C1...) e libreria
    lib = {"swim": [], "bike": [], "run": []}
    counters = {"swim": 0, "bike": 0, "run": 0}
    for d in w["days"]:
        for s in d["sessions"]:
            if s["sport"] in PREFIX:
                counters[s["sport"]] += 1
                s["code"] = "%s%d" % (PREFIX[s["sport"]], counters[s["sport"]])
                lib[s["sport"]].append(s)

    # ---------------- foglio programma
    prog = next(x for x in wb.worksheets if x.title.lower().startswith("programma"))
    # stili di riferimento presi dalla griglia originale
    st_title, st_sub = copy.copy(prog["A1"]), copy.copy(prog["A2"])
    st_head, st_slot = prog["A4"], prog["A5"]
    st_empty = prog["B5"]
    st_sport = {}
    for row in prog.iter_rows(min_row=5, max_row=13, min_col=2, max_col=8):
        for c in row:
            v = str(c.value or "")
            for key, word in (("swim", "Nuoto"), ("bike", "Bike"), ("run", "Corsa"), ("gym", "Preparazione")):
                if v.startswith(word) and key not in st_sport:
                    st_sport[key] = c
    refs = {k: copy.copy(v._style) for k, v in st_sport.items()}
    ref_empty, ref_head, ref_slot = copy.copy(st_empty._style), copy.copy(st_head._style), copy.copy(st_slot._style)
    # tolgo tutte le settimane dopo la prima
    for rng in list(prog.merged_cells.ranges):
        if rng.min_row > 2:
            prog.unmerge_cells(str(rng))
    prog.delete_rows(15, prog.max_row)
    prog.title = "Programma " + MESI_T[ws0.month - 1]
    prog["A2"] = "%s | Proposta per Jesolo 70.3 · %s" % (week_label(ws0), w["label"])
    grid = {}
    for i, d in enumerate(w["days"]):
        col = 2 + i
        for r in range(5, 14):
            c = prog.cell(r, col)
            c.value = "—"
            c._style = copy.copy(ref_empty)
        if d["sessions"] and all(x["sport"] == "away" for x in d["sessions"]):
            c = prog.cell(7, col)
            c.value = "Fuori casa (sci)"
            c._style = copy.copy(ref_empty)
            continue
        for s in d["sessions"]:
            if not s.get("slot") or s["sport"] not in SPORT_NAME:
                continue
            a = hm(s["slot"].split("–")[0])
            b = hm(s["slot"].split("–")[1])
            rows = [5 + k for k, (_, lo, hi) in enumerate(SLOTS) if a < hi and b > lo] or [5]
            name = s["title"] if s["sport"] == "gym" else SPORT_NAME[s["sport"]]
            code = s.get("code")
            first = "%s (%s)" % (name, code) if code else name
            if s["slot"].split("–")[0] != SLOTS[rows[0] - 5][0].split("–")[0]:
                first += " · %s" % s["slot"].split("–")[0]
            sty = refs.get(s["sport"], refs.get("run"))
            for j, r in enumerate(rows):
                c = prog.cell(r, col)
                c.value = first if j == 0 else (name if j == len(rows) - 1 and len(rows) > 2 else c.value if c.value not in (None, "—") else "")
                c._style = copy.copy(sty)
            grid.setdefault(i, []).append(first)

    # ---------------- fogli libreria
    def fill_lib(title_word, key, label):
        sh = next(x for x in wb.worksheets if title_word in x.title.lower())
        hdr = next((sh.cell(r, 1) for r in range(1, sh.max_row + 1) if re.match(r"^[NBC]\d", str(sh.cell(r, 1).value or ""))), None)
        sec = next((sh.cell(r, 1) for r in range(1, sh.max_row + 1) if str(sh.cell(r, 1).value or "").rstrip().endswith(":") and sh.cell(r, 1).font.b and not re.match(r"^[NBC]\d", str(sh.cell(r, 1).value))), None)
        rows_alt = [sh.cell(r, 1) for r in range(1, sh.max_row + 1) if sh.cell(r, 1).value and not sh.cell(r, 1).font.b][:2]
        tot = next((sh.cell(r, 1) for r in range(1, sh.max_row + 1) if str(sh.cell(r, 1).value or "").startswith("Totale")), None)
        s_hdr = copy.copy(hdr._style) if hdr else None
        s_sec = copy.copy(sec._style) if sec else None
        s_alt = [copy.copy(c._style) for c in rows_alt] or [copy.copy(sh["A3"]._style)] * 2
        s_alt_b = [copy.copy(sh.cell(c.row, 2)._style) for c in rows_alt] or s_alt
        s_tot = copy.copy(tot._style) if tot else s_sec
        sh.delete_rows(4, sh.max_row)
        codes = [s["code"] for s in lib[key]]
        sh["A2"] = "Sedute " + " · ".join(codes) if codes else "Nessuna seduta questa settimana"
        r = 4
        for s in lib[key]:
            c = sh.cell(r, 1, "%s: %s" % (s["code"], s["title"].split(" · ")[-1] if " · " in s["title"] else s["title"]))
            if s_hdr: c._style = copy.copy(s_hdr)
            r += 1
            n = 0
            for step in s["steps"]:
                if step.startswith("Totale"):
                    c = sh.cell(r, 1, step)
                    if s_tot: c._style = copy.copy(s_tot)
                    r += 1
                    continue
                m = re.match(r"^(Riscaldamento|Lavoro|Defaticamento|Dentro|Subito dopo)[^:]*:\s*(.*)$", step)
                if m and s_sec:
                    c = sh.cell(r, 1, m.group(1) + ":")
                    c._style = copy.copy(s_sec)
                    r += 1
                    step = m.group(2)
                    if not step:
                        continue
                ca = sh.cell(r, 1, step)
                cb = sh.cell(r, 2, target_of(step))
                ca._style = copy.copy(s_alt[n % 2]); cb._style = copy.copy(s_alt_b[n % 2])
                n += 1
                r += 1
            if s.get("fuel"):
                ca = sh.cell(r, 1, "Integratori: " + s["fuel"])
                ca._style = copy.copy(s_alt[n % 2]); sh.cell(r, 2)._style = copy.copy(s_alt_b[n % 2])
                r += 1
            r += 1
    fill_lib("nuoto", "swim", "Nuoto")
    fill_lib("bici", "bike", "Bici")
    fill_lib("corsa", "run", "Corsa")

    out_dir = os.path.join(HERE, "exports")
    os.makedirs(out_dir, exist_ok=True)
    out = os.path.join(out_dir, "Programmazione_Giammarco_Santolini_%s.xlsx" % start)
    wb.save(out)
    print(out)
    for i, d in enumerate(w["days"]):
        print(d["date"], grid.get(i, ["(fuori casa)" if d["sessions"] and all(x["sport"] == "away" for x in d["sessions"]) else "riposo"]))


if __name__ == "__main__":
    main()
