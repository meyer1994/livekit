<script setup lang="ts">
import type { Room as LiveKitRoom } from 'livekit-client'

useHead({
  htmlAttrs: { lang: 'en' },
  meta: [{ name: 'viewport', content: 'width=device-width, initial-scale=1' }],
  link: [{ rel: 'icon', href: '/favicon.ico' }]
})

useSeoMeta({
  title: 'LiveKit Voice',
  description: 'Start a voice conversation with the LiveKit agent.'
})

const config = useRuntimeConfig()
const toast = useToast()

const roomName = ref(`room-${crypto.randomUUID().slice(0, 8)}`)
const status = ref<'disconnected' | 'connecting' | 'connected' | 'disconnecting'>('disconnected')
const microphoneEnabled = ref(false)
const audioBlocked = ref(false)
const agentSpeaking = ref(false)
const errorMessage = ref('')
const audioHost = ref<HTMLDivElement | null>(null)
const transcripts = ref<Array<{ id: string, participant: string, text: string }>>([])

let activeRoom: LiveKitRoom | null = null

const isBusy = computed(() => status.value === 'connecting' || status.value === 'disconnecting')
const isConnected = computed(() => status.value === 'connected')
const statusLabel = computed(() => ({
  disconnected: 'Disconnected',
  connecting: 'Connecting',
  connected: 'Live',
  disconnecting: 'Disconnecting'
})[status.value])
const statusColor = computed<'neutral' | 'warning' | 'success'>(() => {
  if (status.value === 'connected') return 'success'
  if (isBusy.value) return 'warning'
  return 'neutral'
})

function describeError(error: unknown) {
  if (error instanceof Error) return error.message

  if (error && typeof error === 'object') {
    const fetchError = error as {
      data?: { message?: string, statusMessage?: string }
      message?: string
    }
    return fetchError.data?.statusMessage || fetchError.data?.message || fetchError.message || 'Something went wrong'
  }

  return 'Something went wrong'
}

function clearSessionState() {
  microphoneEnabled.value = false
  audioBlocked.value = false
  agentSpeaking.value = false
  audioHost.value?.replaceChildren()
}

async function startSession() {
  const requestedRoom = roomName.value.trim()
  if (!requestedRoom || isBusy.value || isConnected.value) return

  status.value = 'connecting'
  errorMessage.value = ''
  transcripts.value = []

  let voiceRoom: LiveKitRoom | null = null

  try {
    const [{ token }, livekit] = await Promise.all([
      $fetch<{ token: string }>('/api/room', {
        method: 'POST',
        body: { roomName: requestedRoom }
      }),
      import('livekit-client')
    ])

    voiceRoom = new livekit.Room({
      adaptiveStream: true,
      dynacast: true,
      audioCaptureDefaults: {
        echoCancellation: true,
        noiseSuppression: true,
        autoGainControl: false,
        channelCount: 1
      }
    })
    activeRoom = voiceRoom

    voiceRoom.on(livekit.RoomEvent.TrackSubscribed, (track) => {
      if (track.kind !== livekit.Track.Kind.Audio) return

      const element = track.attach()
      element.autoplay = true
      audioHost.value?.appendChild(element)
    })

    voiceRoom.on(livekit.RoomEvent.TrackUnsubscribed, (track) => {
      track.detach().forEach(element => element.remove())
    })

    voiceRoom.on(livekit.RoomEvent.AudioPlaybackStatusChanged, () => {
      audioBlocked.value = !voiceRoom?.canPlaybackAudio
    })

    voiceRoom.on(livekit.RoomEvent.ActiveSpeakersChanged, (speakers) => {
      agentSpeaking.value = speakers.some(participant => participant.identity !== voiceRoom?.localParticipant.identity)
    })

    voiceRoom.on(livekit.RoomEvent.DataReceived, (payload, participant, _kind, topic) => {
      if (topic !== 'stt-transcript') return

      try {
        const data = JSON.parse(new TextDecoder().decode(payload)) as {
          participant?: unknown
          text?: unknown
        }
        if (typeof data.text !== 'string') return

        transcripts.value.push({
          id: crypto.randomUUID(),
          participant: typeof data.participant === 'string' ? data.participant : participant?.identity || 'You',
          text: data.text
        })
        transcripts.value = transcripts.value.slice(-20)
      } catch {
        // Ignore malformed data messages from other room participants.
      }
    })

    voiceRoom.on(livekit.RoomEvent.Disconnected, () => {
      if (activeRoom !== voiceRoom) return
      activeRoom = null
      status.value = 'disconnected'
      clearSessionState()
    })

    await voiceRoom.connect(config.public.livekitUrl, token, { autoSubscribe: true })
    await voiceRoom.localParticipant.setMicrophoneEnabled(true)
    microphoneEnabled.value = true

    try {
      await voiceRoom.startAudio()
    } catch {
      audioBlocked.value = true
    }

    status.value = 'connected'
    toast.add({
      title: 'Voice session started',
      description: `Connected to ${requestedRoom}`,
      color: 'success'
    })
  } catch (error) {
    if (voiceRoom) await voiceRoom.disconnect()
    if (activeRoom === voiceRoom) activeRoom = null
    status.value = 'disconnected'
    clearSessionState()
    errorMessage.value = describeError(error)
  }
}

async function disconnect() {
  if (!activeRoom || isBusy.value) return

  status.value = 'disconnecting'
  const roomToClose = activeRoom
  activeRoom = null

  try {
    await roomToClose.disconnect()
  } finally {
    status.value = 'disconnected'
    clearSessionState()
  }
}

async function toggleMicrophone() {
  if (!activeRoom) return

  try {
    const enabled = !microphoneEnabled.value
    await activeRoom.localParticipant.setMicrophoneEnabled(enabled)
    microphoneEnabled.value = enabled
  } catch (error) {
    toast.add({
      title: 'Microphone error',
      description: describeError(error),
      color: 'error'
    })
  }
}

async function enableAudio() {
  if (!activeRoom) return

  try {
    await activeRoom.startAudio()
    audioBlocked.value = false
  } catch (error) {
    toast.add({
      title: 'Audio playback error',
      description: describeError(error),
      color: 'error'
    })
  }
}

onBeforeUnmount(() => {
  activeRoom?.disconnect()
  activeRoom = null
})
</script>

<template>
  <UApp>
    <header class="border-b border-default">
      <UContainer class="flex h-16 items-center justify-between">
        <div class="flex items-center gap-2 font-semibold">
          <UIcon
            name="i-lucide-audio-waveform"
            class="size-5 text-primary"
          />
          LiveKit Voice
        </div>
        <UColorModeButton />
      </UContainer>
    </header>

    <UMain>
      <UContainer class="flex min-h-[calc(100vh-4rem)] items-center justify-center py-12">
        <UCard class="w-full max-w-xl">
          <template #header>
            <div class="flex items-start justify-between gap-4">
              <div>
                <h1 class="text-2xl font-semibold text-highlighted">
                  Talk to the voice agent
                </h1>
                <p class="mt-1 text-sm text-muted">
                  Enter a room name and allow microphone access to begin.
                </p>
              </div>
              <UBadge
                :color="statusColor"
                variant="subtle"
              >
                {{ statusLabel }}
              </UBadge>
            </div>
          </template>

          <form
            v-if="!isConnected"
            class="space-y-5"
            @submit.prevent="startSession"
          >
            <UFormField
              label="Room name"
              name="roomName"
              required
            >
              <UInput
                v-model="roomName"
                class="w-full"
                size="xl"
                icon="i-lucide-hash"
                placeholder="demo-room"
                autocomplete="off"
                maxlength="128"
                :disabled="isBusy"
              />
            </UFormField>

            <UAlert
              v-if="errorMessage"
              color="error"
              variant="subtle"
              icon="i-lucide-circle-alert"
              title="Could not start the session"
              :description="errorMessage"
            />

            <UButton
              type="submit"
              size="xl"
              block
              icon="i-lucide-phone"
              :loading="status === 'connecting'"
              :disabled="!roomName.trim() || isBusy"
            >
              Start voice session
            </UButton>
          </form>

          <div
            v-else
            class="space-y-6"
          >
            <div class="flex flex-col items-center py-4 text-center">
              <div
                class="grid size-24 place-items-center rounded-full bg-primary/10 ring-8 ring-primary/5 transition-transform"
                :class="agentSpeaking ? 'scale-110' : ''"
              >
                <UIcon
                  :name="agentSpeaking ? 'i-lucide-audio-lines' : 'i-lucide-mic'"
                  class="size-10 text-primary"
                />
              </div>
              <p class="mt-5 text-lg font-medium text-highlighted">
                {{ agentSpeaking ? 'Agent is speaking' : 'Listening…' }}
              </p>
              <p class="text-sm text-muted">
                Room: {{ roomName.trim() }}
              </p>
            </div>

            <UAlert
              v-if="audioBlocked"
              color="warning"
              variant="subtle"
              icon="i-lucide-volume-x"
              title="Audio playback is blocked"
              description="Your browser needs permission to play the agent's voice."
              :actions="[{ label: 'Enable audio', onClick: enableAudio }]"
            />

            <div
              v-if="transcripts.length"
              class="space-y-2"
            >
              <p class="text-sm font-medium text-highlighted">
                Recent transcription
              </p>
              <div class="max-h-40 space-y-2 overflow-y-auto rounded-lg bg-elevated p-3">
                <p
                  v-for="transcript in transcripts"
                  :key="transcript.id"
                  class="text-sm"
                >
                  <span class="font-medium text-highlighted">{{ transcript.participant }}:</span>
                  <span class="text-muted"> {{ transcript.text }}</span>
                </p>
              </div>
            </div>

            <div class="grid grid-cols-2 gap-3">
              <UButton
                size="lg"
                block
                color="neutral"
                variant="soft"
                :icon="microphoneEnabled ? 'i-lucide-mic' : 'i-lucide-mic-off'"
                @click="toggleMicrophone"
              >
                {{ microphoneEnabled ? 'Mute' : 'Unmute' }}
              </UButton>
              <UButton
                size="lg"
                block
                color="error"
                variant="soft"
                icon="i-lucide-phone-off"
                @click="disconnect"
              >
                End session
              </UButton>
            </div>
          </div>
        </UCard>
      </UContainer>
    </UMain>

    <div
      ref="audioHost"
      class="sr-only"
      aria-hidden="true"
    />
  </UApp>
</template>
