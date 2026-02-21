# Fake Profile Detection

Detect fraudulent or bot-like social-media accounts using a supervised Artificial Neural Network (ANN) built with Keras.

---

## 📑 Table of Contents
1. [Project Overview](#project-overview)
2. [Model Architecture](#model-architecture)
3. [How to Use](#how-to-use)
4. [Dataset](#dataset)
5. [Results](#results)
6. [Project Structure](#project-structure)
7. [Requirements](#requirements)
8. [License](#license)

---

## Project Overview
Online social networks are plagued by fake profiles that spread misinformation, spam, or malicious links. This repository provides an end-to-end pipeline that:

* Parses two CSV files — `users.csv` (legitimate accounts) and `fakeusers.csv` (malicious accounts).
* Performs feature engineering & preprocessing (encoding, imputation, shuffling, train/val/test split).
* Trains a feed-forward ANN to **classify each profile as *real* or *fake***.
* Achieves ≈99 % test accuracy on the provided dataset.

## Model Architecture
```
Input  ➜  Dense(32, ReLU)
         ➜  Dense(64, ReLU)
         ➜  Dense(64, ReLU)
         ➜  Dense(32, ReLU)
         ➜  Dense(1,  Sigmoid)  ➜  Output (probability of being fake)
```
• Loss: `binary_crossentropy`
• Optimizer: `Adam`
• Metrics: `accuracy`

## How to Use
### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Train the Model
```bash
python fake_profile_detection.py
```
The script will:
1. Read the CSVs.
2. Preprocess & split the data.
3. Train the ANN for 50 epochs.
4. Save the trained weights to `fake_real_profile_model.h5`.

### 3. Inference on New Profiles
```python
from keras.models import load_model
import pandas as pd

model = load_model('fake_real_profile_model.h5')

# Example single profile (replace values accordingly)
sample = {
    "statuses_count": 1200,
    "followers_count": 150,
    "friends_count": 400,
    "favourites_count": 35,
    "listed_count": 2,
    "geo_enabled": 0,
    "profile_use_background_image": 1,
    "lang": 3  # encoded language ID
}

df = pd.DataFrame([sample])
prob_fake = model.predict(df)[0][0]
print(f"Probability of being fake: {prob_fake:.2%}")
print("Prediction:", "Fake" if prob_fake >= 0.5 else "Real")
```

### 4. Visualize Training (optional)
The script automatically plots accuracy and loss curves using Matplotlib.

## Dataset
Feature list:
| Feature | Description |
|---------|-------------|
| `statuses_count` | Number of tweets/posts |
| `followers_count` | Number of followers |
| `friends_count` | Number of friends/followees |
| `favourites_count` | Number of liked posts |
| `listed_count` | Times the user is listed |
| `geo_enabled` | 1 if location is shared |
| `profile_use_background_image` | 1 if profile uses a bg image |
| `lang` | Encoded interface language |

`users.csv` contains genuine users (`isFake = 0`) while `fakeusers.csv` contains labeled fake/bot accounts (`isFake = 1`).

## Results
* **Test Accuracy:** ~99 %
* Training/validation curves are stored in `plots/` (generated at runtime).

## Project Structure
```
Fake_Profile_Detection_new/
├── fake_profile_detection.py   # Main training / inference script
├── README.md                   # You are here
├── users.csv                   # Real user dataset
├── fakeusers.csv               # Fake user dataset
├── fake_real_profile_model.h5  # Saved Keras model (generated)
└── requirements.txt            # Python deps
```

## Requirements
Python ≥ 3.8
```
pandas
numpy
scikit-learn
keras
tensorflow
matplotlib
```

## License
This project is licensed under the MIT License.


