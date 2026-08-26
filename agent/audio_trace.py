import base64
import io
import os
import threading
import wave
from collections import deque
from collections.abc import Sequence

from livekit import rtc
from openinference.semconv.trace import OpenInferenceSpanKindValues, SpanAttributes
from opentelemetry.sdk.trace import ReadableSpan
from opentelemetry.sdk.trace.export import SpanExportResult, SpanExporter


class _PCMBuffer:
    def __init__(self, max_base64_length: int) -> None:
        # Leave room for the WAV header and data-URI prefix.
        self._max_pcm_bytes = max(0, (max_base64_length - 64) * 3 // 4)
        self._data = bytearray()
        self.sample_rate = 0
        self.num_channels = 0
        self.truncated = False

    def append(self, frame: rtc.AudioFrame) -> None:
        self.append_pcm(bytes(frame.data), frame.sample_rate, frame.num_channels)

    def append_pcm(self, pcm: bytes, sample_rate: int, num_channels: int) -> None:
        if not self.sample_rate:
            self.sample_rate = sample_rate
            self.num_channels = num_channels

        if sample_rate != self.sample_rate or num_channels != self.num_channels:
            return

        remaining = self._max_pcm_bytes - len(self._data)
        if remaining <= 0:
            self.truncated = True
            return

        self._data.extend(pcm[:remaining])
        self.truncated = self.truncated or len(pcm) > remaining

    @property
    def duration(self) -> float:
        bytes_per_second = self.sample_rate * self.num_channels * 2
        return len(self._data) / bytes_per_second if bytes_per_second else 0.0

    def attributes(self, prefix: str) -> dict[str, str | float | bool]:
        if not self._data:
            return {}

        output = io.BytesIO()
        with wave.open(output, "wb") as wav:
            wav.setnchannels(self.num_channels)
            wav.setsampwidth(2)
            wav.setframerate(self.sample_rate)
            wav.writeframes(self._data)

        encoded = base64.b64encode(output.getvalue()).decode("ascii")
        return {
            f"{prefix}.audio.url": f"data:audio/wav;base64,{encoded}",
            f"{prefix}.audio.mime_type": "audio/wav",
            f"{prefix}.audio.duration": self.duration,
            f"{prefix}.audio.truncated": self.truncated,
        }


class AudioTraceCapture:
    """Collect audio and associate it with LiveKit's existing span IDs."""

    def __init__(self) -> None:
        self._max_length = int(
            os.getenv("OPENINFERENCE_BASE64_AUDIO_MAX_LENGTH", "2000000")
        )
        self._input = self._new_buffer()
        self._output = self._new_buffer()
        self._input_span_id: int | None = None
        self._input_active = False
        self._span_attributes: dict[int, dict[str, str | float | bool]] = {}
        self._lock = threading.Lock()

        # LiveKit reports speech start shortly after frames begin arriving.
        self._prespeech: deque[tuple[bytes, int, int]] = deque()
        self._prespeech_bytes = 0
        self._prespeech_max_bytes = 576_000

    def _new_buffer(self) -> _PCMBuffer:
        return _PCMBuffer(self._max_length)

    def capture_input(self, frame: rtc.AudioFrame) -> None:
        if self._input_active:
            self._input.append(frame)
            return

        pcm = bytes(frame.data)
        self._prespeech.append((pcm, frame.sample_rate, frame.num_channels))
        self._prespeech_bytes += len(pcm)
        while self._prespeech_bytes > self._prespeech_max_bytes and self._prespeech:
            old_pcm, _, _ = self._prespeech.popleft()
            self._prespeech_bytes -= len(old_pcm)

    def start_input(self, span_id: int) -> None:
        if self._input_span_id != span_id:
            self._save_input()
            self._input = self._new_buffer()
            self._input_span_id = span_id

        self._input_active = True
        while self._prespeech:
            pcm, sample_rate, num_channels = self._prespeech.popleft()
            self._input.append_pcm(pcm, sample_rate, num_channels)
        self._prespeech_bytes = 0

    def end_input(self) -> None:
        self._input_active = False
        self._save_input()

    def _save_input(self) -> None:
        if self._input_span_id is None:
            return
        attributes = self._input.attributes("input")
        if attributes:
            with self._lock:
                self._span_attributes.setdefault(self._input_span_id, {}).update(attributes)

    def capture_output(self, frame: rtc.AudioFrame) -> None:
        self._output.append(frame)

    def finish_output(self, span_id: int) -> None:
        attributes = self._output.attributes("output")
        if attributes:
            with self._lock:
                self._span_attributes.setdefault(span_id, {}).update(attributes)
        self._output = self._new_buffer()

    def take_attributes(self, span_id: int) -> dict[str, str | float | bool]:
        with self._lock:
            return self._span_attributes.pop(span_id, {})


class AudioSpanExporter(SpanExporter):
    """Enrich completed LiveKit turn spans, then delegate to Phoenix's exporter."""

    def __init__(self, delegate: SpanExporter, capture: AudioTraceCapture) -> None:
        self._delegate = delegate
        self._capture = capture

    def export(self, spans: Sequence[ReadableSpan]) -> SpanExportResult:
        return self._delegate.export(tuple(self._enrich(span) for span in spans))

    def shutdown(self) -> None:
        self._delegate.shutdown()

    def force_flush(self, timeout_millis: int = 30000) -> bool:
        return self._delegate.force_flush(timeout_millis)

    def _enrich(self, span: ReadableSpan) -> ReadableSpan:
        attributes = dict(span.attributes or {})
        attributes.update(self._capture.take_attributes(span.context.span_id))

        if span.name == "user_turn":
            attributes[SpanAttributes.OPENINFERENCE_SPAN_KIND] = (
                OpenInferenceSpanKindValues.LLM.value
            )
            if transcript := attributes.get("lk.pii.user_transcript"):
                attributes[SpanAttributes.INPUT_VALUE] = transcript
                attributes[SpanAttributes.INPUT_MIME_TYPE] = "text/plain"
        elif span.name == "agent_turn":
            attributes[SpanAttributes.OPENINFERENCE_SPAN_KIND] = (
                OpenInferenceSpanKindValues.LLM.value
            )
            if user_input := attributes.get("lk.pii.user_input"):
                attributes[SpanAttributes.INPUT_VALUE] = user_input
                attributes[SpanAttributes.INPUT_MIME_TYPE] = "text/plain"
            if response := attributes.get("lk.pii.response.text"):
                attributes[SpanAttributes.OUTPUT_VALUE] = response
                attributes[SpanAttributes.OUTPUT_MIME_TYPE] = "text/plain"

        if attributes == dict(span.attributes or {}):
            return span

        return ReadableSpan(
            name=span.name,
            context=span.context,
            parent=span.parent,
            resource=span.resource,
            attributes=attributes,
            events=span.events,
            links=span.links,
            kind=span.kind,
            instrumentation_info=span.instrumentation_info,
            status=span.status,
            start_time=span.start_time,
            end_time=span.end_time,
            instrumentation_scope=span.instrumentation_scope,
        )
