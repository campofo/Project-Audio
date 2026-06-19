import json

import numpy as np

from forest_defense.classifier import AudioClassifier
from forest_defense.config import LocationConfig, NodeConfig
from forest_defense.incidents import IncidentLog
from forest_defense.preprocessing import AudioProcessor


class DummyModel:
    def __init__(self, probabilities):
        self.probabilities = probabilities
        self.output_shape = (None, len(probabilities))

    def predict(self, batch, verbose=0):
        return np.array([self.probabilities])


def make_config(tmp_path):
    return NodeConfig(
        node_id="fdp-test-node",
        location=LocationConfig(latitude=9.4, longitude=-0.8),
        model_path="model1_1.h5",
        confidence_threshold=0.75,
        incident_classes={"chainsaw", "gunshot"},
        labels=["background", "chainsaw", "gunshot"],
        incident_log_path=str(tmp_path / "incidents.jsonl"),
        device_registry_path=str(tmp_path / "devices.json"),
        fleet_db_path=str(tmp_path / "fleet.db"),
        device_api_key="classifier-test-key",
    )


def test_classifier_maps_prediction_to_label_and_incident():
    classifier = AudioClassifier(
        model=DummyModel([0.05, 0.9, 0.05]),
        labels=["background", "chainsaw", "gunshot"],
        confidence_threshold=0.75,
        incident_classes={"chainsaw", "gunshot"},
        processor=AudioProcessor(),
    )

    result = classifier.classify_processed(np.zeros((128, 157, 1)))

    assert result.label == "chainsaw"
    assert result.class_index == 1
    assert result.confidence == 0.9
    assert result.is_verified is True
    assert result.is_incident is True


def test_classifier_keeps_low_confidence_prediction_unverified():
    classifier = AudioClassifier(
        model=DummyModel([0.4, 0.45, 0.15]),
        labels=["background", "chainsaw", "gunshot"],
        confidence_threshold=0.75,
        incident_classes={"chainsaw", "gunshot"},
        processor=AudioProcessor(),
    )

    result = classifier.classify_processed(np.zeros((128, 157, 1)))

    assert result.label == "chainsaw"
    assert result.is_verified is False
    assert result.is_incident is False


def test_incident_log_writes_jsonl_records(tmp_path):
    config = make_config(tmp_path)
    classifier = AudioClassifier(
        model=DummyModel([0.05, 0.9, 0.05]),
        labels=config.labels,
        confidence_threshold=config.confidence_threshold,
        incident_classes=config.incident_classes,
        processor=AudioProcessor(),
    )
    prediction = classifier.classify_processed(np.zeros((128, 157, 1)))
    log = IncidentLog(config.incident_log_path)

    log.append(log.build_record(config, prediction))
    records = log.list_records()

    assert len(records) == 1
    assert records[0]["node_id"] == "fdp-test-node"
    assert records[0]["class_label"] == "chainsaw"
    assert records[0]["incident"] is True
    assert json.loads((tmp_path / "incidents.jsonl").read_text())["confidence"] == 0.9
    assert log.summary()["by_device"] == {"fdp-test-node": 1}
