#!/bin/sh

# Load .env from script directory and ensure NOAA_HOME is set
DIR="$(cd "$(dirname "$0")" && pwd)"
if [ -f "$DIR/.env" ]; then
	# shellcheck disable=SC1090
	. "$DIR/.env"
fi
NOAA_HOME=${NOAA_HOME:-"$DIR"}

#PIPER_MODEL="/usr/local/share/piper/models/en_US-danny-low.onnx"
PIPER_MODEL="/usr/local/share/piper/models/en_US-amy-medium.onnx"
PIPER_BIN="/usr/local/bin/piper/piper"


echo "Beginning Piper speech generation"

# Generate WAV files using Piper
$PIPER_BIN --model "$PIPER_MODEL" --output_file "$NOAA_HOME/long_term.wav" < "$NOAA_HOME/long_term.txt"
$PIPER_BIN --model "$PIPER_MODEL" --output_file "$NOAA_HOME/short_term.wav" < "$NOAA_HOME/short_term.txt"
$PIPER_BIN --model "$PIPER_MODEL" --output_file "$NOAA_HOME/near_term.wav" < "$NOAA_HOME/near_term.txt"
$PIPER_BIN --model "$PIPER_MODEL" --output_file "$NOAA_HOME/synopsis.wav" < "$NOAA_HOME/synopsis.txt"

echo "Completed Piper speech generation"

echo "Beginning wav to mp3 conversion"

# Convert WAV → MP3 using lame (same as before)
"/usr/bin/lame" --vbr-new -V3 "$NOAA_HOME/long_term.wav" "$NOAA_HOME/long_term.mp3"
"/usr/bin/lame" --vbr-new -V3 "$NOAA_HOME/short_term.wav" "$NOAA_HOME/short_term.mp3"
"/usr/bin/lame" --vbr-new -V3 "$NOAA_HOME/near_term.wav" "$NOAA_HOME/near_term.mp3"
"/usr/bin/lame" --vbr-new -V3 "$NOAA_HOME/synopsis.wav" "$NOAA_HOME/synopsis.mp3"

echo "Completed wav to mp3 conversion"
