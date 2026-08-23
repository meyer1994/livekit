import asyncio
import json
import logging
import time

from livekit import rtc
from livekit.agents import Agent, AgentSession, AutoSubscribe, JobContext, WorkerOptions, cli, room_io
from livekit.plugins import openai
from openai.types import realtime


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("room-agent")


class RoomAgent(Agent):
    """Thin room abstraction: one agent session and one participant per room."""

    def __init__(self, *, ctx: JobContext, session: AgentSession):
        super().__init__(instructions="Transcribe and echo the participant's speech.")
        self.ctx = ctx
        self._agent_session = session
        self.participant: rtc.RemoteParticipant | None = None
        self.shutdown = asyncio.Event()
        self._tasks: set[asyncio.Task] = set()

        session.on("user_input_transcribed", self._on_transcript)
        session.on("error", self._on_error)
        session.on("agent_state_changed", self._on_agent_state_changed)
        session.on("user_state_changed", self._on_user_state_changed)

    def _spawn(self, coro):
        task = asyncio.create_task(coro)
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)
        return task

    async def _publish_debug(self, event: str, **details):
        payload = {
            "event": event,
            "timestamp": time.time(),
            "details": {key: str(value) for key, value in details.items()},
        }
        try:
            await self.ctx.room.local_participant.publish_data(
                json.dumps(payload).encode(),
                reliable=True,
                topic="agent-debug",
            )
        except Exception:
            logger.exception("failed to publish debug event %s", event)

    async def _publish_transcript(self, transcript: str):
        participant = self.participant
        if participant is None:
            return

        payload = {
            "participant": participant.identity,
            "text": transcript,
            "timestamp": time.time(),
        }
        try:
            await self.ctx.room.local_participant.publish_data(
                json.dumps(payload).encode(),
                reliable=True,
                topic="stt-transcript",
            )
        except Exception:
            logger.exception("failed to publish transcript")

    async def _handle_transcript(self, transcript: str):
        logger.info("realtime transcript: %s", transcript)
        await self._publish_transcript(transcript)
        await self._publish_debug("transcript_received", characters=len(transcript))

    def _on_transcript(self, event):
        logger.info("transcription final=%s text=%r", event.is_final, event.transcript)
        if event.is_final and event.transcript.strip():
            self._spawn(self._handle_transcript(event.transcript))

    def _on_error(self, event):
        logger.error("session error: %s", event)
        self._spawn(
            self._publish_debug(
                "session_error",
                source=type(event.source).__name__,
                error=event.error,
            )
        )

    def _on_agent_state_changed(self, event):
        self._spawn(self._publish_debug("agent_state_changed", state=event.new_state))

    def _on_user_state_changed(self, event):
        self._spawn(self._publish_debug("user_state_changed", state=event.new_state))

    def _on_track_subscribed(self, track, publication, participant):
        self._spawn(
            self._publish_debug(
                "track_subscribed",
                participant=participant.identity,
                kind=track.kind,
                source=publication.source,
            )
        )

    def _on_track_unsubscribed(self, track, publication, participant):
        self._spawn(
            self._publish_debug(
                "track_unsubscribed",
                participant=participant.identity,
                kind=track.kind,
                source=publication.source,
            )
        )

    async def start(self):
        await self.ctx.connect(auto_subscribe=AutoSubscribe.AUDIO_ONLY)
        self.participant = await self.ctx.wait_for_participant()
        identity = self.participant.identity
        logger.info("connected to participant %s", identity)
        self._spawn(self._publish_debug("participant_connected", participant=identity))

        self.ctx.room.on("track_subscribed", self._on_track_subscribed)
        self.ctx.room.on("track_unsubscribed", self._on_track_unsubscribed)
        self.ctx.room.on(
            "active_speakers_changed",
            lambda speakers: self._spawn(
                self._publish_debug(
                    "active_speakers_changed",
                    participants=[speaker.identity for speaker in speakers],
                )
            ),
        )
        self.ctx.room.on(
            "connection_state_changed",
            lambda state: self._spawn(self._publish_debug("connection_state_changed", state=state)),
        )
        self.ctx.room.on("participant_disconnected", lambda *_: self.shutdown.set())
        self.ctx.room.on("disconnected", lambda *_: self.shutdown.set())

        logger.info("starting realtime session")
        self._spawn(self._publish_debug("realtime_session_starting", participant=identity))
        try:
            await self._agent_session.start(
                room=self.ctx.room,
                agent=self,
                room_options=room_io.RoomOptions(
                    participant_identity=identity,
                    close_on_disconnect=True,
                    delete_room_on_close=True,
                    audio_input=True,
                    audio_output=room_io.AudioOutputOptions(track_name="agent_audio"),
                    text_output=False,
                    text_input=False,
                ),
            )
            logger.info("realtime session started")
        except Exception as error:
            logger.exception("failed to start realtime session")
            self._spawn(self._publish_debug("realtime_session_error", error=error))
            raise

        self._spawn(self._publish_debug("room_ready", room=self.ctx.room.name, participant=identity))
        self._spawn(self._greet())
        await self.shutdown.wait()

    async def _greet(self):
        try:
            await self._agent_session.generate_reply(
                instructions="Greet the participant briefly and say you are ready to echo them."
            )
        except Exception:
            logger.exception("failed to greet participant")
            await self._publish_debug("greeting_error")

    async def close(self):
        self.shutdown.set()
        for task in list(self._tasks):
            task.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks.clear()
        await self._agent_session.aclose()


def new_session() -> AgentSession:
    return AgentSession(
        llm=openai.realtime.RealtimeModel(
            model="gpt-realtime-2.1-mini",
            voice="marin",
            input_audio_transcription=realtime.AudioTranscription(
                model="gpt-4o-transcribe",
            ),
            turn_detection=realtime.realtime_audio_input_turn_detection.SemanticVad(
                type="semantic_vad",
                eagerness="medium",
                create_response=True,
                interrupt_response=True,
            ),
        ),
    )


async def entrypoint(ctx: JobContext):
    agent = RoomAgent(ctx=ctx, session=new_session())
    try:
        await agent.start()
    finally:
        await agent.close()


if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint))
