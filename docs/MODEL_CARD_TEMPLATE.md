# Model Card: Forest Defense Audio Classifier

## Model

- Model file:
- Version:
- Training date:
- Owner:

## Intended Use

Classify short audio windows from Forest Defense monitoring nodes into normal background audio and forest-threat classes such as chainsaw, gunshot, and fire/crackling.

## Class Order

The exact class order must match the model output order.

1. background
2. chainsaw
3. gunshot
4. fire_crackling

## Training Data

- Positive classes:
- Negative/background classes:
- Field locations:
- Recording devices:
- Sample rate:
- Clip duration:

## Evaluation

- Test set size:
- Accuracy:
- Precision by class:
- Recall by class:
- Confusion matrix location:
- Recommended confidence threshold:

## Known Limits

- Performance may degrade in heavy rain, wind, overlapping speech, dense insect noise, or with microphones different from the training devices.
- This classifier should support alert triage, not replace human verification or partner response protocols.
