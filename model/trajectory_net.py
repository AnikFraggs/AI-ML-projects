"""
model/trajectory_net.py
-----------------------
TrajectoryNet — architecture EXACTLY matches uploaded trajectory_model.pth

Binary-analysed weights shape:
  net.0  Linear(13 → 128)  weight [128,13]  bias [128]
  net.2  Linear(128 → 64)  weight [64,128]  bias [64]
  net.4  Linear(64 → 2)    weight [2,64]    bias [2]
  Activations: ReLU (indices 1, 3)
  Output: raw [Cd, Cl]  (Cd index 0, Cl index 1)

13 Input Features (must match scaler.pkl StandardScaler fit order):
  0  velocity_ms         launch velocity [m/s]
  1  reynolds_number     Re = rho*v*d/mu
  2  air_density         rho [kg/m³]
  3  angle_deg           elevation angle [°]
  4  mass_kg             projectile mass [kg]
  5  area_m2             cross-sectional area [m²]
  6  wind_speed_ms       wind speed [m/s]
  7  wind_dir_sin        sin(wind_direction_radians)
  8  pressure_pa         atmospheric pressure [Pa]
  9  pressure_norm       pressure / 101325
  10 mach_number         v / speed_of_sound
  11 humidity_pct        relative humidity [%]
  12 temperature_c       temperature [°C]
"""

import torch
import torch.nn as nn
import math

_MU_AIR = 1.81e-5   # dynamic viscosity of air [Pa·s]


class TrajectoryNet(nn.Module):
    """3-layer MLP — matches uploaded trained weights exactly."""

    def __init__(self, input_dim: int = 13):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(input_dim, 128),  # net.0
            nn.ReLU(),                   # net.1
            nn.Linear(128, 64),         # net.2
            nn.ReLU(),                   # net.3
            nn.Linear(64, 2),           # net.4
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """Returns tensor [Cd, Cl] shape (batch, 2)."""
        return self.net(x)


def build_features(params: dict, weather: dict, rho: float, mach: float) -> list:
    """
    Build the 13-element feature vector.

    Parameters
    ----------
    params  : {velocity, mass, area, angle}
    weather : {wind_speed, wind_direction, temperature, humidity, pressure}
    rho     : air density [kg/m³]  — from atmosphere_model.air_density()
    mach    : Mach number          — from atmosphere_model.mach_number()

    Returns
    -------
    list of 13 floats in the exact order expected by scaler.pkl
    """
    v      = float(params["velocity"])
    mass   = float(params["mass"])
    area   = float(params["area"])
    angle  = float(params.get("angle", 45.0))
    d      = 2.0 * math.sqrt(area / math.pi)   # effective diameter [m]

    ws     = float(weather.get("wind_speed",      0.0))
    wd_rad = math.radians(float(weather.get("wind_direction", 0.0)))
    temp   = float(weather.get("temperature",    15.0))
    hum    = float(weather.get("humidity",        50.0))
    pres   = float(weather.get("pressure",    101325.0))

    Re = rho * v * d / _MU_AIR

    return [
        v,                   # 0  velocity_ms
        Re,                  # 1  reynolds_number
        rho,                 # 2  air_density
        angle,               # 3  angle_deg
        mass,                # 4  mass_kg
        area,                # 5  area_m2
        ws,                  # 6  wind_speed_ms
        math.sin(wd_rad),    # 7  wind_dir_sin
        pres,                # 8  pressure_pa
        pres / 101325.0,     # 9  pressure_norm
        mach,                # 10 mach_number
        hum,                 # 11 humidity_pct
        temp,                # 12 temperature_c
    ]
