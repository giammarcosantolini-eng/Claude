"""Piano giornaliero dal 30/11/2026 a Ironman 70.3 Jesolo (24/04/2027).

Uso:  python season.py   -> crea season.html (pagina separata dalla dashboard)
Legge: data/calendar/season.json (impegni), data/coach/strength.json, data/coach/track.json
"""
import datetime as dt
import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
D = dt.date
START, RACE = D(2026, 11, 30), D(2027, 4, 24)
HOLIDAYS = {D(2026, 12, 4), D(2026, 12, 8), D(2026, 12, 25), D(2026, 12, 26), D(2027, 1, 1), D(2027, 1, 6),
            D(2027, 3, 29), D(2027, 4, 25)}
GG = ["Lunedì", "Martedì", "Mercoledì", "Giovedì", "Venerdì", "Sabato", "Domenica"]


def rj(p, default=None):
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def P(s):
    s = int(round(s))
    return "%d:%02d" % (s // 60, s % 60)


def m2hm(m):
    return "%d:%02d" % (m // 60, m % 60)


# ------------------------------------------------------------------ riferimenti che crescono nel tempo
def lerp(a, b, t):
    return a + (b - a) * max(0.0, min(1.0, t))


def frac(d, d0, d1):
    return (d - d0).days / max(1, (d1 - d0).days)


def ftp(d):  # ipotesi: si aggiorna con i test
    if d < D(2026, 12, 2): return 194
    if d < D(2027, 1, 27): return 200
    if d < D(2027, 3, 31): return 205
    return 210


def run_p(d):
    t = frac(d, D(2026, 12, 1), D(2027, 2, 28))
    return {
        "E": (lerp(308, 300, t), lerp(330, 320, t)),           # facile
        "T": lerp(268, 256, t),                                # soglia / ritmo mezza
        "I": lerp(236, 226, frac(d, D(2026, 12, 1), D(2027, 1, 17))),  # ripetute 800-1000
        "K10": 240, "HM": 256, "R703": (300, 312),
    }


def css(d):
    return 105 if d < D(2027, 2, 1) else 103


def sw(d, z):
    c = css(d)
    off = {"A1": (15, 20), "A2": (6, 12), "B1": (-2, 2), "B2": (-6, -3), "C1": (-12, -8), "RACE": (2, 6)}[z]
    return "%s–%s/100" % (P(c + off[0]), P(c + off[1]))


def W(d, lo, hi=None):
    f = ftp(d)
    return "%d–%d W" % (round(f * lo), round(f * (hi or lo))) if hi else "%d W" % round(f * lo)


def E(d):
    e = run_p(d)["E"]
    return "%s–%s/km (FC 135-145)" % (P(e[0]), P(e[1]))


# ------------------------------------------------------------------ sedute
def S(sport, title, start, dur, steps, km=None, fuel="", key=False, alts=None, note="", ok=False):
    return {"sport": sport, "title": title, "start": start, "dur": dur, "steps": steps, "km": km,
            "fuel": fuel, "key": key, "alts": alts or [], "note": note, "ok": ok}


F_SWIM = "Acqua a bordo vasca."
F_EASY = "Solo acqua."
F_Q_RUN = "1 Electrolytes Boost in borraccia. 1 gel Limone con sodio 10-15' prima della parte veloce."
F_BIKE_IN = "Borraccia con 1 Electrolytes Boost (sui rulli si suda tanto)."


def F_LONG(h, carbs="60-80"):
    return ("%s g di carboidrati l'ora (1 Carbo Bar + 1 gel l'ora le prime 2 ore, poi 2 gel l'ora; gel con caffeina "
            "nell'ultima ora se è mattina). 1 Electrolytes Boost per borraccia, circa 1 l'ora. Durata %s." % (carbs, h))


def swim_css(d, k, kind="base"):
    if kind == "base":
        main = ["10 x 100 in B1 %s, recupero 15''" % sw(d, "B1"), "12 x 100 in B1 %s, recupero 15''" % sw(d, "B1"),
                "4 x 300 in B1 %s, recupero 25''" % sw(d, "B1")][k % 3]
        tot = [2800, 3000, 3000][k % 3]
    elif kind == "build":
        main = ["6 x 200 in B1 %s, recupero 20''" % sw(d, "B1"), "4 x 300 in B1 %s, recupero 25''" % sw(d, "B1"),
                "3 x 400 in B1 %s, recupero 30''" % sw(d, "B1")][k % 3]
        tot = 3000
    else:  # specifico 70.3
        main = ["3 x 500 a ritmo gara %s, recupero 30''" % sw(d, "RACE"), "4 x 400 a ritmo gara %s, recupero 20''" % sw(d, "RACE"),
                "5 x 400: dispari ritmo gara %s, pari B1 %s, recupero 20''" % (sw(d, "RACE"), sw(d, "B1")),
                "2 x 900 a ritmo gara %s, recupero 1'" % sw(d, "RACE")][k % 4]
        tot = 3200
    return S("swim", "Nuoto · soglia", "06:00", 70, [
        "Riscaldamento: 300 sciolti A1 %s, 8 x 50 tecnica (25 esercizio + 25 nuotata)" % sw(d, "A1"),
        "Lavoro: " + main, "4 x 50 in B2 %s, recupero 20''" % sw(d, "B2"), "Defaticamento: 200 sciolti A1",
        "Totale circa %d m" % tot], fuel=F_SWIM, alts=["05:45", "08:00", "19:00"])


def swim_end(d, meters, extra=""):
    return S("swim", "Nuoto · fondo", "06:00", 75, [
        "Riscaldamento: 400 A1 %s" % sw(d, "A1"),
        "Lavoro: blocchi da 500 in A2 %s, recupero 20'', fino a %d m totali" % (sw(d, "A2"), meters - 600) + (". " + extra if extra else ""),
        "Defaticamento: 200 A1", "Totale circa %d m" % meters], fuel=F_SWIM, alts=["05:45", "08:00", "19:00"])


def swim_easy(d, start="17:00", meters=2000):
    return S("swim", "Nuoto · facile e tecnica", start, 45, [
        "%d m in A1-A2 %s" % (meters - 400, sw(d, "A1")), "8 x 25: 1 piano 1 forte (C1 %s)" % sw(d, "C1"),
        "200 sciolti", "Totale circa %d m" % meters], fuel=F_SWIM, alts=["18:00", "09:00"])


def kg_step(d):
    """+2,5 kg per lato ogni 3 settimane da metà dicembre, al massimo +7,5 kg."""
    return max(0, min(3, (d - D(2026, 12, 14)).days // 21 + 1)) if d >= D(2026, 12, 14) else 0


def bump(line, step):
    if step == 0 or "manubri" in line or "elastico" in line.lower():
        return line
    line = re.sub(r"\((\d+(?:,\d)?)\+(\d+(?:,\d)?) kg\)", lambda m: "(%s+%s kg)" % ((("%g" % (float(m.group(1).replace(",", ".")) + 2.5 * step)).replace(".", ","),) * 2), line)
    line = re.sub(r"(?<![+\d])(\d+) kg(?!\))", lambda m: ("%g kg" % (int(m.group(1)) + 2.5 * step)).replace(".", ","), line)
    return line


def gym(d, which, start="06:45", light=False):
    lib = (rj(os.path.join(DATA, "coach", "strength.json"), {}) or {}).get(which, [])
    st = 0 if light else kg_step(d)
    steps = [bump(x, st) for x in lib if x and not x.endswith(":")] if lib else []
    if st:
        steps = ["Carichi +%s kg per lato rispetto alla scheda del coach. Se le ultime 2 ripetute non sono pulite, resta al carico precedente" % ("%g" % (2.5 * st)).replace(".", ",")] + steps
    if light:
        steps = ["Versione leggera: 3 serie invece di 4, stessi esercizi, carichi -20%"] + steps
    return S("gym", "Preparazione " + which, start, 60 if not light else 45, steps or ["Seduta di forza del coach"],
             fuel="Solo acqua. Creatina dopo la seduta.", alts=["06:30", "19:00"])


def gym_maint(d, start="06:45"):
    st = 3
    return S("gym", "Forza di mantenimento", start, 40, [
        "Meno serie ma carichi alti: mantieni la forza costruita in inverno",
        bump("3 x 6 stacco a una gamba al Smith dx + sx (20+20 kg)", st + 1),
        bump("3 x 8 affondi al Smith dx + sx (15+15 kg)", st + 1), bump("3 x 12 calf raise al Smith (15+15 kg)", st + 1),
        "Core: plank 1', laterali 40'' dx e sx, x 2"],
        fuel="Solo acqua. Creatina dopo la seduta.", alts=["06:30", "19:00"])


def run_easy(d, mins, strides=0, start="19:00", title="Corsa · facile"):
    e = run_p(d)["E"]
    km = round(mins * 60 / ((e[0] + e[1]) / 2), 1)
    st = ["%d' facili a %s" % (mins, E(d))]
    if strides:
        st.append("%d allunghi da 20'' progressivi (ultimi metri a circa %s/km), recupero camminando" % (strides, P(run_p(d)["I"] - 10)))
    return S("run", title, start, mins + (5 if strides else 0), st, km=km, fuel=F_EASY, alts=["06:30", "20:30"])


def track(d, reps, dist, pace_lo, pace_hi, rec, title="Pista · ripetute", note=""):
    work = reps * dist / 1000 * (pace_lo + pace_hi) / 2 / 60 + (reps - 1) * rec / 60
    dur = int(round(10 + 5 + work + 5))
    km = round(2.5 + reps * dist / 1000 + 1, 1)
    main = "%d x %d m a %s–%s/km, recupero %s camminando o corsa lentissima (FC sotto 130)" % (
        reps, dist, P(pace_lo), P(pace_hi), "%d'%02d''" % (rec // 60, rec % 60))
    wed = d.weekday() == 2 and d not in HOLIDAYS
    if wed and dur <= 50:  # mercoledì esce alle 18:30: in pista dalle 18:40, chiude alle 19:30
        return S("run", title, "18:40", dur, [
            "Riscaldamento in pista: 10' a %s" % E(d), "5' tra slanci, andature e 3 allunghi", main,
            "Defaticamento: 5' facili, entro le 19:30 quando chiude la pista"] + ([note] if note else []),
            km=km, fuel=F_Q_RUN, key=True, alts=["19:00"], ok=True)
    if d in HOLIDAYS or d.weekday() >= 5:
        return S("run", title, "10:30", dur, [
            "Riscaldamento in pista: 10' a %s" % E(d), "5' tra slanci, andature e 3 allunghi", main, "Defaticamento: 5' facili"]
            + ([note] if note else []), km=km, fuel=F_Q_RUN, key=True, alts=["15:00"], ok=True)
    why = "la pista chiude alle 19:30 e la seduta dura %d'" % dur if wed else "la sera la pista è aperta solo fino alle 19:30"
    return S("run", title.replace("Pista", "Su strada"), "19:00", dur, [
        "Su strada da casa (%s): scegli un tratto piatto e misura i giri con il tasto giro o il giro automatico ogni %d m" % (why, dist),
        "Riscaldamento: 10' a %s" % E(d), "5' tra slanci, andature e 3 allunghi", main, "Defaticamento: 5' facili"]
        + ([note] if note else []), km=km, fuel=F_Q_RUN, key=True, alts=["20:30", "06:00"])


def road_tempo(d, blocks, km_each, pace, rec, start="19:00", title="Corsa · soglia su strada"):
    work = blocks * km_each * pace / 60 + (blocks - 1) * rec / 60
    dur = int(round(15 + work + 8))
    km = round(2.5 + blocks * km_each + 1.5, 1)
    return S("run", title, start, dur, [
        "Riscaldamento: 15' a %s + 4 allunghi" % E(d),
        "%d x %s km a %s/km (FC 168-175), recupero %d'' corsa lenta" % (blocks, ("%g" % km_each).replace(".", ","), P(pace), rec),
        "Defaticamento: 8' facili"], km=km, fuel=F_Q_RUN, key=True, alts=["06:00", "20:30"])


def bike_z2(d, mins, start="06:15", drills=True):
    st = ["%d' in Z2 a %s (65-72%% FTP), cadenza 85-95" % (mins, W(d, .65, .72))]
    if drills:
        st.append("Dentro: 5 x 1' cadenza alta 105-110 rpm, recupero 2'")
    return S("bike", "Bici · fondo sui rulli", start, mins, st, fuel=F_BIKE_IN, alts=["06:00", "19:00"])


def bike_q(d, sets, mins, lo, hi, rec, label, start="19:00"):
    dur = 15 + sets * mins + (sets - 1) * rec + 10
    return S("bike", "Bici · " + label, start, dur, [
        "Riscaldamento: 15' progressivi da %s a %s" % (W(d, .55), W(d, .75)),
        "%d x %d' a %s (%d-%d%% FTP), recupero %d' a %s" % (sets, mins, W(d, lo, hi), lo * 100, hi * 100, rec, W(d, .55)),
        "Defaticamento: 10' a %s" % W(d, .5)], fuel=F_BIKE_IN + " 1 gel Mango a metà seduta.", key=True,
        alts=["20:30", "06:00"])


def bike_long(d, mins, blocks=None, brick=0, brick_pace=None, start="08:30", outdoor=True):
    st = ["%s totali in Z2 a %s (65-75%% FTP), %s" % (m2hm(mins), W(d, .65, .75),
                                                    "su strada, percorso piatto se possibile" if outdoor else "sui rulli se piove")]
    if blocks:
        st.append("Dentro: %s" % blocks)
    title = "Bici lunga"
    dur = mins
    if brick:
        bp = brick_pace or run_p(d)["R703"]
        st.append("Subito dopo (cambio in meno di 5'): corsa %d' a %s–%s/km" % (brick, P(bp[0]), P(bp[1])))
        title = "Bici lunga + corsa (brick)"
        dur += brick + 5
    return S("bike", title, start, dur, st, km=round(mins / 60 * 27, 0), fuel=F_LONG(m2hm(mins)), key=bool(blocks),
             alts=["10:00", "07:30"])


def long_run(d, km, tail=None, start="08:30"):
    e = run_p(d)["E"]
    mins = int(round(km * (e[0] + e[1]) / 2 / 60))
    st = ["%s km a %s" % (("%g" % km).replace(".", ","), E(d))]
    if tail:
        st.append(tail)
    fuel = F_EASY if km < 16 else "1 gel Mango ogni 40' dopo la prima ora. Acqua o 1 Electrolytes Boost se fa caldo."
    return S("run", "Corsa lunga", start, mins, st, km=km, fuel=fuel, key=bool(tail), alts=["07:30", "10:00"])


def ftp_test(d, start="06:15"):
    return S("bike", "Test FTP (20')", start, 60, [
        "Stessa bici e stesso protocollo del 20 ottobre", "Riscaldamento: 15' progressivi + 3 x 1' a 110% (recupero 1')",
        "5' a tutta, poi 10' facili", "20' a tutta, il più regolare possibile: FTP = 95% della media",
        "Defaticamento 10'", "Il giorno prima solo sedute facili. Mandami il risultato: ricalcolo tutti i watt."],
        fuel=F_BIKE_IN, key=True, alts=["06:00", "19:00"])


def rest(note="Riposo. Stretching o camminata se ti va."):
    return S("rest", "Riposo", "", 0, [note])


def away(note):
    return S("away", "Fuori casa", "", 0, [note])


# ------------------------------------------------------------------ settimane
WEEKS = [
    ("2026-11-30", "rec1", "Recupero dopo Fiumicino e test FTP"),
    ("2026-12-07", "base", "Base 1"), ("2026-12-14", "base", "Base 2"), ("2026-12-21", "base", "Base 3 · Natale"),
    ("2026-12-28", "base", "Base 4 · Capodanno"),
    ("2027-01-04", "b10", "Specifico 10 km"), ("2027-01-11", "t10", "Scarico e gara 10 km"),
    ("2027-01-18", "bhm", "Verso la mezza 1"), ("2027-01-25", "bhm", "Verso la mezza 2 · test FTP"),
    ("2027-02-01", "bhm", "Verso la mezza 3"), ("2027-02-08", "rec", "Scarico"),
    ("2027-02-15", "shm", "Specifico mezza"), ("2027-02-22", "thm", "Scarico e Roma-Ostia"),
    ("2027-03-01", "rechm", "Recupero dopo la mezza"),
    ("2027-03-08", "spec", "Specifico 70.3 · 1 · duathlon test"), ("2027-03-15", "spec", "Specifico 70.3 · 2"),
    ("2027-03-22", "spec", "Specifico 70.3 · 3 · simulazione gara"), ("2027-03-29", "recftp", "Scarico, test FTP e mezza di allenamento"),
    ("2027-04-05", "spec", "Specifico 70.3 · 4 · triathlon sprint test"), ("2027-04-12", "taper", "Scarico pre-gara"),
    ("2027-04-19", "race", "Settimana gara"),
]
PHASE = {"rec1": "Recupero", "base": "Base", "rec": "Scarico", "b10": "10 km", "t10": "10 km", "bhm": "Mezza",
         "shm": "Mezza", "thm": "Mezza", "rechm": "Recupero", "spec": "70.3", "recftp": "Scarico", "taper": "70.3",
         "race": "Gara"}


def week_days(ws, typ, k):
    out = []
    for i in range(7):
        d = ws + dt.timedelta(days=i)
        rp = run_p(d)
        s = []
        if typ == "rec1":
            s = [[swim_easy(d, "06:30", 2400), bike_z2(d, 45, "19:00", drills=False)],
                 [gym(d, "Upper", light=True), run_easy(d, 40, 6)],
                 [ftp_test(d), run_easy(d, 35)],
                 [swim_end(d, 3000), bike_z2(d, 60, "19:00")],
                 [], [], []][i]
        elif typ == "base":
            s = [[swim_css(d, k), run_easy(d, [45, 45, 50, 50][k], 6)],
                 [gym(d, "Upper"), bike_q(d, [3, 3, 2, 3][k], [12, 15, 20, 15][k], .88, .92, 5, "sweet spot")],
                 [bike_z2(d, 60), track(d, *[(6, 800, rp["I"] - 2, rp["I"] + 4, 120), (5, 1000, rp["I"], rp["I"] + 6, 150),
                                             (8, 600, rp["I"] - 6, rp["I"], 90), (6, 1000, rp["I"], rp["I"] + 5, 120)][k])],
                 [swim_end(d, [3200, 3400, 3500, 3500][k]), run_easy(d, [30, 35, 40, 45][k])],
                 [gym(d, "Lower")],
                 [bike_long(d, [135, 150, 165, 180][k], [None, "2 x 15' a %s (80-85%% FTP)" % W(d, .8, .85), "3 x 15' a %s (80-85%% FTP)" % W(d, .8, .85),
                                                       "3 x 20' a %s (80-85%% FTP)" % W(d, .8, .85)][k], brick=15)],
                 [long_run(d, [15, 16, 17, 18][k]), swim_easy(d, "17:00", 2500)]][i]
        elif typ == "rec":
            s = [[swim_easy(d, "06:30", 2400)], [bike_z2(d, 45, "19:00", drills=False)],
                 [run_easy(d, 35, 6)], [swim_end(d, 2500)], [rest()],
                 [bike_long(d, 90, None)], [long_run(d, 10), swim_easy(d)]][i]
        elif typ == "b10":
            s = [[swim_css(d, 0, "build"), run_easy(d, 45, 6)],
                 [gym(d, "Upper"), bike_q(d, 4, 8, .98, 1.02, 4, "soglia")],
                 [bike_z2(d, 60, "08:00"), dict(track(d, 3, 2000, rp["K10"] + 2, rp["K10"] + 5, 150, note="Oggi è festivo: pista aperta 10:00-15:00"), start="10:30", ok=True)],
                 [swim_end(d, 3200)], [gym(d, "Lower")],
                 [bike_long(d, 150, "3 x 12' a %s (80-85%% FTP)" % W(d, .8, .85), brick=15, brick_pace=(290, 295))],
                 [long_run(d, 17, "Ultimi 3 km a %s/km (soglia)" % P(rp["T"])), swim_easy(d)]][i]
        elif typ == "t10":
            s = [[swim_css(d, 1, "build"), run_easy(d, 40, 6)],
                 [gym(d, "Upper", light=True), bike_q(d, 3, 3, 1.03, 1.06, 3, "attivazione")],
                 [track(d, 5, 1000, rp["K10"] - 3, rp["K10"], 120, title="Pista · rifinitura")],
                 [swim_easy(d, "06:30", 2500), run_easy(d, 30)], [rest("Riposo. Frullato di barbabietola a colazione.")],
                 [run_easy(d, 20, 4, "10:00", "Corsa · attivazione pre-gara")],
                 [S("run", "GARA · 10 km", "09:30", 45, [
                     "Obiettivo sotto i 40': %s/km" % P(rp["K10"]),
                     "Km 1-2 a 4:01-4:02 (non partire più forte), km 3-8 a 3:59-4:00, km 9-10 a tutta",
                     "Riscaldamento: 15' facili + 4 allunghi, finito 10' prima del via",
                     "Il ritmo lo decidiamo meglio dopo la gara di Fiumicino: lo aggiorno io"],
                     km=10, fuel="Colazione 3 ore prima. Gel con sodio 15' prima del via. Frullato venerdì e sabato.", key=True)]][i]
        elif typ == "bhm":
            tails = ["Ultimi 4 km a %s/km (ritmo mezza)", "Ultimi 6 km a %s/km (ritmo mezza)", "Ultimi 8 km a %s/km (ritmo mezza)"]
            wed = [track(d, 3, 2000, rp["T"] - 2, rp["T"] + 2, 90, title="Pista · soglia"),
                   track(d, 4, 1600, rp["T"] - 4, rp["T"], 60, title="Pista · soglia"),
                   track(d, 2, 3000, rp["HM"], rp["HM"] + 4, 120, title="Pista · ritmo mezza")][k]
            s = [[swim_css(d, k, "build"), rest("Riposo: ieri gara.") if k == 0 else run_easy(d, 45, 6)],
                 [gym(d, "Upper"), bike_q(d, [3, 3, 2][k], [10, 12, 20][k], [1.0, .98, .95][k], [1.03, 1.01, .98][k], [5, 5, 6][k], "soglia")],
                 [ftp_test(d)] if k == 1 else [bike_z2(d, 60), wed],
                 [swim_end(d, 3500), road_tempo(d, 4, 1.6, rp["T"], 60) if k == 1 else run_easy(d, 35)], [gym(d, "Lower")],
                 [bike_long(d, [165, 180, 195][k], ["3 x 15'", "3 x 20'", "2 x 30'"][k] + " a %s (80-85%% FTP)" % W(d, .8, .85), brick=20, brick_pace=(295, 300))],
                 [long_run(d, [18, 20, 21][k], tails[k] % P(rp["HM"] + 3)), swim_easy(d)]][i]
        elif typ == "shm":
            s = [[swim_css(d, 0, "build"), run_easy(d, 45, 6)],
                 [gym(d, "Upper"), bike_q(d, 2, 20, .95, .98, 6, "soglia")],
                 [bike_z2(d, 60), track(d, 2, 3000, rp["HM"] - 2, rp["HM"] + 2, 120, title="Pista · ritmo mezza")],
                 [swim_end(d, 3500), run_easy(d, 40)], [gym(d, "Lower", light=True)],
                 [bike_long(d, 180, "2 x 30' a %s (78-82%% FTP)" % W(d, .78, .82))],
                 [long_run(d, 18, "Dal km 6 al km 16: 10 km a %s/km (ritmo mezza)" % P(rp["HM"] + 2)), swim_easy(d)]][i]
        elif typ == "thm":
            s = [[swim_css(d, 1, "build"), run_easy(d, 40, 6)],
                 [bike_q(d, 3, 5, .95, .98, 3, "attivazione")],
                 [track(d, 4, 1600, rp["HM"] - 3, rp["HM"], 60, title="Pista · rifinitura")],
                 [swim_easy(d, "06:30", 2500), run_easy(d, 30)], [rest("Riposo. Frullato di barbabietola a colazione.")],
                 [run_easy(d, 20, 4, "10:00", "Corsa · attivazione pre-gara"), swim_easy(d, "17:00", 1500)],
                 [S("run", "GARA · Roma-Ostia", "09:00", 92, [
                     "Obiettivo sotto 1:30: %s/km" % P(rp["HM"]),
                     "Km 1-5 a 4:17-4:18, km 6-15 a 4:15-4:16, dal 16 spingi se stai bene",
                     "Riscaldamento: 10' facili + 3 allunghi"],
                     km=21.1, fuel="Colazione 3 ore prima. Gel con sodio 15' prima del via, poi gel al km 7 e al km 14 (quello con caffeina al 14). Frullato venerdì e sabato.", key=True)]][i]
        elif typ == "rechm":
            s = [[rest("Riposo: ieri mezza maratona.")], [bike_z2(d, 45, "19:00", drills=False)],
                 [swim_easy(d, "06:30", 2500), run_easy(d, 30)], [swim_end(d, 2500)], [rest()],
                 [bike_long(d, 120, None)], [long_run(d, 12), swim_easy(d)]][i]
        elif typ in ("spec",):
            sat = [bike_long(d, 210, "2 x 45' a %s (78-82%% FTP, ritmo gara)" % W(d, .78, .82), brick=20),
                   bike_long(d, 240, "3 x 30' a %s (80%% FTP)" % W(d, .78, .82), brick=30),
                   bike_long(d, 175, "SIMULAZIONE: 90 km a %s (75-80%% FTP) con alimentazione da gara" % W(d, .75, .8), brick=50),
                   bike_long(d, 270, "3 x 40' a %s (78-82%% FTP)" % W(d, .78, .82), brick=30)][k]
            if k == 2:
                sat["title"] = "Simulazione gara: bici 90 km + corsa 10 km"
                sat["fuel"] = "Come in gara: 80-90 g di carboidrati l'ora in bici (2 gel l'ora + 1 Carbo Bar nella prima ora), 1 Electrolytes Boost l'ora; in corsa 1 gel ogni 25'. Frullato a colazione."
            sun = [long_run(d, 16, "4 x 1 km a %s/km dentro la seconda metà" % P(rp["HM"] + 4)),
                   long_run(d, 19), long_run(d, 12, None), long_run(d, 20, "Ultimi 6 km a %s/km" % P(rp["HM"] + 14))][k]
            s = [[swim_css(d, k, "spec"), run_easy(d, 45, 6) if k != 3 else run_easy(d, 40, 6)],
                 [gym_maint(d), bike_q(d, [3, 2, 3, 2][k], [20, 30, 25, 40][k], .8, .85, 5, "ritmo gara")],
                 [bike_z2(d, [75, 90, 90, 90][k]), track(d, *[(6, 1000, rp["K10"] - 5, rp["K10"], 90), (5, 1200, rp["K10"] - 2, rp["K10"] + 2, 90),
                                             (7, 800, rp["I"] - 2, rp["I"] + 3, 90), (6, 1000, rp["K10"] - 5, rp["K10"], 90)][k], title="Pista · velocità")],
                 [swim_end(d, [3500, 3800, 3800, 4000][k], "Ultimi 1.900 m continui a ritmo gara %s" % sw(d, "RACE") if k in (2, 3) else ""), run_easy(d, [40, 45, 50, 50][k])],
                 [swim_easy(d, "06:00", 2200)] + ([bike_z2(d, 45, "19:00", drills=False)] if k else []),
                 [sat], [sun]][i]
        elif typ == "recftp":
            s = [[swim_easy(d, "08:00", 2500), run_easy(d, 35, 6, "10:30")],  # Pasquetta
                 [bike_z2(d, 45, "19:00", drills=False)],
                 [ftp_test(d)], [swim_end(d, 3000), run_easy(d, 35)], [rest()],
                 [bike_long(d, 120, None, brick=15)], [long_run(d, 12), swim_easy(d)]][i]
        elif typ == "taper":
            s = [[swim_css(d, 3, "spec"), run_easy(d, 40, 6)],
                 [gym_maint(d), bike_q(d, 2, 20, .8, .82, 5, "ritmo gara")],
                 [track(d, 5, 1000, rp["K10"] - 5, rp["K10"], 90, title="Pista · brillantezza")],
                 [swim_end(d, 3000, "1.500 m continui a ritmo gara %s" % sw(d, "RACE")), run_easy(d, 30)],
                 [swim_easy(d, "06:30", 2000)],
                 [bike_long(d, 135, "2 x 20' a %s (ritmo gara)" % W(d, .78, .8), brick=15)],
                 [long_run(d, 12)]][i]
        elif typ == "race":
            rp7 = rp["R703"]
            s = [[S("swim", "Nuoto · richiamo", "06:30", 45, ["400 A1", "4 x 200 a ritmo gara %s, recupero 20''" % sw(d, "RACE"), "4 x 50 B2", "200 sciolti", "Totale circa 2.000 m"], fuel=F_SWIM),
                  run_easy(d, 30, 6)],
                 [bike_q(d, 3, 8, .78, .82, 4, "richiamo ritmo gara")],
                 [swim_easy(d, "06:30", 1500), S("run", "Corsa · richiamo", "19:00", 30, ["20' facili a %s" % E(d), "4 x 2' a %s/km, recupero 1'" % P(rp7[0] - 20)], km=5, fuel=F_EASY)],
                 [S("run", "Viaggio a Jesolo", "", 25, ["20' di corsa facile appena arrivi, più 4 allunghi", "Cena con pasta o riso, niente cibi nuovi"], km=4, fuel="Frullato di barbabietola a colazione e a cena.")],
                 [S("swim", "Nuoto in mare + bici di prova", "09:00", 50, [
                     "15-20' di nuoto in mare con la muta: avvistamenti ogni 6-8 bracciate, 4 x 1' a ritmo gara",
                     "20' di bici facile con 3 x 1' a %s per controllare cambi e freni" % W(d, .8),
                     "Check-in bici e borse nel pomeriggio, poi gambe su"], fuel="Frullato a colazione. Pranzo e cena ricchi di carboidrati (8-10 g per kg nei 2 giorni: chiedi le quantità alla nutrizionista).")],
                 [S("race", "IRONMAN 70.3 JESOLO", "08:00", 330, [
                     "Sveglia 4:45. Colazione alle 5:00: 120-150 g di carboidrati (fette biscottate, miele, banana), frullato di barbabietola",
                     "NUOTO 1,9 km: partenza controllata i primi 200 m, poi %s. Obiettivo 34-36'" % sw(d, "RACE"),
                     "T1: entro 4'",
                     "BICI 90 km: %s (75-80%% FTP), mai sopra %s in salita o in ripartenza. Obiettivo 2:53-2:58" % (W(d, .75, .8), W(d, .9)),
                     "T2: entro 3'",
                     "CORSA 21,1 km: km 1-5 a %s/km anche se ti senti fresco, poi %s–%s/km, dal km 16 quello che hai. Obiettivo 1:48-1:52" % (P(rp7[1] + 5), P(rp7[0]), P(rp7[1])),
                     "Totale stimato: 5:20-5:30"],
                     fuel="Bici: 80-90 g di carboidrati l'ora (2 gel l'ora + 1 Carbo Bar nella prima ora), gel con caffeina a 2h e a 2h40, 1 Electrolytes Boost per borraccia. Corsa: 1 gel ogni 25-30' (caffeina al km 10), acqua a ogni ristoro.", key=True)],
                 [rest("Recupero. Camminata, viaggio di ritorno. Festa!")]][i]
        s = special(d, s or [], rp)
        out.append((d, s))
    return out


# ------------------------------------------------------------------ gare del Lazio e acque libere (date 2027 stimate dal calendario 2026)
def race_ev(title, start, dur, kind, steps, fuel, km=None, sport="race"):
    x = S(sport, title, start, dur, steps, km=km, fuel=fuel, key=True, ok=True)
    x["kind"] = kind  # "test" o "allenamento"
    return x


def ow(d, start, mins, extra=""):
    return S("swim", "Acque libere", start, mins, [
        "%d' in mare con la muta e la cuffia in neoprene: l'acqua ad aprile è sui 14-16 °C" % mins,
        "I primi 5' piano per abituarti al freddo, poi tratti da 3-4' a ritmo gara %s" % sw(d, "RACE"),
        "Avvistamenti ogni 6-8 bracciate, prova a nuotare dritto verso un punto a terra",
        "Mai da solo: in compagnia o con la boa di sicurezza"] + ([extra] if extra else []), fuel="Una bevanda calda dopo.",
        alts=["16:00", "11:00"], ok=True)


def special(d, s, rp):
    iso = d.isoformat()
    if iso == "2026-12-04":
        return [bike_z2(d, 90, "09:00"), dict(run_easy(d, 30, 6, "15:00", "Corsa · veloce prima del volo"),
                steps=["30' facili a %s, più 6 allunghi" % E(d), "Aereo alle 21:00: doccia e via"])]
    if iso == "2027-02-18":  # il ritmo mezza della settimana va al giovedì sera
        return [x for x in s if x["sport"] != "run"] + [road_tempo(d, 2, 4, rp["HM"] + 2, 120, title="Corsa · ritmo mezza su strada")]
    if iso == "2027-02-20":  # sabato: bici lunga, domenica duathlon
        return [bike_long(d, 150, "2 x 20' a %s (80%% FTP)" % W(d, .78, .82), start="08:30")]
    if iso == "2027-02-21":
        return [race_ev("Duathlon di Carnevale · Sabaudia", "09:30", 80, "allenamento", [
            "Duathlon sprint: circa 5 km corsa, 20 km bici, 2,5 km corsa",
            "SOLO ALLENAMENTO: tra 7 giorni c'è la Roma-Ostia. Corsa a %s/km (ritmo mezza, non di più), bici a %s" % (P(rp["HM"]), W(d, .8, .88)),
            "Usalo per provare i cambi e la bici dopo la corsa",
            "Data stimata dal 2026 (22 febbraio): verifica sul calendario FITRI 2027"],
            "1 gel con sodio 15' prima del via. Acqua in bici.", km=7.5)]
    if iso == "2027-03-13":  # sabato prima del duathlon test: niente brick lungo
        return [bike_long(d, 120, None, start="09:00")]
    if iso == "2027-03-14":
        return [race_ev("Duathlon Sprint di Ostia", "09:30", 80, "test", [
            "Duathlon sprint: circa 5 km corsa, 20 km bici, 2,5 km corsa",
            "TEST A TUTTA: corsa 1 a %s/km, bici a %s (95-100%% FTP), corsa 2 quello che resta" % (P(rp["K10"] + 5), W(d, .95, 1.0)),
            "Cosa misura: quanto tieni in bici a tutta e come corri dopo. Segna i tempi dei cambi",
            "Data stimata dal 2026 (15 marzo): verifica sul calendario FITRI 2027"],
            "Colazione 3 ore prima, frullato di barbabietola. 1 gel con sodio 15' prima del via.", km=7.5)]
    if iso == "2027-03-21":
        return s + [ow(d, "15:00", 25)]
    if iso == "2027-03-28":
        return s + [ow(d, "15:00", 30, "Domenica di Pasqua: se la spiaggia non è raggiungibile, sposta a lunedì 29 (festivo)")]
    if iso == "2027-04-03":
        return [S("swim", "Test nuoto in mare · Ibiza", "10:00", 45, [
                    "Riscaldamento: 10' sciolti con la muta",
                    "TEST: 1.900 m continui a ritmo gara %s, come a Jesolo: partenza controllata, avvistamenti ogni 6-8 bracciate" % sw(d, "RACE"),
                    "Obiettivo 34-36'. Avvia il Garmin in modalità acque libere e segna il tempo: mi serve per Jesolo",
                    "Non a tutta: stasera c'è la mezza",
                    "Acqua a Ibiza ad aprile circa 16 °C: muta e cuffia in neoprene, mai da solo"],
                    fuel="Colazione normale 2 ore prima. Dopo: pranzo ricco di carboidrati entro le 14:00.", key=False, ok=True),
                race_ev("Ibiza Media Maratón (di allenamento)", "18:00", 100, "allenamento", [
                    "ALLENAMENTO, non gara: km 1-10 a %s/km, km 11-21 a %s/km" % (P(rp["HM"] + 25), P(rp["HM"] + 12)),
                    "Arrivi con il nuoto della mattina nelle gambe, come a Jesolo arrivi con nuoto e bici: chiudi con la sensazione di averne ancora",
                    "Prova l'alimentazione della gara: 1 gel ogni 25-30'",
                    "Partenza alle 18:00 nel 2026 (Sant Josep): l'orario 2027 non è ancora confermato, e alcuni siti indicano il 10 aprile invece del 3"],
                    "Pranzo entro le 14:00, uno spuntino leggero alle 16:00. Frullato: a Ibiza usa uno shot di barbabietola da 70 ml alle 15:00. 1 gel ogni 25-30', acqua ai ristori.",
                    km=21.1, sport="run")]
    if iso == "2027-04-04":
        return [rest("Rientro da Ibiza. Se te la senti, 30' di bici o corsa sciolta, altrimenti riposo.")]
    if iso == "2027-04-10":
        return [bike_long(d, 180, "2 x 30' a %s (ritmo gara)" % W(d, .78, .82), start="08:30")]
    if iso == "2027-04-11":
        return [race_ev("Triathlon Sprint · Santa Marinella", "10:00", 80, "test", [
            "Triathlon sprint: 750 m nuoto, 20 km bici, 5 km corsa",
            "TEST GENERALE PER JESOLO a 13 giorni: muta, partenza in mare, avvistamenti, cambi, alimentazione",
            "Nuoto a %s, bici a %s (90-95%% FTP), corsa a %s/km" % (sw(d, "B1"), W(d, .9, .95), P(rp["K10"] + 5)),
            "Dopo la gara: 1h30 di bici facile a %s per completare il volume della settimana" % W(d, .6, .7),
            "Data stimata dal 2026 (12 aprile): verifica sul calendario FITRI 2027"],
            "Colazione 3 ore prima, frullato di barbabietola. 1 gel con sodio 15' prima del via.", km=5)]
    if iso == "2027-04-18":
        return s + [ow(d, "15:00", 30, "Ultima uscita in mare prima di Jesolo: usa la muta della gara")]
    return s


# ------------------------------------------------------------------ calendario, lavoro, conflitti
def hm(x):
    h, m = x.split(":")
    return int(h) * 60 + int(m)


def main():
    cal = rj(os.path.join(DATA, "calendar", "season.json"), []) or []
    track_open = (rj(os.path.join(DATA, "coach", "track.json"), {}) or {}).get("open", [[]] * 7)
    weeks_out, conflicts = [], []
    counters = {}
    for ws_s, typ, label in WEEKS:
        ws = D.fromisoformat(ws_s)
        k = counters.get(typ, 0)
        counters[typ] = k + 1
        days = []
        tot = {"h": 0, "run": 0.0, "bike": 0.0, "swim": 0, "hs": {"swim": 0, "bike": 0, "run": 0, "gym": 0}}
        for d, sess in week_days(ws, typ, k):
            iso = d.isoformat()
            evs, away_t = [], None
            for e in cal:
                tbc = "tbc" in e["title"].lower()
                title = e["title"].replace("⚽", "").replace(" (time TBC)", "").strip()
                if e["allday"]:
                    if e["start"][:10] <= iso < e["end"][:10]:
                        away_t = title.replace("Stay at ", "").replace("Soggiorno: ", "")
                    continue
                if e["start"][:10] != iso:
                    continue
                home = e["source"] == "roma" and "olimpico" in e["location"].lower()
                s0, e0 = hm(e["start"][11:16]), hm(e["end"][11:16]) or 24 * 60
                if e["source"] == "roma":
                    title += " (allo stadio)" if home else " (in TV)"
                    if tbc:
                        title += " · orario da definire"
                    elif home:
                        s0, e0 = s0 - 120, min(24 * 60, e0 + 60)
                evs.append({"title": title, "s": s0, "e": e0, "tbc": tbc,
                            "time": "" if tbc else "%s–%s" % (m2hm(s0), m2hm(e0))})
            work = d.weekday() < 5 and d not in HOLIDAYS and not away_t
            blocks = [x for x in evs if not x["tbc"]] + ([{"title": "Lavoro", "s": 8 * 60 + 40, "e": 18 * 60 + 45}] if work else [])
            if away_t and d < RACE - dt.timedelta(days=3) and iso != "2026-12-04":
                note = "Sei fuori casa (%s). Se scii, conta come allenamento aerobico: niente altro. Se non scii: 30-40' di corsa facile a %s." % (away_t, E(d))
                sess = [away(note)]
            out_s, taken = [], []
            for x in sess:
                x = dict(x)
                if x["sport"] in ("rest", "away") or not x["start"]:
                    out_s.append(x)
                    continue
                if iso == "2027-01-05" and x["title"] == "Bici · soglia":
                    x["ok"] = True
                    x["steps"] = x["steps"] + ["Venezia-Roma è alle 18:30: fai i rulli guardando la partita"]
                if x["sport"] == "race":
                    x["ok"] = True
                cands = [x["start"]] + x["alts"]
                if d in HOLIDAYS and d.weekday() < 5 and hm(x["start"]) < 8 * 60:
                    cands = ["08:30"] + cands
                chosen = None
                for c in cands:
                    a, b = hm(c), hm(c) + x["dur"]
                    if a < 5 * 60 + 45 or ((d.weekday() >= 5 or d in HOLIDAYS) and a < 7 * 60):
                        continue
                    clash = [y for y in blocks if not (b + 30 <= y["s"] or a >= y["e"] + 15)]
                    if x.get("ok"):
                        clash = [y for y in clash if y["title"] != "Lavoro" and "TV" not in y["title"] and "ironman" not in y["title"].lower()]
                    if not clash and all(b <= ta or a >= tb for ta, tb in taken):
                        chosen = c
                        break
                if chosen is None:
                    conflicts.append((iso, x["title"], [y["title"] for y in blocks]))
                    x["clash"] = True
                    chosen = x["start"]
                elif chosen != x["start"]:
                    x["moved"] = "spostata dalle %s per %s" % (x["start"], ", ".join(y["title"] for y in blocks if not (hm(x["start"]) + x["dur"] + 30 <= y["s"] or hm(x["start"]) >= y["e"] + 15)) or "orario")
                a = hm(chosen)
                taken.append((a, a + x["dur"]))
                x["slot"] = "%s–%s" % (chosen, m2hm(a + x["dur"]))
                if x["sport"] == "run" and x["title"].startswith("Pista"):
                    x["track"] = ", ".join("%s–%s" % tuple(r) for r in track_open[d.weekday()]) or "chiusa agli amatori: falle su strada"
                out_s.append(x)
                tot["h"] += x["dur"] / 60
                if x["sport"] in tot["hs"]:
                    tot["hs"][x["sport"]] += x["dur"] / 60
                if x["sport"] == "run" and x.get("km"): tot["run"] += x["km"]
                if x["sport"] == "bike" and x.get("km"): tot["bike"] += x["km"]
                if x["sport"] == "swim":
                    for st in x["steps"]:
                        if st.startswith("Totale"):
                            tot["swim"] += int("".join(ch for ch in st if ch.isdigit()) or 0)
            out_s.sort(key=lambda x: x.get("slot", "99"))
            # frullato di barbabietola per le sedute chiave
            beet = None
            key = [x for x in out_s if x.get("key") and x.get("slot")]
            if key:
                x0 = key[0]
                a = hm(x0["slot"].split("–")[0])
                wake = 6 * 60 if d.weekday() < 5 else 7 * 60
                if "IRONMAN" in x0["title"] or "GARA" in x0["title"]:
                    beet = "Frullato di barbabietola: a colazione e a cena il giorno prima" + (", e alle 5:00 con la colazione." if "IRONMAN" in x0["title"] else ".")
                elif a - 180 < wake:
                    beet = "Frullato di barbabietola la sera prima, a cena verso le 20."
                elif work and 8 * 60 + 10 < a - 180 < 19 * 60:
                    beet = "Frullato di barbabietola a colazione (e anche ieri a colazione)."
                else:
                    beet = "Frullato di barbabietola alle %s." % m2hm(a - 180)
            days.append({"date": iso, "dow": d.weekday(), "away": away_t, "holiday": d in HOLIDAYS,
                         "events": [{"title": y["title"], "time": y["time"]} for y in evs], "sessions": out_s, "beet": beet})
        weeks_out.append({"start": ws_s, "label": label, "phase": PHASE[typ], "typ": typ, "days": days,
                          "tot": {"h": round(tot["h"], 1), "run": round(tot["run"]), "bike": round(tot["bike"]), "swim": tot["swim"],
                                  "hs": {k2: round(v, 1) for k2, v in tot["hs"].items()}},
                          "ftp": ftp(ws + dt.timedelta(days=3)), "css": P(css(ws))})
    for c in conflicts:
        print("CONFLITTO", c)
    payload = {"weeks": weeks_out, "built": dt.datetime.now().strftime("%d/%m/%Y"), "race": RACE.isoformat()}
    with open(os.path.join(HERE, "season_template.html"), encoding="utf-8") as f:
        html = f.read()
    html = html.replace("/*__DATA__*/null", json.dumps(payload, ensure_ascii=False, separators=(",", ":")))
    with open(os.path.join(HERE, "season.html"), "w", encoding="utf-8") as f:
        f.write(html)
    print("Piano creato: %d settimane, %d KB" % (len(weeks_out), os.path.getsize(os.path.join(HERE, "season.html")) // 1024))
    for w in weeks_out:
        hs = w["tot"]["hs"]
        print(w["start"], w["label"][:24].ljust(24), "ore %4.1f | nuoto %.1fh %5dm | bici %.1fh | corsa %.1fh %3dkm | forza %.1fh" % (w["tot"]["h"], hs["swim"], w["tot"]["swim"], hs["bike"], hs["run"], w["tot"]["run"], hs["gym"]))


if __name__ == "__main__":
    main()
