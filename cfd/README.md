# CFD Directory

Place your SOLIDWORKS or OpenFOAM case files here.

Suggested structure:
  cfd/
  ├── solidworks/       .SLDPRT, .SLDASM files (projectile geometry)
  ├── openfoam/         OpenFOAM case directories
  │   ├── sphere_case/
  │   ├── missile_case/
  │   └── javelin_case/
  └── results/          Extracted Cd/Cl values from CFD

Tip: Export Cd/Cl values from CFD into ml/real_data.csv for training.
