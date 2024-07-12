import librosa
import matplotlib.pyplot as plt
import numpy as np
import numpy as np
import librosa


class AudioProcessor:
    @staticmethod
    def preprocess_audio(audio_data, rate=16000, target_length=5 * 16000):
        y = audio_data.astype(float)
        if rate != 16000:
            y = librosa.resample(y, orig_sr=rate, target_sr=16000)
        if target_length:
            if len(y) < target_length:
                # Pad audio if it's shorter than target length
                padding = target_length - len(y)
                y = np.pad(y, (0, padding), 'constant')
            elif len(y) > target_length:
                # Truncate audio if it's longer than target length
                y = y[:target_length]
        mel_spectrogram = librosa.feature.melspectrogram(y=y, sr=16000)
        log_mel_spectrogram = librosa.power_to_db(mel_spectrogram, ref=np.max)
        return np.expand_dims(log_mel_spectrogram, axis=-1)