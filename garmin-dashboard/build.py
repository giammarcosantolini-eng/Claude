"""Legge data/ e crea dashboard.html (un solo file, si apre senza server).

Uso:  python build.py
Solo librerie standard di Python. Nel file finiscono solo numeri aggregati:
niente GPS, niente nome utente.
"""
import datetime as dt
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
OUT = os.path.join(HERE, "dashboard.html")

# ------------------------------------------------------------ obiettivi
GOAL = {
    "name": "Ironman 70.3 Jesolo",
    "date": "2027-04-24",
    "target": "5:30:00",
    # una possibile ripartizione del tempo obiettivo (secondi)
    "split": {"swim": 35 * 60, "t": 8 * 60, "bike": 173 * 60, "run": 114 * 60},
    "dist": {"swim": 1.9, "bike": 90.0, "run": 21.1},
}
TESTS = [
    {"name": "10 km di corsa", "date": "2027-01-17", "km": 10.0, "target": 40 * 60},
    {"name": "Roma-Ostia (mezza)", "date": "2027-02-28", "km": 21.0975, "target": 90 * 60},
]

SPORT = {
    "lap_swimming": "swim", "open_water_swimming": "swim", "swimming": "swim",
    "cycling": "bike", "road_biking": "bike", "indoor_cycling": "bike",
    "virtual_ride": "bike", "gravel_cycling": "bike", "mountain_biking": "bike",
    "running": "run", "treadmill_running": "run", "trail_running": "run",
    "track_running": "run", "indoor_running": "run",
    "strength_training": "gym", "hiit": "gym", "indoor_cardio": "gym",
    "multi_sport": "multi",
}
ORDER = ["swim", "bike", "run", "gym", "multi", "other"]


def read_json(path, default=None):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def load_folder(name):
    """Tutti gli elementi delle finestre scaricate, senza doppioni per data."""
    seen, folder = {}, os.path.join(DATA, name)
    if os.path.isdir(folder):
        for f in sorted(os.listdir(folder)):
            if f.endswith(".json"):
                for x in read_json(os.path.join(folder, f), []) or []:
                    k = x.get("calendarDate") or x.get("summaryDate") if isinstance(x, dict) else None
                    seen[k or id(x)] = x
    return list(seen.values())


def g(d, *keys):
    for k in keys:
        if not isinstance(d, dict):
            return None
        d = d.get(k)
    return d


def monday(d):
    return d - dt.timedelta(days=d.weekday())


def main():
    today = dt.date.today()
    acts = read_json(os.path.join(DATA, "activities.json"), []) or []
    A = []
    for a in acts:
        try:
            day = dt.date.fromisoformat(a["startTimeLocal"][:10])
        except (KeyError, ValueError):
            continue
        A.append({
            "day": day,
            "sport": SPORT.get(g(a, "activityType", "typeKey"), "other"),
            "type": g(a, "activityType", "typeKey"),
            "name": (a.get("activityName") or "")[:60],
            "km": (a.get("distance") or 0) / 1000,
            "sec": a.get("duration") or 0,
            # tempo in movimento: esclude le pause a bordo vasca e ai semafori
            "mov": a.get("movingDuration") or a.get("duration") or 0,
            "elev": a.get("elevationGain") or 0,
            "hr": a.get("averageHR"),
            "load": a.get("activityTrainingLoad") or 0,
            "kcal": a.get("calories") or 0,
            "np": a.get("normPower"),
            "pw": a.get("avgPower"),
            # scarto i parziali impossibili (errori GPS): meno di 2:30/km
            "f1k": a.get("fastestSplit_1000") if (a.get("fastestSplit_1000") or 0) >= 150 else None,
            "f5k": a.get("fastestSplit_5000") if (a.get("fastestSplit_5000") or 0) >= 750 else None,
            "zones": [a.get("hrTimeInZone_%d" % i) or 0 for i in range(1, 6)],
        })

    # ---------------------------------------------------- settimane
    first = min([a["day"] for a in A] or [today])
    w0, wn = monday(first), monday(today)
    weeks = []
    w = w0
    while w <= wn:
        weeks.append(w)
        w += dt.timedelta(days=7)
    wi = {w: i for i, w in enumerate(weeks)}

    def blank():
        return {s: {"km": 0.0, "h": 0.0, "n": 0} for s in ORDER}

    wk = [blank() for _ in weeks]
    load = [0.0] * len(weeks)
    zones = [[0.0] * 5 for _ in weeks]
    perf = {k: [[0.0, 0.0] for _ in weeks] for k in ("run", "eff", "bike", "swim")}
    for a in A:
        i = wi[monday(a["day"])]
        s = wk[i][a["sport"]]
        s["km"] += a["km"]; s["h"] += a["sec"] / 3600; s["n"] += 1
        load[i] += a["load"]
        for z in range(5):
            zones[i][z] += a["zones"][z] / 3600
        if a["sport"] == "run" and a["km"] > 2:
            perf["run"][i][0] += a["mov"]; perf["run"][i][1] += a["km"]
            if a["hr"]:
                # efficienza: metri al minuto per ogni battito (piu' alto = meglio)
                perf["eff"][i][0] += (a["km"] * 1000 / (a["sec"] / 60)) / a["hr"] * a["sec"]
                perf["eff"][i][1] += a["sec"]
        if a["sport"] == "bike" and a["np"]:
            perf["bike"][i][0] += a["np"] * a["sec"]; perf["bike"][i][1] += a["sec"]
        if a["sport"] == "swim" and a["km"] > 0.3:
            perf["swim"][i][0] += a["mov"]; perf["swim"][i][1] += a["km"] * 10  # /100 m, solo tempo in acqua

    def ratio(pair, nd=1):
        return round(pair[0] / pair[1], nd) if pair[1] else None

    weekly = {
        "labels": [w.isoformat() for w in weeks],
        "sports": {s: {"km": [round(x[s]["km"], 1) for x in wk],
                       "h": [round(x[s]["h"], 2) for x in wk],
                       "n": [x[s]["n"] for x in wk]} for s in ORDER},
        "load": [round(x) for x in load],
        "zones": [[round(z, 2) for z in row] for row in zones],
        "perf": {
            "run": [ratio(p) for p in perf["run"]],      # sec/km
            "eff": [ratio(p, 2) for p in perf["eff"]],   # m/min per battito
            "bike": [ratio(p, 0) for p in perf["bike"]],  # watt normalizzati
            "swim": [ratio(p) for p in perf["swim"]],    # sec/100 m
        },
    }

    # ---------------------------------------------------- giornalieri
    days = {}
    for x in load_folder("daily"):
        d = x.get("calendarDate")
        if not d:
            continue
        days.setdefault(d, {}).update({
            "rhr": g(x, "heartRate", "restingValue"),
            "kcal": g(x, "calories", "burnedTotal"),
            "kact": g(x, "calories", "burnedActive"),
            "stress": g(x, "stress", "avgLevel"),
            "bbmax": g(x, "bodyBattery", "maxValue"),
            "steps": g(x, "movement", "steps", "value") if isinstance(g(x, "movement", "steps"), dict) else g(x, "movement", "steps"),
        })
    for x in load_folder("sleep"):
        d = x.get("calendarDate")
        if d and x.get("sleepTimeSeconds"):
            days.setdefault(d, {}).update({
                "sleep": round(x["sleepTimeSeconds"] / 3600, 2),
                "deep": round((x.get("deepSleepSeconds") or 0) / 3600, 2),
                "rem": round((x.get("remSleepSeconds") or 0) / 3600, 2),
                "score": g(x, "sleepScores", "overall", "value"),
            })
    for x in load_folder("hrv"):
        d = x.get("calendarDate")
        if d and x.get("lastNightAvg"):
            days.setdefault(d, {}).update({
                "hrv": x.get("lastNightAvg"), "hrv7": x.get("weeklyAvg"),
                "hlo": g(x, "baseline", "balancedLow"), "hhi": g(x, "baseline", "balancedUpper"),
                "hst": x.get("status"),
            })
    for x in load_folder("weight"):
        d = x.get("summaryDate")
        wgt = g(x, "latestWeight", "weight")
        if d and wgt:
            days.setdefault(d, {})["kg"] = round(wgt / 1000, 1)
    dkeys = sorted(k for k in days if k <= today.isoformat())
    daily = {"labels": dkeys}
    for f in ("rhr", "kcal", "kact", "sleep", "deep", "rem", "score", "hrv", "hrv7", "hlo", "hhi", "kg", "stress", "bbmax"):
        daily[f] = [days[k].get(f) for k in dkeys]
    hst = next((days[k].get("hst") for k in reversed(dkeys) if days[k].get("hst")), None)

    # ---------------------------------------------------- prestazione recente
    six = today - dt.timedelta(weeks=6)
    eight = today - dt.timedelta(weeks=8)

    def recent(sport, cond=lambda a: True):
        r = [a for a in A if a["sport"] == sport and a["day"] >= six and cond(a)]
        return sum(a["mov"] for a in r), sum(a["km"] for a in r)

    rs, rk = recent("run", lambda a: a["km"] > 2)
    bs, bk = recent("bike", lambda a: a["type"] in ("road_biking", "cycling") and a["km"] > 20)
    ss, sk = recent("swim", lambda a: a["km"] > 0.3)
    best5 = min([a["f5k"] for a in A if a["f5k"] and a["day"] >= eight] or [0]) or None
    now = {
        "run_pace": rs / rk if rk else None,           # sec/km
        "bike_kmh": bk / (bs / 3600) if bs else None,  # km/h
        "swim_pace": ss / (sk * 10) if sk else None,   # sec/100 m
        "best5k": best5,
    }

    # ---------------------------------------------------- record
    def top(sport, key, rev=True, cond=lambda a: True):
        r = [a for a in A if a["sport"] == sport and a[key] and cond(a)]
        if not r:
            return None
        a = sorted(r, key=lambda a: a[key], reverse=rev)[0]
        return {"day": a["day"].isoformat(), "name": a["name"], "km": round(a["km"], 2),
                "sec": round(a["sec"]), "elev": round(a["elev"]), "load": round(a["load"]),
                "val": a[key]}

    big_week = max(range(len(weeks)), key=lambda i: sum(wk[i][s]["h"] for s in ORDER)) if weeks else None
    records = {
        "run_long": top("run", "km"), "bike_long": top("bike", "km"), "swim_long": top("swim", "km"),
        "f1k": top("run", "f1k", rev=False), "f5k": top("run", "f5k", rev=False),
        "elev": top("bike", "elev"), "load": max((top(s, "load") for s in ("swim", "bike", "run", "gym", "multi")),
                                                 key=lambda r: r["val"] if r else -1),
        "week": {"start": weeks[big_week].isoformat(),
                 "h": round(sum(wk[big_week][s]["h"] for s in ORDER), 1),
                 "km": round(sum(wk[big_week][s]["km"] for s in ORDER), 1),
                 "n": sum(wk[big_week][s]["n"] for s in ORDER)} if big_week is not None else None,
    }
    kc = [(k, days[k].get("kcal")) for k in dkeys if days[k].get("kcal")]
    if kc:
        k, v = max(kc, key=lambda x: x[1])
        records["kcal"] = {"day": k, "val": v}

    totals = {"n": len(A), "km": round(sum(a["km"] for a in A)), "h": round(sum(a["sec"] for a in A) / 3600),
              "first": first.isoformat()}

    # ---------------------------------------------------- piano del coach
    coach = None
    nutrition = None
    runmodel = None
    plan = read_json(os.path.join(DATA, "coach", "plan.json"))
    strength = read_json(os.path.join(DATA, "coach", "strength.json"), {}) or {}
    if plan:
        lib = dict(plan.get("library", {}))
        lib.update(strength)

        def sport_of(t):
            t = t.lower()
            if "nuoto" in t: return "swim"
            if "bike" in t or "cycling" in t or "bici" in t: return "bike"
            if "corsa" in t or "test" in t or "km" in t and "nuoto" not in t: return "run"
            if "preparazione" in t: return "gym"
            return "other"

        done_by_day = {}
        for a in A:
            done_by_day.setdefault(a["day"].isoformat(), []).append(a)
        nut = read_json(os.path.join(DATA, "coach", "nutrition.json"), {}) or {}
        DUR = {"N1": 70, "N2": 75, "N3": 70, "C1": 50, "C2": 60, "C3": 65, "C4": 50, "C5": 50,
               "B1": 55, "B2": 55, "B3": 180, "Upper": 60, "Lower": 60}
        DUR_TXT = {"2000m": 45, "test": 75}

        def fuel(b, sp, key):
            """Integrazione consigliata per la seduta: (testo, kcal extra)."""
            t = b["text"].lower()
            evening = b["start"] >= "16"
            if sp == "swim":
                return "Acqua a bordo vasca. Nessun gel: la seduta dura poco più di un'ora.", 0
            if sp == "gym":
                return "Solo acqua. Creatina dopo la seduta.", 0
            if "test" in t:
                return "1 gel Limone con sodio 15' prima del via. Borraccia con 1 Electrolytes Boost durante il riscaldamento.", 120
            if sp == "run":
                if key in ("C2", "C3", "C5"):
                    return "1 Electrolytes Boost in borraccia. 1 gel Limone con sodio 10-15' prima della parte veloce.", 120
                return "Solo acqua: corsa facile e breve.", 0
            if sp == "bike":
                if key == "B3":
                    return ("60-80 g di carboidrati l'ora. Prime 2 ore: 1 Carbo Bar + 1 gel all'ora. Dalla terza ora: 2 gel l'ora, "
                            "il gel con caffeina nell'ultima ora. 1 Electrolytes Boost per borraccia (circa 1 l'ora)."), 650
                extra = " Niente gel con caffeina: è sera e disturba il sonno." if evening else ""
                if key == "B1":
                    return "Borraccia con 1 Electrolytes Boost (sui rulli si suda tanto). 1 gel Mango dopo 30'." + extra, 120
                return "Borraccia con 1 Electrolytes Boost (sui rulli si suda tanto)." + extra, 0
            return "", 0

        def meals_for(blocks):
            tips = []
            starts = sorted(b["start"] for b in blocks)
            if any(s < "07:30" for s in starts):
                tips.append("Prima dell'allenamento del mattino: 2 fette biscottate con miele (dalla colazione). Il resto della colazione subito dopo.")
            if any("08:" in s for s in starts):
                tips.append("Colazione completa verso le 7:00, almeno un'ora e mezza prima di partire.")
            if any("12:" <= s < "16:" for s in starts):
                tips.append("Pranzo entro le 11:30, così arrivi all'allenamento con la digestione fatta.")
            if any(s >= "16:" for s in starts):
                tips.append("Merenda del piano verso le 16:30. Cena dopo l'allenamento.")
            return tips

        cal = (read_json(os.path.join(DATA, "calendar", "events.json"), {}) or {}).get("events", [])

        def hm2m(x):
            h, m = x.replace(".", ":").split(":")[:2]
            return int(h) * 60 + int(m)

        WORK = (8 * 60 + 40, 18 * 60 + 45)  # lavoro 9:00-18:40 + 20 min di viaggio: libero dalle 19:00

        def busy(day):
            out = []
            if day.weekday() < 5:
                out.append({"title": "Lavoro", "allday": False, "s": WORK[0], "e": WORK[1], "time": "9:00–18:40 (+20 min di viaggio)", "work": True})
            for e in cal:
                if e["allday"]:
                    if e["start"][:10] <= day.isoformat() < e["end"][:10]:
                        out.append({"title": e["title"], "allday": True})
                    continue
                if e["start"][:10] == day.isoformat():
                    out.append({"title": e["title"], "allday": False, "s": hm2m(e["start"][11:16]),
                                "e": hm2m(e["end"][11:16]) if e["end"][:10] == day.isoformat() else 24 * 60,
                                "time": e["start"][11:16] + "–" + e["end"][11:16]})
            return out

        def slot_range(b, key):
            s0 = hm2m(b["start"])
            dur = DUR.get(key) or next((v for k, v in DUR_TXT.items() if k in b["text"].lower()), None) or (hm2m(b["slot"].split("–")[-1]) - s0 if "–" in b["slot"] else 60)
            return s0, s0 + dur

        def free(s, e, ev, taken):
            return all(e + 30 <= x["s"] or s >= x["e"] + 15 for x in ev if not x["allday"]) and \
                   all(e <= a or s >= b for a, b in taken)

        ovr = read_json(os.path.join(DATA, "coach", "overrides.json"), []) or []
        GGN = ["lun", "mar", "mer", "gio", "ven", "sab", "dom"]
        for w in plan["weeks"]:
            ws = dt.date.fromisoformat(w["start"])
            for o in ovr:
                k = (dt.date.fromisoformat(o["date"]) - ws).days
                if not 0 <= k < 7:
                    continue
                src = next((b for b in w["days"][k] if b["text"] == o["text"] and not b.get("moved")), None)
                if not src:
                    continue
                w["days"][k].remove(src)
                nk = (dt.date.fromisoformat(o["new_date"]) - ws).days
                nb = dict(src, start=o["new_slot"].split("–")[0], slot=o["new_slot"],
                          moved="da %s %s" % (GGN[k], src["slot"]), why=o.get("why", ""), ok=o.get("ok", False),
                          meal=o.get("meal"), fuel=o.get("fuel"))
                if o.get("new_text"):
                    nb["text"] = o["new_text"]
                w["days"][nk].append(nb)
                w["days"][nk].sort(key=lambda x: x["start"])

        planK = sum(m.get("kcal", 0) for m in nut.get("meals", []))
        ks = [k for k in dkeys if (today - dt.timedelta(days=28)).isoformat() <= k < today.isoformat()]
        rest = sum(days[k].get("kcal") or 0 for k in ks) and \
            sum(g(x, "calories", "burnedResting") or 0 for x in load_folder("daily") if x.get("calendarDate") in ks) / max(1, len(ks))
        rest = rest or 2000
        bmr_min = rest / 1440
        RATE = {"swim": 8.4, "run": 12.8, "gym": 4.6, "bike": 10.0, "multi": 10.0, "other": 6.0}
        RATE_KEY = {"B1": 12.2, "B2": 8.4, "B3": 7.2}

        def kcal_est(sess):
            tot = rest + 50
            for s in sess:
                a, z = s["_r"]
                r = RATE_KEY.get(s["key"], RATE.get(s["sport"], 6.0))
                tot += max(0, r - bmr_min) * (z - a)
            return round(tot)

        out_weeks = []
        for w in plan["weeks"]:
            ws = dt.date.fromisoformat(w["start"])
            if ws < monday(today) or ws > monday(today) + dt.timedelta(days=7):
                continue
            days_out = []
            for k, blocks in enumerate(w["days"]):
                day = ws + dt.timedelta(days=k)
                avail = list(done_by_day.get(day.isoformat(), []))
                sess = []
                ev = busy(day)
                ranges = []
                for b in blocks:
                    k0 = (b["codes"] or [None])[0]
                    ranges.append(slot_range(b, k0))
                for bi, b in enumerate(blocks):
                    sp = sport_of(b["text"])
                    key = (b["codes"] or [None])[0]
                    if not key and "upper" in b["text"].lower(): key = "Upper"
                    if not key and "lower" in b["text"].lower(): key = "Lower"
                    match = next((a for a in avail if a["sport"] == sp or (sp == "bike" and a["sport"] == "multi")), None)
                    if match:
                        avail.remove(match)
                    if match: st = "done"
                    elif day < today: st = "missed"
                    elif day == today: st = "today"
                    else: st = "todo"
                    ftxt, fkcal = fuel(b, sp, key)
                    if b.get("fuel"):
                        ftxt = b["fuel"]
                    s0, e0 = ranges[bi]
                    clash = [] if b.get("ok") else [x for x in ev if not x["allday"] and not (e0 + 30 <= x["s"] or s0 >= x["e"])]
                    move = None
                    if clash:
                        dur = e0 - s0
                        others = [r for j, r in enumerate(ranges) if j != bi]
                        cands = ("06:00", "06:30", "19:00", "19:30", "20:00") if day.weekday() < 5 else \
                                ("07:00", "09:00", "10:30", "15:30", "16:30", "17:30")
                        for cand in cands:
                            cs = hm2m(cand)
                            if free(cs, cs + dur, ev, others):
                                move = "%s–%02d:%02d" % (cand, (cs + dur) // 60, (cs + dur) % 60)
                                break
                    sess.append({"slot": b["slot"], "text": b["text"], "sport": sp, "key": key, "fuel": ftxt, "fkcal": fkcal,
                                 "clash": [("%s %s" % (x["title"], x["time"])) for x in clash], "move": move, "_r": (s0, e0), "moved": b.get("moved"), "why": b.get("why"),
                                 "detail": lib.get(key, []) if key else [], "status": st,
                                 "did": {"km": round(match["km"], 2), "sec": round(match["sec"]), "hr": match["hr"]} if match else None})
                extra = [{"sport": a["sport"], "km": round(a["km"], 2), "sec": round(a["sec"])} for a in avail]
                # frullato di barbabietola: 3 ore prima degli sforzi importanti
                beet = None
                hard = [x for x in sess if x["key"] in ("C2", "C3", "C5", "B1") or "test" in x["text"].lower()]
                if hard and nut.get("beet"):
                    x0 = hard[0]
                    st = hm2m(x0["slot"].split("–")[0])
                    at = st - 180
                    name = x0["text"].split(" · ")[0]
                    wake = 6 * 60 if day.weekday() < 5 else 7 * 60  # non si sveglia prima (nel weekend mai prima delle 7)
                    if at < wake:
                        beet = ("Frullato di barbabietola la sera prima, a cena verso le 20: %s è troppo presto per prenderlo 3 ore prima. "
                                "Non più tardi, per non doverti alzare di notte." % name)
                        if "test" in x0["text"].lower():
                            beet = ("Frullato di barbabietola sabato a colazione e sabato a cena verso le 20 (anche venerdì a colazione, se riesci): "
                                    "con la sveglia alle 7 non c'è tempo per prenderlo 3 ore prima, ma con 2-3 giorni di carico il nitrato resta alto fino alla gara. "
                                    "Domenica mattina niente frullato: troppo vicino al via, rischi problemi di stomaco.")
                    elif day.weekday() < 5 and WORK[0] - 30 < at < WORK[1]:
                        beet = ("Frullato di barbabietola a colazione (al lavoro non puoi prenderlo 3 ore prima di %s). "
                                "Prendilo anche il giorno prima: con il carico il nitrato resta alto fino a sera." % name)
                    else:
                        beet = "Frullato di barbabietola alle %d:%02d, 3 ore prima di %s." % (at // 60, at % 60, name)
                        if "test" in x0["text"].lower():
                            beet += " Prendine una dose anche venerdì e sabato a colazione: con 2-3 giorni di carico l'effetto è più forte."
                real = days.get(day.isoformat(), {}).get("kcal") if day < today else None
                kout = real or kcal_est(sess)
                for x in sess:
                    x.pop("_r", None)
                days_out.append({"date": day.isoformat(), "sessions": sess, "kout": kout, "kreal": bool(real),
                                 "kin": planK + sum(x["fkcal"] for x in sess) + (nut["beet"]["kcal"] if beet else 0), "beet": beet, "extra": extra, "meals": [x["meal"] for x in blocks if x.get("meal")] or meals_for(blocks), "events": [x for x in ev if not x.get("work")],
                                 "fuel_kcal": sum(x["fkcal"] for x in sess)})
            out_weeks.append({"label": w["label"], "note": w.get("note", ""), "start": w["start"], "days": days_out})
        coach = out_weeks or None
        # ---- ritmi di corsa stimati: modello passo/battito dalle corse recenti + gare
        cut = today - dt.timedelta(weeks=10)
        pts = [(a["hr"], a["mov"] / a["km"]) for a in A
               if a["sport"] == "run" and a["day"] >= cut and a["km"] > 3 and a["hr"] and a["mov"]]
        rp = None
        if len(pts) >= 8:
            n = len(pts); mx = sum(p[0] for p in pts) / n; my = sum(p[1] for p in pts) / n
            sb = sum((p[0] - mx) * (p[1] - my) for p in pts) / (sum((p[0] - mx) ** 2 for p in pts) or 1)
            sa = my - sb * mx
            at_hr = lambda h: sa + sb * h
            b5 = now["best5k"]
            p5 = b5 / 5 if b5 else at_hr(170)
            hm = (b5 * (21.0975 / 5) ** 1.06) / 21.0975 if b5 else at_hr(165)
            k10 = (b5 * 2 ** 1.06) / 10 if b5 else at_hr(170)
            g10 = TESTS[0]["target"] / TESTS[0]["km"]
            g5 = TESTS[0]["target"] * (5 / 10) ** 1.06 / 5
            ghm = TESTS[1]["target"] / TESTS[1]["km"]
            rp = {"easy": (at_hr(145), at_hr(135)), "hm": hm, "k10": k10, "p5": p5, "g10": g10, "g5": g5, "ghm": ghm,
                  "race703": GOAL["split"]["run"] / GOAL["dist"]["run"], "hr703": (GOAL["split"]["run"] / GOAL["dist"]["run"] - sa) / sb,
                  "n": len(pts)}

        def P(s):
            s = round(s)
            return "%d:%02d" % (s // 60, s % 60)

        def run_paces(x):
            if not rp or x["sport"] != "run":
                return None
            k, t = x["key"], x["text"].lower()
            e = "%s–%s/km" % (P(rp["easy"][0]), P(rp["easy"][1]))
            if k in ("C1", "C4"):
                return ["Facile a 140 bpm: dalle tue corse corrisponde a circa %s." % e,
                        "Se il battito sale sopra 145, rallenta: conta il battito, non il passo."] + \
                       (["Allunghi: progressivi, ultimi 20'' veloci ma sciolti (circa %s/km), recupero camminando." % P(rp["p5"] - 15)] if k == "C1" else [])
            if k == "C2":
                return ["Riscaldamento a circa %s." % e,
                        "8 km medio a 170-175 bpm: oggi circa %s–%s/km (il tuo ritmo da mezza è circa %s)." % (P(rp["hm"] - 10), P(rp["hm"] - 2), P(rp["hm"])),
                        "Obiettivo Roma-Ostia sotto 1:30: %s/km. Se lo tieni sotto i 175 bpm sei in linea." % P(rp["ghm"])]
            if k == "C3":
                return ["Riscaldamento a circa %s." % e,
                        "Test del coach: 8 x 1000 a 3:30-3:40/km, per vedere se hai quel passo. Dai tuoi dati oggi il ritmo sostenibile è %s–%s/km (miglior km di sempre 3:55)." % (P(rp["p5"] - 8), P(rp["p5"] - 2)),
                        "Come farlo: prima ripetuta a 3:40 e guarda come la chiudi. Se dalla terza non tieni sotto 3:45 o il battito supera 188, passa a %s–%s/km (ritmo da 10 km sotto i 40') e completa tutte e 8." % (P(rp["g5"] - 5), P(rp["g5"])),
                        "Il risultato è un dato prezioso: segna i tempi di ogni ripetuta, la dashboard li legge dal Garmin se usi il tasto giro.",
                        "Recupero 2'30: camminata o corsa lentissima, il battito deve scendere sotto 130."]
            if k == "C5":
                return ["Variazioni: 2' forti a circa %s/km (ritmo 10 km), 2' piano a circa %s/km." % (P(rp["k10"]), P(rp["easy"][1]))]
            if "test" in t:
                return ["Stima attuale sui 10 km: %s/km. Primi 3 km a %s, poi %s, ultimi 2 km a tutta." % (P(rp["k10"]), P(rp["k10"] + 3), P(rp["k10"] - 2)),
                        "Obiettivo di gennaio sotto i 40': %s/km. Il test ti dice quanto manca." % P(rp["g10"])]
            return ["Facile: circa %s." % e]

        for w in coach or []:
            for d in w["days"]:
                for x in d["sessions"]:
                    x["paces"] = run_paces(x)
        runmodel = rp
        track = read_json(os.path.join(DATA, "coach", "track.json"))
        if track and coach:
            for w in coach:
                for d in w["days"]:
                    wd = dt.date.fromisoformat(d["date"]).weekday()
                    for x in d["sessions"]:
                        if x["sport"] == "run" and (x["key"] in ("C2", "C3", "C5") or "test" in x["text"].lower()) and "gara" not in x["text"].lower():
                            x["track"] = ", ".join("%s–%s" % tuple(r) for r in track["open"][wd]) or "chiusa agli amatori"
        nutrition = nut

    races = []
    for r in (read_json(os.path.join(DATA, "multisport.json"), {}) or {}).values():
        legs = {}
        for l in r["legs"]:
            t, d = l.get("type") or "", l.get("distance") or 0
            tm = l.get("moving") or l.get("duration") or 0
            if "swim" in t and d: legs["swim"] = round(tm / (d / 100))
            elif ("cycl" in t or "bik" in t) and tm: legs["bike"] = round(d / 1000 / (tm / 3600), 1)
            elif "run" in t and d: legs["run"] = round(tm / (d / 1000))
        races.append({"date": r["date"], "name": (r.get("name") or "").replace(" Multisport", ""), "legs": legs})
    races.sort(key=lambda r: r["date"])

    # punti battito / prestazione per i grafici di tendenza
    hrpts = {"run": [], "swim": [], "bike": []}
    for a in A:
        if not a["hr"] or not a["mov"]:
            continue
        d = a["day"].isoformat()
        if a["sport"] == "run" and a["km"] > 2:
            hrpts["run"].append([d, a["hr"], round(a["mov"] / a["km"]), round(a["km"], 1), a["name"]])
        elif a["type"] == "lap_swimming" and a["km"] > 0.5 and a["mov"] >= 0.8 * a["sec"]:
            # solo sedute quasi continue: con molte pause il battito medio crolla e falsa il confronto
            hrpts["swim"].append([d, a["hr"], round(a["mov"] / (a["km"] * 10)), round(a["km"] * 1000), a["name"]])
        elif a["sport"] == "bike" and (a["np"] or a["pw"]):
            hrpts["bike"].append([d, a["hr"], round(a["pw"] or a["np"]), round(a["km"], 1), a["name"]])

    sz = read_json(os.path.join(DATA, "coach", "swimzones.json"))
    swimzones = None
    if sz:
        css = sz["css"]
        swimzones = {"css": css, "source": sz.get("source", ""), "zones": {}}
        for k, (lo, hi, desc) in sz["zones"].items():
            swimzones["zones"][k] = {"fast": css + lo if lo > -50 else None, "slow": css + hi, "desc": desc}

    payload = {
        "swimzones": swimzones,
        "hrpts": hrpts,
        "runmodel": runmodel if plan else None,
        "races": races,
        "coach": coach, "nutrition": nutrition,
        "today": today.isoformat(), "built": dt.datetime.now().strftime("%d/%m/%Y %H:%M"),
        "goal": GOAL, "tests": TESTS, "weekly": weekly, "daily": daily, "hst": hst,
        "now": now, "records": records, "totals": totals,
        "fitage": read_json(os.path.join(DATA, "fitnessage.json"), {}) and {
            "age": round(read_json(os.path.join(DATA, "fitnessage.json"))["fitnessAge"], 1),
            "real": read_json(os.path.join(DATA, "fitnessage.json")).get("chronologicalAge")},
    }
    with open(os.path.join(HERE, "template.html"), encoding="utf-8") as f:
        html = f.read()
    html = html.replace("/*__DATA__*/null", json.dumps(payload, ensure_ascii=False, separators=(",", ":")))
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(html)
    print("Dashboard creata: %s (%d KB)" % (OUT, os.path.getsize(OUT) // 1024))


if __name__ == "__main__":
    main()
