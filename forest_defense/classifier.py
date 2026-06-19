from dataclasses import dataclass
from typing import Iterable, Sequence

import numpy as np

from .config import NodeConfig, validate_label_count
from .preprocessing import AudioProcessor


@dataclass(frozen=True)
class PredictionResult:
    label: str
    class_index: int
    confidence: float
    probabilities: Sequence[float]
    is_incident: bool
    is_verified: bool


class AudioClassifier:
    def __init__(
        self,
        model,
        labels: Sequence[str],
        confidence_threshold: float,
        incident_classes: Iterable[str],
        processor: AudioProcessor,
    ) -> None:
        self.model = model
        self.labels = list(labels)
        self.confidence_threshold = confidence_threshold
        self.incident_classes = set(incident_classes)
        self.processor = processor

    @classmethod
    def from_config(cls, config: NodeConfig) -> "AudioClassifier":
        import tensorflow as tf

        model = tf.keras.models.load_model(config.model_path)
        output_shape = getattr(model, "output_shape", None)
        if output_shape and output_shape[-1]:
            validate_label_count(config.labels, int(output_shape[-1]))

        return cls(
            model=model,
            labels=config.labels,
            confidence_threshold=config.confidence_threshold,
            incident_classes=config.incident_classes,
            processor=AudioProcessor(
                target_rate=config.sample_rate,
                target_duration_seconds=config.sample_duration_seconds,
            ),
        )

    def classify_processed(self, processed_audio: np.ndarray) -> PredictionResult:
        batch = np.expand_dims(processed_audio, axis=0)
        raw_prediction = self.model.predict(batch, verbose=0)
        probabilities = np.asarray(raw_prediction)[0].astype(float)
        class_index = int(np.argmax(probabilities))
        validate_label_count(self.labels, len(probabilities))

        confidence = float(probabilities[class_index])
        label = self.labels[class_index]
        is_verified = confidence >= self.confidence_threshold
        is_incident = is_verified and label in self.incident_classes

        return PredictionResult(
            label=label,
            class_index=class_index,
            confidence=confidence,
            probabilities=probabilities.tolist(),
            is_incident=is_incident,
            is_verified=is_verified,
        )

    def classify_audio(self, audio_data: np.ndarray, source_rate: int) -> PredictionResult:
        processed = self.processor.preprocess_audio(audio_data, source_rate=source_rate)
        return self.classify_processed(processed)
