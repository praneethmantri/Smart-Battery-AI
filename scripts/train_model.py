"""
CLI script to train the unplug predictor model using the processed dataset.
"""

import sys
import os

# Add root directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from ml.train import train_unplug_model

if __name__ == "__main__":
    data_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data", "processed", "charging_history.csv"))
    model_output = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "ml", "artifacts", "unplug_predictor.joblib"))

    if not os.path.exists(data_path):
        print(f"Data file not found at {data_path}. Running synthetic data generator first...")
        from scripts.generate_synthetic_data import main as generate_data
        generate_data()

    print("Starting ML Model Training...")
    train_unplug_model(data_path=data_path, output_model_path=model_output)
    print("Training finished successfully.")
