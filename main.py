# main.py
import threading
import numpy as np
import tensorflow as tf
from audio_recorder import AudioRecorder
from preprocessing import AudioProcessor


# Load the trained model
model = tf.keras.models.load_model('model1_1.h5')

def classify_audio(audio_queue, audio_processor):
    while True:
        if not audio_queue.empty():
            audio_data = audio_queue.get()
            processed_data = audio_processor.preprocess_audio(audio_data)
            processed_data = np.expand_dims(processed_data, axis=0)
            prediction = model.predict(processed_data)
            result = np.argmax(prediction, axis=1)
            event_description = f"Detected class: {result}"
            print(prediction)

if __name__ == '__main__':

    audio_recorder = AudioRecorder()
    audio_processor = AudioProcessor()

    audio_queue = audio_recorder.get_audio_queue()

    recording_thread = threading.Thread(target=audio_recorder.record_audio)
    prediction_thread = threading.Thread(target=classify_audio, args=(audio_queue, audio_processor))

    recording_thread.start()
    prediction_thread.start()

    recording_thread.join()
    prediction_thread.join()
