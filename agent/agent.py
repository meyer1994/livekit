from collections.abc import AsyncIterable
from contextvars import ContextVar

from livekit import agents
from livekit.agents import telemetry
from livekit.agents import Agent, AgentSession
from livekit.plugins import openai
from opentelemetry.sdk.trace import TracerProvider, SpanProcessor
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.trace import Span


provider = TracerProvider()
exporter = OTLPSpanExporter(endpoint='http://phoenix:6006/v1/traces')
processor = BatchSpanProcessor(exporter)
provider.add_span_processor(processor)
telemetry.set_tracer_provider(provider)


class Assistant(Agent):
    def __init__(self) -> None:
        super().__init__(
            instructions=(
                "You are a helpful and cheerful voice assistant. "
                "Be friendly, positive, and concise."
            )
        )

server = agents.AgentServer()


@server.rtc_session()
async def entrypoint(ctx: agents.JobContext) -> None:
    session = AgentSession(
        stt=openai.STT(model="gpt-4o-mini-transcribe", use_realtime=True),
        llm=openai.LLM(model="gpt-4.1-mini"),
        tts=openai.TTS(model="gpt-4o-mini-tts", voice="marin"),
    )

    await session.start(room=ctx.room, agent=Assistant())
    await session.generate_reply(instructions="Greet the user cheerfully.", allow_interruptions=False)


if __name__ == "__main__":
    agents.cli.run_app(server)
