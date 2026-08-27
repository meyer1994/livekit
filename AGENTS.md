# AGENTS.md

## Project structure

- `agent/` — Python 3.12 LiveKit voice agent and OpenTelemetry tracing.
- `app/` — Nuxt 4 web client and server-side room-token endpoint.
- `index.html` — legacy/standalone static browser client; it has no build step.
- `docker-compose.yml` — local LiveKit, Phoenix, agent, and app stack.
- `.railway/railway.ts` — Railway infrastructure definition.
- `.github/workflows/ci.yml` — app lint and typecheck CI.

## Package managers

- Use **uv** in `agent/`. Dependencies are declared in `agent/pyproject.toml`
  and locked in `agent/uv.lock`.
- Use **pnpm 11.22.0** in `app/`. Dependencies are declared in
  `app/package.json` and locked in `app/pnpm-lock.yaml`.
- Do not substitute `pip`, npm, or yarn, and keep lockfiles updated when
  dependencies change.

## Build and check commands

Run commands from the repository root unless noted otherwise.

### Python agent

```bash
cd agent
uv sync --locked
uv run --locked --no-sync python -m py_compile agent.py audio_trace.py
```

Run the agent locally with:

```bash
cd agent
uv run --locked python agent.py start
```

Build only its container with:

```bash
docker compose build agent
```

### Nuxt app

```bash
cd app
pnpm install --frozen-lockfile
pnpm build
pnpm lint
pnpm typecheck
```

Run development mode with `cd app && pnpm dev`. Build only its container with:

```bash
docker compose build app
```

### Static client

`index.html` has no build step. Serve it for manual testing with:

```bash
npx serve .
```

### Whole stack

`OPENAI_API_KEY` is required by the agent.

```bash
export OPENAI_API_KEY=your-key
docker compose build
docker compose up
```

Use `docker compose up --build` to build and start in one command, and `docker
compose down` to stop the stack.

## Docker containers

- `livekit` — `livekit/livekit-server:latest`; signaling on `7880`, TCP media on
  `7881`, and UDP media on `7882`.
- `phoenix` — `arizephoenix/phoenix:latest`; trace UI/OTLP HTTP on `6006` and
  OTLP gRPC on `4317`.
- `agent` — built from `agent/Dockerfile`; connects to LiveKit, OpenAI, and
  Phoenix.
- `app` — built from `app/Dockerfile`; Nuxt server exposed on `3000`.

Useful commands:

```bash
docker compose ps
docker compose logs -f agent
docker compose logs -f app
docker compose restart agent
```

## Basic `jq` recipes for CLI output

Ask CLIs for JSON when they support it, then inspect the result with `jq`:

```bash
some-cli --json | jq .                    # pretty-print
some-cli --json | jq 'keys'               # list top-level keys
some-cli --json | jq '.items[]'           # iterate an array
some-cli --json | jq '.items[] | {id, name, status}'
some-cli --json | jq '.items[] | select(.status == "failed")'
some-cli --json | jq -r '.items[].name'   # raw text output
some-cli --json | jq '[.items[] | select(.enabled)] | length'
```

For newline-delimited JSON, use slurp mode to create an array:

```bash
some-cli --json-lines | jq -s '.'
some-cli --json-lines | jq -s 'group_by(.status) | map({status: .[0].status, count: length})'
```

Docker Compose can also provide JSON for inspection:

```bash
docker compose ps --format json | jq .
docker compose ps --format json | jq -r '.[] | [.Service, .State, .Status] | @tsv'
```

When a command mixes logs with JSON, redirect diagnostics away from the pipe
when appropriate:

```bash
some-cli --json 2>cli-errors.log | jq .
```
