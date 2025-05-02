# Logs each model prediction to a CSV file for retraining or review purposes.

import os
import csv
from datetime import datetime

LOG_FILE = "prediction_log.csv"

def log_prediction(image_name, predicted_class, confidence):
    """Append a prediction record to the CSV log file."""
    log_entry = {
        "timestamp": datetime.now().isoformat(),
        "image": image_name,
        "predicted_class": predicted_class,
        "confidence": round(confidence * 100, 2)
    }

    file_exists = os.path.isfile(LOG_FILE)
    with open(LOG_FILE, mode="a", newline="") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=log_entry.keys())
        if not file_exists:
            writer.writeheader()
        writer.writerow(log_entry)
