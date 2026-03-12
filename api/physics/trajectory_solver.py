"""
api/physics/trajectory_solver.py
6-DOF RK4 trajectory integrator.

Pipeline
--------
User Inputs → Feature Engineering → ML Model → Physics Solver → Trajectory Points

Forces modelled
---------------
  1. Drag          : F_d = ½ρ·Cd·A·v_rel²   (Mach-corrected)
  2. Gravity       : WGS-84 Somigliana + free-air
  3. Coriolis      : full 3-D NED frame
  4. Eötvös effect : eastward velocity correction to gravity
  5. Wind          : relative velocity calculated from wind vector
"""
import math
from .atmosphere_model import air_density, speed_of_sound
from .gravity_model    import gravity
from .coriolis_force   import coriolis_acceleration, eotvos_correction


def _mach_drag_factor(mach: float) -> float:
    """Transonic drag rise multiplier on Cd."""
    if mach < 0.80: return 1.0
    if mach < 1.00: return 1.0 + 3.0 * (mach - 0.80)
    if mach < 1.20: return 1.6 - 0.5  * (mach - 1.00)
    return max(0.8, 1.5 / mach)


def _derivatives(state, t, params, weather, Cd, Cl):
    """Compute 6 derivatives for RK4: dx,dy,dz,dvx,dvy,dvz."""
    x, y, z, vx, vy, vz = state

    ws  = weather.get("wind_speed",      0.0)
    wd  = math.radians(weather.get("wind_direction", 0.0))
    wx  = ws * math.cos(wd)
    wy  = ws * math.sin(wd)

    # Relative velocity (projectile minus wind)
    rvx, rvy, rvz = vx - wx, vy - wy, vz
    rv  = max(math.sqrt(rvx**2 + rvy**2 + rvz**2), 1e-9)

    alt_abs = params["altitude"] + z
    temp    = weather.get("temperature",  15.0)
    pres    = weather.get("pressure",  101325.0)
    hum     = weather.get("humidity",     50.0)

    rho   = air_density(alt_abs, temp, pres, hum)
    a_snd = speed_of_sound(alt_abs, temp)
    mach  = rv / a_snd
    mf    = _mach_drag_factor(mach)

    # Drag force → acceleration
    F_drag = 0.5 * rho * Cd * mf * params["area"] * rv**2
    a_drag = F_drag / params["mass"]

    # Gravity
    g = gravity(params["latitude"], alt_abs)
    eotvos = eotvos_correction(vy, params["latitude"], alt_abs)

    # Coriolis
    cx, cy, cz = coriolis_acceleration(vx, vy, vz, params["latitude"])

    # Net accelerations
    ax = -a_drag * (rvx / rv) + cx
    ay = -a_drag * (rvy / rv) + cy
    az = -a_drag * (rvz / rv) - g + eotvos + cz

    return [vx, vy, vz, ax, ay, az]


def solve_trajectory(params: dict, weather: dict,
                     Cd: float, Cl: float) -> dict:
    """
    Integrate projectile trajectory using 4th-order Runge-Kutta.

    Parameters
    ----------
    params  : {latitude, longitude, altitude, velocity, angle, azimuth,
               mass, area, shape}
    weather : {wind_speed, wind_direction, temperature, humidity, pressure}
    Cd      : drag coefficient  (from ML model)
    Cl      : lift coefficient  (from ML model)

    Returns
    -------
    dict with keys:
      trajectory        — list of {t, x, y, z, v} dicts
      range_m           — total range [m]
      max_height_m      — apogee [m]
      time_of_flight_s  — TOF [s]
      impact_speed_ms   — impact speed [m/s]
      impact_speed_kmh  — impact speed [km/h]
      lateral_drift_m   — y-axis drift [m]
      downrange_m       — x-axis range [m]
      mach_launch       — Mach number at launch
    """
    lat  = params["latitude"]
    alt0 = params["altitude"]
    v0   = params["velocity"]
    elev = math.radians(params["angle"])
    az   = math.radians(params.get("azimuth", 0.0))

    vx0 = v0 * math.cos(elev) * math.cos(az)
    vy0 = v0 * math.cos(elev) * math.sin(az)
    vz0 = v0 * math.sin(elev)

    state = [0.0, 0.0, 0.0, vx0, vy0, vz0]

    dt   = 0.005 if v0 > 500 else (0.02 if v0 > 50 else 0.05)
    rec  = max(1, round(0.5 / dt))   # record every ~0.5 s

    t       = 0.0
    max_h   = 0.0
    traj    = []
    step    = 0
    max_t   = 3600.0

    while state[2] >= 0.0 and t < max_t:
        x, y, z, vx, vy, vz = state
        rv = math.sqrt((vx - weather.get("wind_speed",0)*math.cos(math.radians(weather.get("wind_direction",0))))**2
                       + (vy - weather.get("wind_speed",0)*math.sin(math.radians(weather.get("wind_direction",0))))**2
                       + vz**2)

        if step % rec == 0:
            traj.append({"t": round(t,2), "x": round(x,1),
                         "y": round(y,1), "z": round(z,1),
                         "v": round(rv,1)})

        # RK4
        k1 = _derivatives(state, t,        params, weather, Cd, Cl)
        s2 = [s + 0.5*dt*k for s,k in zip(state, k1)]
        k2 = _derivatives(s2,    t+0.5*dt, params, weather, Cd, Cl)
        s3 = [s + 0.5*dt*k for s,k in zip(state, k2)]
        k3 = _derivatives(s3,    t+0.5*dt, params, weather, Cd, Cl)
        s4 = [s + dt*k     for s,k in zip(state, k3)]
        k4 = _derivatives(s4,    t+dt,     params, weather, Cd, Cl)

        state = [s + (dt/6.0)*(a+2*b+2*c+d)
                 for s,a,b,c,d in zip(state,k1,k2,k3,k4)]

        if state[2] > max_h:
            max_h = state[2]
        t    += dt
        step += 1

        if state[2] < 0.0:
            traj.append({"t": round(t,2), "x": round(state[0],1),
                         "y": round(state[1],1), "z": 0.0,
                         "v": round(math.sqrt(state[3]**2+state[4]**2+state[5]**2),1)})
            break

    imp   = traj[-1]
    rng   = math.sqrt(imp["x"]**2 + imp["y"]**2)
    impV  = math.sqrt(state[3]**2 + state[4]**2 + state[5]**2)
    mach0 = v0 / speed_of_sound(alt0, weather.get("temperature", 15.0))

    return {
        "trajectory":        traj,
        "range_m":           round(rng, 1),
        "max_height_m":      round(max_h, 1),
        "time_of_flight_s":  round(t, 2),
        "impact_speed_ms":   round(impV, 1),
        "impact_speed_kmh":  round(impV * 3.6, 1),
        "lateral_drift_m":   round(imp["y"], 1),
        "downrange_m":       round(imp["x"], 1),
        "mach_launch":       round(mach0, 3),
    }
