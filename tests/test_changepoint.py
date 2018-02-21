import unittest
import os

import numpy as np
import scipy
import scipy.stats

from sdt.changepoint import bayes_offline as offline
from sdt.changepoint import bayes_online as online


path, f = os.path.split(os.path.abspath(__file__))
data_path = os.path.join(path, "data_changepoint")


class TestOfflineObs(unittest.TestCase):
    def _test_univ(self, func, res):
        a = np.atleast_2d(np.arange(10000)).T
        r = func(a, 10, 1000)
        self.assertAlmostEqual(r, res)

    def _test_multiv(self, func, res):
        a = np.arange(10000).reshape((-1, 2))
        r = func(a, 10, 1000)
        self.assertAlmostEqual(r, res)

    def test_gaussian_obs_univ(self):
        """changepoint.offline.gaussian_obs_likelihood, univariate

        This is a regression test against the output of the original
        implementation.
        """
        self._test_univ(offline.gaussian_obs_likelihood,
                        -7011.825860906335)

    def test_gaussian_obs_multiv(self):
        """changepoint.offline.gaussian_obs_likelihood, multivariate

        This is a regression test against the output of the original
        implementation.
        """
        self._test_multiv(offline.gaussian_obs_likelihood,
                          -16386.465097707242)

    def test_ifm_obs_univ(self):
        """changepoint.offline.ifm_obs_likelihood, univariate

        This is a regression test against the output of the original
        implementation.
        """
        self._test_univ(offline.ifm_obs_likelihood,
                        -7716.5452917994835)

    def test_ifm_obs_multiv(self):
        """changepoint.offline.ifm_obs_likelihood, multivariate

        This is a regression test against the output of the original
        implementation.
        """
        self._test_multiv(offline.ifm_obs_likelihood,
                          -16808.615307987133)

    def test_fullcov_obs_univ(self):
        """changepoint.offline.fullconv_obs_likelihood, univariate

        This is a regression test against the output of the original
        implementation.
        """
        self._test_univ(offline.fullcov_obs_likelihood,
                        -7716.5452917994835)

    def test_fullcov_obs_multiv(self):
        """changepoint.offline.fullconv_obs_likelihood, multivariate

        This is a regression test against the output of the original
        implementation.
        """
        self._test_multiv(offline.fullcov_obs_likelihood,
                          -13028.349084233618)
    def test_fullcov_obs_univ_numba(self):
        """changepoint.offline.fullconv_obs_likelihood, univariate, numba

        This is a regression test against the output of the original
        implementation.
        """
        self._test_univ(offline.fullcov_obs_likelihood_numba,
                        -7716.5452917994835)

    def test_fullcov_obs_multiv_numba(self):
        """changepoint.offline.fullconv_obs_likelihood, multivariate, numba

        This is a regression test against the output of the original
        implementation.
        """
        self._test_multiv(offline.fullcov_obs_likelihood_numba,
                          -13028.349084233618)


class TestOfflinePriors(unittest.TestCase):
    def test_const_prior(self):
        """changepoint.offline.const_prior"""
        self.assertAlmostEqual(offline.const_prior(4, np.empty(99), []), 0.01)

    def test_geometric_prior(self):
        """changepoint.offline.geometric_prior"""
        self.assertAlmostEqual(offline.geometric_prior(4, [], [0.1]),
                               0.9**3 * 0.1)

    def test_neg_binomial_prior(self):
        """changepoint.offline.neg_binomial_prior"""
        t = 4
        k = 100
        p = 0.1
        self.assertAlmostEqual(offline.neg_binomial_prior(t, [], [k, p]),
                               (scipy.misc.comb(t - k, k - 1) * p**k *
                                (1 - p)**(t - k)))


class TestOfflineDetection(unittest.TestCase):
    def setUp(self):
        self.rand_state = np.random.RandomState(0)
        self.data = np.concatenate([self.rand_state.normal(100, 10, 30),
                                    self.rand_state.normal(30, 5, 40),
                                    self.rand_state.normal(50, 20, 20)])
        self.data2 = np.concatenate([self.rand_state.normal(40, 10, 30),
                                     self.rand_state.normal(200, 5, 40),
                                     self.rand_state.normal(80, 20, 20)])
        self.Finder = offline.BayesOfflinePython

    def test_offline_changepoint_gauss_univ(self):
        """changepoint.offline.offline_changepoint_detection: Gauss, univariate

        This is a regression test against the output of the original
        implementation.
        """
        f = self.Finder("const", "gauss")
        prob, Q, P, Pcp = f.find_changepoints(
            self.data, truncate=-20, full_output=True)
        orig = np.load(os.path.join(data_path, "offline_gauss_univ.npz"))
        np.testing.assert_allclose(Q, orig["Q"])
        np.testing.assert_allclose(P, orig["P"])
        np.testing.assert_allclose(Pcp, orig["Pcp"], rtol=1e-6)

    def test_offline_changepoint_full_multiv(self):
        """changepoint.offline.offline_changepoint_detection: full cov., multiv

        This is a regression test against the output of the original
        implementation.
        """
        f = self.Finder("const", "full_cov")
        prob, Q, P, Pcp = f.find_changepoints(
            np.array([self.data, self.data2]), truncate=-20,
            full_output=True)
        orig = np.load(os.path.join(data_path, "offline_full_multiv.npz"))
        np.testing.assert_allclose(Q, orig["Q"])
        np.testing.assert_allclose(P, orig["P"])
        np.testing.assert_allclose(Pcp, orig["Pcp"], rtol=1e-6)


class TestOfflineDetectionNumba(TestOfflineDetection):
    def setUp(self):
        super().setUp()
        self.Finder = offline.BayesOfflineNumba

    def test_offline_changepoint_gauss_univ(self):
        """changepoint.offline.offline_changepoint_detection: Gauss, numba

        This is a regression test against the output of the original
        implementation.
        """
        super().test_offline_changepoint_gauss_univ()

    def test_offline_changepoint_full_multiv(self):
        """changepoint.offline.offline_changepoint_detection: full cov., numba

        This is a regression test against the output of the original
        implementation.
        """
        super().test_offline_changepoint_full_multiv()


class TestOnlineHazard(unittest.TestCase):
    def test_constant_hazard(self):
        """changepoint.online.constant_hazard"""
        lam = 2
        a = np.arange(10).reshape((2, -1))
        h = online.constant_hazard(a, np.array([lam]))
        np.testing.assert_allclose(h, 1/lam * np.ones_like(a))


class TestOnlineStudentTPython(unittest.TestCase):
    def setUp(self):
        self.rand_state = np.random.RandomState(0)
        self.data = np.concatenate([self.rand_state.normal(100, 10, 30),
                                    self.rand_state.normal(30, 5, 40),
                                    self.rand_state.normal(50, 20, 20)])
        self.t_params = 0.1, 0.01, 1, 0
        self.t = online.StudentTPython(*self.t_params)

    def test_updatetheta(self):
        """changepoint.online.StudentTPython.update_theta

        This is a regression test against the output of the original
        implementation.
        """
        self.t.update_theta(self.data[0])
        np.testing.assert_allclose(self.t.alpha, [0.1, 0.6])
        np.testing.assert_allclose(self.t.beta,
                                   [1.00000000e-02, 3.45983319e+03])
        np.testing.assert_allclose(self.t.kappa, [1., 2.])
        np.testing.assert_allclose(self.t.mu, [0., 58.82026173])

    def test_pdf(self):
        """changepoint.online.StudentTPython.pdf

        This is a regression test against the output of the original
        implementation.
        """
        self.t.update_theta(self.data[0])
        r = self.t.pdf(self.data[0])
        np.testing.assert_allclose(r, [0.0002096872696608132,
                                       0.0025780687692425132])

    def test_reset(self):
        """changepoint.online.StudentTPython.reset"""
        self.t.update_theta(self.data[0])
        self.t.update_theta(self.data[1])
        self.t.reset()

        np.testing.assert_equal(self.t.alpha, [self.t.alpha0])
        np.testing.assert_equal(self.t.beta, [self.t.beta0])
        np.testing.assert_equal(self.t.kappa, [self.t.kappa0])
        np.testing.assert_equal(self.t.mu, [self.t.mu0])


class TestOnlineStudentTNumba(TestOnlineStudentTPython):
    def setUp(self):
        super().setUp()
        self.t = online.StudentTNumba(*self.t_params)

    def test_t_pdf(self):
        """changepoint.online.t_pdf"""
        t_params = dict(x=10, df=2, loc=3, scale=2)
        self.assertAlmostEqual(online.t_pdf(**t_params),
                               scipy.stats.t.pdf(**t_params))

    def test_updatetheta(self):
        """changepoint.online.StudentTNumba.update_theta

        This is a regression test against the output of the original
        implementation.
        """
        super().test_updatetheta()

    def test_pdf(self):
        """changepoint.online.StudentTNumba.pdf

        This is a regression test against the output of the original
        implementation.
        """
        super().test_pdf()

    def test_reset(self):
        """changepoint.online.StudentTNumba.reset"""
        super().test_reset()


class TestOnlineFinderPython(unittest.TestCase):
    def setUp(self):
        self.rand_state = np.random.RandomState(0)
        self.data = np.concatenate([self.rand_state.normal(100, 10, 30),
                                    self.rand_state.normal(30, 5, 40),
                                    self.rand_state.normal(50, 20, 20)])
        self.h_params = np.array([250])
        self.t_params = np.array([0.1, 0.01, 1, 0])
        self.finder = online.BayesOnlinePython("const", "student_t",
                                               self.h_params, self.t_params)

        self.orig = np.load(os.path.join(data_path, "online.npz"))["R"]

    def test_reset(self):
        """changepoint.online.OnlineFinderPython.reset"""
        self.finder.update(self.data[0])
        self.finder.update(self.data[1])
        self.finder.reset()

        np.testing.assert_equal(self.finder.probabilities, [np.array([1])])

    def test_update(self):
        """changepoint.online.OnlineFinderPython.update

        This is a regression test against the output of the original
        implementation.
        """
        self.finder.update(self.data[0])
        self.finder.update(self.data[1])

        np.testing.assert_allclose(self.finder.probabilities[0], [1])
        np.testing.assert_allclose(self.finder.probabilities[1],
                                   self.orig[:2, 1])
        np.testing.assert_allclose(self.finder.probabilities[2],
                                   self.orig[:3, 2])

    def test_find_changepoints(self):
        """changepoint.online.OnlineFinderPython.find_changepoints

        This is a regression test against the output of the original
        implementation.
        """
        self.finder.find_changepoints(self.data)
        R = np.zeros((len(self.data) + 1,) * 2)
        for i, p in enumerate(self.finder.probabilities):
            R[:i+1, i] = p
        np.testing.assert_allclose(R, self.orig)

    def test_get_probabilities(self):
        """changepoint.online.OnlineFinderPython.get_probabilities"""
        self.finder.find_changepoints(self.data)
        np.testing.assert_allclose(self.finder.get_probabilities(10),
                                   self.orig[10, 10:-1])


class TestOnlineFinderNumba(TestOnlineFinderPython):
    def setUp(self):
        super().setUp()
        self.finder = online.BayesOnlineNumba("const", "student_t",
                                              self.h_params, self.t_params)

    def test_reset(self):
        """changepoint.online.OnlineFinderNumba.reset"""
        super().test_reset()

    def test_update(self):
        """changepoint.online.OnlineFinderNumba.update

        This is a regression test against the output of the original
        implementation.
        """
        super().test_update()

    def test_find_changepoints(self):
        """changepoint.online.OnlineFinderNumba.find_changepoints

        This is a regression test against the output of the original
        implementation.
        """
        super().test_find_changepoints()

    def test_get_probabilites(self):
        """changepoint.online.OnlineFinderNumba.get_probabilities"""
        super().test_get_probabilities()


if __name__ == "__main__":
    unittest.main()