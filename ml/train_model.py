"""
ml/train_model.py
Train TrajectoryNet on 80,000 physics-informed synthetic samples.

Run:   python ml/train_model.py
Out:   models/trajectory_model.pth   ml/scaler.pkl
"""
import os, sys, math, random, json
import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, TensorDataset
from sklearn.preprocessing import StandardScaler
import joblib

ROOT = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, ROOT)

from model.trajectory_net          import TrajectoryNet, build_features
from api.physics.atmosphere_model  import air_density, mach_number

os.makedirs(os.path.join(ROOT, "models"), exist_ok=True)
os.makedirs(os.path.join(ROOT, "ml"),     exist_ok=True)

# ── Physics-based ground-truth Cd/Cl labels ──────────────────────────────────

def physics_cd(mach, re, shape_factor=1.0):
    if mach < 0.8:
        cd = 24/re + 6/(1+math.sqrt(re)) + 0.4 if re < 1000 else (0.44 if re < 1e5 else 0.1)
    elif mach < 1.0:
        cd = 0.44 + 1.2*(mach-0.8)**1.5
    elif mach < 1.2:
        cd = 0.44 + 0.6*math.exp(-2*(mach-1.0)**2) + 0.3
    else:
        cd = 0.9/mach + 0.1
    return float(np.clip(cd * shape_factor, 0.05, 2.5))

def physics_cl(angle_deg, mach):
    aoa  = min(abs(angle_deg), 15.0)
    cl2d = 2*math.pi*math.radians(aoa)
    cl   = cl2d/math.sqrt(max(1-mach**2,0.01)) if mach < 0.9 else cl2d*0.5
    return float(np.clip(cl*0.15, 0.0, 0.8))

def generate_sample():
    # Stratified Mach sampling: 40% sub, 30% trans, 30% super
    regime = random.choices(["sub","trans","super"],[0.4,0.3,0.3])[0]
    v = {"sub": random.uniform(0.5,280), "trans": random.uniform(280,420),
         "super": random.uniform(420,2500)}[regime]
    mass  = random.uniform(0.01, 5000)
    area  = random.uniform(1e-4, 3.0)
    angle = random.uniform(1, 89)
    alt   = random.uniform(0, 30000)
    temp  = random.uniform(-50, 50)
    hum   = random.uniform(0, 100)
    pres  = random.uniform(60000, 105000)
    ws    = random.uniform(0, 80)
    wd    = random.uniform(0, 360)
    rho   = air_density(alt, temp, pres, hum)
    mach  = mach_number(v, alt, temp)
    shape = random.choice([1.0,1.0,0.8,0.5,0.3,0.25])
    d     = 2.0*math.sqrt(area/math.pi)
    Re    = rho*v*d/1.81e-5
    Cd    = physics_cd(mach, Re, shape)
    Cl    = physics_cl(angle, mach)
    feat  = build_features({"velocity":v,"mass":mass,"area":area,"angle":angle},
                            {"wind_speed":ws,"wind_direction":wd,
                             "temperature":temp,"humidity":hum,"pressure":pres},
                            rho, mach)
    return feat, [Cd, Cl]

# ── Generate dataset ──────────────────────────────────────────────────────────
N = 80_000
print(f"Generating {N:,} synthetic training samples ...")
X_list, y_list = [], []
for _ in range(N):
    f, y = generate_sample()
    X_list.append(f); y_list.append(y)

X = np.array(X_list, dtype=np.float32)
y = np.array(y_list, dtype=np.float32)

idx   = np.random.permutation(N); split = int(0.9*N)
X_tr, X_val = X[idx[:split]], X[idx[split:]]
y_tr, y_val = y[idx[:split]], y[idx[split:]]

scaler = StandardScaler()
X_tr_s  = scaler.fit_transform(X_tr)
X_val_s = scaler.transform(X_val)
joblib.dump(scaler, os.path.join(ROOT, "ml", "scaler.pkl"))
print("Scaler saved → ml/scaler.pkl")

tr_dl  = DataLoader(TensorDataset(torch.tensor(X_tr_s), torch.tensor(y_tr)),
                    batch_size=512, shuffle=True,  num_workers=0)
val_dl = DataLoader(TensorDataset(torch.tensor(X_val_s),torch.tensor(y_val)),
                    batch_size=512, shuffle=False, num_workers=0)

device  = torch.device("cuda" if torch.cuda.is_available() else "cpu")
model   = TrajectoryNet(input_dim=13).to(device)
opt     = torch.optim.AdamW(model.parameters(), lr=3e-4, weight_decay=1e-4)
sched   = torch.optim.lr_scheduler.CosineAnnealingLR(opt, T_max=50)
loss_fn = nn.HuberLoss()

print(f"Training on {device} ...")
best_val = float("inf")
history  = {"train":[], "val":[]}

for epoch in range(1, 51):
    model.train()
    tr_loss = sum(
        (lambda pred,loss: (opt.zero_grad(), loss.backward(), opt.step(), loss.item()))(
            model(xb.to(device)), loss_fn(model(xb.to(device)), yb.to(device))
        )[3] for xb,yb in tr_dl)
    sched.step()
    model.eval()
    val_loss = 0.0
    with torch.no_grad():
        for xb,yb in val_dl:
            val_loss += loss_fn(model(xb.to(device)), yb.to(device)).item()
    tl = tr_loss/len(tr_dl); vl = val_loss/len(val_dl)
    history["train"].append(tl); history["val"].append(vl)
    if vl < best_val:
        best_val = vl
        torch.save(model.state_dict(), os.path.join(ROOT,"models","trajectory_model.pth"))
    if epoch%10==0: print(f"  Epoch {epoch:3d}  train={tl:.5f}  val={vl:.5f}")

with open(os.path.join(ROOT,"models","training_history.json"),"w") as f:
    json.dump(history, f)
print(f"\nBest val: {best_val:.6f}")
print("Model saved → models/trajectory_model.pth")
