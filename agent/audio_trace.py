import base64
import io
import os
import wave

from livekit import rtc
from openinference.semconv.trace import (
    AudioAttributes,
    OpenInferenceSpanKindValues,
    SpanAttributes,
)
from phoenix.otel import using_session


class _PCMBuffer:
    def __init__(self, max_base64_length: int) -> None:
        # Leave room for the WAV header and data-URI prefix.
        self._max_pcm_bytes = max(0, (max_base64_length - 64) * 3 // 4)
        self._data = bytearray()
        self.sample_rate = 0
        self.num_channels = 0
        self.truncated = False

    def append(self, frame: rtc.AudioFrame) -> None:
        if not self.sample_rate:
            self.sample_rate = frame.sample_rate
            self.num_channels = frame.num_channels

        if (
            frame.sample_rate != self.sample_rate
            or frame.num_channels != self.num_channels
        ):
            return

        remaining = self._max_pcm_bytes - len(self._data)
        if remaining <= 0:
            self.truncated = True
            return

        pcm = bytes(frame.data)
        self._data.extend(pcm[:remaining])
        self.truncated = self.truncated or len(pcm) > remaining

    @property
    def duration(self) -> float:
        bytes_per_second = self.sample_rate * self.num_channels * 2
        return len(self._data) / bytes_per_second if bytes_per_second else 0.0

    def wav_bytes(self) -> bytes | None:
        if not self._data:
            return None

        output = io.BytesIO()
        with wave.open(output, "wb") as wav:
            wav.setnchannels(self.num_channels)
            wav.setsampwidth(2)
            wav.setframerate(self.sample_rate)
            wav.writeframes(self._data)
        return output.getvalue()

    def data_uri(self) -> str | None:
        wav = self.wav_bytes()
        if wav is None:
            return None
        return f"data:audio/wav;base64,{base64.b64encode(wav).decode('ascii')}"


class AudioTraceCapture:
    def __init__(self) -> None:
        max_length = int(os.getenv("OPENINFERENCE_BASE64_AUDIO_MAX_LENGTH", "2000000"))
        self.input = _PCMBuffer(max_length)
        self.output = _PCMBuffer(max_length)
        self._exported = False

    def capture_input(self, frame: rtc.AudioFrame) -> None:
        self.input.append(frame)

    def capture_output(self, frame: rtc.AudioFrame) -> None:
        self.output.append(frame)

    @staticmethod
    def _set_audio_attributes(span, url: str, audio: _PCMBuffer) -> None:
        span.set_attribute(
            SpanAttributes.OPENINFERENCE_SPAN_KIND,
            OpenInferenceSpanKindValues.LLM.value,
        )
        span.set_attribute(AudioAttributes.AUDIO_URL, url)
        span.set_attribute(AudioAttributes.AUDIO_MIME_TYPE, "audio/wav")
        span.set_attribute("audio.duration", audio.duration)
        span.set_attribute("audio.truncated", audio.truncated)

    def export(self, tracer, room_name: str) -> None:
        if self._exported:
            return

        input_url = self.input.data_uri()
        output_url = self.output.data_uri()
        if input_url is None and output_url is None:
            return

        self._exported = True
        with using_session(room_name):
            with tracer.start_as_current_span("voice.session.audio") as session_span:
                session_span.set_attribute(
                    SpanAttributes.OPENINFERENCE_SPAN_KIND,
                    OpenInferenceSpanKindValues.LLM.value,
                )

                if input_url is not None:
                    session_span.set_attribute("input.audio.url", input_url)
                    session_span.set_attribute("input.audio.mime_type", "audio/wav")
                    with tracer.start_as_current_span("voice.input.audio") as input_span:
                        self._set_audio_attributes(input_span, input_url, self.input)
                        input_span.set_attribute("voice.direction", "input")

                if output_url is not None:
                    session_span.set_attribute("output.audio.url", output_url)
                    session_span.set_attribute("output.audio.mime_type", "audio/wav")
                    with tracer.start_as_current_span("voice.output.audio") as output_span:
                        self._set_audio_attributes(output_span, output_url, self.output)
                        output_span.set_attribute("voice.direction", "output")
