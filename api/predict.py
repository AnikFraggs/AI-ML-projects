"""
api/predict.py
Core prediction pipeline:

  User Inputs → Weather API → Feature Engineering → ML Model (Cd,Cl)
      → Physics Solver → Trajectory Points → VTK Export

This module wires all stages together and is called by backendapi.py.
"""
import os
import sys
import math

# Allow imports from project root
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import torch
import joblib
import numpy as np

from model.trajectory_net   import TrajectoryNet, build_features
from api.physics             import air_density, mach_number, solve_trajectory
from api.utils.vtk_export    import export_vtk

# ── Load trained model + scaler once at import time ────────────────────────

_MODEL_PATH  = os.path.join(os.path.dirname(__file__), "..", "models", "trajectory_model.pth")
_SCALER_PATH = os.path.join(os.path.dirname(__file__), "..", "ml", "scaler.pkl")

_model  = None
_scaler = None

def _load_model():
    global _model, _scaler
    if _model is not None:
        return
    try:
        _model = TrajectoryNet(input_dim=13)
        _model.load_state_dict(
            torch.load(os.path.abspath(_MODEL_PATH), map_location="cpu")
        )
        _model.eval()
        _scaler = joblib.load(os.path.abspath(_SCALER_PATH))
        print("[predict] Loaded trajectory_model.pth + scaler.pkl")
    except Exception as e:
        print(f"[predict] WARNING: Could not load model: {e}")
        print("[predict] Falling back to physics-based Cd/Cl defaults")
        _model  = None
        _scaler = None


def predict_cd_cl(params: dict, weather: dict) -> dict:
    """
    Stage 3+4: Feature Engineering → ML Model → [Cd, Cl]

    Falls back to empirical defaults if model is unavailable.

    Returns
    -------
    {"Cd": float, "Cl": float, "source": "ml"|"fallback"}
    """
    _load_model()

    alt  = params.get("altitude",  0.0)
    temp = weather.get("temperature", 15.0)
    pres = weather.get("pressure", 101325.0)
    hum  = weather.get("humidity",  50.0)

    rho  = air_density(alt, temp, pres, hum)
    mach = mach_number(params["velocity"], alt, temp)

    if _model is not None and _scaler is not None:
        feat = build_features(params, weather, rho, mach)
        x    = np.array([feat], dtype=np.float32)
        x_s  = _scaler.transform(x)
        with torch.no_grad():
            out = _model(torch.tensor(x_s)).numpy()[0]
        Cd = float(max(out[0], 0.05))
        Cl = float(max(min(out[1], 0.8), 0.0))
        source = "ml"
    else:
        # Physics-based fallback (Mach-dependent sphere)
        if mach < 0.8:
            Cd = 0.47
        elif mach < 1.0:
            Cd = 0.47 + 1.2 * (mach - 0.8) ** 1.5
        else:
            Cd = max(0.9 / mach + 0.1, 0.25)
        Cl     = 0.0
        source = "fallback"

    return {"Cd": round(Cd, 5), "Cl": round(Cl, 5),
            "mach": round(mach, 4), "rho": round(rho, 5),
            "source": source}


def run_pipeline(params: dict, weather: dict,
                 export_vtk_flag: bool = False) -> dict:
    """
    Full pipeline from user inputs to trajectory results.

    Parameters
    ----------
    params : {latitude, longitude, altitude, velocity, angle, azimuth,
              mass, area, shape}
    weather: {wind_speed, wind_direction, temperature, humidity, pressure}
    export_vtk_flag : if True, write .vtk and .csv to output/

    Returns
    -------
    {
      "aerodynamics": {Cd, Cl, mach, rho, source},
      "results":      {range_m, max_height_m, time_of_flight_s,
                       impact_speed_ms, impact_speed_kmh,
                       lateral_drift_m, downrange_m, mach_launch},
      "trajectory":   [{t, x, y, z, v}, ...],
      "vtk":          {vtk_path, csv_path, n_points}  | None
    }
    """
    # Stage 3+4: Feature Engineering + ML inference
    aero = predict_cd_cl(params, weather)

    # Stage 5: Physics Solver (RK4)
    result = solve_trajectory(params, weather, aero["Cd"], aero["Cl"])

    # Stage 6+7: VTK Export (optional)
    vtk_info = None
    if export_vtk_flag:
        vtk_info = export_vtk(
            trajectory  = result["trajectory"],
            output_path = "output/trajectory.vtk",
            params      = params,
            result      = result,
        )

    return {
        "aerodynamics": aero,
        "results":      {k: v for k, v in result.items() if k != "trajectory"},
        "trajectory":   result["trajectory"],
        "vtk":          vtk_info,
    }
