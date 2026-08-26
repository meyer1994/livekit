from collections.abc import AsyncIterable
from contextvars import ContextVar
import datetime as dt
import os

from livekit import agents
from livekit.agents import JobProcess, WorkerOptions, telemetry
from livekit.agents import Agent, AgentSession
from livekit.plugins import openai, silero
from opentelemetry.sdk.trace import TracerProvider, SpanProcessor
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.trace import Span
from opentelemetry.util.types import AttributeValue


provider = TracerProvider()
exporter = OTLPSpanExporter()
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

def prewarm(proc: JobProcess) -> None:
    proc.userdata["vad"] = silero.VAD.load()


async def entrypoint(ctx: agents.JobContext) -> None:
    session = AgentSession(
        stt=openai.STT(model="gpt-4o-mini-transcribe", use_realtime=True),
        llm=openai.LLM(model="gpt-4.1-mini"),
        tts=openai.TTS(model="gpt-4o-mini-tts", voice="marin"),
        vad=ctx.proc.userdata["vad"]  # given to us by the prewarm function
    )

    # set the tracer provider for the session
    telemetry.set_tracer_provider(
        tracer_provider=provider,
        metadata={
            "session.id": ctx.room.name or 'unknown' + '_' + dt.now().strftime("%Y-%m-%d %H:%M:%S")
        }
    )

    await session.start(room=ctx.room, agent=Assistant())
    await session.generate_reply(instructions="Greet the user cheerfully.", allow_interruptions=False)


if __name__ == "__main__":
    agents.cli.run_app(WorkerOptions(
        entrypoint_fnc=entrypoint,
        prewarm_fnc=prewarm,
    ))
