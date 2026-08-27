<script setup lang="ts">
import type { TranscriptionSegment } from 'livekit-client'

useHead({
  htmlAttrs: { lang: 'en' },
  link: [{ rel: 'icon', href: '/favicon.ico' }]
})

useSeoMeta({
  title: 'LiveKit Voice',
  description: 'Start a voice conversation with the LiveKit agent.'
})

const roomName = ref(`room`)
onMounted(() => roomName.value = randomRoomName())

function randomRoomName() {
  return `room-${crypto.randomUUID().slice(0, 8)}`
}

type LogEntry = {
  id: number
  name: string
  payload: string
  time: string
}

type ConversationEntry = LogEntry & {
  text: string
}

const events = ref<LogEntry[]>([])
const transcriptions = ref<ConversationEntry[]>([])
const messages = ref<ConversationEntry[]>([])
let entryId = 0

function formatPayload(value: unknown): string {
  try {
    if (value instanceof Uint8Array) {
      return new TextDecoder().decode(value)
    }

    const result = JSON.stringify(value, (_key, nestedValue) => {
      if (nestedValue instanceof Uint8Array) {
        return `[Uint8Array: ${nestedValue.byteLength} bytes]`
      }
      if (typeof nestedValue === 'bigint') {
        return nestedValue.toString()
      }
      return nestedValue
    }, 2)

    return result === undefined ? String(value) : result
  } catch {
    return String(value)
  }
}

function readableText(value: unknown): string {
  if (typeof value === 'string') return value
  if (value instanceof Uint8Array) return new TextDecoder().decode(value)
  if (Array.isArray(value)) return value.map(readableText).filter(Boolean).join(' ')

  if (value && typeof value === 'object') {
    const record = value as Record<string, unknown>
    for (const key of ['text', 'message', 'content', 'transcript', 'transcription']) {
      if (record[key] !== undefined) {
        const text = readableText(record[key])
        if (text) return text
      }
    }
  }

  return formatPayload(value)
}

function recordEvent(name: string, payload: unknown) {
  events.value.push({
    id: ++entryId,
    name,
    payload: formatPayload(payload),
    time: new Date().toLocaleTimeString()
  })
}

function recordTranscription(transcripts: TranscriptionSegment[]) {
  transcripts
    .filter(transcript => transcript.final)
    .forEach(transcript => {
      const entry = {
        id: ++entryId,
        text: readableText(transcript.text),
        name: 'transcription-received',
        payload: formatPayload(transcript),
        time: new Date().toLocaleTimeString()
      }
      transcriptions.value.push(entry)
      events.value.push({ ...entry })
    })

  transcripts.forEach(transcript => recordEvent('transcription-received', transcript))
}

function recordMessage(payload: unknown) {
  const entry = {
    id: ++entryId,
    text: readableText(payload),
    name: 'chat-message',
    payload: formatPayload(payload),
    time: new Date().toLocaleTimeString()
  }
  messages.value.push(entry)
  events.value.push({ ...entry })
}

function endChat(disconnect: () => void) {
  disconnect()
  tokenClear()
  events.value = []
  transcriptions.value = []
  messages.value = []
}

const {
  data: tokenData,
  error: tokenError,
  status: tokenStatus,
  execute: tokenExecute,
  clear: tokenClear
} = useAsyncData('token', () => {
  return $fetch('/api/room', {
    method: 'POST',
    body: { roomName: roomName.value.trim() }
  })
}, { immediate: false, server: false })
</script>

<template>
  <UApp>
    <UMain class="min-h-screen">
      <UContainer class="flex min-h-screen items-center justify-center py-6 sm:py-8">
        <UCard
          v-if="!tokenData?.token"
          class="w-full max-w-lg"
          :ui="{ body: 'flex flex-col gap-4' }"
        >
          <div class="text-center">
            <UIcon
              name="i-lucide-audio-waveform"
              class="size-8 text-primary"
            />
            <h1 class="mt-3 text-2xl font-semibold text-highlighted">
              LiveKit Voice
            </h1>
            <p class="mt-1 text-sm text-muted">
              Talk to the voice agent.
            </p>
          </div>

          <form
            class="space-y-4"
            @submit.prevent="tokenExecute"
          >
            <UFieldGroup class="w-full">
              <UInput
                v-model="roomName"
                class="flex-1"
                size="xl"
                icon="i-lucide-hash"
                placeholder="Room name"
                autocomplete="off"
                maxlength="128"
                autofocus
              />
              <UButton
                type="button"
                color="neutral"
                variant="outline"
                icon="i-lucide-dices"
                aria-label="Generate a random room name"
                @click="roomName = randomRoomName()"
              />
            </UFieldGroup>

            <UAlert
              v-if="tokenError"
              color="error"
              variant="subtle"
              :description="tokenError.message"
            />

            <UButton
              type="submit"
              size="xl"
              block
              icon="i-lucide-plus"
              :loading="tokenStatus === 'pending'"
              :disabled="!roomName.trim()"
            >
              Create room
            </UButton>
          </form>
        </UCard>

        <div
          v-else
          class="flex h-[calc(100vh-3rem)] min-h-0 w-full min-w-0 max-w-full flex-col gap-4 overflow-hidden sm:h-[calc(100vh-4rem)]"
        >
          <div class="flex items-center justify-between gap-4 px-1">
            <div>
              <p class="text-xs font-medium uppercase tracking-widest text-primary">
                Live conversation
              </p>
              <h1 class="text-xl font-semibold text-highlighted">
                {{ roomName }}
              </h1>
            </div>
            <UBadge
              color="success"
              variant="subtle"
              class="shrink-0"
            >
              <span class="size-1.5 rounded-full bg-success" />
              Connected
            </UBadge>
          </div>

          <VoiceRoom
            v-slot="{ toggleMicrophone, disconnect, isMicrophoneEnabled, roomState, connectionState }"
            :token="tokenData.token"
            @connected="recordEvent('connected', $event)"
            @reconnecting="recordEvent('reconnecting', $event)"
            @signal-reconnecting="recordEvent('signal-reconnecting', $event)"
            @reconnected="recordEvent('reconnected', $event)"
            @disconnected="recordEvent('disconnected', $event)"
            @connection-state-changed="recordEvent('connection-state-changed', $event)"
            @moved="recordEvent('moved', $event)"
            @media-devices-changed="recordEvent('media-devices-changed', $event)"
            @participant-connected="recordEvent('participant-connected', $event)"
            @participant-disconnected="recordEvent('participant-disconnected', $event)"
            @track-published="recordEvent('track-published', $event)"
            @track-subscribed="recordEvent('track-subscribed', $event)"
            @track-subscription-failed="recordEvent('track-subscription-failed', $event)"
            @track-unpublished="recordEvent('track-unpublished', $event)"
            @track-unsubscribed="recordEvent('track-unsubscribed', $event)"
            @track-muted="recordEvent('track-muted', $event)"
            @track-unmuted="recordEvent('track-unmuted', $event)"
            @local-track-published="recordEvent('local-track-published', $event)"
            @local-track-unpublished="recordEvent('local-track-unpublished', $event)"
            @local-audio-silence-detected="recordEvent('local-audio-silence-detected', $event)"
            @active-speakers-changed="recordEvent('active-speakers-changed', $event)"
            @participant-metadata-changed="recordEvent('participant-metadata-changed', $event)"
            @participant-name-changed="recordEvent('participant-name-changed', $event)"
            @participant-attributes-changed="recordEvent('participant-attributes-changed', $event)"
            @participant-active="recordEvent('participant-active', $event)"
            @room-metadata-changed="recordEvent('room-metadata-changed', $event)"
            @data-received="recordEvent('data-received', $event)"
            @sip-dtmf-received="recordEvent('sip-dtmf-received', $event)"
            @transcription-received="recordTranscription"
            @connection-quality-changed="recordEvent('connection-quality-changed', $event)"
            @track-stream-state-changed="recordEvent('track-stream-state-changed', $event)"
            @track-subscription-permission-changed="recordEvent('track-subscription-permission-changed', $event)"
            @track-subscription-status-changed="recordEvent('track-subscription-status-changed', $event)"
            @audio-playback-changed="recordEvent('audio-playback-changed', $event)"
            @video-playback-changed="recordEvent('video-playback-changed', $event)"
            @media-devices-error="recordEvent('media-devices-error', $event)"
            @participant-permissions-changed="recordEvent('participant-permissions-changed', $event)"
            @signal-connected="recordEvent('signal-connected', $event)"
            @recording-status-changed="recordEvent('recording-status-changed', $event)"
            @participant-encryption-status-changed="recordEvent('participant-encryption-status-changed', $event)"
            @encryption-error="recordEvent('encryption-error', $event)"
            @dc-buffer-status-changed="recordEvent('dc-buffer-status-changed', $event)"
            @active-device-changed="recordEvent('active-device-changed', $event)"
            @chat-message="recordMessage"
            @local-track-subscribed="recordEvent('local-track-subscribed', $event)"
            @metrics-received="recordEvent('metrics-received', $event)"
            @data-track-published="recordEvent('data-track-published', $event)"
            @data-track-unpublished="recordEvent('data-track-unpublished', $event)"
            @local-data-track-published="recordEvent('local-data-track-published', $event)"
            @local-data-track-unpublished="recordEvent('local-data-track-unpublished', $event)"
          >
            <UCard
              class="min-h-0 flex-1 flex h-full min-h-0 min-w-0 max-w-full flex-col overflow-hidden"
              :ui="{
                body: 'flex min-h-0 flex-1 flex-col p-0 sm:p-0',
                footer: 'border-t border-default p-4 sm:p-4'
              }"
            >
              <div class="grid min-h-0 min-w-0 flex-1 lg:grid-cols-2">
                <!-- events -->
                <section class="flex min-h-0 min-w-0 max-w-full flex-col overflow-y-auto p-4 lg:border-r lg:border-default lg:p-6">
                  <div class="mb-4 flex items-center justify-between gap-3">
                    <div>
                      <h2 class="font-semibold text-highlighted">
                        Events
                      </h2>
                      <p class="text-sm text-muted">
                        LiveKit room activity
                      </p>
                    </div>
                    <UBadge
                      color="neutral"
                      variant="subtle"
                    >
                      {{ events.length }}
                    </UBadge>
                  </div>

                  <div class="min-h-0 flex-1 overflow-y-auto pr-1">
                    <div
                      v-if="!events.length"
                      class="flex h-full min-h-32 items-center justify-center rounded-lg border border-dashed border-default p-6 text-center text-sm text-muted"
                    >
                      Waiting for room events...
                    </div>
                    <div
                      v-else
                      class="space-y-3"
                    >
                      <article
                        v-for="event in events"
                        :key="event.id"
                        class="rounded-lg border border-default bg-elevated/30 p-3"
                      >
                        <div class="flex items-center justify-between gap-3">
                          <span class="font-mono text-xs font-medium text-primary">
                            {{ event.name }}
                          </span>
                          <time class="shrink-0 text-[11px] text-dimmed">
                            {{ event.time }}
                          </time>
                        </div>
                        <pre class="mt-2 max-h-32 overflow-auto whitespace-pre-wrap break-words font-mono text-xs text-muted">{{ event.payload }}</pre>
                      </article>
                    </div>
                  </div>
                </section>

                <!-- conversation -->
                <section class="grid min-h-0 min-w-0 max-w-full grid-rows-2 divide-y divide-default border-t border-default lg:border-t-0">
                  <div class="flex min-h-0 flex-col p-4 lg:p-6">
                    <div class="mb-4 flex items-center justify-between gap-3">
                      <div>
                        <h2 class="font-semibold text-highlighted">
                          Transcriptions
                        </h2>
                        <p class="text-sm text-muted">
                          Speech recognized from the room
                        </p>
                      </div>
                      <UBadge
                        color="neutral"
                        variant="subtle"
                      >
                        {{ transcriptions.length }}
                      </UBadge>
                    </div>

                    <div class="min-h-0 flex-1 overflow-y-auto pr-1">
                      <div
                        v-if="!transcriptions.length"
                        class="flex h-full min-h-24 items-center justify-center rounded-lg border border-dashed border-default p-6 text-center text-sm text-muted"
                      >
                        Waiting for transcriptions...
                      </div>
                      <div
                        v-else
                        class="space-y-3"
                      >
                        <article
                          v-for="transcription in transcriptions"
                          :key="transcription.id"
                          class="rounded-lg bg-primary/5 p-3"
                        >
                          <div class="flex items-center justify-between gap-3 text-[11px] text-dimmed">
                            <span>{{ transcription.name }}</span>
                            <time>{{ transcription.time }}</time>
                          </div>
                          <p class="mt-2 text-sm text-highlighted">
                            {{ transcription.text }}
                          </p>
                        </article>
                      </div>
                    </div>
                  </div>

                  <div class="flex min-h-0 flex-col p-4 lg:p-6">
                    <div class="mb-4 flex items-center justify-between gap-3">
                      <div>
                        <h2 class="font-semibold text-highlighted">
                          Messages received
                        </h2>
                        <p class="text-sm text-muted">
                          Chat data from participants
                        </p>
                      </div>
                      <UBadge
                        color="neutral"
                        variant="subtle"
                      >
                        {{ messages.length }}
                      </UBadge>
                    </div>

                    <div class="min-h-0 flex-1 overflow-y-auto pr-1">
                      <div
                        v-if="!messages.length"
                        class="flex h-full min-h-24 items-center justify-center rounded-lg border border-dashed border-default p-6 text-center text-sm text-muted"
                      >
                        No messages received.
                      </div>
                      <div
                        v-else
                        class="space-y-3"
                      >
                        <article
                          v-for="message in messages"
                          :key="message.id"
                          class="rounded-lg bg-elevated/60 p-3"
                        >
                          <div class="flex items-center justify-between gap-3 text-[11px] text-dimmed">
                            <span>{{ message.name }}</span>
                            <time>{{ message.time }}</time>
                          </div>
                          <p class="mt-2 whitespace-pre-wrap break-words text-sm text-highlighted">
                            {{ message.text }}
                          </p>
                        </article>
                      </div>
                    </div>
                  </div>
                </section>
              </div>

              <template #footer>
                <div class="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                  <p class="text-sm text-muted">
                    {{ roomState === 'connected' ? 'Room is ready' : '' }}
                    {{ roomState === 'disconnected' ? 'Room is disconnected' : '' }}
                    {{ roomState === 'reconnecting' ? 'Room is reconnecting' : '' }}
                  </p>
                  <div class="flex gap-2">
                    <UButton
                      color="neutral"
                      variant="soft"
                      icon="i-lucide-mic"
                      :disabled="connectionState !== 'connected'"
                      :label="isMicrophoneEnabled ? 'Mute' : 'Unmute'"
                      @click="toggleMicrophone"
                    />
                    <UButton
                      color="error"
                      variant="soft"
                      icon="i-lucide-phone-off"
                      label="End"
                      @click="endChat(disconnect)"
                    />
                  </div>
                </div>
              </template>
            </UCard>
          </VoiceRoom>
        </div>
      </UContainer>
    </UMain>
  </UApp>
</template>
