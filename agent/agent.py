import logging

from livekit.agents import JobContext, WorkerOptions, cli


logging.basicConfig(level=logging.INFO)


async def entrypoint(ctx: JobContext):
    """Join a room and send one greeting to the first participant."""
    await ctx.connect()

    participant = await ctx.wait_for_participant()
    logging.info("Connected to participant %s", participant.identity)

    await ctx.room.local_participant.publish_data(
        b"Hello from the LiveKit agent!",
        reliable=True,
        destination_identities=[participant.identity],
        topic="agent-greeting",
    )


if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint))
