#!/usr/bin/env bash
# Smoke teszt egy futó Kovászdada példányon.
# Használat: smoke_test.sh <BASE_URL> [ELVÁRT_VERZIÓ] [TIMEOUT_MP]
set -euo pipefail

BASE_URL="${1:?Add meg az alap URL-t, pl. http://localhost:8000}"
EXPECTED_VERSION="${2:-}"
TIMEOUT="${3:-60}"
BASE_URL="${BASE_URL%/}"

json() { python3 -c "import json, sys; print(json.load(sys.stdin)$1)"; }

echo "▶ Várakozás: $BASE_URL/api/health (max ${TIMEOUT}s, elvárt verzió: ${EXPECTED_VERSION:-bármely})"
deadline=$((SECONDS + TIMEOUT))
body=""
until body=$(curl -fsS --max-time 15 "$BASE_URL/api/health" 2>/dev/null) && \
      { [ -z "$EXPECTED_VERSION" ] || [ "$(echo "$body" | json "['version']")" = "$EXPECTED_VERSION" ]; }; do
  if [ "$SECONDS" -ge "$deadline" ]; then
    echo "✖ Időtúllépés. Utolsó válasz: ${body:-nincs}"
    exit 1
  fi
  sleep 5
done
echo "✔ Health OK: $body"

echo "▶ Főoldal betöltése"
curl -fsS "$BASE_URL/" -o /tmp/kovaszdada_index.html
grep -q "Kovászdada" /tmp/kovaszdada_index.html
echo "✔ Főoldal OK"

echo "▶ Új kovász létrehozása"
id=$(curl -fsS -X POST "$BASE_URL/api/starters" -H "Content-Type: application/json" \
  -d '{"name":"Smoke-teszt","flour_type":"BL-55"}' | json "['id']")
echo "✔ Létrehozva, id=$id"

echo "▶ Etetés rögzítése"
curl -fsS -X POST "$BASE_URL/api/starters/$id/feedings" -H "Content-Type: application/json" \
  -d '{"starter_g":20,"flour_g":40,"water_g":40,"temp_c":24}' > /dev/null
echo "✔ Etetés OK"

echo "▶ Állapot lekérdezése"
stage=$(curl -fsS "$BASE_URL/api/starters/$id/status" | json "['stage']")
[ "$stage" = "WAKING" ] || { echo "✖ Váratlan állapot: $stage"; exit 1; }
echo "✔ Állapot OK: $stage"

echo "▶ Arány-javaslat"
x=$(curl -fsS "$BASE_URL/api/suggest-ratio?hours=12&temp_c=24" | json "['x']")
[ "$x" = "4" ] || { echo "✖ Váratlan arány: 1:$x:$x"; exit 1; }
echo "✔ Arány-javaslat OK: 1:$x:$x"

echo "✅ Minden smoke teszt sikeres: $BASE_URL"