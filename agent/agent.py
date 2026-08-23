import asyncio
import logging

from livekit.agents import Agent, AgentSession, JobContext, WorkerOptions, cli, room_io
from livekit.plugins import openai, silero


logging.basicConfig(level=logging.INFO)


async def entrypoint(ctx: JobContext):
    """Transcribe speech and send the final transcript back as data."""
    session = AgentSession(
        stt=openai.STT(model="gpt-4o-mini-transcribe"),
        vad=silero.VAD.load(
            activation_threshold=0.65,
            min_speech_duration=0.15,
            min_silence_duration=0.8,
        ),
    )

    shutdown = asyncio.Event()
    participant = None

    async def echo_transcript(transcript: str):
        if participant is None:
            return
        message = f"Echo: {transcript}".encode()
        await ctx.room.local_participant.publish_data(
            message,
            reliable=True,
            destination_identities=[participant.identity],
            topic="stt-echo",
        )

    @session.on("user_input_transcribed")
    def on_transcript(event):
        if event.is_final and event.transcript.strip():
            logging.info("Transcript: %s", event.transcript)
            asyncio.create_task(echo_transcript(event.transcript))

    await session.start(
        room=ctx.room,
        agent=Agent(instructions="Transcribe the user's speech."),
        room_options=room_io.RoomOptions(
            audio_input=True,
            audio_output=False,
        ),
    )
    await ctx.connect()

    participant = await ctx.wait_for_participant()
    logging.info("Connected to participant %s", participant.identity)
    ctx.room.on("disconnected", lambda *_: shutdown.set())

    await ctx.room.local_participant.publish_data(
        b"Hello from the LiveKit agent!",
        reliable=True,
        destination_identities=[participant.identity],
        topic="agent-greeting",
    )

    try:
        await shutdown.wait()
    finally:
        await session.aclose()


if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint))
