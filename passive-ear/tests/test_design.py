"""Geometric tests only — NOT clinical, material, or acoustic validation."""
import importlib.util
import json
from pathlib import Path
import unittest
import numpy as np
import trimesh
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('build',ROOT/'tools/build.py'); build=importlib.util.module_from_spec(spec);spec.loader.exec_module(build)
DEFAULT=json.loads((ROOT/'examples/default-fit.json').read_text())
class DesignTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.shell,cls.cradle=build.make(DEFAULT)
    def test_shell_closed_positive_single_solid(self):
        self.assertTrue(self.shell.is_watertight);self.assertTrue(self.shell.is_volume);self.assertEqual(len(self.shell.split()),1)
    def test_cradle_closed_positive_single_solid(self):
        self.assertTrue(self.cradle.is_watertight);self.assertTrue(self.cradle.is_volume);self.assertEqual(len(self.cradle.split()),1)
    def test_default_envelope(self): np.testing.assert_allclose(self.shell.extents,[18,24,12],atol=.001)
    def test_no_canal_nozzle(self): self.assertAlmostEqual(float(self.shell.bounds[0,2]),-6,places=5)
    def test_left_mirror(self):
        left,_=build.make(dict(DEFAULT,side='left'));self.assertAlmostEqual(left.volume,self.shell.volume,places=3)
        np.testing.assert_allclose(left.center_mass,self.shell.center_mass*[-1,1,1],atol=.001)
    def test_guardrails(self):
        for h,w in [(23,22),(33,22),(28,18),(28,26),(float('nan'),22),(28,float('inf'))]:
            with self.assertRaises(ValueError):build.parameters(dict(DEFAULT,concha_height_mm=h,concha_width_mm=w))
        with self.assertRaises(ValueError):build.parameters(dict(DEFAULT,side='unknown'))
    def test_extreme_sizes(self):
        for h,w in [(24,19),(32,25)]:
            s,c=build.make(dict(DEFAULT,concha_height_mm=h,concha_width_mm=w));self.assertTrue(s.is_volume);self.assertTrue(c.is_volume)
            np.testing.assert_allclose(s.extents,[w-4,h-4,12],atol=.002)
    def test_bore_containment_sampled(self):
        # Every sampled inner point stays within the outer ellipse. Not a shortest-distance wall certification.
        t=np.linspace(0,2*np.pi,256)
        for z in np.linspace(-6,6,97):
            cx,cy,rx,ry=build.inside(z);_,_,ox,oy=build.outside(z)
            self.assertLess(np.max(((cx+rx*np.cos(t))/ox)**2+((cy+ry*np.sin(t))/oy)**2),.86)
    def test_bore_center_not_blocked(self):
        # Sections form a single ring each; aperture center must remain inside inner polygon.
        for z in np.linspace(-6,6,49):
            _,_,rx,ry=build.inside(z);self.assertGreater(min(rx,ry),2.5)
        self.assertEqual(self.shell.euler_number,0) # one through-hole (torus topology)
    def test_expected_collar_interference(self):
        inter=trimesh.boolean.intersection([self.shell,self.cradle],engine='manifold')
        self.assertGreater(inter.volume,10);self.assertLess(inter.volume,100)
    def test_exported_files(self):
        for name in ['shell','cradle','shell-section']:
            m=trimesh.load(ROOT/f'cad/{name}.stl');self.assertTrue(m.is_volume)
        r=json.loads((ROOT/'cad/build-report.json').read_text());self.assertFalse(r['minimum_wall_certified'])
    def test_scad_contains_customization(self):
        source=(ROOT/'cad/pebble.scad').read_text()
        for token in ['concha_height_mm','concha_width_mm','side','polyhedron','section','cradle','BENCH ONLY']:self.assertIn(token,source)
if __name__=='__main__':unittest.main()
