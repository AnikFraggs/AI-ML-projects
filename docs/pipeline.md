# TRAJECTORY.AI — Full Pipeline Documentation

## Pipeline Flow

```
User Inputs                    frontend/index.html (HTML form)
(latitude, longitude, altitude,
 velocity, angle, mass, area)
        │
        ▼
Weather API                    frontend/js/app.js  → api/backendapi.py
(wind_speed, wind_direction,
 temperature, humidity, pressure)
        │
        ▼
Feature Engineering            model/trajectory_net.py → build_features()
(13 features: velocity, Re,
 density, mach, angle, mass,
 area, wind, pressure, humidity,
 temperature)
        │
        ▼
ML Model (Cd, Cl)              models/trajectory_model.pth
(TrajectoryNet: Linear 13→128  ml/scaler.pkl
 →ReLU→128→64→ReLU→64→2)
        │
        ▼
Physics Solver                 api/physics/trajectory_solver.py
(RK4 6-DOF integrator:
 Gravity + Drag + Coriolis
 + Eötvös + Wind)
        │
        ▼
Trajectory Points              [{t, x, y, z, v}, ...]
(x=downrange, y=lateral,
 z=altitude)
        │
        ▼
VTK Export                     api/utils/vtk_export.py
(ASCII PolyData + CSV,
 scalars: speed/altitude/time/mach,
 vectors: velocity)
        │
        ▼
Visualization                  frontend/js/renderer3d.js (Three.js)
(3D Orbit / Side View /         OR open trajectory.vtk in ParaView
 Top-Down)
```

## File Map

| Stage | File |
|-------|------|
| UI inputs | frontend/index.html, frontend/js/app.js |
| Live physics (browser) | frontend/js/physics.js |
| 3D render | frontend/js/renderer3d.js |
| API endpoints | api/backendapi.py |
| Full pipeline | api/predict.py |
| Atmosphere | api/physics/atmosphere_model.py |
| Gravity | api/physics/gravity_model.py |
| Coriolis | api/physics/coriolis_force.py |
| RK4 Solver | api/physics/trajectory_solver.py |
| VTK export | api/utils/vtk_export.py |
| ML model def | model/trajectory_net.py |
| Trained weights | models/trajectory_model.pth |
| Scaler | ml/scaler.pkl |
| Synthetic training | ml/train_model.py |
| Real data fine-tune | ml/train_real_data.py |
| Sample data | dataset/real_data_template.csv |

## API Reference

### POST /predict
Full AI + Physics pipeline.

**Request:**
```json
{
  "params": {
    "latitude": 28.6, "longitude": 77.2, "altitude": 200,
    "velocity": 800, "angle": 45, "azimuth": 0,
    "mass": 50, "area": 0.07, "shape": "missile"
  },
  "weather": {
    "wind_speed": 15, "wind_direction": 270,
    "temperature": 20, "humidity": 60, "pressure": 101000
  },
  "export_vtk": false
}
```

**Response:**
```json
{
  "aerodynamics": {"Cd": 0.31, "Cl": 0.08, "mach": 2.34, "rho": 0.94, "source": "ml"},
  "results": {
    "range_m": 45000, "max_height_m": 12200,
    "time_of_flight_s": 142.3, "impact_speed_ms": 710.5,
    "lateral_drift_m": -45.2, "downrange_m": 44980
  },
  "trajectory": [{"t":0.0,"x":0.0,"y":0.0,"z":0.0,"v":800.0}, ...],
  "vtk": null
}
```

### GET /health
```json
{
  "status": "ok",
  "model_loaded": true,
  "pipeline": ["User Inputs", "Weather API", "Feature Engineering", ...]
}
```

## ParaView Visualization Guide

1. Start the API: `python api/backendapi.py`
2. Run simulation with `"export_vtk": true` in the request
3. Open ParaView
4. File → Open → `output/trajectory.vtk`
5. Click **Apply**
6. Colour by `speed` or `mach` scalar
7. Filters → Glyph → vector field `velocity` for arrow visualization
8. View → Animation → play for time-animated flight path
