#!/usr/bin/env bash
# Build the distributable zip from skills/openhasp-page/.
# The zip unpacks to openhasp-page/, which is what both ~/.claude/skills/ and the
# claude.ai skill uploader expect.
set -euo pipefail

cd "$(dirname "$0")"
VERSION=$(python3 -c 'import json;print(json.load(open(".claude-plugin/plugin.json"))["version"])')
STAGE=$(mktemp -d)
trap 'rm -rf "$STAGE"' EXIT

mkdir -p "$STAGE/openhasp-page"
cp skills/openhasp-page/SKILL.md \
   skills/openhasp-page/reference.md \
   skills/openhasp-page/validate.py \
   LICENSE \
   "$STAGE/openhasp-page/"
cp INSTALL.md "$STAGE/openhasp-page/README.md"

mkdir -p dist
rm -f "dist/openhasp-page-skill-$VERSION.zip"
(cd "$STAGE" && zip -q -r -X "openhasp-page-skill-$VERSION.zip" openhasp-page)
mv "$STAGE/openhasp-page-skill-$VERSION.zip" dist/

echo "dist/openhasp-page-skill-$VERSION.zip"
unzip -l "dist/openhasp-page-skill-$VERSION.zip"
