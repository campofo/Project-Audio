# audio_recorder.py
import pyaudio
import numpy as np
import queue

class AudioRecorder:
    FORMAT = pyaudio.paInt16
    CHANNELS = 1
    RATE = 44100
    CHUNK = 1024
    RECORD_SECONDS = 5

    def __init__(self):
        self.audio_queue = queue.Queue()

    def record_audio(self):
        audio = pyaudio.PyAudio()
        stream = audio.open(format=self.FORMAT, channels=self.CHANNELS, rate=self.RATE, input=True, frames_per_buffer=self.CHUNK)
        print("Recording...")

        while True:
            frames = []
            try:
                for _ in range(0, int(self.RATE / self.CHUNK * self.RECORD_SECONDS)):
                    data = stream.read(self.CHUNK, exception_on_overflow=False)
                    frames.append(np.frombuffer(data, dtype=np.int16))
                audio_data = np.hstack(frames)
                self.audio_queue.put(audio_data)
            except IOError as e:
                print(f"Error recording audio: {e}")
                continue

    def get_audio_queue(self):
        return self.audio_queue

