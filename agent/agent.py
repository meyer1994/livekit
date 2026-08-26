from collections.abc import AsyncIterable

from livekit import agents, rtc
from livekit.agents import Agent, AgentSession, ModelSettings
from livekit.agents.telemetry import set_tracer_provider
from livekit.plugins import openai
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from phoenix.otel import register, using_session

from audio_trace import AudioTraceCapture


class Assistant(Agent):
    def __init__(self, audio_capture: AudioTraceCapture) -> None:
        super().__init__(
            instructions=(
                "You are a helpful and cheerful voice assistant. "
                "Be friendly, positive, and concise."
            )
        )
        self.audio_capture = audio_capture

    def stt_node(
        self,
        audio: AsyncIterable[rtc.AudioFrame],
        model_settings: ModelSettings,
    ):
        async def capture_input():
            async for frame in audio:
                self.audio_capture.capture_input(frame)
                yield frame

        return Agent.default.stt_node(self, capture_input(), model_settings)

    def tts_node(
        self,
        text: AsyncIterable[str],
        model_settings: ModelSettings,
    ):
        async def capture_output():
            async for frame in Agent.default.tts_node(self, text, model_settings):
                self.audio_capture.capture_output(frame)
                yield frame

        return capture_output()


def setup_tracing() -> TracerProvider:
    provider = register(
        project_name="livekit-agent",
        protocol="http/protobuf",
        batch=True,
        set_global_tracer_provider=False,
        auto_instrument=False,
        verbose=False,
        resource=Resource.create({"service.name": "livekit-agent"}),
    )
    set_tracer_provider(provider)
    return provider


server = agents.AgentServer()


@server.rtc_session()
async def entrypoint(ctx: agents.JobContext) -> None:
    trace_provider = setup_tracing()
    tracer = trace_provider.get_tracer("livekit-agent.audio")
    audio_capture = AudioTraceCapture()

    def export_audio_trace() -> None:
        audio_capture.export(tracer, ctx.room.name)
        trace_provider.force_flush()

    async def flush_traces() -> None:
        export_audio_trace()

    ctx.add_shutdown_callback(flush_traces)

    with using_session(ctx.room.name):
        session = AgentSession(
            stt=openai.STT(model="gpt-4o-mini-transcribe", use_realtime=True),
            llm=openai.LLM(model="gpt-4.1-mini"),
            tts=openai.TTS(model="gpt-4o-mini-tts", voice="marin"),
        )
        session.on("close", lambda _: export_audio_trace())

        await session.start(room=ctx.room, agent=Assistant(audio_capture))
        await session.generate_reply(
            instructions="Greet the user cheerfully and ask how you can help. 10 words or less."
        )


if __name__ == "__main__":
    agents.cli.run_app(server)
