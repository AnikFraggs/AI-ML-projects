
import math


def gravity(latitude_deg: float, altitude_m: float) -> float:
  
    lat    = math.radians(latitude_deg)
    sin2   = math.sin(lat) ** 2
    g_e    = 9.7803253359      # equatorial gravity [m/s²]
    k      = 0.00193185265241  # Somigliana constant
    e2     = 0.00669437999013  # first eccentricity squared

    # Surface gravity (Somigliana)
    g_s = (g_e * (1.0 + k * sin2)) / math.sqrt(1.0 - e2 * sin2)

    # Free-air altitude correction
    R = 6_378_137.0            # WGS-84 equatorial radius [m]
    return g_s * (R / (R + altitude_m)) ** 2
