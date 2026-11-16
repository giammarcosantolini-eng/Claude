#!/bin/sh
# Scarica i dati Garmin nuovi e ricostruisce la dashboard.
cd "$(dirname "$0")" || exit 1
python3 pull.py && { python3 calendar_sync.py || echo 'Calendari non aggiornati'; } && python3 build.py
