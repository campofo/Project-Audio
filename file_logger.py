from datetime import datetime


class FileLogger:
    def __init__(self, file):
        self.file = file

    def log_event(self, event_description):
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        with open(self.file, 'a') as f:
            f.write(f"{timestamp}-{event_description}\n")
