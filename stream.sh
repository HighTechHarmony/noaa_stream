#!/bin/sh
# Generate ezstream.xml from template if needed, then run ezstream
SCRIPT_DIR="$(dirname "$0")"
if [ -x "$SCRIPT_DIR/gen_ezstream.sh" ]; then
	# gen_ezstream.sh will fail if EZSTREAM_PASSWORD not set
	"$SCRIPT_DIR/gen_ezstream.sh" || exit 1
fi

nohup /usr/bin/ezstream -c "$SCRIPT_DIR/ezstream.xml" &

