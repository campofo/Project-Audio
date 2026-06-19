import queue
from typing import Optional

import numpy as np


class AudioRecorder:
    FORMAT = None
    CHANNELS = 1
    CHUNK = 1024

    def __init__(
        self,
        rate: int = 44100,
        record_seconds: int = 5,
        audio_queue: Optional[queue.Queue] = None,
    ) -> None:
        self.rate = rate
        self.record_seconds = record_seconds
        self.audio_queue = audio_queue or queue.Queue()

    def record_audio(self) -> None:
        import pyaudio

        audio = pyaudio.PyAudio()
        stream = audio.open(
            format=pyaudio.paInt16,
            channels=self.CHANNELS,
            rate=self.rate,
            input=True,
            frames_per_buffer=self.CHUNK,
        )
        print(
            f"Recording {self.record_seconds}s windows at {self.rate} Hz. "
            "Press Ctrl+C to stop."
        )

        try:
            while True:
                frames = []
                chunks = int(self.rate / self.CHUNK * self.record_seconds)
                for _ in range(chunks):
                    data = stream.read(self.CHUNK, exception_on_overflow=False)
                    frames.append(np.frombuffer(data, dtype=np.int16))
                self.audio_queue.put(np.hstack(frames))
        finally:
            stream.stop_stream()
            stream.close()
            audio.terminate()

    def get_audio_queue(self) -> queue.Queue:
        return self.audio_queue
