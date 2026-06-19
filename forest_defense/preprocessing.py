from typing import Optional

import numpy as np


class AudioProcessor:
    def __init__(
        self,
        target_rate: int = 16000,
        target_duration_seconds: int = 5,
        n_mels: int = 128,
    ) -> None:
        self.target_rate = target_rate
        self.target_duration_seconds = target_duration_seconds
        self.n_mels = n_mels

    @property
    def target_length(self) -> int:
        return int(self.target_rate * self.target_duration_seconds)

    def normalize_length(self, audio_data: np.ndarray, source_rate: int) -> np.ndarray:
        y = np.asarray(audio_data, dtype=np.float32)
        if source_rate != self.target_rate:
            import librosa

            y = librosa.resample(y, orig_sr=source_rate, target_sr=self.target_rate)

        if len(y) < self.target_length:
            y = np.pad(y, (0, self.target_length - len(y)), mode="constant")
        elif len(y) > self.target_length:
            y = y[: self.target_length]

        return y

    def preprocess_audio(
        self,
        audio_data: np.ndarray,
        source_rate: Optional[int] = None,
    ) -> np.ndarray:
        import librosa

        rate = source_rate or self.target_rate
        y = self.normalize_length(audio_data, rate)
        mel = librosa.feature.melspectrogram(
            y=y,
            sr=self.target_rate,
            n_mels=self.n_mels,
        )
        log_mel = librosa.power_to_db(mel, ref=np.max)
        return np.expand_dims(log_mel, axis=-1)
