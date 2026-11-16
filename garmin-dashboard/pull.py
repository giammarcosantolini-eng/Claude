"""Scarica i dati Garmin (sola lettura) in data/ come JSON.

Uso:  python pull.py          -> ultimi 12 mesi (solo il nuovo se gia' scaricato)
      python pull.py --all    -> tutto lo storico
Solo librerie standard di Python. La chiave non viene mai stampata.
"""
import datetime as dt
import json
import os
import sys
import time
import urllib.error
import urllib.request

BASE = "https://personal.connectapi.garmin.com"
TOKEN_URL = BASE + "/personalapitoken-service/personal-api/personal-api-key/token"
HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
PAUSE = 0.4          # secondi tra una chiamata e l'altra
FINAL_AFTER = 3      # finestre finite da piu' di 3 giorni non si riscaricano


class TooBig(Exception):
    """HTTP 500: risposta troppo grande, va dimezzato l'intervallo."""


def log(msg):
    print(msg.encode("ascii", "replace").decode("ascii"), flush=True)


def read_json(path, default=None):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def write_json(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False)
    os.replace(tmp, path)


# ---------------------------------------------------------------- token
def api_key():
    key = os.environ.get("GARMIN_PERSONAL_API_KEY", "").strip()
    if key:
        return key
    env_file = os.path.join(HERE, ".env.local")
    if os.path.exists(env_file):
        with open(env_file, encoding="utf-8") as f:
            for line in f:
                if line.startswith("GARMIN_PERSONAL_API_KEY="):
                    return line.split("=", 1)[1].strip()
    return ""


def get_token(force=False):
    path = os.path.join(DATA, "token.json")
    saved = read_json(path, {})
    if not force and saved.get("token") and time.time() - saved.get("at", 0) < 20 * 3600:
        return saved["token"]
    key = api_key()
    if not key:
        sys.exit("ERRORE: chiave GARMIN_PERSONAL_API_KEY non impostata. "
                 "Controlla le variabili d'ambiente (o .env.local).")
    req = urllib.request.Request(TOKEN_URL, data=b"", method="POST",
                                 headers={"Authorization": "ApiKey " + key})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            token = r.read().decode("utf-8").strip()
    except urllib.error.HTTPError as e:
        sys.exit("ERRORE: Garmin ha rifiutato la chiave (HTTP %s). La chiave e' "
                 "mancante, sbagliata o scaduta: ricontrollala." % e.code)
    write_json(path, {"token": token, "at": time.time()})
    return token


# ---------------------------------------------------------------- HTTP
def api_get(path, retried_auth=False):
    for attempt in range(5):
        time.sleep(PAUSE)
        req = urllib.request.Request(BASE + path, headers={
            "Authorization": "Bearer " + get_token(), "Accept": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=90) as r:
                body = r.read()
                if r.status == 204 or not body.strip():
                    return None
                return json.loads(body.decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code == 401 and not retried_auth:
                get_token(force=True)
                return api_get(path, retried_auth=True)
            if e.code == 500:
                raise TooBig(path)
            if e.code in (429, 502, 503, 504):
                wait = 5 * (attempt + 1)
                log("   server occupato (%s), riprovo tra %ss..." % (e.code, wait))
                time.sleep(wait)
                continue
            if e.code in (400, 404):
                return None
            raise
        except (urllib.error.URLError, TimeoutError) as e:
            log("   errore di rete (%s), riprovo..." % e)
            time.sleep(5 * (attempt + 1))
    raise RuntimeError("troppi tentativi falliti: " + path)


# ---------------------------------------------------------------- finestre
def windows(start, end, days):
    cur = start
    while cur <= end:
        stop = min(cur + dt.timedelta(days=days - 1), end)
        yield cur, stop
        cur = stop + dt.timedelta(days=1)


def fetch_halving(make_path, extract, a, b):
    """Scarica [a,b]; su HTTP 500 dimezza l'intervallo e riprova."""
    try:
        return extract(api_get(make_path(a, b)))
    except TooBig:
        if a == b:
            log("   giorno %s troppo grande, salto" % a)
            return []
        mid = a + (b - a) // 2
        return (fetch_halving(make_path, extract, a, mid)
                + fetch_halving(make_path, extract, mid + dt.timedelta(days=1), b))


def pull_ranged(name, label, start, end, days, make_path, extract):
    folder = os.path.join(DATA, name)
    today = dt.date.today()
    anchor = dt.date(2000, 1, 1)  # finestre allineate: stessi nomi file a ogni giro
    start = anchor + dt.timedelta(days=((start - anchor).days // days) * days)
    wins = list(windows(start, end, days))
    keep = {"%s_%s.json" % (a, b) for a, b in wins}
    if os.path.isdir(folder):  # tolgo finestre vecchie con altri confini (eviterebbero doppioni)
        for f in os.listdir(folder):
            if f.endswith(".json") and f not in keep and f[:10] >= wins[0][0].isoformat():
                os.remove(os.path.join(folder, f))
    for i, (a, b) in enumerate(wins, 1):
        f = os.path.join(folder, "%s_%s.json" % (a, b))
        if os.path.exists(f) and (today - b).days > FINAL_AFTER:
            continue
        log("%s: finestra %d/%d (%s -> %s)" % (label, i, len(wins), a, b))
        items = fetch_halving(make_path, extract, a, b)
        write_json(f, items)  # salvo subito: se si ferma, riparte da qui


def as_list(x, key=None):
    if x is None:
        return []
    if key and isinstance(x, dict):
        x = x.get(key) or []
    return x if isinstance(x, list) else [x]


# ---------------------------------------------------------------- attivita'
def pull_activities(start):
    path = os.path.join(DATA, "activities.json")
    acts = {str(a["activityId"]): a for a in read_json(path, [])}
    known_before = set(acts)
    recent_cut = (dt.datetime.now() - dt.timedelta(days=FINAL_AFTER)).strftime("%Y-%m-%d")
    n, page = 0, 20
    while True:
        log("Attivita': pagina %d (%d scaricate finora)" % (n // page + 1, len(acts)))
        try:
            batch = api_get("/activitylist-service/activities/search/activities"
                            "?start=%d&limit=%d" % (n, page)) or []
        except TooBig:
            if page == 1:
                n += 1
                continue
            page = max(1, page // 2)
            continue
        for a in batch:
            acts[str(a["activityId"])] = a
        write_json(path, sorted(acts.values(), key=lambda a: a.get("startTimeLocal", ""),
                                reverse=True))
        if len(batch) < page:
            break
        oldest = min(a.get("startTimeLocal", "") for a in batch)
        if oldest[:10] < start.isoformat():
            break
        if known_before and all(str(a["activityId"]) in known_before for a in batch) \
                and oldest[:10] < recent_cut:
            break  # da qui in poi e' tutto gia' scaricato
        n += len(batch)
    return list(acts.values())


# ---------------------------------------------------------------- main
def main():
    os.makedirs(DATA, exist_ok=True)
    today = dt.date.today()
    if "--all" in sys.argv:
        start = dt.date(2000, 1, 1)
    else:
        start = today - dt.timedelta(days=365)
    get_token()

    acts = pull_activities(start)
    if "--all" in sys.argv and acts:
        start = dt.date.fromisoformat(min(a["startTimeLocal"][:10] for a in acts)) \
            - dt.timedelta(days=30)
    else:
        # niente dati prima del primo orologio: parto un mese prima della prima attivita'
        if acts:
            first = dt.date.fromisoformat(min(a["startTimeLocal"][:10] for a in acts))
            start = max(start, first - dt.timedelta(days=30))

    pull_ranged("daily", "Riepiloghi giornalieri", start, today, 60,
                lambda a, b: "/usersummary-service/v2/dailysummaries?startDate=%s&endDate=%s" % (a, b),
                lambda r: as_list(r, "data"))
    pull_ranged("sleep", "Sonno", start, today, 31,
                lambda a, b: "/sleep-service/sleep/dailySleepSummariesByDate?startDate=%s&endDate=%s" % (a, b),
                as_list)
    pull_ranged("hrv", "HRV", start, today, 180,
                lambda a, b: "/hrv-service/hrv/daily/%s/%s" % (a, b),
                lambda r: as_list(r, "hrvSummaries"))
    pull_ranged("weight", "Peso", start, today, 180,
                lambda a, b: "/weight-service/weight/range/%s/%s" % (a, b),
                lambda r: as_list(r, "dailyWeightSummaries"))

    log("Eta' fitness e zone cardiache...")
    for name, p in (("fitnessage", "/fitnessage-service/fitnessage/v2/%s" % today),
                    ("hrzones", "/biometric-service/heartRateZones/v2")):
        try:
            write_json(os.path.join(DATA, name + ".json"), api_get(p))
        except TooBig:
            pass

    summary()


def load_folder(name):
    out = []
    folder = os.path.join(DATA, name)
    if os.path.isdir(folder):
        for f in sorted(os.listdir(folder)):
            if f.endswith(".json"):
                out += read_json(os.path.join(folder, f), []) or []
    return out


def summary():
    acts = read_json(os.path.join(DATA, "activities.json"), [])
    log("")
    log("FATTO. Cosa e' arrivato:")
    if acts:
        d = sorted(a["startTimeLocal"][:10] for a in acts)
        log("  Attivita':  %d  (dal %s al %s)" % (len(acts), d[0], d[-1]))
    for name, label, keyf in (
            ("daily", "Giorni", lambda x: x.get("calendarDate") if (x.get("heartRate") or {}).get("restingValue") or (x.get("movement") or {}).get("steps") else None),
            ("sleep", "Notti", lambda x: x.get("calendarDate") if x.get("sleepTimeSeconds") else None),
            ("hrv", "Notti HRV", lambda x: x.get("calendarDate") if x.get("lastNightAvg") else None),
            ("weight", "Pesate", lambda x: x.get("summaryDate") or x.get("calendarDate"))):
        dates = sorted({k for k in (keyf(x) for x in load_folder(name)) if k})
        if dates:
            log("  %-11s %d  (dal %s al %s)" % (label + ":", len(dates), dates[0], dates[-1]))
        else:
            log("  %-11s 0" % (label + ":"))


if __name__ == "__main__":
    main()
