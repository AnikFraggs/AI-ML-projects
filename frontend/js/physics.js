/**
 * frontend/js/physics.js
 * In-browser physics mirror — same formulas as the Python backend.
 * Used for live density display and fallback simulation if API is offline.
 */

const OMEGA = 7.2921159e-5;

function airDensity(alt, tempC, pressurePa, humidityPct) {
  const T0=288.15, L=0.0065, H_trop=11000, T_trop=216.65;
  const T_isa = alt<=H_trop ? T0-L*alt : T_trop;
  const T = Math.max(T_isa + (tempC+273.15-T0), 180);
  const P_isa = alt<=H_trop
    ? 101325*Math.pow(T0/T_isa, 9.80665/(287.058*L))
    : 101325*Math.pow(T0/T_trop, 9.80665/(287.058*L))
      *Math.exp(-9.80665*(alt-H_trop)/(287.058*T_trop));
  const P = P_isa*(pressurePa/101325);
  const Psat = 611.21*Math.exp((18.678-tempC/234.5)*(tempC/(257.14+tempC)));
  const Pv = (humidityPct/100)*Psat;
  const Tv = T/(1-(Pv/P)*(1-287.058/461.495));
  return Math.min(Math.max(P/(287.058*Tv), 0.001), 2.0);
}

function speedOfSound(alt, tempC) {
  const T0=288.15, L=0.0065, H_trop=11000;
  const T_isa = alt<=H_trop ? T0-L*alt : 216.65;
  return Math.sqrt(1.4*287.058*Math.max(T_isa+(tempC+273.15-T0),180));
}

function gravity(latDeg, altM) {
  const lat=latDeg*Math.PI/180, sin2=Math.sin(lat)**2;
  const g_s=(9.7803253359*(1+0.00193185265241*sin2))/Math.sqrt(1-0.00669437999013*sin2);
  return g_s*(6378137/(6378137+altM))**2;
}

function coriolisAcc(vx, vy, vz, latDeg) {
  const lat=latDeg*Math.PI/180;
  const Ox=OMEGA*Math.cos(lat), Oz=OMEGA*Math.sin(lat);
  return [-2*(Oz*vy), 2*(Oz*vx-Ox*vz), 2*Ox*vy];
}

function machDragFactor(m) {
  if(m<0.8) return 1;
  if(m<1.0) return 1+3*(m-0.8);
  if(m<1.2) return 1.6-0.5*(m-1);
  return Math.max(0.8, 1.5/m);
}

/**
 * Run RK4 simulation in-browser (fallback when API offline).
 * Returns same shape as API /predict response.
 */
function simulateLocal(params, weather, Cd, Cl) {
  const {latitude, altitude, velocity, angle, azimuth=0, mass, area} = params;
  const elev = angle*Math.PI/180, az = azimuth*Math.PI/180;
  let vx=velocity*Math.cos(elev)*Math.cos(az);
  let vy=velocity*Math.cos(elev)*Math.sin(az);
  let vz=velocity*Math.sin(elev);
  const ws=weather.wind_speed||0, wd=(weather.wind_direction||0)*Math.PI/180;
  const wx=ws*Math.cos(wd), wy=ws*Math.sin(wd);
  let [x,y,z]=[0,0,0], t=0, maxH=0;
  const traj=[], dt=velocity>500?0.005:velocity>50?0.02:0.05;
  let step=0; const rec=Math.max(1,Math.round(0.5/dt));
  while(z>=0&&t<3600){
    const rvx=vx-wx, rvy=vy-wy, rvz=vz;
    const rv=Math.max(Math.sqrt(rvx**2+rvy**2+rvz**2),1e-9);
    const altAbs=altitude+z;
    const rho=airDensity(altAbs, weather.temperature||15, weather.pressure||101325, weather.humidity||50);
    const mach=rv/speedOfSound(altAbs, weather.temperature||15);
    const F=0.5*rho*Cd*machDragFactor(mach)*area*rv**2;
    const ad=F/mass;
    const g=gravity(latitude, altAbs);
    const [cx,cy,cz]=coriolisAcc(vx,vy,vz,latitude);
    const ax=-ad*(rvx/rv)+cx, ay=-ad*(rvy/rv)+cy, az_=-ad*(rvz/rv)-g+cz;
    if(step%rec===0) traj.push({t:+t.toFixed(2),x:+x.toFixed(1),y:+y.toFixed(1),z:+z.toFixed(1),v:+rv.toFixed(1)});
    vx+=ax*dt; vy+=ay*dt; vz+=az_*dt;
    x+=vx*dt; y+=vy*dt; z+=vz*dt;
    if(z>maxH)maxH=z; t+=dt; step++;
    if(z<0){traj.push({t:+t.toFixed(2),x:+x.toFixed(1),y:+y.toFixed(1),z:0,v:+rv.toFixed(1)});break;}
  }
  const imp=traj[traj.length-1];
  const range=Math.sqrt((imp?.x||0)**2+(imp?.y||0)**2);
  const impV=Math.sqrt(vx**2+vy**2+vz**2);
  const mach0=velocity/speedOfSound(altitude,weather.temperature||15);
  return {
    aerodynamics:{Cd,Cl,mach:+mach0.toFixed(3),source:"local_fallback"},
    results:{range_m:+range.toFixed(1),max_height_m:+maxH.toFixed(1),
             time_of_flight_s:+t.toFixed(2),impact_speed_ms:+impV.toFixed(1),
             impact_speed_kmh:+(impV*3.6).toFixed(1),
             lateral_drift_m:+(imp?.y||0).toFixed(1),
             downrange_m:+(imp?.x||0).toFixed(1),mach_launch:+mach0.toFixed(3)},
    trajectory:traj
  };
}
