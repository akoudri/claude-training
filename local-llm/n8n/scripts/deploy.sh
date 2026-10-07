#!/usr/bin/env bash
# Déploie les workflows dans l'instance n8n locale :
# identifiants de l'instance → build → import → publication du formulaire d'entrée
# et des workflows appelés par d'autres (sous-workflows, workflow d'erreur) → redémarrage.
set -euo pipefail
cd "$(dirname "$0")/../.."

CREDS_FILE=n8n/config/credentials.local.json # exclu de git (n8n/config/*)
docker compose exec -T postgres sh -c \
  'psql -U "$POSTGRES_USER" -d n8n -At -F "|" -c "SELECT name, id FROM credentials_entity"' \
  | node n8n/scripts/credentials-map.mjs > "$CREDS_FILE.tmp"
mv "$CREDS_FILE.tmp" "$CREDS_FILE"

OUT=$(mktemp -d)
trap 'rm -rf "$OUT"' EXIT
node n8n/scripts/build.mjs --credentials "$CREDS_FILE" --out "$OUT"

docker compose exec -T n8n rm -rf /tmp/workflows-import
docker compose cp "$OUT/." n8n:/tmp/workflows-import
docker compose exec -T n8n n8n import:workflow --separate --input=/tmp/workflows-import
PUBLISH_IDS=${PUBLISH_IDS-cnfFormulaire02a cnfAnalyse000002 cnfAlerteEchec04 cnfSynthese00003}
for id in $PUBLISH_IDS; do docker compose exec -T n8n n8n publish:workflow --id="$id"; done
docker compose restart n8n
echo "Déploiement terminé."
