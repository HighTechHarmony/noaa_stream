#!/bin/sh
# Generate ezstream.xml from template if needed, then run ezstream
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$SCRIPT_DIR"
if [ "$(basename "$SCRIPT_DIR")" = "scripts" ]; then
	PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
fi
if [ -x "$SCRIPT_DIR/gen_ezstream.sh" ]; then
	# gen_ezstream.sh will fail if EZSTREAM_PASSWORD not set
	"$SCRIPT_DIR/gen_ezstream.sh" || exit 1
fi

mkdir -p "$PROJECT_ROOT/logs"
nohup /usr/bin/ezstream -c "$PROJECT_ROOT/ezstream.xml" >> "$PROJECT_ROOT/logs/nohup.out" 2>&1 &

