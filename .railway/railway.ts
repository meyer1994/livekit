import {
  defineRailway,
  github,
  image,
  preserve,
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
      LIVEKIT_API_KEY: "devkey",
      LIVEKIT_API_SECRET: "secret",
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
      LIVEKIT_URL: "ws://${{livekit.RAILWAY_PRIVATE_DOMAIN}}:7880",
      LIVEKIT_API_KEY: "devkey",
      LIVEKIT_API_SECRET: "secret",
      OPENAI_API_KEY: preserve(),
      OTEL_EXPORTER_OTLP_ENDPOINT:
        "http://${{phoenix.RAILWAY_PRIVATE_DOMAIN}}:6006",
      OTEL_EXPORTER_OTLP_PROTOCOL: "http/protobuf",
      OTEL_SERVICE_NAME: "livekit-agent",
    },
  });

  const app = service("app", {
    source: github(repository, { rootDirectory: "app" }),
    env: {
      NUXT_LIVEKIT_API_KEY: "devkey",
      NUXT_LIVEKIT_API_SECRET: "secret",
      NUXT_PUBLIC_LIVEKIT_URL:
        "ws://${{livekit.RAILWAY_TCP_PROXY_DOMAIN}}:${{livekit.RAILWAY_TCP_PROXY_PORT}}",
    },
  });

  return project("livekit", {
    resources: [livekit, phoenix, agent, app],
  });
});
