
import math

OMEGA = 7.2921159e-5   # Earth rotation rate [rad/s]


def coriolis_acceleration(vx: float, vy: float, vz: float,
                           latitude_deg: float) -> tuple:
    lat = math.radians(latitude_deg)
    Ox  = OMEGA * math.cos(lat)   # northward component
    Oz  = OMEGA * math.sin(lat)   # upward component

    # -2 * (Ω × v)
    ax = -2.0 * ( Oz * vy)
    ay =  2.0 * ( Oz * vx - Ox * vz)
    az =  2.0 * ( Ox * vy)

    return (ax, ay, az)


def eotvos_correction(vy: float, latitude_deg: float,
                      altitude_m: float) -> float:
 
    lat = math.radians(latitude_deg)
    R   = 6_378_137.0
    return (2.0 * OMEGA * vy * math.cos(lat)
            + vy ** 2 / (R + altitude_m))
