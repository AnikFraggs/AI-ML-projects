"""
dataset/generate_synthetic.py
Generate a synthetic Cd/Cl dataset and save to CSV.
Used for inspection, analysis, or training other models.

Run: python dataset/generate_synthetic.py --n 10000
"""
import sys, os, argparse, random, math
import numpy as np
import pandas as pd
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from api.physics.atmosphere_model import air_density, mach_number

def physics_cd(mach, re, sf=1.0):
    if mach<0.8: cd=24/re+6/(1+math.sqrt(re))+0.4 if re<1000 else (0.44 if re<1e5 else 0.1)
    elif mach<1.0: cd=0.44+1.2*(mach-0.8)**1.5
    elif mach<1.2: cd=0.44+0.6*math.exp(-2*(mach-1.0)**2)+0.3
    else: cd=0.9/mach+0.1
    return float(np.clip(cd*sf,0.05,2.5))

def physics_cl(angle, mach):
    aoa=min(abs(angle),15.0); cl2d=2*math.pi*math.radians(aoa)
    cl=cl2d/math.sqrt(max(1-mach**2,0.01)) if mach<0.9 else cl2d*0.5
    return float(np.clip(cl*0.15,0.0,0.8))

def main():
    parser=argparse.ArgumentParser(); parser.add_argument("--n",type=int,default=5000); args=parser.parse_args()
    rows=[]
    for _ in range(args.n):
        v=random.uniform(0.5,2500); mass=random.uniform(0.01,5000); area=random.uniform(1e-4,3.0)
        angle=random.uniform(1,89); alt=random.uniform(0,30000)
        temp=random.uniform(-50,50); hum=random.uniform(0,100); pres=random.uniform(60000,105000)
        ws=random.uniform(0,80); wd=random.uniform(0,360)
        rho=air_density(alt,temp,pres,hum); mach=mach_number(v,alt,temp)
        d=2.0*math.sqrt(area/math.pi); Re=rho*v*d/1.81e-5
        sf=random.choice([1.0,1.0,0.8,0.5,0.3,0.25])
        rows.append({"velocity":round(v,2),"mass":round(mass,4),"area":round(area,6),"angle":round(angle,1),
                     "altitude":round(alt,1),"wind_speed":round(ws,2),"wind_direction":round(wd,1),
                     "temperature":round(temp,1),"humidity":round(hum,1),"pressure":round(pres,1),
                     "Cd":round(physics_cd(mach,Re,sf),5),"Cl":round(physics_cl(angle,mach),5)})
    df=pd.DataFrame(rows)
    out=f"dataset/synthetic_{args.n}.csv"; df.to_csv(out,index=False)
    print(f"Saved {args.n} samples → {out}")
    print(f"Cd: {df.Cd.min():.3f} – {df.Cd.max():.3f}")
    print(f"Cl: {df.Cl.min():.3f} – {df.Cl.max():.3f}")

if __name__=="__main__": main()
