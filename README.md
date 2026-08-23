# Minimal self-hosted LiveKit

This is the smallest local setup: a LiveKit server and a Python agent started by
Docker Compose. The agent's dependencies are managed with `uv` and pinned in
`agent/uv.lock`.

## Start it

The agent uses OpenAI Whisper-compatible STT for this first test, so provide an
OpenAI API key before starting:

```bash
export OPENAI_API_KEY=your-openai-api-key
docker compose up --build
```

The services are then available at:

- LiveKit signaling/API: `ws://localhost:7880`
- LiveKit TCP media: `localhost:7881`
- LiveKit UDP media: `localhost:7882`

The development server uses these credentials:

```text
LIVEKIT_API_KEY=devkey
LIVEKIT_API_SECRET=secret
```

The agent registers with LiveKit and waits for a room job. When a participant
joins its room, it sends one reliable data message:

```text
Hello from the LiveKit agent!
```

It also transcribes microphone audio with OpenAI STT and speaks the response
back with OpenAI TTS. Each final transcript is sent as a reliable data message
prefixed with `Echo:` and spoken aloud. The agent uses Silero VAD with a longer
silence window and prefix padding to avoid false starts, lost first syllables,
and cutting off speech. The browser never plays its local microphone track back
through the speakers.

Follow the agent logs with:

```bash
docker compose logs -f agent
```

## Use the browser client

`index.html` uses the official `livekit-client` browser library, daisyUI, and
Tailwind's browser build. Serve the directory locally, for example:

```bash
npx serve .
```

Open the displayed URL, then generate a local development token in another
terminal:

```bash
lk token create \
  --api-key devkey \
  --api-secret secret \
  --join \
  --room demo-room \
  --identity web-user \
  --valid-for 24h
```

Paste the resulting token into the page and connect to `ws://localhost:7880`.
Enable the microphone or camera after connecting. The agent sends a greeting as
LiveKit data, which appears in the page log.

The official LiveKit UI components are React-based, so this page uses the
official browser client directly and provides its own plain HTML controls.
Never expose an API secret in a production frontend; generate tokens from a
backend instead.

Stop everything with:

```bash
docker compose down
```

## Notes

This intentionally uses LiveKit's `--dev` mode and fixed development
credentials. It is suitable for local experiments only. Before deploying,
replace dev mode with a real LiveKit configuration, generate strong API
credentials, and configure TLS, firewall rules, and the required media ports.
