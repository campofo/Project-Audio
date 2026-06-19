import sys
import types

import numpy as np

from forest_defense.preprocessing import AudioProcessor


def test_normalize_length_pads_short_audio():
    processor = AudioProcessor(target_rate=16000, target_duration_seconds=5)
    audio = np.ones(1000)

    normalized = processor.normalize_length(audio, source_rate=16000)

    assert len(normalized) == 80000
    assert np.all(normalized[:1000] == 1)
    assert np.all(normalized[1000:] == 0)


def test_normalize_length_truncates_long_audio():
    processor = AudioProcessor(target_rate=16000, target_duration_seconds=5)
    audio = np.arange(90000)

    normalized = processor.normalize_length(audio, source_rate=16000)

    assert len(normalized) == 80000
    assert normalized[-1] == 79999


def test_preprocess_audio_returns_log_mel_channel_shape(monkeypatch):
    fake_librosa = types.SimpleNamespace()
    fake_librosa.feature = types.SimpleNamespace(
        melspectrogram=lambda y, sr, n_mels: np.ones((n_mels, 157))
    )
    fake_librosa.power_to_db = lambda mel, ref: mel
    monkeypatch.setitem(sys.modules, "librosa", fake_librosa)

    processor = AudioProcessor(target_rate=16000, target_duration_seconds=5, n_mels=64)
    processed = processor.preprocess_audio(np.ones(80000), source_rate=16000)

    assert processed.shape == (64, 157, 1)
