# main.py
import threading
import time

import numpy as np
import tensorflow as tf
from audio_recorder import AudioRecorder
from preprocessing import AudioProcessor
from file_logger import FileLogger

class_names = {
    0: 'chainsaw',
    1: 'dog_bark',
    2: 'engine_idling',
    3: 'gun_shot'
}


# Load the trained model
model = tf.keras.models.load_model('model1_1.h5')
log_file=FileLogger('logs.txt')
def classify_audio(audio_queue, audio_processor):
    while True:
        if not audio_queue.empty():
            audio_data = audio_queue.get()
            processed_data = audio_processor.preprocess_audio(audio_data)
            processed_data = np.expand_dims(processed_data, axis=0)
            prediction = model.predict(processed_data)
            result = np.argmax(prediction, axis=1)[0]
            event_description = f"Detected sound: {class_names[result]} confidence:{round(prediction[0][result]*100,2)}%"
            log_file.log_event(event_description)
            print(result)

            #Class Names: ['chainsaw' 'dog_bark' 'engine_idling' 'gun_shot']


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
