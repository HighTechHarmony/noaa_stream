#!/bin/sh

# Load the project-root .env and keep NOAA_HOME rooted at the project directory.
DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$DIR"
if [ "$(basename "$DIR")" = "scripts" ]; then
	PROJECT_ROOT="$(dirname "$DIR")"
fi
if [ -f "$PROJECT_ROOT/.env" ]; then
	# shellcheck disable=SC1090
	. "$PROJECT_ROOT/.env"
fi
NOAA_HOME=${NOAA_HOME:-"$PROJECT_ROOT"}
FORECAST_TEXT_DIR="$NOAA_HOME/forecasts/text"
FORECAST_AUDIO_DIR="$NOAA_HOME/forecasts/audio"
mkdir -p "$FORECAST_AUDIO_DIR"

SWIFT_HOME="/opt/swift"
LD_LIBRARY_PATH="/opt/swift/lib"
SWIFT_BIN="/opt/swift/bin"

export  SWIFT_HOME
export  LD_LIBRARY_PATH

#exec "$SWIFT_BIN/swift.bin" -o long_term.wav -p audio/channels=2,audio/sampling-rate=44100 -f long_term.txt
#exec "$SWIFT_BIN/swift.bin" -o short_term.wav -p audio/channels=2,audio/sampling-rate=44100 -f short_term.txt
#exec "$SWIFT_BIN/swift.bin" -o near_term.wav -p audio/channels=2,audio/sampling-rate=44100 -f near_term.txt
#exec "$SWIFT_BIN/swift.bin" -o synopsis.wav -p audio/channels=2,audio/sampling-rate=44100 -f synopsis.txt

echo Beginning Cepstral speech generation
"$SWIFT_BIN/swift.bin" -o "$FORECAST_AUDIO_DIR/long_term.wav" -p audio/channels=2,audio/sampling-rate=44100 -f "$FORECAST_TEXT_DIR/long_term.txt"
"$SWIFT_BIN/swift.bin" -o "$FORECAST_AUDIO_DIR/short_term.wav" -p audio/channels=2,audio/sampling-rate=44100 -f "$FORECAST_TEXT_DIR/short_term.txt"
"$SWIFT_BIN/swift.bin" -o "$FORECAST_AUDIO_DIR/near_term.wav" -p audio/channels=2,audio/sampling-rate=44100 -f "$FORECAST_TEXT_DIR/near_term.txt"
"$SWIFT_BIN/swift.bin" -o "$FORECAST_AUDIO_DIR/synopsis.wav" -p audio/channels=2,audio/sampling-rate=44100 -f "$FORECAST_TEXT_DIR/synopsis.txt"
echo "Completed Cepstral speech generation"

echo "Beginning wav to mp3 conversion"
#for f in *.wav; do lame --vbr-new -V 3 "$f" "${f%.wav}.mp3"; done
"/usr/bin/lame" --vbr-new -V3 "$FORECAST_AUDIO_DIR/long_term.wav" "$FORECAST_AUDIO_DIR/long_term.mp3"
"/usr/bin/lame" --vbr-new -V3 "$FORECAST_AUDIO_DIR/short_term.wav" "$FORECAST_AUDIO_DIR/short_term.mp3"
"/usr/bin/lame" --vbr-new -V3 "$FORECAST_AUDIO_DIR/near_term.wav" "$FORECAST_AUDIO_DIR/near_term.mp3"
"/usr/bin/lame" --vbr-new -V3 "$FORECAST_AUDIO_DIR/synopsis.wav" "$FORECAST_AUDIO_DIR/synopsis.mp3"

echo "Completed wav to mp3 conversion"
