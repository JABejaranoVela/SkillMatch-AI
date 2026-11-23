#!/usr/bin/env bash
set -Eeuo pipefail

fail() {
  printf 'Release rejected: %s\n' "$1" >&2
  exit 1
}

tag="${RELEASE_TAG:-}"
app_bot="${RELEASE_PLEASE_APP_BOT:-}"
number='(0|[1-9][0-9]{0,8})'
[[ "$tag" =~ ^v${number}\.${number}\.${number}$ ]] || fail "expected a stable vX.Y.Z tag"
[[ -z "$app_bot" || "$app_bot" =~ ^[a-z0-9][a-z0-9-]{0,38}\[bot\]$ ]] ||
  fail "invalid Release Please App bot login"

author="$(gh api "repos/${GITHUB_REPOSITORY}/releases/tags/${tag}" |
  jq -er --arg tag "$tag" --arg app "$app_bot" '
    select(.tag_name == $tag and .draft == false and .prerelease == false
      and (.author.login == "github-actions[bot]" or ($app != "" and .author.login == $app)))
    | .author.login
  ')" || fail "no stable release published by an authorized bot for that tag"

sha="$(git rev-parse --verify "refs/tags/${tag}^{commit}")" || fail "release tag is missing"
git merge-base --is-ancestor "$sha" "$GITHUB_SHA" || fail "release commit is outside main"
version="${tag#v}"
[[ "$(git show "$sha:version.txt")" == "$version" ]] || fail "version.txt disagrees with tag"
git show "$sha:.release-please-manifest.json" |
  jq -e --arg version "$version" '.["."] == $version' >/dev/null ||
  fail "release manifest disagrees with tag"

gh api --paginate --slurp "repos/${GITHUB_REPOSITORY}/commits/${sha}/pulls" |
  jq -e --arg sha "$sha" --arg repo "$GITHUB_REPOSITORY" --arg author "$author" '
    any(.[][];
      .base.ref == "main" and .base.repo.full_name == $repo
      and .head.repo.full_name == $repo
      and (.head.ref == "release-please--branches--main"
           or (.head.ref | startswith("release-please--branches--main--components--")))
      and .user.login == $author
      and .merged_at != null and .merge_commit_sha == $sha
      and any(.labels[]; .name == "autorelease: tagged")
    )
  ' >/dev/null || fail "no matching merged Release Please PR"

printf 'tag=%s\nsha=%s\n' "$tag" "$sha" >> "$GITHUB_OUTPUT"
