#!/usr/bin/env python3
"""Images use exported geometry, never an imagined internal mechanism."""
from pathlib import Path
import json
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Ellipse, PathPatch
from matplotlib.path import Path as MPath
from mpl_toolkits.mplot3d.art3d import Poly3DCollection
import numpy as np
import trimesh
ROOT=Path(__file__).resolve().parents[1]; OUT=ROOT/'docs/images'; OUT.mkdir(exist_ok=True,parents=True)
BG='#f2f0e9'; INK='#173b33'; TAUPE='#b8ab96'; GREEN='#52685b'
plt.rcParams.update({'font.family':'DejaVu Sans','text.color':INK,'axes.labelcolor':INK,'font.size':11})
shell=trimesh.load(ROOT/'cad/shell.stl'); cradle=trimesh.load(ROOT/'cad/cradle.stl'); cut=trimesh.load(ROOT/'cad/shell-section.stl')

def mesh(ax,m,color,offset=(0,0,0)):
    poly=Poly3DCollection(m.triangles+np.array(offset),facecolors=color,linewidths=0,shade=True,lightsource=matplotlib.colors.LightSource(azdeg=225,altdeg=50),zsort='average');ax.add_collection3d(poly)
def scene(name,title,subtitle,parts,lim=17,elev=50,azim=-58):
    fig=plt.figure(figsize=(12,9),facecolor=BG);ax=fig.add_axes([.03,.08,.94,.78],projection='3d',facecolor=BG)
    for m,c,o in parts:mesh(ax,m,c,o)
    ax.set(xlim=(-lim,lim),ylim=(-lim,lim),zlim=(-lim*.65,lim*.65));ax.set_box_aspect([1,1,.8]);ax.view_init(elev,azim);ax.set_axis_off();ax.set_proj_type('ortho')
    fig.text(.07,.94,'PEBBLE / P0',fontsize=13,weight='bold');fig.text(.07,.885,title,fontsize=28,weight='bold');fig.text(.07,.84,subtitle,fontsize=11)
    fig.text(.07,.045,'CAD-derived geometry  •  millimetres  •  unvalidated bench prototype, not for wear',fontsize=10)
    fig.savefig(OUT/name,dpi=180,facecolor=BG);plt.close(fig)
scene('cad-perspective.png','Earbud, not ear trumpet.','18 × 24 × 12 mm rigid body  /  compliant retaining ring + short fin  /  zero batteries',[(shell,TAUPE,(0,0,0)),(cradle,GREEN,(0,0,0))])
scene('cad-exploded.png','Two parts. No electronics.','Left: PP acoustic body     Right: flexible cradle (offset for inspection; stretches over body)',[(shell,TAUPE,(-14,0,0)),(cradle,GREEN,(14,0,0))],lim=33)
scene('cad-cutaway.png','An open acoustic path.','Half the rigid body removed to expose the oblique taper. No diaphragm, hidden lever, or canal insert.',[(cut,TAUPE,(0,0,0))],lim=18,elev=20,azim=-28)
# Orthographic silhouettes from exact mesh vertex projections, bore at both end planes.
fig,axs=plt.subplots(1,3,figsize=(14,6),facecolor=BG)
for ax,(dims,title) in zip(axs,[((0,1),'OUTWARD FACE · +Z'),((0,2),'SIDE · X/Z'),((1,2),'SIDE · Y/Z')]):
    i,j=dims
    for m,color in [(cradle,GREEN),(shell,TAUPE)]:
        from matplotlib.collections import PolyCollection
        ax.add_collection(PolyCollection(m.triangles[:,:,[i,j]],facecolors=color,edgecolors='none'))
    ax.set_aspect('equal');ax.autoscale();ax.set_title(title,pad=20,fontsize=11);ax.set_facecolor(BG);ax.grid(alpha=.16);ax.set_xlabel('mm');ax.set_ylabel('mm')
    if dims==(0,1):ax.add_patch(Ellipse((-.5,.7),9.4,13.2,color=INK));ax.annotate('9.4 × 13.2 mouth',xy=(0,3),xytext=(-13,21),arrowprops={'arrowstyle':'->','color':INK},fontsize=9)
fig.suptitle('PEBBLE P0 / Default-size orthographic envelope',fontsize=20,weight='bold');fig.text(.06,.025,'Rigid body 18 W × 24 H × 12 D mm. Flexible cradle envelope 20.4 W × 30.6 H mm. Open outlet 5.2 × 5.8 mm.\nMesh edges are not production fillets; lip rounding and safe standoff require redesign + inspection before any human fit.',fontsize=10)
fig.subplots_adjust(bottom=.22,top=.8,wspace=.4);fig.savefig(OUT/'cad-dimensions.png',dpi=180);plt.close(fig)
# Explicit schematic only: a geometric ear outline and same CAD projected into concha.
fig,ax=plt.subplots(figsize=(9,10),facecolor=BG);ax.set_facecolor(BG)
t=np.linspace(0,2*np.pi,250);ax.fill(22*np.cos(t)+2*np.sin(2*t),34*np.sin(t),color='#dcc4ac',ec='#a48972',lw=2)
ax.add_patch(Ellipse((0,3),29,48,angle=-8,fill=False,ec='#a48972',lw=3));ax.add_patch(Ellipse((0,-2),20,29,angle=10,fc='#c3a58d',ec='#a48972'))
from matplotlib.collections import PolyCollection
for m,color in [(cradle,GREEN),(shell,TAUPE)]:
    tri=m.triangles[:,:,[0,1]].copy();tri[:,:,1]-=2
    ax.add_collection(PolyCollection(tri,facecolors=color,edgecolors='none'))
ax.add_patch(Ellipse((-.5,-1.3),9.4,13.2,fc=INK))
ax.annotate('Soft fin rests in upper bowl\n(proposed fit; not verified)',xy=(0,14),xytext=(31,25),arrowprops={'arrowstyle':'->','color':INK},fontsize=11)
ax.annotate('Compact outer-ear body\nNothing wraps behind the ear',xy=(8,-4),xytext=(31,-4),arrowprops={'arrowstyle':'->','color':INK},fontsize=11)
ax.annotate('Outlet remains outside canal\n2 mm minimum gap to verify',xy=(0,-10),xytext=(28,-28),arrowprops={'arrowstyle':'->','color':INK},fontsize=11)
ax.set(xlim=(-30,89),ylim=(-43,46));ax.set_aspect('equal');ax.axis('off');fig.text(.08,.94,'PEBBLE / Proposed placement',fontsize=23,weight='bold');fig.text(.08,.89,'Schematic ear + CAD projection. Not a scan, fit simulation, or photograph.',fontsize=10);fig.text(.08,.05,'Appearance target: matte stone / charcoal • chunky at the earbud scale, not over-ear scale\nA phone image does not establish depth, canal clearance, or safe retention.',fontsize=10)
fig.savefig(OUT/'placement-schematic.png',dpi=180);plt.close(fig)
print('Rendered five CAD/schematic figures.')
