NOAA Stream (noaa_stream)
=========================

Summary
-------
Small collection of scripts to fetch NOAA discussion (AFD) and stream audio via ezstream.

Files of interest
-----------------
- scripts/tts_noaa.pl — fetches the NOAA AFD product and writes forecast text files.
- scripts/speak_piper.sh and scripts/speak_cepstral.sh — generate forecast audio.
- scripts/gen_ezstream.sh and scripts/stream.sh — configure and launch ezstream.
- list.m3u — root-level playlist referencing assets/audio and forecasts/audio.
- forecasts/text and forecasts/audio — generated forecast text and audio.
- assets/audio — supporting audio such as the stream beeps.
- cache — synopsis backup and other transient files.
- scripts and tests — operational scripts and Python API tests.

Directory layout and cron
-------------------------
Generated forecast text is stored in `forecasts/text/`, generated WAV/MP3 files in `forecasts/audio/`, and the NOAA synopsis backup in `cache/`. Supporting beeps live in `assets/audio/`; operational scripts are in `scripts/`; historical variants and unused samples are retained in `archive/`. Stream launcher output is written under `logs/`.

Keep `.env`, `abbreviations.csv`, `config.toml`, `ezstream.xml`, `ezstream.xml.template`, and `list.m3u` at the project root. `NOAA_HOME` remains the project root; the installed ezstream service's `WorkingDirectory` and XML path therefore do not change. 

The following Cron example illustrates how the system can keep the forecast text and audio generation up to date on an ongoing basis:
```cron
00 * * * * /home/scott/noaa_stream/scripts/tts_noaa.pl >/dev/null 2>&1
01 * * * * /home/scott/noaa_stream/scripts/speak_piper.sh >/dev/null 2>&1
```

Do this as part of the coordinated migration, after the new forecast folders are populated and the scripts are in place. Do not leave both old and new entries enabled, or a forecast could be processed twice. The historical Cepstral example, if enabled, should use `/home/scott/noaa_stream/scripts/speak_cepstral.sh`.
Dependencies
------------
- Perl (with modules: HTTP::Request, WWW::Curl::UserAgent, File::Copy, FindBin)
- ezstream (the ezstream binary)
- awk (standard on Unix)
 - A local Text-to-Speech engine (recommended: piper) for generating audio files from the discussion text
 - An audio distribution server (recommended: Icecast) to serve the live stream to listeners

Configuration
-------------
This project uses environment variables for configuration and supports a `.env` file at the project root. `scripts/tts_noaa.pl` loads that file when `NOAA_HOME` is not already set.

Important environment variables
 - `NOAA_HOME` — optional; override the project root used for files. Defaults to the repository root, including when scripts run from `scripts/`.
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
./scripts/stream.sh
```

`scripts/stream.sh` calls `scripts/gen_ezstream.sh` when it is executable, writes the root `ezstream.xml` with restricted permissions, then launches `ezstream`.

Text-to-Speech (TTS)
--------------------
This project expects a TTS component to convert the generated files in `forecasts/text/` into audio files under `forecasts/audio/`, consumed by ezstream through the root `list.m3u`. The configured local TTS is `piper`.

Example (pseudo-command — replace with your TTS CLI):

```sh
# generate a WAV from synopsis
piper --model MODEL_NAME --input forecasts/text/synopsis.txt --output forecasts/audio/synopsis.wav
# or using a generic TTS command
tts-cli --input forecasts/text/synopsis.txt --output forecasts/audio/synopsis.wav
```

After generating audio files, ensure the root `list.m3u` references them in the desired order.

Distribution / Icecast
----------------------
For serving the audio to listeners, use a distribution server such as `Icecast`. `ezstream` can push to an Icecast instance by configuring the server connection in `ezstream.xml.template` (hostname, port, mountpoint, user, password). If you host Icecast locally, set the template to point at `127.0.0.1` and the correct port (default `8000`).

Quick notes:
- Install Icecast on Debian/Ubuntu: `sudo apt-get install icecast2` and follow the prompts to configure passwords.
- Configure `ezstream.xml.template` server entries to match your Icecast credentials and mountpoint.
- Use secure passwords and consider enabling TLS (`<tls>required</tls>`) for remote connections.

For containerized or CI deployments, supply Icecast credentials via secrets and generate root `ezstream.xml` at startup using `scripts/gen_ezstream.sh`.

Notes on security
-----------------
- Keep `.env` out of version control (add to .gitignore) — it contains secrets.
- The generated `ezstream.xml` will be written with `chmod 600` to reduce exposure.
- Consider using TLS (`<tls>required</tls>`) and a secure hostname/port in `ezstream.xml.template` for production.

Deploying / Automation
----------------------
- Use `systemd` or another supervisor to run `scripts/stream.sh` on boot. The installed `ezstream.service` can continue invoking ezstream directly with the root XML.
- For CI or container deployment, supply `EZSTREAM_PASSWORD` as a secret and have the entrypoint run `scripts/gen_ezstream.sh` before starting ezstream.

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
ExecStart=/home/scott/noaa_stream/scripts/stream.sh
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
- If you need multiple server configurations or dynamic templating, replace `scripts/gen_ezstream.sh` with a more capable templating tool (envsubst, mustache, jinja2, etc.).

Forecast Summary API
--------------------
The summary API is a separate Python service. It reads `forecasts/text/` without changing the files or invoking the scraper, TTS scripts, or stream service. It uses FastAPI served by Uvicorn and sends on-demand summary requests to the configured Ollama `/api/chat` endpoint.

Install the API dependencies in an isolated virtual environment:

```sh
cd /home/scott/noaa_stream
python3 -m venv .venv-summary
.venv-summary/bin/pip install -r requirements-summary.txt
```

Set the Ollama URL and a model already installed on that server in `config.toml`. The service never downloads a model. Relative `paths.forecast_dir` values are resolved relative to `config.toml`; the configured value is `forecasts/text`. The API address and port are also configured there.

Run it in the foreground:

```sh
.venv-summary/bin/python scripts/summary_api.py --config config.toml
```

The default Ollama timeouts allow a sleeping host or wake-up proxy to respond: connection timeout 15 seconds, response timeout 240 seconds, and an overall generation deadline of 300 seconds. These can be raised in `config.toml` if wake-up and inference take longer. A cache hit for an unchanged forecast does not contact Ollama. A cache miss holds the requesting HTTP connection open while generation runs; clients and any reverse proxy must allow that duration. Network failures are not retried. Invalid model output gets one correction attempt within the same deadline.

Endpoints:

```text
GET /healthz
GET /api/v1/forecasts/synopsis
GET /api/v1/forecasts/synopsis/message_summary
GET /api/v1/forecasts/near_term
GET /api/v1/forecasts/near_term/message_summary
GET /api/v1/forecasts/short_term
GET /api/v1/forecasts/short_term/message_summary
GET /api/v1/forecasts/long_term
GET /api/v1/forecasts/long_term/message_summary
```

The forecast URLs return the exact source file as `text/plain` and never call Ollama. The nested `message_summary` URLs return JSON with the validated MeshCore-sized summary and metadata.

Examples:

```sh
curl http://192.168.16.28:8765/api/v1/forecasts/near_term
curl http://192.168.16.28:8765/api/v1/forecasts/near_term/message_summary
```

The JSON `summary` field from `message_summary` is the MeshCore payload: printable ASCII, at most 133 characters including spaces and punctuation, and at most four sentences. The JSON metadata is not part of that payload. Overlong or invalid model output is rejected rather than truncated. Forecast summaries are not independently fact-checked; verify operationally important details against the NOAA source.

The API caches valid output in memory while a section's source contents remain unchanged. Restarting the service clears that cache. It reads one section per request; the existing scraper writes files in place, so source stability checks are best-effort and do not make a four-file product update atomic. Source timestamps report filesystem modification time, not a freshness guarantee. Health checks report API/config process liveness and do not require Ollama to be awake.

Expected errors include `404` for an unknown section or missing source, `502` for rejected or invalid Ollama output, `503` when Ollama/source/capacity is unavailable, and `504` when an Ollama timeout expires.

Systemd deployment
------------------
The separate `summary-api.service` example runs as the unprivileged `scott` user and does not depend on or start the scraper, TTS, stream, or Ollama services. Adjust its user and paths if this checkout is installed elsewhere. Install and start it explicitly:

```sh
sudo install -m 0644 summary-api.service /etc/systemd/system/summary-api.service
sudo systemctl daemon-reload
sudo systemctl enable --now summary-api.service
sudo systemctl status summary-api.service
```

View logs with `sudo journalctl -u summary-api.service -f`. The unit is read-only and has a 256 MB memory limit; configuration and forecast files must be readable by the service user.

For trusted LAN/VPN clients only, change `[api].host` to `0.0.0.0` (or the intended interface address), restart the summary service, and restrict the firewall to trusted clients. The API has no authentication or TLS; do not expose it directly to the public Internet. `/healthz` remains available while Ollama is asleep; a summary request waits only up to the configured deadlines.
