# LiveKit Voice UI

A minimal Nuxt 4 and Nuxt UI client for the LiveKit voice agent.

## Setup

Copy the environment example and install dependencies:

```bash
cp .env.example .env
pnpm install
```

The development values in `.env.example` match the repository's local LiveKit server. For a remote server, set `NUXT_PUBLIC_LIVEKIT_URL` to its public `wss://` URL and provide the matching API key and secret.

Start LiveKit and the Python agent from the repository root:

```bash
export OPENAI_API_KEY=your-openai-api-key
docker compose up --build
```

Then run the Nuxt app from this directory:

```bash
pnpm dev
```

Open `http://localhost:3000`, enter a room name, and click **Start voice session**. The app requests a token from `POST /api/room`, connects to LiveKit, and publishes the microphone automatically.

## API

`POST /api/room`

```json
{
  "roomName": "demo-room"
}
```

returns:

```json
{
  "token": "<livekit-access-token>"
}
```

The endpoint intentionally has no authentication for now. The LiveKit API secret remains server-side.
