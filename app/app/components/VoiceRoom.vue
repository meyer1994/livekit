<script setup lang="ts">
import type { ConnectionState, Room, RoomEventCallbacks } from 'livekit-client'

const props = defineProps<{ token: string }>()
const emit = defineEmits<{
  'connected': Parameters<RoomEventCallbacks['connected']>
  'reconnecting': Parameters<RoomEventCallbacks['reconnecting']>
  'signal-reconnecting': Parameters<RoomEventCallbacks['signalReconnecting']>
  'reconnected': Parameters<RoomEventCallbacks['reconnected']>
  'disconnected': Parameters<RoomEventCallbacks['disconnected']>
  'connection-state-changed': Parameters<RoomEventCallbacks['connectionStateChanged']>
  'moved': Parameters<RoomEventCallbacks['moved']>
  'media-devices-changed': Parameters<RoomEventCallbacks['mediaDevicesChanged']>
  'participant-connected': Parameters<RoomEventCallbacks['participantConnected']>
  'participant-disconnected': Parameters<RoomEventCallbacks['participantDisconnected']>
  'track-published': Parameters<RoomEventCallbacks['trackPublished']>
  'track-subscribed': Parameters<RoomEventCallbacks['trackSubscribed']>
  'track-subscription-failed': Parameters<RoomEventCallbacks['trackSubscriptionFailed']>
  'track-unpublished': Parameters<RoomEventCallbacks['trackUnpublished']>
  'track-unsubscribed': Parameters<RoomEventCallbacks['trackUnsubscribed']>
  'track-muted': Parameters<RoomEventCallbacks['trackMuted']>
  'track-unmuted': Parameters<RoomEventCallbacks['trackUnmuted']>
  'local-track-published': Parameters<RoomEventCallbacks['localTrackPublished']>
  'local-track-unpublished': Parameters<RoomEventCallbacks['localTrackUnpublished']>
  'local-audio-silence-detected': Parameters<RoomEventCallbacks['localAudioSilenceDetected']>
  'active-speakers-changed': Parameters<RoomEventCallbacks['activeSpeakersChanged']>
  'participant-metadata-changed': Parameters<RoomEventCallbacks['participantMetadataChanged']>
  'participant-name-changed': Parameters<RoomEventCallbacks['participantNameChanged']>
  'participant-attributes-changed': Parameters<RoomEventCallbacks['participantAttributesChanged']>
  'participant-active': Parameters<RoomEventCallbacks['participantActive']>
  'room-metadata-changed': Parameters<RoomEventCallbacks['roomMetadataChanged']>
  'data-received': Parameters<RoomEventCallbacks['dataReceived']>
  'sip-dtmf-received': Parameters<RoomEventCallbacks['sipDTMFReceived']>
  'transcription-received': Parameters<RoomEventCallbacks['transcriptionReceived']>
  'connection-quality-changed': Parameters<RoomEventCallbacks['connectionQualityChanged']>
  'track-stream-state-changed': Parameters<RoomEventCallbacks['trackStreamStateChanged']>
  'track-subscription-permission-changed': Parameters<RoomEventCallbacks['trackSubscriptionPermissionChanged']>
  'track-subscription-status-changed': Parameters<RoomEventCallbacks['trackSubscriptionStatusChanged']>
  'audio-playback-changed': Parameters<RoomEventCallbacks['audioPlaybackChanged']>
  'video-playback-changed': Parameters<RoomEventCallbacks['videoPlaybackChanged']>
  'media-devices-error': Parameters<RoomEventCallbacks['mediaDevicesError']>
  'participant-permissions-changed': Parameters<RoomEventCallbacks['participantPermissionsChanged']>
  'signal-connected': Parameters<RoomEventCallbacks['signalConnected']>
  'recording-status-changed': Parameters<RoomEventCallbacks['recordingStatusChanged']>
  'participant-encryption-status-changed': Parameters<RoomEventCallbacks['participantEncryptionStatusChanged']>
  'encryption-error': Parameters<RoomEventCallbacks['encryptionError']>
  'dc-buffer-status-changed': Parameters<RoomEventCallbacks['dcBufferStatusChanged']>
  'active-device-changed': Parameters<RoomEventCallbacks['activeDeviceChanged']>
  'chat-message': Parameters<RoomEventCallbacks['chatMessage']>
  'local-track-subscribed': Parameters<RoomEventCallbacks['localTrackSubscribed']>
  'metrics-received': Parameters<RoomEventCallbacks['metricsReceived']>
  'data-track-published': Parameters<RoomEventCallbacks['dataTrackPublished']>
  'data-track-unpublished': Parameters<RoomEventCallbacks['dataTrackUnpublished']>
  'local-data-track-published': Parameters<RoomEventCallbacks['localDataTrackPublished']>
  'local-data-track-unpublished': Parameters<RoomEventCallbacks['localDataTrackUnpublished']>
}>()

const config = useRuntimeConfig()
const audioHost = ref<HTMLDivElement | null>(null)

// the cast is to make vue ts happy, otherwise, it will think room is always null
const room = ref<Room | null>(null)

const connectionState = ref<ConnectionState | null>(null)
const isMicrophoneEnabled = ref(false) // by default, the microphone is muted

onMounted(async () => {
  const livekit = await import('livekit-client')
  const { RoomEvent } = livekit
  room.value = new livekit.Room({ adaptiveStream: true, dynacast: true })

  room.value.on(RoomEvent.Connected, (...args) => emit('connected', ...args))
  room.value.on(RoomEvent.Reconnecting, (...args) => emit('reconnecting', ...args))
  room.value.on(RoomEvent.SignalReconnecting, (...args) => emit('signal-reconnecting', ...args))
  room.value.on(RoomEvent.Reconnected, (...args) => emit('reconnected', ...args))
  room.value.on(RoomEvent.Disconnected, state => emit('disconnected', state))
  room.value.on(RoomEvent.ConnectionStateChanged, (state: ConnectionState) => {
    connectionState.value = state
    emit('connection-state-changed', state)
  })
  room.value.on(RoomEvent.Moved, (...args) => emit('moved', ...args))
  room.value.on(RoomEvent.MediaDevicesChanged, (...args) => emit('media-devices-changed', ...args))
  room.value.on(RoomEvent.ParticipantConnected, (...args) => emit('participant-connected', ...args))
  room.value.on(RoomEvent.ParticipantDisconnected, (...args) => emit('participant-disconnected', ...args))
  room.value.on(RoomEvent.TrackPublished, (...args) => emit('track-published', ...args))
  room.value.on(RoomEvent.TrackSubscribed, (track, ...args) => {
    if (track.kind === livekit.Track.Kind.Audio) audioHost.value?.appendChild(track.attach())
    emit('track-subscribed', track, ...args)
  })
  room.value.on(RoomEvent.TrackSubscriptionFailed, (...args) => emit('track-subscription-failed', ...args))
  room.value.on(RoomEvent.TrackUnpublished, (...args) => emit('track-unpublished', ...args))
  room.value.on(RoomEvent.TrackUnsubscribed, (track, ...args) => {
    track.detach().forEach(element => element.remove())
    emit('track-unsubscribed', track, ...args)
  })
  room.value.on(RoomEvent.TrackMuted, (...args) => emit('track-muted', ...args))
  room.value.on(RoomEvent.TrackUnmuted, (...args) => emit('track-unmuted', ...args))
  room.value.on(RoomEvent.LocalTrackPublished, (...args) => emit('local-track-published', ...args))
  room.value.on(RoomEvent.LocalTrackUnpublished, (...args) => emit('local-track-unpublished', ...args))
  room.value.on(RoomEvent.LocalAudioSilenceDetected, (...args) => emit('local-audio-silence-detected', ...args))
  room.value.on(RoomEvent.ActiveSpeakersChanged, (...args) => emit('active-speakers-changed', ...args))
  room.value.on(RoomEvent.ParticipantMetadataChanged, (...args) => emit('participant-metadata-changed', ...args))
  room.value.on(RoomEvent.ParticipantNameChanged, (...args) => emit('participant-name-changed', ...args))
  room.value.on(RoomEvent.ParticipantAttributesChanged, (...args) => emit('participant-attributes-changed', ...args))
  room.value.on(RoomEvent.ParticipantActive, (...args) => emit('participant-active', ...args))
  room.value.on(RoomEvent.RoomMetadataChanged, (...args) => emit('room-metadata-changed', ...args))
  room.value.on(RoomEvent.DataReceived, (...args) => emit('data-received', ...args))
  room.value.on(RoomEvent.SipDTMFReceived, (...args) => emit('sip-dtmf-received', ...args))
  room.value.on(RoomEvent.TranscriptionReceived, (...args) => emit('transcription-received', ...args))
  room.value.on(RoomEvent.ConnectionQualityChanged, (...args) => emit('connection-quality-changed', ...args))
  room.value.on(RoomEvent.TrackStreamStateChanged, (...args) => emit('track-stream-state-changed', ...args))
  room.value.on(RoomEvent.TrackSubscriptionPermissionChanged, (...args) => emit('track-subscription-permission-changed', ...args))
  room.value.on(RoomEvent.TrackSubscriptionStatusChanged, (...args) => emit('track-subscription-status-changed', ...args))
  room.value.on(RoomEvent.AudioPlaybackStatusChanged, (...args) => emit('audio-playback-changed', ...args))
  room.value.on(RoomEvent.VideoPlaybackStatusChanged, (...args) => emit('video-playback-changed', ...args))
  room.value.on(RoomEvent.MediaDevicesError, (...args) => emit('media-devices-error', ...args))
  room.value.on(RoomEvent.ParticipantPermissionsChanged, (...args) => emit('participant-permissions-changed', ...args))
  room.value.on(RoomEvent.SignalConnected, (...args) => emit('signal-connected', ...args))
  room.value.on(RoomEvent.RecordingStatusChanged, (...args) => emit('recording-status-changed', ...args))
  room.value.on(RoomEvent.ParticipantEncryptionStatusChanged, (...args) => emit('participant-encryption-status-changed', ...args))
  room.value.on(RoomEvent.EncryptionError, (...args) => emit('encryption-error', ...args))
  room.value.on(RoomEvent.DCBufferStatusChanged, (...args) => emit('dc-buffer-status-changed', ...args))
  room.value.on(RoomEvent.ActiveDeviceChanged, (...args) => emit('active-device-changed', ...args))
  room.value.on(RoomEvent.ChatMessage, (...args) => emit('chat-message', ...args))
  room.value.on(RoomEvent.LocalTrackSubscribed, (...args) => emit('local-track-subscribed', ...args))
  room.value.on(RoomEvent.MetricsReceived, (...args) => emit('metrics-received', ...args))
  room.value.on(RoomEvent.DataTrackPublished, (...args) => emit('data-track-published', ...args))
  room.value.on(RoomEvent.DataTrackUnpublished, (...args) => emit('data-track-unpublished', ...args))
  room.value.on(RoomEvent.LocalDataTrackPublished, (...args) => emit('local-data-track-published', ...args))
  room.value.on(RoomEvent.LocalDataTrackUnpublished, (...args) => emit('local-data-track-unpublished', ...args))

  await room.value.connect(config.public.livekitUrl, props.token)
  await room.value.localParticipant.setMicrophoneEnabled(isMicrophoneEnabled.value)
  await room.value.startAudio()
})

onBeforeUnmount(async () => await room.value?.disconnect())

defineSlots<{
  default: (props: {
    startAudio: () => Promise<void> | void
    toggleMicrophone: () => Promise<void> | void
    disconnect: () => Promise<void> | void
    isMicrophoneEnabled: boolean
    roomState: ConnectionState | null
    connectionState: ConnectionState | null
  }) => VNode
}>()
</script>

<template>
  <slot
    :start-audio="async () => await room?.startAudio()"
    :toggle-microphone="async () => {
      await room?.localParticipant.setMicrophoneEnabled(!isMicrophoneEnabled)
      isMicrophoneEnabled = !isMicrophoneEnabled
    }"
    :disconnect="async () => await room?.disconnect()"
    :is-microphone-enabled="isMicrophoneEnabled"
    :room-state="connectionState"
    :connection-state="connectionState"
  />
  <div
    ref="audioHost"
    class="sr-only"
    aria-hidden="true"
  />
</template>
