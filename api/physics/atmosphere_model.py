
import math


def air_density(altitude_m: float, temp_c: float,
                pressure_pa: float, humidity_pct: float) -> float:
    
    T0, L, H_trop, T_trop = 288.15, 0.0065, 11000.0, 216.65

    # 1. ISA temperature
    T_isa = T0 - L * altitude_m if altitude_m <= H_trop else T_trop

    # 2. Surface offset
    dT = (temp_c + 273.15) - T0
    T  = max(T_isa + dT, 180.0)

    # 3. ISA pressure at altitude
    if altitude_m <= H_trop:
        P_isa = 101325.0 * (T0 / T_isa) ** (9.80665 / (287.058 * L))
    else:
        P_isa = (101325.0
                 * (T0 / T_trop) ** (9.80665 / (287.058 * L))
                 * math.exp(-9.80665 * (altitude_m - H_trop) / (287.058 * T_trop)))
    P = P_isa * (pressure_pa / 101325.0)

    # 4. Buck saturation vapour pressure [Pa]
    Psat = 611.21 * math.exp((18.678 - temp_c / 234.5)
                              * (temp_c / (257.14 + temp_c)))
    Pv   = (humidity_pct / 100.0) * Psat

    # 5. Virtual temperature and density
    Tv = T / (1.0 - (Pv / P) * (1.0 - 287.058 / 461.495))
    return float(min(max(P / (287.058 * Tv), 0.001), 2.0))


def speed_of_sound(altitude_m: float, temp_c: float) -> float:
    T0, L, H_trop = 288.15, 0.0065, 11000.0
    T_isa = T0 - L * altitude_m if altitude_m <= H_trop else 216.65
    T     = max(T_isa + (temp_c + 273.15 - T0), 180.0)
    return math.sqrt(1.4 * 287.058 * T)


def mach_number(velocity_ms: float, altitude_m: float, temp_c: float) -> float:
    return velocity_ms / speed_of_sound(altitude_m, temp_c)
