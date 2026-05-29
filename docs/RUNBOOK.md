# VoiceSaju Runbook — Local Development

This runbook covers Phase 1 PoC local-dev datastore bring-up via docker-compose.
For deployment / cloud provisioning, see `docs/architecture.md` §13 (Phase 2).

---

## 1. Prerequisites

- Docker Desktop 4.x (or Docker Engine 24+) with Compose v2.
- Local CLI tools (optional but recommended for verification):
  - `psql` (PostgreSQL 16 client)
  - `redis-cli`

Check versions:

```bash
docker --version
docker compose version
```

---

## 2. Start datastores

From the repo root:

```bash
docker compose up -d
```

This starts two services defined in `docker-compose.yml`:

| Service  | Image              | Host port | Volume                     |
|----------|--------------------|-----------|----------------------------|
| postgres | postgres:16-alpine | 5432      | `voicesaju_postgres_data`  |
| redis    | redis:7-alpine     | 6379      | `voicesaju_redis_data`     |

Both services declare healthchecks; expect them to report `healthy` within ~30 seconds.

Check status:

```bash
docker compose ps
```

You should see both containers `Up` with `(healthy)` state.

---

## 3. Verify connectivity

### 3.1 PostgreSQL

Connection string (see `api/.env.example`):

```
postgresql+asyncpg://voicesaju:voicesaju@localhost:5432/voicesaju
```

Quick check (drop the `+asyncpg` suffix for raw `psql`):

```bash
psql "postgresql://voicesaju:voicesaju@localhost:5432/voicesaju" -c "SELECT version();"
```

Expected: `PostgreSQL 16.x ...` line.

### 3.2 Redis

```bash
redis-cli -u redis://localhost:6379/0 PING
```

Expected: `PONG`.

---

## 4. Local app configuration

Copy `api/.env.example` to `api/.env.local` (do not commit) and adjust as needed:

```bash
cp api/.env.example api/.env.local
```

Generate a real `LOCAL_KEK_BASE64` for envelope encryption tests:

```bash
python -c "import os, base64; print(base64.b64encode(os.urandom(32)).decode())"
```

Paste the output into `LOCAL_KEK_BASE64` inside `api/.env.local`. **Never commit
real KEK material.** `.env.local` is already gitignored alongside `.env*`.

---

## 5. Stop / reset

```bash
# Stop containers, keep data
docker compose down

# Stop AND delete named volumes (full reset — wipes DB + Redis state)
docker compose down -v
```

---

## 6. Troubleshooting

### Port conflict on 5432 or 6379

If you already run Postgres/Redis locally, either stop the local service or edit
the host-port mapping in `docker-compose.yml` (left side of `5432:5432`).

### Container fails healthcheck

Inspect logs:

```bash
docker compose logs postgres
docker compose logs redis
```

### Permission issues on macOS / Linux volumes

Named volumes are managed by Docker and should not require host-side permission
fixes. If you previously bind-mounted a host path, switch to the named volumes in
the committed `docker-compose.yml`.

---

## 7. Out of scope (Phase 2)

The following are explicitly **not** covered here and are deferred to Phase 2:

- Managed Postgres provisioning (Fly Postgres / Neon / Supabase).
- Managed Redis provisioning (Upstash).
- Secrets management (Doppler / Fly secrets / Vercel env).
- Cloudflare R2 (object storage) — see also ISSUE-005 (deferred) and ISSUE-099 (local mock).

References:
- `docs/architecture.md` §13.1 — production datastore plan.
- PRD NFR-005 (data security) and NFR-016 (deployment).
