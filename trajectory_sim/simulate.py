"""
trajectory_sim/simulate.py
Standalone simulation script — runs without the Flask API.
Useful for batch runs, MATLAB comparison, or offline analysis.

Usage:
    python trajectory_sim/simulate.py
    python trajectory_sim/simulate.py --velocity 800 --angle 45 --vtk
"""
import sys, os, argparse, json
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from api.predict   import run_pipeline
from api.utils.vtk_export import export_vtk

DEFAULT_PARAMS = {
    "latitude": 28.6, "longitude": 77.2, "altitude": 200,
    "velocity": 30,   "angle": 45,       "azimuth": 0,
    "mass": 0.62,     "area": 0.045,     "shape": "sphere",
}
DEFAULT_WEATHER = {
    "wind_speed": 5, "wind_direction": 90,
    "temperature": 25, "humidity": 60, "pressure": 101325,
}

def main():
    parser = argparse.ArgumentParser(description="TrajectoryAI standalone sim")
    parser.add_argument("--velocity", type=float, default=30)
    parser.add_argument("--angle",    type=float, default=45)
    parser.add_argument("--mass",     type=float, default=0.62)
    parser.add_argument("--area",     type=float, default=0.045)
    parser.add_argument("--altitude", type=float, default=200)
    parser.add_argument("--vtk",      action="store_true")
    args = parser.parse_args()

    params  = {**DEFAULT_PARAMS, "velocity":args.velocity, "angle":args.angle,
               "mass":args.mass, "area":args.area, "altitude":args.altitude}
    weather = DEFAULT_WEATHER.copy()

    print(f"\n{'='*55}")
    print(f"  TRAJECTORY.AI — Standalone Simulation")
    print(f"  Velocity: {params['velocity']} m/s  Angle: {params['angle']}°")
    print(f"{'='*55}\n")

    result = run_pipeline(params, weather, export_vtk_flag=args.vtk)

    print(f"  ML Source  : {result['aerodynamics']['source']}")
    print(f"  Cd         : {result['aerodynamics']['Cd']}")
    print(f"  Cl         : {result['aerodynamics']['Cl']}")
    print(f"  Range      : {result['results']['range_m']} m")
    print(f"  Max Height : {result['results']['max_height_m']} m")
    print(f"  TOF        : {result['results']['time_of_flight_s']} s")
    print(f"  Drift      : {result['results']['lateral_drift_m']} m")
    print(f"  Points     : {len(result['trajectory'])}")

    if args.vtk and result.get('vtk'):
        print(f"\n  VTK → {result['vtk']['vtk_path']}")
        print(f"  CSV → {result['vtk']['csv_path']}")
        print("  Open in ParaView: File → Open → Apply → Colour by speed")

    outfile = "trajectory_sim/last_result.json"
    with open(outfile, "w") as f:
        json.dump({k:v for k,v in result.items() if k!="trajectory"}, f, indent=2)
    print(f"\n  Results saved → {outfile}")

if __name__ == "__main__":
    main()
