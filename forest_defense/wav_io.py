import wave
from pathlib import Path
from typing import Tuple

import numpy as np


def read_wav_mono(path: str) -> Tuple[np.ndarray, int]:
    source = Path(path)
    with wave.open(str(source), "rb") as handle:
        channels = handle.getnchannels()
        sample_width = handle.getsampwidth()
        sample_rate = handle.getframerate()
        frames = handle.readframes(handle.getnframes())

    if sample_width == 2:
        audio = np.frombuffer(frames, dtype=np.int16).astype(np.float32)
    elif sample_width == 1:
        audio = (np.frombuffer(frames, dtype=np.uint8).astype(np.float32) - 128.0) * 256.0
    else:
        raise ValueError("Only 8-bit and 16-bit PCM WAV files are supported")

    if channels > 1:
        audio = audio.reshape(-1, channels).mean(axis=1)

    return audio, sample_rate
