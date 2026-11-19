"""Independent checks of the activation formulas and temporal LP mechanism."""
import unittest

import mujoco
import numpy as np

from check_temporal_margin import margin
from validate_activation_dynamics import endpoints


class TemporalAnalysisTests(unittest.TestCase):
    def test_endpoint_equations_match_native_mujoco(self):
        grid = np.linspace(0, 1, 101)[:, None]
        tau = np.array([[0.01, 0.04, 0.0]])
        low, high, _, _ = endpoints(grid, tau, 0.002)
        for index, a in enumerate(grid[:, 0]):
            self.assertAlmostEqual(low[index, 0], a + 0.002 * mujoco.mju_muscleDynamics(0, a, tau[0]), places=14)
            self.assertAlmostEqual(high[index, 0], a + 0.002 * mujoco.mju_muscleDynamics(1, a, tau[0]), places=14)

    def test_tangents_are_sufficient_bounds_on_entire_domain(self):
        grid = np.linspace(0, 1, 1001)[:, None]
        tau = np.array([[0.01, 0.04, 0.0]])
        low, high, _, _ = endpoints(grid, tau, 0.002)
        for center in np.linspace(0, 1, 21):
            l, h, dl, dh = endpoints(np.array([[center]]), tau, 0.002)
            self.assertTrue(np.all(h + dh * (grid - center) <= high + 1e-14))
            self.assertTrue(np.all(l + dl * (grid - center) >= low - 1e-14))

    def test_two_point_margin_matches_analytic_solution(self):
        active = np.ones((2, 1, 1))
        target = np.array([[0.0], [1.0]])
        tau = np.array([[0.01, 0.04]])
        independent = margin(active, target, tau, 0.002, 1, None)
        temporal = margin(active, target, tau, 0.002, 1, 1.0)
        # Minimize e with a0<=e, a1>=1-e and a1<=0.6*a0+0.4.
        # Hence 1-e <= 0.6*e+0.4, giving e >= 0.375.
        self.assertAlmostEqual(independent['minimum_max_torque_error_Nm'], 0, places=12)
        self.assertAlmostEqual(temporal['minimum_max_torque_error_Nm'], 0.375, places=12)
        self.assertAlmostEqual(temporal['numerical_dual_lower_bound_Nm'], 0.375, places=12)


if __name__ == '__main__':
    unittest.main()
