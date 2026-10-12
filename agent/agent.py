from livekit import agents
from livekit.agents import (
    Agent,
    AgentSession,
    JobProcess,
    WorkerOptions,
    mcp,
    telemetry,
)
from livekit.plugins import openai, silero
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

provider = TracerProvider()
exporter = OTLPSpanExporter()
processor = BatchSpanProcessor(exporter)
provider.add_span_processor(processor)


class PrefixedMCPServerHTTP(mcp.MCPServerHTTP):
    """Prefixes tool names so servers exposing the same tool name can share an agent."""

    def __init__(self, url: str, *, prefix: str, **kwargs) -> None:
        super().__init__(url, **kwargs)
        self._prefix = prefix

    async def _list_raw_tools(self):
        tools = await super()._list_raw_tools()
        return [
            tool.model_copy(update={"name": f"{self._prefix}{tool.name}"})
            for tool in tools
        ]

    async def _call_tool(self, name, arguments, *, progress_callback=None):
        return await super()._call_tool(
            name.removeprefix(self._prefix),
            arguments,
            progress_callback=progress_callback,
        )


class Assistant(Agent):
    def __init__(self) -> None:
        super().__init__(
            instructions=(
                "You are a helpful and cheerful voice assistant. "
                "Be friendly, positive, and concise."
            ),
            tools=[
                mcp.MCPToolset(
                    id="nuxt",
                    mcp_server=PrefixedMCPServerHTTP(
                        prefix="nuxt_",
                        url="https://nuxt.com/mcp",
                    ),
                ),
                mcp.MCPToolset(
                    id="nuxt-ui",
                    mcp_server=PrefixedMCPServerHTTP(
                        prefix="nuxt_ui_",
                        url="https://ui.nuxt.com/mcp",
                    ),
                ),
            ],
        )


def prewarm(proc: JobProcess) -> None:
    proc.userdata["vad"] = silero.VAD.load()


async def entrypoint(ctx: agents.JobContext) -> None:
    session = AgentSession(
        stt=openai.STT(model="gpt-4o-mini-transcribe"),
        llm=openai.LLM(model="gpt-4.1-mini"),
        tts=openai.TTS(model="gpt-4o-mini-tts", voice="marin"),
        vad=ctx.proc.userdata["vad"],  # given to us by the prewarm function
    )

    # set the tracer provider for the session
    telemetry.set_tracer_provider(
        tracer_provider=provider,
        metadata={"session.id": ctx.room.name or "NONE"},
    )

    await session.start(
        room=ctx.room,
        agent=Assistant(),
    )
    await session.generate_reply(
        instructions="Greet the user cheerfully.",
        allow_interruptions=False,
    )


if __name__ == "__main__":
    agents.cli.run_app(
        WorkerOptions(
            entrypoint_fnc=entrypoint,
            prewarm_fnc=prewarm,
        )
    )
