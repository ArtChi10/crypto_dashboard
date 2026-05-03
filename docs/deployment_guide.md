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

Edit `.env.production`:

```text
DJANGO_SECRET_KEY=<long-random-secret>
DJANGO_DEBUG=False
DJANGO_ALLOWED_HOSTS=<server-ip-or-domain>

POSTGRES_DB=crypto_dashboard
POSTGRES_USER=crypto_dashboard
POSTGRES_PASSWORD=<strong-password>
DATABASE_URL=postgresql://crypto_dashboard:<strong-password>@db:5432/crypto_dashboard
```

Keep `POSTGRES_PASSWORD` and the password inside `DATABASE_URL` in sync. Do not
commit `.env.production`.

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
