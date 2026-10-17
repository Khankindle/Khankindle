// PEBBLE P0 — BENCH ONLY. Native parametric CAD, millimetres.
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
