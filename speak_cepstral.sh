#!/bin/sh

# Load .env from script directory and ensure NOAA_HOME is set
DIR="$(cd "$(dirname "$0")" && pwd)"
if [ -f "$DIR/.env" ]; then
	# shellcheck disable=SC1090
	. "$DIR/.env"
fi
NOAA_HOME=${NOAA_HOME:-"$DIR"}

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
"$SWIFT_BIN/swift.bin" -o $NOAA_HOME/long_term.wav -p audio/channels=2,audio/sampling-rate=44100 -f $NOAA_HOME/long_term.txt
"$SWIFT_BIN/swift.bin" -o $NOAA_HOME/short_term.wav -p audio/channels=2,audio/sampling-rate=44100 -f $NOAA_HOME/short_term.txt
"$SWIFT_BIN/swift.bin" -o $NOAA_HOME/near_term.wav -p audio/channels=2,audio/sampling-rate=44100 -f $NOAA_HOME/near_term.txt
"$SWIFT_BIN/swift.bin" -o $NOAA_HOME/synopsis.wav -p audio/channels=2,audio/sampling-rate=44100 -f $NOAA_HOME/synopsis.txt
echo "Completed Cepstral speech generation"

echo "Beginning wav to mp3 conversion"
#for f in *.wav; do lame --vbr-new -V 3 "$f" "${f%.wav}.mp3"; done
"/usr/bin/lame" --vbr-new -V3 $NOAA_HOME/long_term.wav $NOAA_HOME/long_term.mp3 
"/usr/bin/lame" --vbr-new -V3 $NOAA_HOME/short_term.wav $NOAA_HOME/short_term.mp3 
"/usr/bin/lame" --vbr-new -V3 $NOAA_HOME/near_term.wav $NOAA_HOME/near_term.mp3 
"/usr/bin/lame" --vbr-new -V3 $NOAA_HOME/synopsis.wav $NOAA_HOME/synopsis.mp3 

echo "Completed wav to mp3 conversion"
