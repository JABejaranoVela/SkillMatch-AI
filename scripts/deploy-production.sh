#!/usr/bin/env bash

set -Eeuo pipefail

DEPLOY_SHA="${1:-}"
GHCR_OWNER="${2:-}"
APP_DIR="/srv/apps/skillmatch-ai"
BACKUP_DIR="/srv/backups/skillmatch-ai/postgres"
DEPLOY_ENV="${APP_DIR}/.env.deploy"
DEPLOY_ENV_TMP=""
BACKUP_TMP=""

cleanup_temporary_files() {
  if [[ -n "${DEPLOY_ENV_TMP}" ]]; then
    rm -f "${DEPLOY_ENV_TMP}"
  fi
  if [[ -n "${BACKUP_TMP}" ]]; then
    rm -f "${BACKUP_TMP}"
  fi
}
trap cleanup_temporary_files EXIT

fail() {
  printf 'Deployment error: %s\n' "$1" >&2
  exit 1
}

retry() {
  local attempts="$1"
  local delay="$2"
  shift 2

  local attempt
  for ((attempt = 1; attempt <= attempts; attempt++)); do
    if "$@"; then
      return 0
    fi
    if ((attempt < attempts)); then
      sleep "${delay}"
    fi
  done
  return 1
}

[[ "${DEPLOY_SHA}" =~ ^[0-9a-f]{40}$ ]] || fail "DEPLOY_SHA must be a full Git SHA"
[[ "${GHCR_OWNER}" =~ ^[a-z0-9._-]+$ ]] || fail "GHCR owner must be lowercase"
[[ "$(pwd)" == "${APP_DIR}" ]] || fail "run this script from ${APP_DIR}"
[[ -f .env.prod ]] || fail ".env.prod is missing"
[[ -f docker-compose.prod.yml ]] || fail "docker-compose.prod.yml is missing"
[[ -f docker-compose.prod.override.yml ]] || fail "docker-compose.prod.override.yml is missing"
[[ -d "${BACKUP_DIR}" && -w "${BACKUP_DIR}" ]] || fail "backup directory is not writable"

DOCKER=(sudo -n docker)
if [[ -n "${DOCKER_CONFIG:-}" ]]; then
  [[ -d "${DOCKER_CONFIG}" ]] || fail "temporary Docker config is missing"
  DOCKER+=(--config "${DOCKER_CONFIG}")
fi

COMPOSE=(
  "${DOCKER[@]}" compose
  --env-file .env.prod
  --env-file .env.deploy
  -f docker-compose.prod.yml
  -f docker-compose.prod.override.yml
)

umask 077
DEPLOY_ENV_TMP="$(mktemp "${APP_DIR}/.env.deploy.tmp.XXXXXX")"
cat > "${DEPLOY_ENV_TMP}" <<EOF
BACKEND_IMAGE=ghcr.io/${GHCR_OWNER}/skillmatch-ai-backend:${DEPLOY_SHA}
FRONTEND_IMAGE=ghcr.io/${GHCR_OWNER}/skillmatch-ai-frontend:${DEPLOY_SHA}
EOF

[[ "$(wc -l < "${DEPLOY_ENV_TMP}")" -eq 2 ]] || fail "invalid deployment environment"
grep -Fxq "BACKEND_IMAGE=ghcr.io/${GHCR_OWNER}/skillmatch-ai-backend:${DEPLOY_SHA}" "${DEPLOY_ENV_TMP}" \
  || fail "invalid backend image reference"
grep -Fxq "FRONTEND_IMAGE=ghcr.io/${GHCR_OWNER}/skillmatch-ai-frontend:${DEPLOY_SHA}" "${DEPLOY_ENV_TMP}" \
  || fail "invalid frontend image reference"
mv -f "${DEPLOY_ENV_TMP}" "${DEPLOY_ENV}"
DEPLOY_ENV_TMP=""

"${COMPOSE[@]}" config --quiet
"${COMPOSE[@]}" up -d --wait --wait-timeout 120 db
"${COMPOSE[@]}" pull backend email-worker frontend

# Validate the real bind mount with the user configured in the new backend image.
"${COMPOSE[@]}" run --rm --no-deps backend \
  sh -c 'test -w /app/storage/resumes'

SHORT_SHA="${DEPLOY_SHA:0:12}"
TIMESTAMP="$(date -u +%Y%m%d_%H%M%S)"
BACKUP_FILE="${BACKUP_DIR}/skillmatch_predeploy_${TIMESTAMP}_${SHORT_SHA}.sql"
BACKUP_TMP="${BACKUP_FILE}.tmp"

"${COMPOSE[@]}" exec -T db \
  sh -c 'pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB"' > "${BACKUP_TMP}"
[[ -s "${BACKUP_TMP}" ]] || fail "PostgreSQL backup is empty"
mv -f "${BACKUP_TMP}" "${BACKUP_FILE}"
BACKUP_TMP=""
printf 'Pre-deploy backup created: %s\n' "${BACKUP_FILE}"

# The image was pulled above; Compose must not build on the VPS.
"${COMPOSE[@]}" run --rm backend alembic upgrade head
"${COMPOSE[@]}" up -d --no-build --wait --wait-timeout 180
"${COMPOSE[@]}" ps

retry 12 5 curl -fsS http://127.0.0.1:8001/api/v1/health > /dev/null \
  || fail "backend localhost health check failed"
retry 12 5 curl -fsSI http://127.0.0.1:8080 > /dev/null \
  || fail "frontend localhost health check failed"
retry 12 5 curl -fsSI https://skillmatch.jabejarano.tech > /dev/null \
  || fail "public frontend health check failed"
retry 12 5 curl -fsS https://skillmatch.jabejarano.tech/api/v1/health > /dev/null \
  || fail "public API health check failed"

# Conservative cleanup only: no -a, no volumes, no data or backup deletion.
"${DOCKER[@]}" image prune -f

printf 'Deployment completed for %s\n' "${DEPLOY_SHA}"
