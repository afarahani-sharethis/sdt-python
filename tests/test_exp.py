# -*- coding: utf-8 -*-
import unittest
import os
import pickle

import pandas as pd
import numpy as np

import sdt.exp_fit


path, f = os.path.split(os.path.abspath(__file__))
data_path = os.path.join(path, "data_exp")


class TestOdeSolver(unittest.TestCase):
    def setUp(self):
        legendre_order = 20
        num_exp = 2
        self.solver = sdt.exp_fit.ode_solver(legendre_order, num_exp)
        a = np.ones(num_exp + 1)
        self.residual_condition = np.zeros(num_exp)

        # first unit vector
        self.rhs = np.zeros(legendre_order)
        self.rhs[0] = 1

        self.solver.setCoeffs(a)

    def test_solve(self):
        # this was calculated using the original algorithm
        orig = np.load(os.path.join(data_path, "ode_solve.npy"))
        s = self.solver.solve(self.residual_condition, self.rhs)
        np.testing.assert_allclose(s, orig)

    def test_tangent(self):
        # this was calculated using the original algorithm
        orig = np.load(os.path.join(data_path, "ode_tangent.npy"))
        self.solver.solve(self.residual_condition, self.rhs)
        t = self.solver.tangent()
        np.testing.assert_allclose(t, orig)


class TestExpFit(unittest.TestCase):
    def setUp(self):
        self.alpha = 30  # offset
        self.beta = (-2, -4)  # amplitudes of exponents
        self.gamma = (-0.15, -0.02)  # exponential rates

        legendre_order = 20
        num_exp = len(self.gamma)
        stop_time = 10
        num_steps = 1000
        self.time = np.linspace(0, stop_time, num_steps)
        self.a0 = np.ones(num_exp + 1)

        self.fitter = sdt.exp_fit.expfit(self.time, legendre_order, num_exp)

    def test_opt_coeff(self):
        ydata = self.alpha
        for b, g in zip(self.beta, self.gamma):
            ydata += b*np.exp(g*self.time)

        a, b, g, aopt = self.fitter.getOptCoeffs(ydata, self.a0)
        orig = np.array((self.alpha, ) + self.beta + self.gamma)
        fitted = np.hstack((a, b, g))
        np.testing.assert_allclose(fitted, orig, rtol=1e-4)


if __name__ == "__main__":
    unittest.main()