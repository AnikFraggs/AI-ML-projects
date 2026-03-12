# Setup Guide

## Quick Start (3 commands)

```bash
cd projectile-ai
pip install flask flask-cors torch scikit-learn joblib numpy
python api/backendapi.py
```

Open `frontend/index.html` in your browser.

## Requirements

- Python 3.10+
- pip packages: flask flask-cors torch scikit-learn joblib numpy pandas

## Retrain the Model

```bash
# Synthetic data (80,000 samples, ~15 min CPU):
python ml/train_model.py

# Your own real data:
# 1. Fill in dataset/real_data_template.csv → save as ml/real_data.csv
# 2. Run:
python ml/train_real_data.py
```

## Directory Map

```
projectile-ai/
├── cfd/                   SOLIDWORKS / OpenFOAM CFD cases
├── trajectory_sim/        MATLAB or standalone Python simulations
├── dataset/               Synthetic + real training data
│   └── real_data_template.csv
├── model/                 PyTorch model definition
│   └── trajectory_net.py
├── api/                   Flask backend
│   ├── backendapi.py      REST endpoints
│   ├── predict.py         Full pipeline
│   ├── physics/           Physics modules
│   │   ├── atmosphere_model.py
│   │   ├── gravity_model.py
│   │   ├── coriolis_force.py
│   │   └── trajectory_solver.py
│   └── utils/
│       └── vtk_export.py
├── frontend/              HTML + JS + Three.js UI
│   ├── index.html
│   ├── css/style.css
│   └── js/
│       ├── physics.js     In-browser physics mirror
│       ├── renderer3d.js  Three.js 3D viewport
│       └── app.js         Main controller
├── docs/                  This documentation
├── models/
│   └── trajectory_model.pth   ← YOUR TRAINED MODEL
├── ml/
│   ├── scaler.pkl             ← YOUR TRAINED SCALER
│   ├── train_model.py
│   └── train_real_data.py
└── requirements.txt
```
