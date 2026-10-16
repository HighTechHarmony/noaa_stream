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

#PIPER_MODEL="/usr/local/share/piper/models/en_US-danny-low.onnx"
PIPER_MODEL="/usr/local/share/piper/models/en_US-amy-medium.onnx"
PIPER_BIN="/usr/local/bin/piper/piper"


echo "Beginning Piper speech generation"

# Generate WAV files using Piper
$PIPER_BIN --model "$PIPER_MODEL" --output_file "$FORECAST_AUDIO_DIR/long_term.wav" < "$FORECAST_TEXT_DIR/long_term.txt"
$PIPER_BIN --model "$PIPER_MODEL" --output_file "$FORECAST_AUDIO_DIR/short_term.wav" < "$FORECAST_TEXT_DIR/short_term.txt"
$PIPER_BIN --model "$PIPER_MODEL" --output_file "$FORECAST_AUDIO_DIR/near_term.wav" < "$FORECAST_TEXT_DIR/near_term.txt"
$PIPER_BIN --model "$PIPER_MODEL" --output_file "$FORECAST_AUDIO_DIR/synopsis.wav" < "$FORECAST_TEXT_DIR/synopsis.txt"

echo "Completed Piper speech generation"

echo "Beginning wav to mp3 conversion"

# Convert WAV → MP3 using lame (same as before)
"/usr/bin/lame" --vbr-new -V3 "$FORECAST_AUDIO_DIR/long_term.wav" "$FORECAST_AUDIO_DIR/long_term.mp3"
"/usr/bin/lame" --vbr-new -V3 "$FORECAST_AUDIO_DIR/short_term.wav" "$FORECAST_AUDIO_DIR/short_term.mp3"
"/usr/bin/lame" --vbr-new -V3 "$FORECAST_AUDIO_DIR/near_term.wav" "$FORECAST_AUDIO_DIR/near_term.mp3"
"/usr/bin/lame" --vbr-new -V3 "$FORECAST_AUDIO_DIR/synopsis.wav" "$FORECAST_AUDIO_DIR/synopsis.mp3"

echo "Completed wav to mp3 conversion"
