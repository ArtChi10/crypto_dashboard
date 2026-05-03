# Deployment Guide: Docker Compose With PostgreSQL

This guide describes the production-oriented Docker Compose setup for a small
server. It targets an Ubuntu 24.04 / LXC host with Docker Compose, PostgreSQL,
and HTTP access by server IP.

HTTPS is intentionally not configured here. It is expected to be handled in a
separate step.

## Server Prerequisites

Install on the server:

- Docker Engine;
- Docker Compose plugin;
- Git.

The current expected server class:

- Ubuntu 24.04 / LXC;
- 2 CPU;
- 2 GB RAM;
- 32 GB disk;
- public or private IP reachable from your browser.

## Clone The Repository

```bash
git clone <repository-url>
cd crypto_dashboard
```

## Configure Environment

Create a production environment file from the example:

```bash
cp .env.production.example .env.production
```

Edit `.env.production` using `.env.production.example` as the template. It must
define the Django secret key, debug mode, allowed hosts, PostgreSQL database
name, PostgreSQL user, PostgreSQL password, and `DATABASE_URL`.

Keep the PostgreSQL password and the password inside `DATABASE_URL` in sync. Do
not commit `.env.production`; it is server-only configuration.

## Start The Stack

```bash
docker compose -f docker-compose.prod.yml up -d --build
```

The `web` service runs:

- `python manage.py migrate`;
- `python manage.py collectstatic --noinput`;
- `gunicorn config.wsgi:application --bind 0.0.0.0:8000`.

Caddy listens on port `80` and proxies Django through the internal Docker
network. It also serves `/static/` and `/media/` from Docker volumes.

## Check The Stack

```bash
docker compose -f docker-compose.prod.yml ps
docker compose -f docker-compose.prod.yml logs -f web
```

Open:

```text
http://SERVER_IP/
```

## Stop The Stack

```bash
docker compose -f docker-compose.prod.yml down
```

This stops containers but keeps named volumes.

## Persistent Data

Persistent named volumes:

- `postgres_data` for PostgreSQL data;
- `media_data` for uploaded/generated media artifacts;
- `static_data` for collected static files;
- `caddy_data` and `caddy_config` for Caddy runtime state.

Back up at least:

- `postgres_data`;
- `media_data`.

The exact backup mechanism depends on server policy. At minimum, take database
dumps and preserve media artifacts before upgrades.

## Updating The Deployment

```bash
git pull
docker compose -f docker-compose.prod.yml up -d --build
```

Then check:

```bash
docker compose -f docker-compose.prod.yml ps
docker compose -f docker-compose.prod.yml logs -f web
```

## GitHub Actions SSH Deploy

The repository includes an optional GitHub Actions workflow for deploying over
SSH after checks pass on `main`:

```text
.github/workflows/deploy.yml
```

Required GitHub Secrets:

| Secret | Purpose |
| --- | --- |
| `DEPLOY_HOST` | Server host or IP. The current server uses `195.54.178.243`. |
| `DEPLOY_PORT` | External SSH port. The current server uses `16470`. |
| `DEPLOY_USER` | SSH user. The current server uses `crypto`. |
| `DEPLOY_PATH` | Repository path on the server. The current server uses `/home/crypto/crypto_dashboard`. |
| `DEPLOY_HEALTHCHECK_URL` | Healthcheck URL from inside the server. The current stack uses `http://127.0.0.1/`. |
| `DEPLOY_SSH_KEY` | SSH deploy key material for the deploy user. Store it only as a GitHub Secret. |

The workflow:

- runs Django check, Ruff check, Ruff format check, and Django tests;
- starts an SSH agent with the configured deploy key;
- adds the server host key through `ssh-keyscan` using the configured SSH port;
- enters the server repository path;
- fetches `origin/main`;
- resets the server working tree to `origin/main`;
- rebuilds and starts the production Docker Compose stack;
- prints `docker compose` service status;
- runs a server-local healthcheck with retries, so the web container has time to
  finish migrations, collect static files, and start Gunicorn.

The server-local healthcheck uses the internal URL configured in
`DEPLOY_HEALTHCHECK_URL`. The public site is currently reachable through the
provider forwarding path at:

```text
http://195.54.178.243:16471/
```

The workflow does not create or modify `.env.production`. That file must remain
on the server and stay out of git.

To create a dedicated deploy key locally:

```powershell
ssh-keygen -t ed25519 -C "github-actions-crypto-dashboard-deploy" -f .\crypto_dashboard_deploy_key
```

Add the public key to `/home/crypto/.ssh/authorized_keys` on the server. Add the
secret key content to the GitHub Secret named `DEPLOY_SSH_KEY`.

## HTTPS Note

This setup serves HTTP on port `80` using a basic Caddy configuration. HTTPS,
domain configuration, and certificate handling are intentionally left for the
next deployment task.

## Limitations

- This is a simple Docker Compose setup, not a full platform deployment.
- UI pipeline execution is still synchronous.
- No background queue is configured.
- No HTTPS is configured in this task.
- No server hardening checklist is included here.
