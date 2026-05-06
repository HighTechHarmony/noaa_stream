#!/bin/sh
# Generate ezstream.xml from template by substituting PASSWORD_PLACEHOLDER
# Requires environment variable EZSTREAM_PASSWORD to be set.

TEMPLATE="$(dirname "$0")/ezstream.xml.template"
OUT="$(dirname "$0")/ezstream.xml"

if [ -z "$EZSTREAM_PASSWORD" ]; then
  echo "ERROR: EZSTREAM_PASSWORD not set. Set it in the environment or in .env" >&2
  exit 1
fi

if [ ! -r "$TEMPLATE" ]; then
  echo "ERROR: template $TEMPLATE not readable" >&2
  exit 2
fi

# Use awk to perform a safe substitution of the placeholder
awk -v pw="$EZSTREAM_PASSWORD" '{gsub(/PASSWORD_PLACEHOLDER/, pw); print}' "$TEMPLATE" > "$OUT" || exit 3

# Restrict permissions on generated file
chmod 600 "$OUT" || true

echo "Generated $OUT"
