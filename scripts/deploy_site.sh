#!/usr/bin/env bash
# Publish site/index.html to the gh-pages branch.
#
# The page is a build artifact, not source. main stays free of it — site/index.html is
# gitignored there — so the 3.6 MB blob never lands in the history we read and bisect.
# It goes to gh-pages instead, built with plumbing so the working tree is never touched
# and no checkout is needed.
#
# Each deploy is parented on the previous gh-pages tip, which makes the push a
# fast-forward. That is deliberate: a replace-the-branch scheme would need --force, and a
# deploy script is not a good reason to keep a destructive command in the loop.
#
# Usage: scripts/deploy_site.sh   (from anywhere in the repo)

set -euo pipefail
cd "$(git rev-parse --show-toplevel)"

PAGE=site/index.html
[ -f "$PAGE" ] || { echo "error: $PAGE missing — run scripts/build_site.py first" >&2; exit 1; }

# Refuse to publish a page older than the payload it is built from. The two have gone out
# of step before, and a stale page is worse than no page because it looks current.
if [ site/payload.js -nt "$PAGE" ]; then
  echo "error: payload.js is newer than index.html — run scripts/build_site.py first" >&2
  exit 1
fi

# AS_OF is the date the count describes; SNAPSHOT is the day the sources were fetched.
# They differ, and the site reports AS_OF, so the deploy message must too.
SNAP=$(python3 -c "import sys;sys.path.insert(0,'scripts');import config;print(config.AS_OF)")
FETCHED=$(python3 -c "import sys;sys.path.insert(0,'scripts');import config;print(config.SNAPSHOT)")
NCITY=$(python3 - <<'PY'
import json, pathlib
s = pathlib.Path("site/payload.js").read_text(encoding="utf-8")
d = json.loads(s[s.index("=") + 1:].rstrip().rstrip(";"))
print(len(d["audited"]))
PY
)

# .nojekyll stops Pages running the page through Jekyll, which is pure latency here and
# would silently drop any path beginning with an underscore.
blob=$(git hash-object -w "$PAGE")
nojekyll=$(printf '' | git hash-object -w --stdin)
tree=$(printf '100644 blob %s\tindex.html\n100644 blob %s\t.nojekyll\n' "$blob" "$nojekyll" | git mktree)

msg="Publish site — snapshot ${SNAP} (sources ${FETCHED}), ${NCITY} cities audited"
if parent=$(git rev-parse --verify --quiet refs/heads/gh-pages); then
  if [ "$(git rev-parse "$parent^{tree}")" = "$tree" ]; then
    echo "gh-pages already matches this page; nothing to publish."
    exit 0
  fi
  commit=$(git commit-tree "$tree" -p "$parent" -m "$msg")
else
  commit=$(git commit-tree "$tree" -m "$msg")
fi

git update-ref refs/heads/gh-pages "$commit"
echo "gh-pages -> $(git rev-parse --short "$commit")  ($msg)"
echo
echo "Now run:  git push origin gh-pages"
