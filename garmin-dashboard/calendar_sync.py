"""Scarica i calendari (link privati in data/calendars.json) e salva
gli impegni delle prossime settimane in data/calendar/events.json.

Uso:  python calendar_sync.py
Solo librerie standard. I link restano in data/ (mai su GitHub).
"""
import datetime as dt
import json
import os
import re
import urllib.request

try:
    from zoneinfo import ZoneInfo
    ROME = ZoneInfo("Europe/Rome")
except Exception:  # Windows senza tzdata
    ROME = None

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
DAYS_BACK, DAYS_AHEAD = 7, 21


def unfold(text):
    return re.sub(r"\r?\n[ \t]", "", text).splitlines()


def parse_dt(prop, value):
    """Ritorna (datetime locale Roma senza tz, tutto_il_giorno)."""
    if "VALUE=DATE" in prop or re.fullmatch(r"\d{8}", value):
        return dt.datetime.strptime(value[:8], "%Y%m%d"), True
    v = value.rstrip("Z")
    d = dt.datetime.strptime(v[:15], "%Y%m%dT%H%M%S")
    if value.endswith("Z") and ROME:
        d = d.replace(tzinfo=dt.timezone.utc).astimezone(ROME).replace(tzinfo=None)
    elif "TZID=" in prop and ROME:
        tz = prop.split("TZID=")[1].split(";")[0]
        try:
            d = d.replace(tzinfo=ZoneInfo(tz)).astimezone(ROME).replace(tzinfo=None)
        except Exception:
            pass
    return d, False


def expand(ev, start, end, lo, hi):
    """Occorrenze di un evento (supporta RRULE DAILY/WEEKLY semplici)."""
    rr = ev.get("RRULE")
    if not rr:
        return [(start, end)] if end >= lo and start <= hi else []
    rule = dict(p.split("=", 1) for p in rr.split(";") if "=" in p)
    freq, step = rule.get("FREQ"), int(rule.get("INTERVAL", 1))
    until = parse_dt("", rule["UNTIL"])[0] if "UNTIL" in rule else hi
    count = int(rule.get("COUNT", 10 ** 6))
    byday = rule.get("BYDAY", "")
    wd = {"MO": 0, "TU": 1, "WE": 2, "TH": 3, "FR": 4, "SA": 5, "SU": 6}
    days = [wd[d[-2:]] for d in byday.split(",") if d[-2:] in wd] if byday else None
    out, n, cur, dur = [], 0, start, end - start
    while cur <= min(until, hi) and n < count:
        if freq == "DAILY":
            ok = True
            nxt = cur + dt.timedelta(days=step)
        elif freq == "WEEKLY":
            ok = days is None or cur.weekday() in days
            nxt = cur + dt.timedelta(days=1)
            if days is None:
                nxt = cur + dt.timedelta(weeks=step)
        else:
            return [(start, end)] if end >= lo and start <= hi else []
        if ok:
            n += 1
            if cur + dur >= lo and cur.date().isoformat() not in ev.get("EXDATES", set()):
                out.append((cur, cur + dur))
        cur = nxt
    return out


def parse_ics(text, source, lo, hi):
    events, ev = [], None
    for line in unfold(text):
        if line == "BEGIN:VEVENT":
            ev = {"EXDATES": set()}
        elif line == "END:VEVENT" and ev is not None:
            if "DTSTART" in ev and ev.get("STATUS") != "CANCELLED":
                s, allday = ev["DTSTART"]
                e = ev.get("DTEND", (s + (dt.timedelta(days=1) if allday else dt.timedelta(hours=1)), allday))[0]
                for a, b in expand(ev, s, e, lo, hi):
                    events.append({"source": source, "title": ev.get("SUMMARY", "Impegno"),
                                   "location": ev.get("LOCATION", ""), "allday": allday,
                                   "start": a.isoformat(timespec="minutes"), "end": b.isoformat(timespec="minutes")})
            ev = None
        elif ev is not None and ":" in line:
            prop, value = line.split(":", 1)
            name = prop.split(";")[0]
            if name in ("DTSTART", "DTEND"):
                ev[name] = parse_dt(prop, value)
            elif name == "EXDATE":
                for v in value.split(","):
                    ev["EXDATES"].add(parse_dt(prop, v)[0].date().isoformat())
            elif name in ("SUMMARY", "LOCATION", "RRULE", "STATUS"):
                ev[name] = value.replace("\\,", ",").replace("\\n", " ").replace("\\;", ";").strip()
    return events


def main():
    with open(os.path.join(DATA, "calendars.json"), encoding="utf-8") as f:
        links = json.load(f)
    today = dt.datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    lo, hi = today - dt.timedelta(days=DAYS_BACK), today + dt.timedelta(days=DAYS_AHEAD)
    allev = []
    for name, url in links.items():
        url = url.replace("webcal://", "https://")
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"}), timeout=60) as r:
                text = r.read().decode("utf-8", "replace")
        except Exception as e:
            print("Calendario %s: non raggiungibile (%s)" % (name, e.__class__.__name__))
            continue
        evs = parse_ics(text, name, lo, hi)
        print("Calendario %s: %d impegni nelle prossime settimane" % (name, len(evs)))
        allev += evs
    allev.sort(key=lambda e: e["start"])
    os.makedirs(os.path.join(DATA, "calendar"), exist_ok=True)
    with open(os.path.join(DATA, "calendar", "events.json"), "w", encoding="utf-8") as f:
        json.dump({"synced": dt.datetime.now().isoformat(timespec="minutes"), "events": allev}, f, ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
