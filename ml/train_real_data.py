"""
ml/train_real_data.py
Fine-tune TrajectoryNet on your own real Cd/Cl measurements.

CSV columns: velocity, mass, area, angle, altitude,
             wind_speed, wind_direction, temperature, humidity, pressure,
             Cd, Cl

Run:  python ml/train_real_data.py
"""
import os, sys, json
import numpy as np, pandas as pd
import torch, torch.nn as nn
from torch.utils.data import DataLoader, TensorDataset
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split
import joblib

ROOT = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, ROOT)

from model.trajectory_net          import TrajectoryNet, build_features
from api.physics.atmosphere_model  import air_density, mach_number

DATA_PATH  = os.path.join(ROOT, "ml",     "real_data.csv")
MODEL_PATH = os.path.join(ROOT, "models", "trajectory_model.pth")
SCALER_PATH= os.path.join(ROOT, "ml",     "scaler.pkl")

EPOCHS=100; BATCH_SIZE=32; LR=5e-5
DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")
os.makedirs(os.path.join(ROOT,"models"), exist_ok=True)

df = pd.read_csv(DATA_PATH)
print(f"Loaded {len(df):,} real samples")

X_list, y_list = [], []
for _, row in df.iterrows():
    rho  = air_density(row.altitude, row.temperature, row.pressure, row.humidity)
    mach = mach_number(row.velocity, row.altitude, row.temperature)
    feat = build_features({"velocity":row.velocity,"mass":row.mass,
                            "area":row.area,"angle":row.angle},
                           {"wind_speed":row.wind_speed,"wind_direction":row.wind_direction,
                            "temperature":row.temperature,"humidity":row.humidity,
                            "pressure":row.pressure}, rho, mach)
    X_list.append(feat); y_list.append([float(row.Cd), float(row.Cl)])

X = np.array(X_list, dtype=np.float32)
y = np.array(y_list, dtype=np.float32)
X_tr,X_val,y_tr,y_val = train_test_split(X, y, test_size=0.15, random_state=42)

scaler = StandardScaler()
X_tr_s = scaler.fit_transform(X_tr); X_val_s = scaler.transform(X_val)
joblib.dump(scaler, SCALER_PATH)

model = TrajectoryNet(13).to(DEVICE)
if os.path.exists(MODEL_PATH):
    model.load_state_dict(torch.load(MODEL_PATH, map_location=DEVICE))
    print("Fine-tuning from pre-trained weights")
else:
    print("Training from scratch")

opt=torch.optim.AdamW(model.parameters(),lr=LR,weight_decay=1e-4)
sched=torch.optim.lr_scheduler.CosineAnnealingLR(opt,T_max=EPOCHS)
loss_fn=nn.HuberLoss()
bs=min(BATCH_SIZE,len(X_tr))
tr_dl=DataLoader(TensorDataset(torch.tensor(X_tr_s),torch.tensor(y_tr)),batch_size=bs,shuffle=True)
val_dl=DataLoader(TensorDataset(torch.tensor(X_val_s),torch.tensor(y_val)),batch_size=64)

best_val=float("inf"); history={"train":[],"val":[]}
for epoch in range(1,EPOCHS+1):
    model.train()
    for xb,yb in tr_dl:
        xb,yb=xb.to(DEVICE),yb.to(DEVICE)
        loss=loss_fn(model(xb),yb); opt.zero_grad(); loss.backward(); opt.step()
    sched.step()
    model.eval(); vl=0.0
    with torch.no_grad():
        for xb,yb in val_dl: vl+=loss_fn(model(xb.to(DEVICE)),yb.to(DEVICE)).item()
    vl/=len(val_dl)
    if vl<best_val: best_val=vl; torch.save(model.state_dict(),MODEL_PATH)
    if epoch%20==0: print(f"  Epoch {epoch:3d}  val={vl:.6f}")

print(f"Done. Best val: {best_val:.6f}  → {MODEL_PATH}")
