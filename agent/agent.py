import asyncio
import logging

from livekit.agents import Agent, AgentSession, JobContext, WorkerOptions, cli, room_io
from livekit.plugins import openai, silero


logging.basicConfig(level=logging.INFO)


async def entrypoint(ctx: JobContext):
    """Transcribe speech and send the final transcript back as data."""
    logging.info("Starting agent")
    session = AgentSession(
        stt=openai.STT(model="gpt-4o-mini-transcribe"),
        tts=openai.TTS(
            model="gpt-4o-mini-tts",
            voice="ash",
            instructions="Speak clearly and conversationally.",
        ),
        vad=silero.VAD.load(
            activation_threshold=0.55,
            min_speech_duration=0.15,
            min_silence_duration=0.5,
            prefix_padding_duration=0.6,
        ),
    )

    participant = None
    shutdown = asyncio.Event()

    async def echo_transcript(transcript: str):
        if participant is None:
            return

        async def publish_echo():
            await ctx.room.local_participant.publish_data(
                f"Echo: {transcript}".encode(),
                reliable=True,
                destination_identities=[participant.identity],
                topic="stt-echo",
            )

        async def speak_echo():
            logging.info("Speaking: %s", transcript)
            speech = session.say(
                f"{transcript}",
                allow_interruptions=False,
                add_to_chat_ctx=False,
            )
            await speech
            logging.info("Done speaking")

        results = await asyncio.gather(
            publish_echo(),
            speak_echo(),
            return_exceptions=True,
        )
        for name, result in zip(("publish", "speak"), results):
            if isinstance(result, Exception):
                logging.error("Failed to %s transcript echo: %s", name, result, exc_info=result)

    @session.on("user_input_transcribed")
    def on_transcript(event):
        logging.info(
            "Transcription event final=%s speaker=%s text=%r",
            event.is_final,
            event.speaker_id,
            event.transcript,
        )
        if event.is_final and event.transcript.strip():
            asyncio.create_task(echo_transcript(event.transcript))

    @session.on("error")
    def on_error(event):
        logging.error("Session error: %s", event)

    logging.info("Starting session")
    await session.start(
        room=ctx.room,
        agent=Agent(instructions="Transcribe the user's speech."),
        room_options=room_io.RoomOptions(
            audio_input=True,
            audio_output=True,
            text_output=False,
            text_input=False,
        ),
    )
    await ctx.connect()

    participant = await ctx.wait_for_participant()
    logging.info("Connected to participant %s", participant.identity)
    ctx.room.on("disconnected", lambda *_: shutdown.set())

    logging.info("Publishing and speaking greeting")
    await ctx.room.local_participant.publish_data(
        b"Hello from the LiveKit agent!",
        reliable=True,
        destination_identities=[participant.identity],
        topic="agent-greeting",
    )
    await session.say(
        "Hello, I am ready. Say something and I will echo it.",
        allow_interruptions=False,
        add_to_chat_ctx=False,
    )

    await shutdown.wait()
    logging.info("Disconnecting")
    await session.aclose()



if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint))
