#!/usr/bin/env python3
"""Reproducible parametric mesh CAD + native OpenSCAD, mm; BENCH PROTOTYPE ONLY."""
import argparse, json, math
from pathlib import Path
import numpy as np
import trimesh

ROOT = Path(__file__).resolve().parents[1]

def parameters(fit):
    h, w = float(fit['concha_height_mm']), float(fit['concha_width_mm'])
    if not (24 <= h <= 32 and 19 <= w <= 25):
        raise ValueError('Outside provisional adult envelope: H 24–32, W 19–25 mm. Manual redesign required.')
    side = fit.get('side', 'right')
    if side not in ('left', 'right'): raise ValueError('side must be left or right')
    return (w-4)/18, (h-4)/24, side

def annular(z, outer, inner, n=128):
    vertices=[]
    for fn in (outer, inner):
        for zz in z:
            cx,cy,rx,ry=fn(zz)
            for t in np.linspace(0,2*np.pi,n,endpoint=False):
                vertices.append([cx+rx*np.cos(t),cy+ry*np.sin(t),zz])
    m=len(z); off=m*n; faces=[]
    for k in range(m-1):
        for j in range(n):
            a=k*n+j; b=k*n+(j+1)%n; c=b+n; d=a+n
            faces.extend([[a,b,c],[a,c,d],[off+a,off+c,off+b],[off+a,off+d,off+c]])
    for j in range(n):
        a=j; b=(j+1)%n
        faces.extend([[a,off+b,b],[a,off+a,off+b]])
        a=(m-1)*n+j; b=(m-1)*n+(j+1)%n
        faces.extend([[a,b,off+b],[a,off+b,off+a]])
    mesh=trimesh.Trimesh(vertices,faces,process=True)
    mesh.fix_normals()
    return mesh

def outside(z):
    f=math.sqrt(1-(z/9)**2)
    return 0,0,9*f,12*f

def inside(z):
    t=(z+6)/12
    return 1-1.5*t,-1.3+2*t,2.6*(4.7/2.6)**t,2.9*(6.6/2.9)**t

def make(fit):
    sx,sy,side=parameters(fit)
    shell=annular(np.linspace(-6,6,49),outside,inside)
    def co(z):
        _,_,x,y=outside(z); return 0,0,x+1.2,y+1.2
    def ci(z):
        _,_,x,y=outside(z); return 0,0,x-.15,y-.15
    collar=annular(np.linspace(-1.6,1.6,13),co,ci)
    fin=trimesh.creation.icosphere(subdivisions=3)
    fin.apply_scale([2.6,4.3,1.25]); fin.apply_translation([0,13.1,0])
    cradle=trimesh.boolean.union([collar,fin],engine='manifold')
    for mesh in (shell,cradle):
        mesh.apply_scale([sx,sy,1])
        if side=='left': mesh.apply_scale([-1,1,1])
    return shell,cradle

SCAD='''// PEBBLE P0 — BENCH ONLY. Native parametric CAD, millimetres.
// Independent acoustic concept, NOT Amano CAD. No certified hearing benefit.
concha_height_mm = 28;
concha_width_mm = 22;
side = "right";
part = "assembly"; // shell, cradle, assembly, exploded, section
N=128; M=48;
sx=(concha_width_mm-4)/18; sy=(concha_height_mm-4)/24;
assert(concha_height_mm>=24 && concha_height_mm<=32);
assert(concha_width_mm>=19 && concha_width_mm<=25);
assert(side=="left" || side=="right");
function z(k)=-6+12*k/M;
function f(z)=sqrt(1-pow(z/9,2));
function ring(z,inner=false,extra=0)= inner ?
 let(t=(z+6)/12) [1-1.5*t,-1.3+2*t,2.6*pow(4.7/2.6,t),2.9*pow(6.6/2.9,t)] :
 [0,0,9*f(z)+extra,12*f(z)+extra];
function pt(k,j,inner=false)=let(r=ring(z(k),inner),a=360*j/N) [r[0]+r[2]*cos(a),r[1]+r[3]*sin(a),z(k)];
// Matching ring topology to the Python exports; planar end rims, open bore.
O=(M+1)*N;
points=concat([for(k=[0:M],j=[0:N-1]) pt(k,j)], [for(k=[0:M],j=[0:N-1]) pt(k,j,true)]);
faces=concat(
 [for(k=[0:M-1],j=[0:N-1]) let(a=k*N+j,b=k*N+(j+1)%N,c=b+N,d=a+N) each [[a,b,c],[a,c,d],[O+a,O+c,O+b],[O+a,O+d,O+c]]],
 [for(j=[0:N-1]) let(a=j,b=(j+1)%N) each [[a,O+b,b],[a,O+a,O+b]]],
 [for(j=[0:N-1]) let(a=M*N+j,b=M*N+(j+1)%N) each [[a,b,O+b],[a,O+b,O+a]]]);
module shell(){ polyhedron(points,[for(face=faces) [for(i=[len(face)-1:-1:0]) face[i]]],convexity=10); }
module ellipse_solid(extra,extend=0){
 // Small ruled slices reproduce the collar's changing external radius.
 for(k=[0:11]) let(a=-1.6-extend+(3.2+2*extend)*k/12,b=-1.6-extend+(3.2+2*extend)*(k+1)/12)
 hull(){ for(v=[a,b]) translate([0,0,v]) linear_extrude(.001) scale([9*f(v)+extra,12*f(v)+extra]) circle(1,$fn=N); }
}
module cradle(){ union(){ difference(){ellipse_solid(1.2); ellipse_solid(-.15,.03);} translate([0,13.1,0]) scale([2.6,4.3,1.25]) sphere(1,$fn=80); } }
module assembly(){
 if(part=="shell") shell();
 else if(part=="cradle") cradle();
 else { color("#bbb2a3") shell(); color("#5a615f") translate([part=="exploded"?27:0,0,0]) cradle(); }
}
scale([side=="left"?-sx:sx,sy,1])
 if(part=="section") difference(){assembly(); translate([0,-40,-20]) cube([40,80,40]);} else assembly();
'''

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--fit',type=Path,default=ROOT/'examples/default-fit.json'); ap.add_argument('--output',type=Path,default=ROOT/'cad'); a=ap.parse_args()
    fit=json.loads(a.fit.read_text()); sx,sy,side=parameters(fit); a.output.mkdir(parents=True,exist_ok=True)
    shell,cradle=make(fit)
    for name,mesh in [('shell',shell),('cradle',cradle)]:
        if not mesh.is_watertight or not mesh.is_volume: raise RuntimeError(f'{name}: invalid solid')
        mesh.export(a.output/f'{name}.stl')
    # CAD-derived physical cutaway (positive-X half removed).
    box=trimesh.creation.box([40,80,40]); box.apply_translation([-20,0,0])
    cut=trimesh.boolean.intersection([shell,box],engine='manifold'); cut.export(a.output/'shell-section.stl')
    scad=SCAD.replace('concha_height_mm = 28;',f'concha_height_mm = {fit["concha_height_mm"]};').replace('concha_width_mm = 22;',f'concha_width_mm = {fit["concha_width_mm"]};').replace('side = "right";',f'side = "{side}";')
    (a.output/'pebble.scad').write_text(scad)
    report={'fit':fit,'status':'BENCH ONLY; no measured acoustic or clinical performance','units':'mm', 'shell_bounds_mm':shell.extents.tolist(),'assembly_bounds_mm':np.ptp(np.vstack([shell.vertices,cradle.vertices]),axis=0).tolist(), 'shell_volume_mm3':float(shell.volume),'cradle_volume_mm3':float(cradle.volume),'estimated_mass_g':float(shell.volume*.0009+cradle.volume*.0011),'mouth_area_mm2':math.pi*4.7*6.6*sx*sy,'outlet_area_mm2':math.pi*2.6*2.9*sx*sy,'shell_watertight':bool(shell.is_watertight),'cradle_watertight':bool(cradle.is_watertight),'minimum_wall_certified':False}
    (a.output/'build-report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))
if __name__=='__main__': main()
