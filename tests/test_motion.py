import unittest
import os
import pickle

import pandas as pd
import numpy as np
import pytest

from sdt import motion, io, testing
from sdt.motion import msd_cdf
from sdt.motion.msd import _displacements
from sdt.helper import numba


path, f = os.path.split(os.path.abspath(__file__))
data_path = os.path.join(path, "data_motion")


class TestDisplacements:
    """motion.msd._displacements"""
    @pytest.fixture
    def trc(self):
        frames = np.arange(20)
        dx = frames + 1
        dy = 2 * dx + 1
        ret = np.array([frames, np.cumsum(dx), np.cumsum(dy)]).T
        return ret

    @pytest.fixture
    def trc_disp_array(self):
        ret = np.full((19, 19, 2), np.NaN)
        for n in range(1, ret.shape[0] + 1):
            num_steps = ret.shape[1] - n + 1
            # First entry (Gaussian sum formula) - 1
            s = (n + 1) * (n + 2) // 2 - 1
            # Last entry
            l = s + (num_steps - 1) * n
            dx = np.linspace(s, l, num_steps)
            dy = 2 * dx + n
            ret[n - 1, :num_steps, 0] = dx
            ret[n - 1, :num_steps, 1] = dy
        return ret

    def test_displacements(self, trc, trc_disp_array):
        """Return array"""
        res = _displacements(trc, np.inf)
        np.testing.assert_allclose(res, trc_disp_array)

    def test_displacements_dict(self, trc, trc_disp_array):
        """Update dict"""
        prev_arr = np.array([1, 2, 3])
        disp_dict = {3: [prev_arr]}
        _displacements(trc, np.inf, disp_dict)

        np.testing.assert_equal(sorted(disp_dict.keys()),
                                np.arange(1, len(trc)))
        for k, v in disp_dict.items():
            if k == 3:
                assert len(v) == 2
                assert v[0] is prev_arr
            else:
                assert len(v) == 1

            np.testing.assert_allclose(
                v[-1],
                trc_disp_array[k-1, :trc_disp_array.shape[1] - k + 1, :])

    def test_gap(self, trc, trc_disp_array):
        """Missing frame"""
        trc = trc[trc[:, 0] != 3]
        res = _displacements(trc, np.inf)
        trc_disp_array[:, 3, :] = np.NaN
        trc_disp_array[0, 2, :] = np.NaN
        trc_disp_array[1, 1, :] = np.NaN
        trc_disp_array[2, 0, :] = np.NaN
        np.testing.assert_allclose(res, trc_disp_array)

    def test_max_lagtime(self, trc, trc_disp_array):
        """`max_lagtime` parameter, return array"""
        m = len(trc) // 2
        res = _displacements(trc, m)
        np.testing.assert_allclose(res, trc_disp_array[:m, ...])

    def test_max_lagtime_dict(self, trc, trc_disp_array):
        """`max_lagtime` parameter, update dict"""
        disp_dict = dict()
        m = len(trc) // 2
        _displacements(trc, m, disp_dict)

        np.testing.assert_equal(sorted(disp_dict.keys()), np.arange(1, m + 1))
        for k, v in disp_dict.items():
            np.testing.assert_allclose(
                v[0],
                trc_disp_array[k-1, :trc_disp_array.shape[1] - k + 1, :])


class TestMotion(unittest.TestCase):
    def setUp(self):
        self.traj1 = io.load(os.path.join(data_path, "B-1_000__tracks.mat"))
        self.traj2 = io.load(os.path.join(data_path, "B-1_001__tracks.mat"))

    def test_all_displacements(self):
        # orig columns: 0: lagt, 1: dx, 2: dy, 3: traj number
        orig = np.load(os.path.join(data_path, "displacements_B-1_000_.npy"))
        disp_dict = motion.all_displacements(self.traj1)

        max_lagt = int(np.max(orig[:, 0]))
        np.testing.assert_equal(len(disp_dict.keys()), max_lagt)
        np.testing.assert_equal(max(disp_dict.keys()), max_lagt)

        for lagt in range(1, max_lagt + 1):
            o = orig[orig[:, 0] == lagt]  # get_msd uses different sign
            o = np.sort(o[:, [1, 2]])  # get coordinate colmuns
            d = np.concatenate(disp_dict[lagt])
            d = d[~(np.isnan(d[:, 0]) | np.isnan(d[:, 1]))]  # remove NaNs
            d = np.sort(d)
            np.testing.assert_allclose(d, o, rtol=1e-5, atol=1e-5)

    def test_all_displacements_with_limit(self):
        # orig columns: 0: lagt, 1: dx, 2: dy, 3: traj number
        orig = np.load(os.path.join(data_path, "displacements_B-1_000_.npy"))

        max_lagt = 10
        disp_dict = motion.all_displacements(self.traj1, max_lagt)

        np.testing.assert_equal(len(disp_dict.keys()), max_lagt)

        for lagt in range(1, max_lagt + 1):
            o = orig[orig[:, 0] == lagt]  # get_msd uses different sign
            o = np.sort(o[:, [1, 2]])  # get coordinate colmuns
            d = np.concatenate(disp_dict[lagt])
            d = d[~(np.isnan(d[:, 0]) | np.isnan(d[:, 1]))]  # remove NaNs
            d = np.sort(d)
            np.testing.assert_allclose(d, o, rtol=1e-5, atol=1e-5)

    def test_all_square_displacements(self):
        orig = np.load(os.path.join(data_path, "square_displacements.npy"))
        with open(os.path.join(data_path, "all_displacements.pkl"), "rb") as f:
            disp_dict = pickle.load(f)

        sd_dict = motion.all_square_displacements(disp_dict, 1, 1)
        max_lagt = len(orig)
        assert(len(sd_dict) == max_lagt)

        for lagt in range(max_lagt):
            o = orig[lagt]
            if np.isscalar(o):
                # this comes from loading .mat files with squeeze_me=True
                o = np.array(o, ndmin=1)
            o = np.sort(o)
            d = np.sort(sd_dict[lagt + 1])
            np.testing.assert_allclose(d, o, rtol=1e-5, atol=1e-5)

    def test_emsd_from_square_displacements(self):
        # orig columns: 0: lagt [ms], msd, stderr, Qian error
        orig = np.load(os.path.join(data_path, "emsd_matlab.npy"))
        with open(os.path.join(data_path, "all_square_displacements.pkl"),
                  "rb") as f:
            sd_dict = pickle.load(f)
        emsd = motion.emsd_from_square_displacements(sd_dict)

        np.testing.assert_allclose(emsd["msd"], orig[:, 1], rtol=1e-5)
        # if there is only one data point, numpy std returns NaN, MATLAB 0
        # therefore remove affected lines
        valid_stderr = np.isfinite(emsd["stderr"].values)
        np.testing.assert_allclose(emsd["stderr"].dropna(),
                                   orig[valid_stderr, 2],
                                   rtol=1e-5)
        np.testing.assert_allclose(emsd["lagt"], orig[:, 0]/1000.)

    def test_emsd(self):
        orig = pd.read_hdf(os.path.join(data_path, "emsd.h5"), "emsd")
        e = motion.emsd([self.traj1, self.traj2], 1, 1)
        columns = ["msd", "stderr", "lagt"]
        np.testing.assert_allclose(e[columns], orig[columns])

    def test_imsd(self):
        # orig gives the same results as trackpy.imsd, except for one case
        # where trackpy is wrong when handling trajectories with missing
        # frames
        orig = pd.read_hdf(os.path.join(data_path, "imsd.h5"), "imsd")
        imsd = motion.imsd(self.traj1, 1, 1)
        np.testing.assert_allclose(imsd, orig)

    def test_msd(self):
        # orig gives the same results as trackpy.msd
        orig = pd.read_hdf(os.path.join(data_path, "msd.h5"), "msd")
        msd = motion.msd(self.traj1[self.traj1["particle"] == 0], 0.16, 100)
        np.testing.assert_allclose(msd, orig)


@pytest.fixture(params=["lsq", "weighted-lsq", "prony"])
def cdf_fit_method_name(request):
    return request.param


@pytest.fixture(params=["lsq", "weighted-lsq", "prony"])
def cdf_fit_function(request):
    if request.param == "lsq":
        return msd_cdf._fit_cdf_lsq, {"weighted": False}
    if request.param == "weighted-lsq":
        return msd_cdf._fit_cdf_lsq, {"weighted": True}
    if request.param == "prony":
        return msd_cdf._fit_cdf_prony, {"poly_order": 30}


class TestMsdCdf:
    msds = np.array([0.02, 0.08])
    t_max = 0.5
    f = 2 / 3
    lagt = 0.01

    def pdf(self, x):
        return (self.f / self.msds[0] * np.exp(-x / self.msds[0]) +
                (1 - self.f) / self.msds[1] * np.exp(-x / self.msds[1]))

    def cdf(self, x):
        return (1 - self.f * np.exp(-x / self.msds[0]) -
                (1 - self.f) * np.exp(-x / self.msds[1]))

    def test_fit_cdf(self, cdf_fit_function):
        x = np.logspace(-5, 0.5, 100)
        b, l = cdf_fit_function[0](x, self.cdf(x), 2, **(cdf_fit_function[1]))

        np.testing.assert_allclose(sorted(b), sorted([-self.f, -1 + self.f]),
                                   atol=5e-3)
        np.testing.assert_allclose(sorted(-1/l), sorted(self.msds),
                                   atol=2e-3)

    def test_emsd_from_square_displacements_cdf(self, cdf_fit_method_name):
        """motion.emsd_from_square_displacements_cdf"""
        sd_dict = {self.lagt: testing.dist_sample(self.pdf, (0, self.t_max),
                                                  10000)}
        e = motion.emsd_from_square_displacements_cdf(
            sd_dict, method=cdf_fit_method_name)
        for e_, m, f_ in zip(e, self.msds, [self.f, (1 - self.f)]):
            assert e_.loc[self.lagt, "lagt"] == self.lagt
            assert e_.loc[self.lagt, "msd"] == pytest.approx(m, abs=0.003)
            assert e_.loc[self.lagt, "fraction"] == pytest.approx(f_, abs=0.02)

    def test_emsd_cdf(self, cdf_fit_method_name):
        px_size = 0.1
        msds = testing.dist_sample(self.pdf, (0, self.t_max), 10000)
        trc = pd.DataFrame(np.cumsum(np.sqrt(msds))[:, None], columns=["x"])
        trc["x"] /= px_size
        trc["y"] = 0
        trc["frame"] = np.arange(len(trc))
        trc["particle"] = 0

        e = motion.emsd_cdf(trc, px_size, 1/self.lagt,
                            method=cdf_fit_method_name)

        for e_, m, f_ in zip(e, self.msds, [self.f, (1 - self.f)]):
            assert e_.loc[self.lagt, "lagt"] == self.lagt
            assert e_.loc[self.lagt, "msd"] == pytest.approx(m, abs=0.003)
            assert e_.loc[self.lagt, "fraction"] == pytest.approx(f_, abs=0.02)


class TestFitMsd(unittest.TestCase):
    def test_fit_msd_matlab(self):
        """motion.fit_msd: Regression test against MATLAB msdplot"""
        # 2 lags
        orig_D_2 = 0.523933764304220
        orig_pa_2 = -np.sqrt(0.242600359795181/4)
        # 5 lags
        orig_D_5 = 0.530084611225235
        orig_pa_5 = -np.sqrt(0.250036294078863/4)

        emsd = pd.read_hdf(os.path.join(data_path, "emsd.h5"), "emsd")

        D_2, pa_2 = motion.fit_msd(emsd, max_lagtime=2)
        D_5, pa_5 = motion.fit_msd(emsd, max_lagtime=5)

        np.testing.assert_allclose(D_2, orig_D_2, rtol=1e-5)
        np.testing.assert_allclose(pa_2, orig_pa_2, rtol=1e-5)
        np.testing.assert_allclose(D_5, orig_D_5, rtol=1e-5)
        np.testing.assert_allclose(pa_5, orig_pa_5, rtol=1e-5)

    def test_fit_msd(self):
        """motion.fit_msd: simple data"""
        lagts = np.arange(1, 11)
        msds = np.arange(2, 12)
        d_exp, pa_exp = 0.25, 0.5
        emsd = pd.DataFrame(dict(lagt=lagts, msd=msds))
        d2, pa2 = motion.fit_msd(emsd, max_lagtime=2)
        d5, pa5 = motion.fit_msd(emsd, max_lagtime=5)
        np.testing.assert_allclose([d2, pa2], [d_exp, pa_exp])
        np.testing.assert_allclose([d5, pa5], [d_exp, pa_exp])

    def test_fit_msd_neg(self):
        """motion.fit_msd: simple data, negative intercept"""
        lagts = np.arange(1, 11)
        msds = np.arange(0, 10)
        d_exp, pa_exp = 0.25, -0.5
        emsd = pd.DataFrame(dict(lagt=lagts, msd=msds))
        d2, pa2 = motion.fit_msd(emsd, max_lagtime=2)
        d5, pa5 = motion.fit_msd(emsd, max_lagtime=5)
        np.testing.assert_allclose([d2, pa2], [d_exp, pa_exp])
        np.testing.assert_allclose([d5, pa5], [d_exp, pa_exp])

    def test_fit_msd_anomalous(self):
        """motion.fit_msd: anomalous diffusion"""
        t = np.arange(0.01, 0.205, 0.01)
        d_e = 0.7
        pa_e = 0.03
        alpha_e = 1.1
        msd = 4 * d_e * t**alpha_e + 4 * pa_e**2
        emsd = pd.DataFrame({"lagt": t, "msd": msd})

        d, pa, a = motion.fit_msd(emsd, model="anomalous")

        np.testing.assert_allclose([d, pa, a], [d_e, pa_e, alpha_e])

    def test_fit_msd_anomalous_neg(self):
        """motion.fit_msd: anomalous diffusion, negative intercept"""
        t = np.arange(0.01, 0.205, 0.01)
        d_e = 0.7
        pa_e = 0.03
        alpha_e = 1.1
        msd = 4 * d_e * t**alpha_e - 4 * pa_e**2
        emsd = pd.DataFrame({"lagt": t, "msd": msd})

        d, pa, a = motion.fit_msd(emsd, model="anomalous")

        np.testing.assert_allclose([d, pa, a], [d_e, -pa_e, alpha_e])

    def test_fit_msd_anomalous_texp(self):
        """motion.fit_msd: anomalous diffusion, exposure time correction"""
        t = np.arange(0.01, 0.205, 0.01)
        d_e = 0.7
        pa_e = 0.03
        alpha_e = 1.1
        t_exp = 0.003

        t_app = motion.exposure_time_corr(t, alpha_e, t_exp)
        msd = 4 * d_e * t_app**alpha_e + 4 * pa_e**2
        emsd = pd.DataFrame({"lagt": t, "msd": msd})

        d, pa, a = motion.fit_msd(emsd, exposure_time=t_exp, model="anomalous")

        np.testing.assert_allclose([d, pa, a], [d_e, pa_e, alpha_e])

    def test_fit_msd_exposure_corr(self):
        """motion.fit_msd: exposure time correction"""
        lagts = np.arange(1, 11)
        msds = np.arange(1, 11)
        emsd = pd.DataFrame(dict(lagt=lagts, msd=msds))
        t = 0.3
        d_exp = 0.25
        pa_exp = np.sqrt(0.1/4)  # shift by t/3 to the left with slope 1
        d, pa = motion.fit_msd(emsd, exposure_time=t)

        np.testing.assert_allclose([d, pa], [d_exp, pa_exp])


class TestExposureTimeCorr(unittest.TestCase):
    def setUp(self):
        self.t = np.linspace(0.01, 0.1, 10)

    def test_numeric_alpha1(self):
        """motion.exposure_time_corr: alpha = 1, numeric"""
        for t_exp in (1e-3, 2e-3, 5e-3, 1e-2):
            t_app = motion.exposure_time_corr(self.t, 1, t_exp,
                                              force_numeric=True)
            np.testing.assert_allclose(t_app, self.t - t_exp / 3, rtol=1e-4)

    def test_analytic_alpha1(self):
        """motion.exposure_time_corr: alpha = 1, analytic"""
        for t_exp in (1e-3, 2e-3, 5e-3, 1e-2):
            t_app = motion.exposure_time_corr(self.t, 1, t_exp,
                                              force_numeric=False)
            np.testing.assert_allclose(t_app, self.t - t_exp / 3)

    def test_numeric_alpha2(self):
        """motion.exposure_time_corr: alpha = 2, numeric"""
        for t_exp in (1e-3, 2e-3, 5e-3, 1e-2):
            t_app = motion.exposure_time_corr(self.t, 2, t_exp,
                                              force_numeric=True)
            np.testing.assert_allclose(t_app, self.t)

    def test_analytic_alpha2(self):
        """motion.exposure_time_corr: alpha = 2, analytic"""
        for t_exp in (1e-3, 2e-3, 5e-3, 1e-2):
            t_app = motion.exposure_time_corr(self.t, 2, t_exp,
                                              force_numeric=False)
            np.testing.assert_allclose(t_app, self.t)

    def test_numeric_texp0(self):
        """motion.exposure_time_corr: exposure_time = 0, numeric"""
        for a in np.linspace(0.1, 2., 20):
            t_app = motion.exposure_time_corr(self.t, a, 0, force_numeric=True)
            np.testing.assert_allclose(t_app, self.t)

    def test_analytic_texp0(self):
        """motion.exposure_time_corr: exposure_time = 0, analytic"""
        for a in np.linspace(0.1, 2., 20):
            t_app = motion.exposure_time_corr(self.t, a, 0,
                                              force_numeric=False)
            np.testing.assert_allclose(t_app, self.t)

    def test_alpha05(self):
        """motion.exposure_time_corr: alpha = 0.5"""
        t_app = motion.exposure_time_corr(self.t, 0.5, 0.005)
        # Result comes from a very simple implemenation which should not be
        # wrong
        r = [0.061779853782074214, 0.10355394844441726, 0.13542268602111515,
             0.1622529550167944, 0.18587833963804673, 0.2072316891474639,
             0.22686517396545597, 0.24513786608867294, 0.2622988847186261,
             0.27852947267829076]
        r = np.array(r)**2
        np.testing.assert_allclose(t_app, r)


class TestMsdTheoretic(unittest.TestCase):
    def setUp(self):
        self.t = np.linspace(0.01, 0.1, 10)

    def test_call(self):
        """motion.msd_theoretic"""
        d = 0.1
        alpha = 1
        t_exp = 0.003
        pa = 0.05
        for f in (-1, 1):
            m = motion.msd_theoretic(self.t, d, f * pa, exposure_time=t_exp)
            np.testing.assert_allclose(
                m, 4 * d * (self.t - t_exp/3) + f * 4 * pa**2)


class TestFindImmobilizations(unittest.TestCase):
    def setUp(self):
        tracks1 = pd.DataFrame(
            np.array([10, 10, 10, 10, 11, 11, 11, 12, 12, 12]),
            columns=["x"])
        tracks1["y"] = 20
        tracks1["particle"] = 0
        tracks1["frame"] = np.arange(len(tracks1))
        tracks2 = tracks1.copy()
        tracks2["particle"] = 1
        self.tracks = pd.concat((tracks1, tracks2), ignore_index=True)

        self.count = np.array([[1, 2, 3, 4, 5, 6, 7, 7, 7, 7],
                               [0, 1, 2, 3, 4, 5, 6, 6, 6, 9],
                               [0, 0, 1, 2, 3, 4, 5, 5, 7, 6],
                               [0, 0, 0, 1, 2, 3, 4, 5, 5, 6],
                               [0, 0, 0, 0, 1, 2, 3, 4, 5, 6],
                               [0, 0, 0, 0, 0, 1, 2, 3, 4, 5],
                               [0, 0, 0, 0, 0, 0, 1, 2, 3, 4],
                               [0, 0, 0, 0, 0, 0, 0, 1, 2, 3],
                               [0, 0, 0, 0, 0, 0, 0, 0, 1, 2],
                               [0, 0, 0, 0, 0, 0, 0, 0, 0, 1]])

    def test_count_immob_python(self):
        # Test the _count_immob_python function
        loc = self.tracks.loc[self.tracks["particle"] == 0, ["x", "y"]]
        old_err = np.seterr(invalid="ignore")
        res = motion.immobilization._count_immob_python(loc.values.T, 1)
        np.seterr(**old_err)
        np.testing.assert_allclose(res, self.count)

    @unittest.skipUnless(numba.numba_available, "numba not numba_available")
    def test_count_immob_numba(self):
        # Test the _count_immob_numba function
        loc = self.tracks.loc[self.tracks["particle"] == 0, ["x", "y"]]
        res = motion.immobilization._count_immob_numba(loc.values.T, 1)
        np.testing.assert_allclose(res, self.count)

    def test_overlapping(self):
        # Test where multiple immobilization candidates overlap in their frame
        # range
        orig = self.tracks.copy()
        immob = np.array([1] + [0]*9 + [3] + [2]*9)
        orig["immob"] = immob
        motion.find_immobilizations(self.tracks, 1, 0)
        np.testing.assert_allclose(self.tracks, orig)

    def test_longest_only(self):
        # Test `longest_only` option
        orig = self.tracks.copy()
        immob = np.array([-1] + [0]*9 + [-1] + [1]*9)
        orig["immob"] = immob
        motion.find_immobilizations(
             self.tracks, 1, 2, longest_only=True, label_mobile=False)
        np.testing.assert_allclose(self.tracks, orig)

    def test_label_mobile(self):
        # Test `label_only` option
        orig = self.tracks.copy()
        immob = np.array([-2] + [0]*9 + [-3] + [1]*9)
        orig["immob"] = immob
        motion.find_immobilizations(
             self.tracks, 1, 2, longest_only=True, label_mobile=True)
        np.testing.assert_allclose(self.tracks, orig)

    def test_atol(self):
        # Test `atol` parameter
        self.tracks.loc[3, "x"] = 9.9
        orig = self.tracks.copy()
        immob = np.array([0]*8 + [-1]*2 + [-1]*1 + [1]*9)
        orig["immob"] = immob
        motion.find_immobilizations(
             self.tracks, 1, 2, longest_only=True, label_mobile=False, atol=1,
             rtol=np.inf)
        np.testing.assert_allclose(self.tracks, orig)

    def test_rtol(self):
        # Test `rtol` parameter
        self.tracks.loc[3, "x"] = 9.9
        orig = self.tracks.copy()
        immob = np.array([0]*8 + [-1]*2 + [-1]*1 + [1]*9)
        orig["immob"] = immob
        motion.find_immobilizations(
             self.tracks, 1, 2, longest_only=True, label_mobile=False,
             atol=np.inf, rtol=0.125)
        np.testing.assert_allclose(self.tracks, orig)


class TestFindImmobilizationsInt(unittest.TestCase):
    def setUp(self):
        tracks1 = pd.DataFrame(
            np.array([10, 10, 10, 10, 11, 11, 11, 12, 12, 12]),
            columns=["x"])
        tracks1["y"] = 20
        tracks1["particle"] = 0
        tracks1["frame"] = np.arange(len(tracks1))
        tracks2 = tracks1.copy()
        tracks2["particle"] = 1
        self.tracks = pd.concat((tracks1, tracks2))

    def test_overlapping(self):
        # Test where multiple immobilization candidates overlap in their frame
        # range
        orig = self.tracks.copy()
        immob = np.array([0]*7 + [1]*3 + [2]*7 + [3]*3)
        orig["immob"] = immob
        motion.find_immobilizations_int(self.tracks, 1, 2, label_mobile=False)
        np.testing.assert_allclose(self.tracks, orig)

    def test_longest_only(self):
        # Test `longest_only` option
        orig = self.tracks.copy()
        immob = np.array([0]*7 + [-1]*3 + [1]*7 + [-1]*3)
        orig["immob"] = immob
        motion.find_immobilizations_int(
             self.tracks, 1, 2, longest_only=True, label_mobile=False)
        np.testing.assert_allclose(self.tracks, orig)

    def test_label_mobile(self):
        # Test `label_only` option
        orig = self.tracks.copy()
        immob = np.array([0]*7 + [-2]*3 + [1]*7 + [-3]*3)
        orig["immob"] = immob
        motion.find_immobilizations_int(
             self.tracks, 1, 2, longest_only=True, label_mobile=True)
        np.testing.assert_allclose(self.tracks, orig)

    def test_find_diag_blocks(self):
        a = np.array([[1, 1, 1, 0, 1, 1, 0, 0, 0, 0, 0],
                      [1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 0],
                      [1, 1, 1, 1, 1, 1, 1, 0, 0, 0, 0],
                      [0, 1, 1, 1, 1, 1, 1, 1, 0, 0, 0],
                      [1, 1, 1, 1, 1, 1, 1, 0, 0, 0, 0],
                      [1, 1, 1, 1, 1, 1, 1, 0, 0, 0, 0],
                      [0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 0],
                      [0, 1, 0, 1, 0, 0, 1, 1, 1, 1, 1],
                      [0, 1, 0, 0, 0, 0, 1, 1, 1, 1, 1],
                      [0, 1, 0, 0, 0, 0, 1, 1, 1, 1, 1],
                      [0, 0, 0, 0, 0, 0, 0, 1, 1, 1, 1]])
        start, end = motion.immobilization._find_diag_blocks(a)
        np.testing.assert_equal(start, [0, 1, 6, 7])
        np.testing.assert_equal(end, [2, 6, 9, 10])


class TestLabelMobile(unittest.TestCase):
    def setUp(self):
        self.immob = np.array([-1, -1, 0, 0, -1, -1, -1, -1, 1, -1, 2])
        self.expected = np.array([-2, -2, 0, 0, -3, -3, -3, -3, 1, -4, 2])

    def test_label_mob_python(self):
        # Test the `_label_mob_python` function
        motion.immobilization._label_mob_python(self.immob, -2)
        np.testing.assert_equal(self.immob, self.expected)

    @unittest.skipUnless(numba.numba_available, "numba not numba_available")
    def test_label_mob_numba(self):
        # Test the `_label_mob_python` function
        motion.immobilization._label_mob_numba(self.immob, -2)
        np.testing.assert_equal(self.immob, self.expected)

    def test_label_mobile(self):
        d = np.array([np.zeros(len(self.immob)),
                      np.zeros(len(self.immob)),
                      [0]*6 + [1]*(len(self.immob)-6)]).T
        df = pd.DataFrame(d, columns=["x", "y", "particle"])
        orig = df.copy()
        orig["immob"] = [-2, -2, 0, 0, -3, -3, -4, -4, 1, -5, 2]
        df["immob"] = self.immob
        motion.label_mobile(df)
        np.testing.assert_equal(df.values, orig.values)

if __name__ == "__main__":
    unittest.main()
