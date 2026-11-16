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
    "split": {"swim": 38 * 60, "t": 8 * 60, "bike": 170 * 60, "run": 114 * 60},
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
    out, folder = [], os.path.join(DATA, name)
    if os.path.isdir(folder):
        for f in sorted(os.listdir(folder)):
            if f.endswith(".json"):
                out += read_json(os.path.join(folder, f), []) or []
    return out


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
            "elev": a.get("elevationGain") or 0,
            "hr": a.get("averageHR"),
            "load": a.get("activityTrainingLoad") or 0,
            "kcal": a.get("calories") or 0,
            "np": a.get("normPower"),
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
            perf["run"][i][0] += a["sec"]; perf["run"][i][1] += a["km"]
            if a["hr"]:
                # efficienza: metri al minuto per ogni battito (piu' alto = meglio)
                perf["eff"][i][0] += (a["km"] * 1000 / (a["sec"] / 60)) / a["hr"] * a["sec"]
                perf["eff"][i][1] += a["sec"]
        if a["sport"] == "bike" and a["np"]:
            perf["bike"][i][0] += a["np"] * a["sec"]; perf["bike"][i][1] += a["sec"]
        if a["sport"] == "swim" and a["km"] > 0.3:
            perf["swim"][i][0] += a["sec"]; perf["swim"][i][1] += a["km"] * 10  # /100 m

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
        return sum(a["sec"] for a in r), sum(a["km"] for a in r)

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

    payload = {
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
