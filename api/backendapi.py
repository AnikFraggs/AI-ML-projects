"""
api/backendapi.py
Flask REST API — full pipeline endpoint.

Routes
------
POST /predict          Full pipeline: ML + Physics + optional VTK
POST /predict/fast     Physics only (no ML, uses fallback Cd/Cl)
GET  /health           Health check + model status
GET  /output/<file>    Serve VTK / CSV output files

Pipeline flow per request:
  User Inputs → Weather → Feature Eng → ML Model → Physics → Trajectory → VTK
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS

from api.predict import run_pipeline, predict_cd_cl, _load_model, _model

app = Flask(__name__)
CORS(app)

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "output")
os.makedirs(OUTPUT_DIR, exist_ok=True)


# ── Helper ───────────────────────────────────────────────────────────────────

def _validate(data: dict) -> tuple:
    """Returns (params, weather, error_str|None)."""
    required_params  = ["latitude", "longitude", "altitude",
                        "velocity", "angle", "mass", "area"]
    required_weather = ["wind_speed", "wind_direction",
                        "temperature", "humidity", "pressure"]

    p = data.get("params", {})
    w = data.get("weather", {})

    for key in required_params:
        if key not in p:
            return None, None, f"Missing params.{key}"
    for key in required_weather:
        if key not in w:
            return None, None, f"Missing weather.{key}"

    params = {
        "latitude":  float(p["latitude"]),
        "longitude": float(p["longitude"]),
        "altitude":  float(p["altitude"]),
        "velocity":  float(p["velocity"]),
        "angle":     float(p["angle"]),
        "azimuth":   float(p.get("azimuth", 0.0)),
        "mass":      float(p["mass"]),
        "area":      float(p["area"]),
        "shape":     str(p.get("shape", "sphere")),
    }
    weather = {
        "wind_speed":      float(w["wind_speed"]),
        "wind_direction":  float(w["wind_direction"]),
        "temperature":     float(w["temperature"]),
        "humidity":        float(w["humidity"]),
        "pressure":        float(w["pressure"]),
    }
    return params, weather, None


# ── Routes ────────────────────────────────────────────────────────────────────

@app.route("/health", methods=["GET"])
def health():
    _load_model()
    return jsonify({
        "status": "ok",
        "model_loaded": _model is not None,
        "pipeline": [
            "User Inputs",
            "Weather API",
            "Feature Engineering",
            "ML Model (Cd, Cl)",
            "Physics Solver (Gravity + Drag + Coriolis)",
            "Trajectory Points",
            "VTK Export",
            "ParaView Visualization",
        ]
    })


@app.route("/predict", methods=["POST"])
def predict():
    """
    Full AI + Physics pipeline.

    Request body
    ------------
    {
      "params": {
        "latitude": 28.6, "longitude": 77.2, "altitude": 200,
        "velocity": 800,  "angle": 45,       "azimuth": 0,
        "mass": 50,       "area": 0.07,      "shape": "missile"
      },
      "weather": {
        "wind_speed": 10, "wind_direction": 270,
        "temperature": 20, "humidity": 60, "pressure": 101000
      },
      "export_vtk": false
    }

    Response
    --------
    {
      "aerodynamics": {"Cd": 0.31, "Cl": 0.08, "mach": 2.34,
                       "rho": 0.9412, "source": "ml"},
      "results":      {"range_m": 45000, "max_height_m": 12200, ...},
      "trajectory":   [{t, x, y, z, v}, ...],
      "vtk":          {"vtk_path": "...", "csv_path": "...", "n_points": 900}
    }
    """
    data = request.get_json(force=True)
    if not data:
        return jsonify({"error": "No JSON body"}), 400

    params, weather, err = _validate(data)
    if err:
        return jsonify({"error": err}), 400

    export_vtk = bool(data.get("export_vtk", False))

    try:
        result = run_pipeline(params, weather, export_vtk_flag=export_vtk)
        return jsonify(result), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/predict/fast", methods=["POST"])
def predict_fast():
    """Physics-only endpoint — skips ML, uses Mach-based Cd fallback."""
    data = request.get_json(force=True)
    if not data:
        return jsonify({"error": "No JSON body"}), 400

    params, weather, err = _validate(data)
    if err:
        return jsonify({"error": err}), 400

    # Force fallback by passing a dummy payload (model not called)
    from api.physics import solve_trajectory
    from api.physics.atmosphere_model import mach_number
    import math

    mach = mach_number(params["velocity"], params["altitude"],
                       weather.get("temperature", 15.0))
    if mach < 0.8:   Cd = 0.47
    elif mach < 1.0: Cd = 0.47 + 1.2 * (mach - 0.8)**1.5
    else:            Cd = max(0.9/mach + 0.1, 0.25)

    try:
        res = solve_trajectory(params, weather, Cd=Cd, Cl=0.0)
        return jsonify({
            "aerodynamics": {"Cd": round(Cd,4), "Cl": 0.0,
                             "source": "physics_fallback"},
            "results":      {k:v for k,v in res.items() if k!="trajectory"},
            "trajectory":   res["trajectory"],
        }), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/output/<path:filename>", methods=["GET"])
def serve_output(filename):
    """Serve generated VTK / CSV files."""
    return send_from_directory(OUTPUT_DIR, filename)


if __name__ == "__main__":
    print("=" * 60)
    print("  TRAJECTORY.AI — Flask API")
    print("  Pipeline: Inputs → Weather → Features → ML → Physics → VTK")
    print("=" * 60)
    _load_model()
    app.run(host="0.0.0.0", port=5000, debug=False)
