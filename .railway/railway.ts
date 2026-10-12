import {
  defineRailway,
  github,
  image,
  project,
  service,
} from "railway/iac";

const repository = "meyer1994/livekit";

export default defineRailway(() => {
  const livekit = service("livekit", {
    source: image("livekit/livekit-server:latest"),
    start: "exec /livekit-server --dev --bind 0.0.0.0",
    // Railway supports TCP proxies, but not Docker Compose's UDP mapping.
    tcp: [7880, 7881],
    env: {
      LIVEKIT_API_KEY: {
        value: "devkey",
        description: "livekit api key shared by the server, agent, and web client.",
      },
      LIVEKIT_API_SECRET: {
        value: "secret",
        description: "livekit api secret shared by the server, agent, and web client.",
      },
    },
  });

  const phoenix = service("phoenix", {
    source: image("arizephoenix/phoenix:latest"),
    // 6006 serves the Phoenix UI and OTLP/HTTP; 4317 serves OTLP/gRPC.
    tcp: [6006, 4317],
  });

  const agent = service("agent", {
    source: github(repository, { rootDirectory: "agent" }),
    env: {
      LIVEKIT_URL: {
        value: "ws://${{livekit.RAILWAY_PRIVATE_DOMAIN}}:7880",
        description: "private websocket URL used by the agent to reach the livekit server.",
      },
      LIVEKIT_API_KEY: {
        value: "devkey",
        description: "livekit api key matching the livekit server configuration.",
      },
      LIVEKIT_API_SECRET: {
        value: "secret",
        description: "livekit api secret matching the livekit server configuration.",
      },
      OPENAI_API_KEY: {
        preserveExisting: true,
        description: "openai api key used by the agent for speech, language, and voice models.",
      },
      OTEL_EXPORTER_OTLP_ENDPOINT: {
        value: "http://${{phoenix.RAILWAY_PRIVATE_DOMAIN}}:6006",
        description: "private phoenix otlp/http endpoint used to export agent traces.",
      },
      OTEL_EXPORTER_OTLP_PROTOCOL: {
        value: "http/protobuf",
        description: "otlp protocol used by the agent trace exporter.",
      },
      OTEL_SERVICE_NAME: {
        value: "livekit-agent",
        description: "service name shown for agent traces in phoenix.",
      },
    },
  });

  const app = service("app", {
    source: github(repository, { rootDirectory: "app" }),
    env: {
      NUXT_LIVEKIT_API_KEY: {
        value: "devkey",
        description: "livekit api key used by the web application token endpoint.",
      },
      NUXT_LIVEKIT_API_SECRET: {
        value: "secret",
        description: "livekit api secret used by the web application token endpoint.",
      },
      NUXT_PUBLIC_LIVEKIT_URL: {
        value:
          "ws://${{livekit.RAILWAY_TCP_PROXY_DOMAIN}}:${{livekit.RAILWAY_TCP_PROXY_PORT}}",
        description: "public websocket URL used by browsers to connect to livekit.",
      },
    },
  });

  return project("livekit", {
    resources: [livekit, phoenix, agent, app],
  });
});
