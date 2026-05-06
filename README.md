NOAA Stream (noaa_stream)
=========================

Summary
-------
Small collection of scripts to fetch NOAA discussion (AFD) and stream audio via ezstream.

Files of interest
-----------------
- tts_noaa.pl — fetches NOAA AFD product and writes synopsis/near_term/short_term/long_term files.
- ezstream.xml.template — ezstream configuration template with password placeholder.
- gen_ezstream.sh — generates ezstream.xml from the template using the password from environment.
- stream.sh — generates ezstream.xml (if generator present) and launches ezstream.
- list.m3u, synopsis.txt, near_term.txt, short_term.txt, long_term.txt — content files used by the stream.

Dependencies
------------
- Perl (with modules: HTTP::Request, WWW::Curl::UserAgent, File::Copy, FindBin)
- ezstream (the ezstream binary)
- awk (standard on Unix)
 - A local Text-to-Speech engine (recommended: piper) for generating audio files from the discussion text
 - An audio distribution server (recommended: Icecast) to serve the live stream to listeners

Configuration
-------------
This project uses environment variables for configuration and supports a .env file in the same directory. The provided `tts_noaa.pl` already loads `.env` (if present) into the process environment.

Important environment variables
- `NOAA_HOME` — optional; override the base path used for files. Defaults to the script directory.
- `NOAA_AFD_URL` — optional; URL to fetch the AFD product. Defaults to the BTV AFD URL used previously.
- `EZSTREAM_PASSWORD` — REQUIRED to generate `ezstream.xml` from the template. Do NOT commit the real password into the repo; place it in a local `.env` or export it in the environment.

Recommended .env (example)
--------------------------
Place a file named `.env` in the repository directory (do not commit with secrets) with lines like:

NOAA_AFD_URL=https://forecast.weather.gov/product.php?site=BTV&issuedby=BTV&product=AFD&format=CI&version=1&glossary=1&highlight=off
EZSTREAM_PASSWORD=your_real_ezstream_password_here

Usage
-----
1. Ensure `EZSTREAM_PASSWORD` is set in the environment or in `.env`.
2. Generate `ezstream.xml` and run the stream:

```sh
cd /path/to/noaa_stream
./stream.sh
```

`stream.sh` will call `gen_ezstream.sh` (if present/executable) which writes `ezstream.xml` with restricted permissions, then launches `ezstream`.

Text-to-Speech (TTS)
--------------------
This project expects a TTS component to convert the generated text files (`synopsis.txt`, `near_term.txt`, `short_term.txt`, `long_term.txt`) into audio files consumed by `ezstream`'s intake (for example via `list.m3u`). A recommended local TTS is `piper` (or any command-line TTS you prefer).

Example (pseudo-command — replace with your TTS CLI):

```sh
# generate a WAV from synopsis
piper --model MODEL_NAME --input synopsis.txt --output synopsis.wav
# or using a generic TTS command
tts-cli --input synopsis.txt --output synopsis.wav
```

After generating audio files, update or generate `list.m3u` so `ezstream` will stream the files in the desired order.

Distribution / Icecast
----------------------
For serving the audio to listeners, use a distribution server such as `Icecast`. `ezstream` can push to an Icecast instance by configuring the server connection in `ezstream.xml.template` (hostname, port, mountpoint, user, password). If you host Icecast locally, set the template to point at `127.0.0.1` and the correct port (default `8000`).

Quick notes:
- Install Icecast on Debian/Ubuntu: `sudo apt-get install icecast2` and follow the prompts to configure passwords.
- Configure `ezstream.xml.template` server entries to match your Icecast credentials and mountpoint.
- Use secure passwords and consider enabling TLS (`<tls>required</tls>`) for remote connections.

For containerized or CI deployments, supply Icecast credentials via secrets and generate `ezstream.xml` at startup using `gen_ezstream.sh`.

Notes on security
-----------------
- Keep `.env` out of version control (add to .gitignore) — it contains secrets.
- The generated `ezstream.xml` will be written with `chmod 600` to reduce exposure.
- Consider using TLS (`<tls>required</tls>`) and a secure hostname/port in `ezstream.xml.template` for production.

Deploying / Automation
----------------------
- Use `systemd` or another supervisor to run `stream.sh` on boot. An example unit file (not provided) should call `gen_ezstream.sh` before starting `ezstream` if you prefer external templating.
- For CI or container deployment, supply `EZSTREAM_PASSWORD` as a secret and have the entrypoint run `gen_ezstream.sh` before starting `ezstream`.
 - For CI or container deployment, supply `EZSTREAM_PASSWORD` as a secret and have the entrypoint run `gen_ezstream.sh` before starting `ezstream`.

Systemd service (example)
-------------------------
To run this stream on system boot under `systemd`, create a service unit at `/etc/systemd/system/noaa-stream.service` (replace the `User` and paths as appropriate). Example unit:

```ini
[Unit]
Description=NOAA AFD stream via ezstream
After=network.target

[Service]
Type=simple
User=scott
WorkingDirectory=/home/scott/noaa_stream
EnvironmentFile=/home/scott/noaa_stream/.env
ExecStart=/home/scott/noaa_stream/stream.sh
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
```

The repository also includes an example unit file you can use: [noaa_stream/ezstream.service](noaa_stream/ezstream.service#L1).

Enable and start:

```sh
sudo systemctl daemon-reload
sudo systemctl enable --now noaa-stream.service
```

Notes:
- Ensure `/home/scott/noaa_stream/.env` is readable only by the service user (`chmod 600`).
- If `ezstream` is not on the service user's `PATH`, use an absolute path in `ExecStart` (e.g. `/usr/bin/ezstream -c /home/scott/noaa_stream/ezstream.xml`).
- Adjust `User=` and `EnvironmentFile=` for your deployment.
Extending
---------
- If you need multiple server configurations or dynamic templating, replace `gen_ezstream.sh` with a more capable templating tool (envsubst, mustache, jinja2, etc.).
