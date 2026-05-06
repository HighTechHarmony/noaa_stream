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

Notes on security
-----------------
- Keep `.env` out of version control (add to .gitignore) — it contains secrets.
- The generated `ezstream.xml` will be written with `chmod 600` to reduce exposure.
- Consider using TLS (`<tls>required</tls>`) and a secure hostname/port in `ezstream.xml.template` for production.

Deploying / Automation
----------------------
- Use `systemd` or another supervisor to run `stream.sh` on boot. An example unit file (not provided) should call `gen_ezstream.sh` before starting `ezstream` if you prefer external templating.
- For CI or container deployment, supply `EZSTREAM_PASSWORD` as a secret and have the entrypoint run `gen_ezstream.sh` before starting `ezstream`.

Extending
---------
- If you need multiple server configurations or dynamic templating, replace `gen_ezstream.sh` with a more capable templating tool (envsubst, mustache, jinja2, etc.).

Contact
-------
This README was generated alongside small code changes to move the NOAA URL and ezstream password into environment-configurable variables.
