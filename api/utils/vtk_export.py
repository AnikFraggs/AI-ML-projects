"""
api/utils/vtk_export.py
Export trajectory points to VTK PolyData + CSV for ParaView.

Pipeline stage: Trajectory Points → VTK Export → ParaView Visualization
"""
import os
import csv
import math


def export_vtk(trajectory: list, output_path: str = "output/trajectory.vtk",
               params: dict = None, result: dict = None) -> dict:
    """
    Write trajectory to ASCII VTK PolyData file.

    Scalar fields written per point:
      - speed       [m/s]
      - altitude    [m]
      - time        [s]
      - mach        (speed / 340)

    Parameters
    ----------
    trajectory   : list of {t, x, y, z, v} dicts from solve_trajectory()
    output_path  : output .vtk file path
    params       : optional launch params for metadata comment
    result       : optional result dict for metadata comment

    Returns
    -------
    dict with vtk_path and csv_path
    """
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

    n_pts = len(trajectory)
    vtk_path = output_path
    csv_path = output_path.replace(".vtk", ".csv")

    # ── VTK ASCII ────────────────────────────────────────────────────────────
    with open(vtk_path, "w") as f:
        f.write("# vtk DataFile Version 3.0\n")
        f.write("TrajectoryAI — projectile trajectory\n")
        if params:
            f.write(f"# v={params.get('velocity','?')}m/s "
                    f"angle={params.get('angle','?')}° "
                    f"mass={params.get('mass','?')}kg\n")
        f.write("ASCII\n")
        f.write("DATASET POLYDATA\n\n")

        # Points (x = downrange, y = lateral, z = altitude)
        f.write(f"POINTS {n_pts} float\n")
        for pt in trajectory:
            f.write(f"{pt['x']:.3f} {pt['y']:.3f} {pt['z']:.3f}\n")

        # Single polyline connecting all points
        f.write(f"\nLINES 1 {n_pts + 1}\n")
        f.write(f"{n_pts} " + " ".join(str(i) for i in range(n_pts)) + "\n")

        # Point data scalars
        f.write(f"\nPOINT_DATA {n_pts}\n")

        # Speed
        f.write("SCALARS speed float 1\n")
        f.write("LOOKUP_TABLE default\n")
        for pt in trajectory:
            f.write(f"{pt['v']:.3f}\n")

        # Altitude
        f.write("SCALARS altitude float 1\n")
        f.write("LOOKUP_TABLE default\n")
        for pt in trajectory:
            f.write(f"{pt['z']:.3f}\n")

        # Time
        f.write("SCALARS time float 1\n")
        f.write("LOOKUP_TABLE default\n")
        for pt in trajectory:
            f.write(f"{pt['t']:.4f}\n")

        # Mach (approx: speed / 340)
        f.write("SCALARS mach float 1\n")
        f.write("LOOKUP_TABLE default\n")
        for pt in trajectory:
            f.write(f"{pt['v']/340.0:.4f}\n")

        # Velocity vectors (tangent to trajectory)
        f.write("VECTORS velocity float\n")
        for i, pt in enumerate(trajectory):
            if i < len(trajectory) - 1:
                dx = trajectory[i+1]['x'] - pt['x']
                dy = trajectory[i+1]['y'] - pt['y']
                dz = trajectory[i+1]['z'] - pt['z']
                mag = max(math.sqrt(dx**2+dy**2+dz**2), 1e-9)
                scale = pt['v'] / mag
                f.write(f"{dx*scale:.3f} {dy*scale:.3f} {dz*scale:.3f}\n")
            else:
                f.write("0.0 0.0 0.0\n")

    # ── CSV ──────────────────────────────────────────────────────────────────
    with open(csv_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["t", "x", "y", "z", "v",
                                               "mach", "altitude_abs"])
        writer.writeheader()
        alt0 = params.get("altitude", 0) if params else 0
        for pt in trajectory:
            writer.writerow({
                "t":            pt["t"],
                "x":            pt["x"],
                "y":            pt["y"],
                "z":            pt["z"],
                "v":            pt["v"],
                "mach":         round(pt["v"] / 340.0, 4),
                "altitude_abs": round(alt0 + pt["z"], 1),
            })

    return {"vtk_path": vtk_path, "csv_path": csv_path, "n_points": n_pts}
