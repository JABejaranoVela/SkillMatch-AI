#!/usr/bin/env bash
set -Eeuo pipefail

tag="${1:-}"
sha="${2:-}"
owner="${3:-}"
auth_dir="${4:-}"
backend_digest="${5:-}"
frontend_digest="${6:-}"
state_dir=/srv/backups/skillmatch-ai/postgres/.release-deployments
app_dir=/srv/apps/skillmatch-ai

fail() {
  printf 'Release deployment stopped: %s\n' "$1" >&2
  exit 1
}

running_image_id() {
  local service="$1" container image
  local compose=(sudo -n docker compose --env-file .env.prod)
  if [[ -f .env.deploy ]]; then
    compose+=(--env-file .env.deploy)
  fi
  compose+=(-f docker-compose.prod.yml -f docker-compose.prod.override.yml)
  container="$("${compose[@]}" ps --status running --quiet "$service" </dev/null)" ||
    fail "could not list running $service"
  [[ "$container" =~ ^[0-9a-f]{12,64}$ ]] || fail "expected one running $service container"
  image="$(sudo -n docker inspect --type container --format '{{if .State.Running}}{{.Image}}{{end}}' "$container" </dev/null)" ||
    fail "could not inspect $service"
  [[ "$image" =~ ^sha256:[0-9a-f]{64}$ ]] || fail "could not identify the running $service image"
  printf '%s\n' "$image"
}

read_running_refs() {
  local backend worker frontend
  backend="$(running_image_id backend)" || exit 1
  worker="$(running_image_id email-worker)" || exit 1
  frontend="$(running_image_id frontend)" || exit 1
  [[ "$backend" == "$worker" ]] || fail "backend and email-worker run different images"
  running_backend_refs="$(sudo -n docker image inspect --format '{{range .RepoDigests}}{{println .}}{{end}}' "$backend" </dev/null)" ||
    fail "could not inspect backend image digests"
  running_frontend_refs="$(sudo -n docker image inspect --format '{{range .RepoDigests}}{{println .}}{{end}}' "$frontend" </dev/null)" ||
    fail "could not inspect frontend image digests"
}

image_ref_is_pinned() {
  local ref="$1" repo="$2"
  [[ "$ref" == "$repo@"* && "${ref#"$repo@"}" =~ ^sha256:[0-9a-f]{64}$ ]]
}

select_running_ref() {
  local refs="$1" repo="$2" ref
  while IFS= read -r ref; do
    if image_ref_is_pinned "$ref" "$repo"; then
      printf '%s\n' "$ref"
      return
    fi
  done <<< "$refs"
  fail "no registry digest for a running image; operator reconciliation required"
}

require_running_refs() {
  local backend="$1" frontend="$2"
  if ! image_ref_is_pinned "$backend" "$backend_repo" ||
     ! image_ref_is_pinned "$frontend" "$frontend_repo" ||
     ! grep -Fxq -- "$backend" <<< "$running_backend_refs" ||
     ! grep -Fxq -- "$frontend" <<< "$running_frontend_refs"; then
    fail "running images do not match the recorded state; operator reconciliation required"
  fi
}

require_saved_refs() {
  if ! cmp -s -- .env.deploy <(printf 'BACKEND_IMAGE=%s\nFRONTEND_IMAGE=%s\n' "$1" "$2"); then
    fail ".env.deploy does not match the recorded digests; operator reconciliation required"
  fi
}

retain_image() {
  local ref="$1" service="$2" expected_id existing_tag retained_id local_tag
  local_tag="skillmatch-retained/$service:sha256-${ref##*:}"
  expected_id="$(sudo -n docker image inspect --format '{{.Id}}' "$ref" </dev/null)" ||
    fail "could not resolve the $service recovery digest locally"
  [[ "$expected_id" =~ ^sha256:[0-9a-f]{64}$ ]] || fail "invalid local $service image ID"
  existing_tag="$(sudo -n docker image ls --format '{{.Repository}}:{{.Tag}}' --filter "reference=$local_tag" </dev/null)" ||
    fail "could not check the local $service retention tag"
  if [[ -z "$existing_tag" ]]; then
    sudo -n docker image tag "$expected_id" "$local_tag" </dev/null ||
      fail "could not retain the $service image locally"
  elif [[ "$existing_tag" != "$local_tag" ]]; then
    fail "unexpected local $service retention tag"
  fi
  retained_id="$(sudo -n docker image inspect --format '{{.Id}}' "$local_tag" </dev/null)" ||
    fail "could not verify the $service retention tag"
  [[ "$retained_id" == "$expected_id" ]] || fail "the $service retention tag has the wrong image ID"
}

number='(0|[1-9][0-9]{0,8})'
[[ "$tag" =~ ^v${number}\.${number}\.${number}$ ]] || fail "invalid release tag"
[[ "$sha" =~ ^[0-9a-f]{40}$ ]] || fail "invalid release SHA"
[[ "$backend_digest" =~ ^sha256:[0-9a-f]{64}$ ]] || fail "invalid backend digest"
[[ "$frontend_digest" =~ ^sha256:[0-9a-f]{64}$ ]] || fail "invalid frontend digest"
[[ "$owner" =~ ^[a-z0-9._-]+$ && -d "$auth_dir" ]] || fail "invalid registry configuration"
[[ "$PWD" == "$app_dir" ]] || fail "unexpected repository directory"

umask 077
mkdir -p -- "$state_dir"
exec 9>"$state_dir/lock"
flock -x 9

receipt="$state_dir/$tag.deployed"
[[ ! -e "$state_dir/pending" && ! -L "$state_dir/pending" ]] ||
  fail "a previous attempt requires operator reconciliation"

backend_repo="ghcr.io/$owner/skillmatch-ai-backend"
frontend_repo="ghcr.io/$owner/skillmatch-ai-frontend"

for previous in "$state_dir"/v*.deployed; do
  [[ -f "$previous" ]] || continue
  [[ "$previous" != "$receipt" ]] || continue
  read -r _ previous_sha _ < "$previous"
  [[ "$previous_sha" =~ ^[0-9a-f]{40}$ && "$previous_sha" != "$sha" ]] ||
    fail "invalid receipt or SHA already deployed under another tag"
  git merge-base --is-ancestor "$previous_sha" "$sha" ||
    fail "release is older than a deployed release or has diverged"
done

read_running_refs
if [[ -e "$receipt" || -L "$receipt" ]]; then
  [[ -f "$receipt" ]] || fail "invalid deployment receipt"
  read -r deployed_tag deployed_sha deployed_backend deployed_frontend < "$receipt" ||
    fail "invalid deployment receipt"
  [[ "$deployed_tag" == "$tag" && "$deployed_sha" == "$sha" ]] ||
    fail "release tag was previously deployed at a different SHA"
  require_running_refs "$backend_repo@$deployed_backend" "$frontend_repo@$deployed_frontend"
  require_saved_refs "$backend_repo@$deployed_backend" "$frontend_repo@$deployed_frontend"
  current_sha="$(git rev-parse --verify HEAD)" ||
    fail "could not verify the checkout SHA; operator reconciliation required"
  [[ "$current_sha" == "$deployed_sha" ]] ||
    fail "checkout SHA does not match the deployed receipt; operator reconciliation required"
  checkout_status="$(git status --porcelain=v1 --untracked-files=all)" ||
    fail "could not verify checkout cleanliness; operator reconciliation required"
  [[ -z "$checkout_status" ]] ||
    fail "checkout has unexpected changes; operator reconciliation required"
  printf 'Release %s already deployed.\n' "$tag"
  exit 0
fi

git diff --quiet
git diff --cached --quiet
[[ "$(git rev-parse --verify "refs/tags/${tag}^{commit}")" == "$sha" ]] || fail "tag moved"
git merge-base --is-ancestor "$sha" refs/remotes/origin/main || fail "release is outside main"
snapshot="$state_dir/$tag.previous-env"
if [[ -e "$snapshot" || -L "$snapshot" ]]; then
  mapfile -t snapshot_lines < "$snapshot" || fail "could not read rollback snapshot"
  [[ "${#snapshot_lines[@]}" == 2 && "${snapshot_lines[0]}" == BACKEND_IMAGE=* &&
     "${snapshot_lines[1]}" == FRONTEND_IMAGE=* ]] || fail "invalid rollback snapshot"
  previous_backend="${snapshot_lines[0]#BACKEND_IMAGE=}"
  previous_frontend="${snapshot_lines[1]#FRONTEND_IMAGE=}"
  require_running_refs "$previous_backend" "$previous_frontend"
else
  previous_backend="$(select_running_ref "$running_backend_refs" "$backend_repo")" || exit 1
  previous_frontend="$(select_running_ref "$running_frontend_refs" "$frontend_repo")" || exit 1
  snapshot_tmp="$(mktemp -- "$state_dir/.snapshot.XXXXXX")"
  trap 'rm -f -- "$snapshot_tmp"' EXIT
  printf 'BACKEND_IMAGE=%s\nFRONTEND_IMAGE=%s\n' "$previous_backend" "$previous_frontend" > "$snapshot_tmp"
  ln -T -- "$snapshot_tmp" "$snapshot"
fi

retain_image "$previous_backend" backend
retain_image "$previous_frontend" frontend

# A failed or interrupted attempt keeps this record and blocks automatic retries.
printf '%s %s %s %s\n' "$tag" "$sha" "$backend_digest" "$frontend_digest" > "$state_dir/pending"
git checkout --detach "$sha" </dev/null
DOCKER_CONFIG="$auth_dir" bash scripts/deploy-production.sh "$sha" "$owner" "$backend_digest" "$frontend_digest" </dev/null
read_running_refs
require_running_refs "$backend_repo@$backend_digest" "$frontend_repo@$frontend_digest"
require_saved_refs "$backend_repo@$backend_digest" "$frontend_repo@$frontend_digest"
retain_image "$backend_repo@$backend_digest" backend
retain_image "$frontend_repo@$frontend_digest" frontend
mv -T -- "$state_dir/pending" "$receipt"
