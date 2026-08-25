# TLDR Mode

TLDR Mode is a proof of concept for a personal content moderation layer owned and
controlled by the individual. It evaluates an article using interests and
choices defined by the reader, irrespective of where the content comes from.

This demo uses [mitmproxy](https://mitmproxy.org/) between a browser and a small
example blog. It demonstrates two settings.

1. TLDR Mode setting, select an author provided concise version of an article.
2. Keywords setting, skip an article when a phrase appears too many times.

When an article is skipped, the reader sees the reason and receives a link to
continue to the next article.

## Architecture

```text
Browser
   |
   | HTTP request for blog.example.com on port 8000
   v
mitmproxy on localhost port 8080
   |
   | Applies the individual policy in proxy/policy.json
   v
Nginx demo blog in Docker on port 8000
```

Only requests for `blog.example.com` are modified by the add on. The host machine
maps that demo domain to `127.0.0.1`, and mitmproxy routes matching requests to
the Nginx container internally.

## Requirements

- Docker Desktop or Docker Engine with Docker Compose.
- Google Chrome or another Chromium based browser.

## Start the demo

From this repository, run the following command.

```bash
docker compose up --build
```

Wait until the `blog` and `tldr-proxy` services are running.

```bash
docker compose ps
```

The demo blog is exposed on port `8000`. mitmproxy listens on port `8080`.

## Add the demo domain to the hosts file

Add the following entry to `/etc/hosts` on the host machine.

```text
127.0.0.1 blog.example.com # tldr-mode-poc
```

On macOS or Linux, append it with the following command. The command first checks
for an existing entry to avoid adding a duplicate.

```bash
grep -qE '^[[:space:]]*127\.0\.0\.1[[:space:]]+blog\.example\.com([[:space:]]|$)' /etc/hosts || \
  echo '127.0.0.1 blog.example.com # tldr-mode-poc' | sudo tee -a /etc/hosts
```

Verify that the domain resolves to the local machine.

```bash
ping -c 1 blog.example.com
```

The output should resolve `blog.example.com` to `127.0.0.1`.

## Configure Chrome for this HTTP demo

Configure an HTTP proxy with these values.

- HTTP proxy host, `127.0.0.1`.
- HTTP proxy port, `8080`.
- HTTPS proxy, leave empty or set to direct.

Chrome normally uses the proxy settings of the operating system. On macOS, the
following command opens a separate Chrome profile configured only for this demo.

```bash
open -na "Google Chrome" --args \
  --user-data-dir=/tmp/tldr-mode-chrome \
  --proxy-server="http=127.0.0.1:8080;https=direct://" \
  --proxy-bypass-list="<-loopback>"
```

This temporary profile avoids changing the proxy configuration of the normal
Chrome profile.

Open the demo home page.

[http://blog.example.com:8000](http://blog.example.com:8000)

## Demonstrate both settings

### 1. TLDR Mode setting

This setting lets a reader choose a concise version of the same article supplied
directly by its author. The proxy does not ask an LLM to generate or reinterpret
the summary.

1. Open [`proxy/policy.json`](proxy/policy.json) and set `tldr_mode.enabled` to
   `false`, then save the file.
2. From the demo home page, open **TLDR Mode setting**.
3. The browser displays the intentionally long article from
   `about-rcb-team/index.html`.
4. Change `tldr_mode.enabled` to `true` in the policy file and save it.
5. Reload **TLDR Mode setting** at the same URL.
6. The same URL now displays the author provided concise article from
   `about-rcb-team/index-tldr.html`.

### 2. Keywords setting

The reader can define phrases and the maximum number of times each phrase may
appear. The example uses the phrase `guaranteed` three times while the configured
limit is two.

1. In `proxy/policy.json`, set `keywords.enabled` to `false` and save the file.
2. Open **Keywords setting** from the home page.
3. The original article containing the repeated phrase is displayed because this
   setting is disabled.
4. Set `keywords.enabled` to `true` and save the file.
5. Reload the same article.
6. TLDR Mode skips the article and explains which phrase exceeded the personal
   limit.
7. Select **Go to the next article** to reach the final article that matches the
   policy.

## Define individual interests and choices

Both settings are represented in
[`proxy/policy.json`](proxy/policy.json).

```json
{
  "tldr_mode": {
    "enabled": false,
    "full_page_name": "index.html",
    "concise_page_name": "index-tldr.html"
  },
  "keywords": {
    "enabled": true,
    "maximum_occurrences": {
      "guaranteed": 2,
      "secret trick": 2,
      "you won't believe": 1
    }
  }
}
```

The proxy reads the complete JSON policy for every article request. Changes to
both settings take effect as soon as the file is saved. No proxy or container
restart is required.

For example, change the limit for `guaranteed` from `2` to `3`, save the file, and
reload the keywords example. The article will be displayed because it now matches
the individual policy.

## Verify without a browser

The home page can be requested through the proxy with curl.

```bash
curl --proxy http://127.0.0.1:8080 \
  http://blog.example.com:8000/
```

The keywords setting can also be verified directly.

```bash
curl --proxy http://127.0.0.1:8080 \
  http://blog.example.com:8000/examples/keyword-heavy.html
```

The response contains `This article was skipped` and explains the configured
limit that was exceeded.

## Stop the demo

```bash
docker compose down
```

Close the temporary Chrome window or restore the normal browser proxy settings.

Remove the hosts entry when the demonstration is complete. Open `/etc/hosts` with
administrator privileges and delete this exact line.

```text
127.0.0.1 blog.example.com # tldr-mode-poc
```

## Proof of concept scope

This project deliberately uses simple rules and unencrypted HTTP so that the idea
is easy to inspect and understand. Do not send sensitive traffic through this
demo proxy.

A fully functional version would require advanced add ons and more sophisticated
logic for content understanding, HTTPS handling, privacy, security, performance,
accessibility, platform compatibility, policy transparency, and controls that
remain exclusively owned by the individual.
