# syntax=docker/dockerfile:1.7
# Multi-stage Dockerfile for the VoiceSaju backend (ISSUE-083, NFR-016).
#
# Build:
#     docker build -t voicesaju-api:dev .
# Run:
#     docker run --rm -p 8000:8000 \
#         -e DATABASE_URL=postgresql+asyncpg://... \
#         voicesaju-api:dev
#
# Two stages:
#   1. **builder** — python:3.11-slim. Installs uv, materializes
#      ``requirements.txt`` via ``uv export`` (lock-pinned, deterministic),
#      and pre-builds wheels into ``/wheels`` so the runtime stage can
#      install offline without uv. We keep uv out of the runtime image so
#      the final image stays slim (NFR-016 < 500 MB) and the attack
#      surface is minimal.
#   2. **runtime** — python:3.11-slim. Installs ``ffmpeg`` via apt for
#      the audio-finalize worker (ISSUE-038/053), drops a non-root
#      ``appuser``, copies wheels + app code, installs into the system
#      Python via pip (offline, --no-index), and runs ``uvicorn`` against
#      ``voicesaju.main:app`` on port 8000.
#
# AC mapping:
#   1. ``docker build .`` → image < 500 MB. (Slim base + wheel-only
#      runtime install + no build toolchain in stage 2 keeps the image
#      well under the budget.)
#   2. ``docker run …`` → HEALTHCHECK against ``/healthz`` returns 200
#      within 30 s (interval 10 s, retries 3, start_period 10 s).
#   3. Container runs as ``USER appuser`` (uid 1000) — see runtime stage.

# ------------------------------------------------------------------
# Stage 1 — builder
# ------------------------------------------------------------------
FROM python:3.11-slim AS builder

# Pin a known-good uv version. Bumping requires a paired claude.md edit
# (per CLAUDE.md §5) since we're touching tooling.
ENV UV_VERSION=0.5.11 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

# Build deps. ``curl`` is needed to fetch the uv installer; we drop
# them all in this stage so they never reach the runtime image.
RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv (single binary; no python deps). The installer drops uv
# into ``/root/.local/bin``; symlink it into /usr/local/bin so it's on
# the default PATH for the subsequent steps.
RUN curl -LsSf https://astral.sh/uv/${UV_VERSION}/install.sh | sh \
    && ln -s /root/.local/bin/uv /usr/local/bin/uv

WORKDIR /build

# Copy only the lock + project metadata first so the wheel build cache
# is shared across code changes (only invalidated when deps change).
COPY pyproject.toml uv.lock ./

# Materialize a fully-pinned requirements.txt from uv.lock, then
# pre-build wheels for every dep. ``--no-dev`` keeps the runtime image
# free of pytest/ruff/black; ``--no-emit-project`` excludes our own
# package from the export (we install the source in the runtime stage).
RUN uv export \
        --no-dev \
        --no-emit-project \
        --no-hashes \
        --format requirements-txt \
        -o /build/requirements.txt

RUN pip wheel \
        --wheel-dir /wheels \
        --no-cache-dir \
        -r /build/requirements.txt

# ------------------------------------------------------------------
# Stage 2 — runtime
# ------------------------------------------------------------------
FROM python:3.11-slim AS runtime

# Settings the runtime cares about. ``PYTHONUNBUFFERED`` is required so
# the JSON logs (ISSUE-079) flush line-by-line into the container's
# stdout/stderr; ``PORT`` is conventional for Fly.io / Cloud Run.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    PORT=8000

# Runtime apt deps:
#   - ``ffmpeg``    — required by the audio-finalize worker for stitching
#                     per-sentence MP3 chunks (ISSUE-038, AP-37).
#   - ``ca-certificates`` — outbound HTTPS to Toss / OpenTelemetry /
#                     Sentry / R2.
#   - ``curl``      — used by HEALTHCHECK below; ~250 KB so the cost is
#                     trivial vs reaching for a separate binary.
# Clean apt lists in the same RUN so the layer doesn't carry the cache.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ffmpeg \
        ca-certificates \
        curl \
    && rm -rf /var/lib/apt/lists/*

# Non-root user (AC3). uid 1000 matches the conventional first-user uid
# on most distros so volume permissions line up with the host.
RUN groupadd --system --gid 1000 appuser \
    && useradd --system --uid 1000 --gid appuser --no-create-home --shell /usr/sbin/nologin appuser

WORKDIR /app

# Install dependencies from the wheels we built in stage 1 — no network
# access, no compilers, no uv binary. The leftover requirements.txt is
# kept at ``/app/requirements.txt`` for ops introspection (``pip freeze``
# would show the same thing but having the original file is cheaper).
COPY --from=builder /wheels /wheels
COPY --from=builder /build/requirements.txt /app/requirements.txt
RUN pip install \
        --no-cache-dir \
        --no-index \
        --find-links=/wheels \
        -r /app/requirements.txt \
    && rm -rf /wheels

# Copy the application source last so unrelated code changes don't bust
# the dep-install layer cache above. ``.dockerignore`` excludes tests,
# .venv, __pycache__, etc.
COPY voicesaju /app/voicesaju
COPY alembic /app/alembic
COPY alembic.ini /app/alembic.ini

# Make the app dir + its contents owned by appuser. ``--from`` copies
# happen as root by default; the chown ensures the runtime user can read
# (but not modify, since we drop privileges before exec).
RUN chown -R appuser:appuser /app

USER appuser

EXPOSE 8000

# Health probe — hits the liveness endpoint registered in
# ``voicesaju.main.create_app``. AC2 requires ``200`` within 30 s of
# container start; we give the readiness path 10 s start_period + 3
# retries × 10 s interval = up to 40 s soft budget, which covers cold
# imports comfortably without flaking on slow CI hosts.
HEALTHCHECK --interval=10s --timeout=3s --start-period=10s --retries=3 \
    CMD curl -fsS http://127.0.0.1:8000/healthz || exit 1

# Default to running the web process. The worker process group uses the
# same image with ``arq voicesaju.jobs.worker.WorkerSettings`` as the
# command override (see docker-compose.dev.yml).
CMD ["uvicorn", "voicesaju.main:app", "--host", "0.0.0.0", "--port", "8000"]
