import { AccessToken } from 'livekit-server-sdk'

interface RoomRequest {
  roomName?: unknown
}

export default defineEventHandler(async (event) => {
  const body = await readBody<RoomRequest>(event)
  const roomName = typeof body?.roomName === 'string' ? body.roomName.trim() : ''

  if (!roomName) {
    throw createError({
      statusCode: 400,
      statusMessage: 'Room name is required'
    })
  }

  if (roomName.length > 128) {
    throw createError({
      statusCode: 400,
      statusMessage: 'Room name must be 128 characters or fewer'
    })
  }

  const config = useRuntimeConfig(event)

  if (!config.livekitApiKey || !config.livekitApiSecret) {
    throw createError({
      statusCode: 500,
      statusMessage: 'LiveKit server credentials are not configured'
    })
  }

  const accessToken = new AccessToken(
    config.livekitApiKey,
    config.livekitApiSecret,
    {
      identity: `voice-user-${crypto.randomUUID()}`,
      ttl: '1h'
    }
  )

  accessToken.addGrant({
    room: roomName,
    roomJoin: true,
    canPublish: true,
    canSubscribe: true
  })

  return {
    token: await accessToken.toJwt()
  }
})
