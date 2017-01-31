# -*- coding: utf-8 -*-
import unittest
import os

import numpy as np
import pandas as pd
from scipy.stats import norm

import sdt.brightness
from sdt import brightness


path, f = os.path.split(os.path.abspath(__file__))
data_path = os.path.join(path, "data_brightness")
loc_path = os.path.join(path, "data_data")


class TestBrightness(unittest.TestCase):
    def setUp(self):
        # for raw image tests
        self.radius = 2
        self.bg_frame = 1
        self.pos1 = [30, 20]
        self.pos2 = [15, 10]

        bg_radius = self.radius + self.bg_frame
        self.feat1_img = np.full((2*bg_radius+1,)*2, 3.)
        self.feat2_img = np.full((2*bg_radius+1,)*2, 3.)
        idx = np.indices(self.feat1_img.shape)
        self.feat_mask = ((idx[0] >= self.bg_frame) &
                          (idx[0] <= 2*self.radius + self.bg_frame) &
                          (idx[1] >= self.bg_frame) &
                          (idx[1] <= 2*self.radius + self.bg_frame))

        self.feat1_img[:bg_radius, :bg_radius] = 4.
        self.feat2_img[:bg_radius, :bg_radius] = 4.
        self.feat1_img[self.feat_mask] = 10
        self.feat1_img[self.feat_mask] = 15

        self.bg = np.mean(self.feat1_img[~self.feat_mask])
        self.bg_median = np.median(self.feat1_img[~self.feat_mask])
        self.bg_dev = np.std(self.feat1_img[~self.feat_mask])

        self.mass1 = (np.sum(self.feat1_img[self.feat_mask]) -
                      self.bg*(2*self.radius + 1)**2)
        self.mass2 = (np.sum(self.feat2_img[self.feat_mask]) -
                      self.bg*(2*self.radius + 1)**2)
        self.mass1_median = (np.sum(self.feat1_img[self.feat_mask]) -
                             self.bg_median*(2*self.radius + 1)**2)

        self.signal1 = np.max(self.feat1_img[self.feat_mask]) - self.bg
        self.signal2 = np.max(self.feat2_img[self.feat_mask]) - self.bg

        self.signal1_median = (np.max(self.feat1_img[self.feat_mask]) -
                               self.bg_median)

        self.img = np.zeros((50, 50))
        self.img[self.pos1[1]-bg_radius:self.pos1[1]+bg_radius+1,
                 self.pos1[0]-bg_radius:self.pos1[0]+bg_radius+1] = \
            self.feat1_img
        self.img[self.pos2[1]-bg_radius:self.pos2[1]+bg_radius+1,
                 self.pos2[0]-bg_radius:self.pos2[0]+bg_radius+1] = \
            self.feat2_img

    def test_from_raw_image_single(self):
        res = sdt.brightness._from_raw_image_single(
            self.pos1, self.img, self.radius, self.bg_frame)
        np.testing.assert_allclose(
            np.array(res),
            np.array([self.signal1, self.mass1, self.bg, self.bg_dev]))

    def test_from_raw_image_single_median(self):
        res = sdt.brightness._from_raw_image_single(
            self.pos1, self.img, self.radius, self.bg_frame, np.median)
        np.testing.assert_allclose(
            np.array(res),
            np.array([self.signal1_median, self.mass1_median, self.bg_median,
                      self.bg_dev]))

    def test_from_raw_image(self):
        data = np.array([self.pos1, self.pos2])
        data = pd.DataFrame(data, columns=["x", "y"])
        data["frame"] = 0
        expected = data.copy()
        expected["signal"] = np.array([self.signal1, self.signal2])
        expected["mass"] = np.array([self.mass1, self.mass2])
        expected["bg"] = self.bg
        expected["bg_dev"] = self.bg_dev
        sdt.brightness.from_raw_image(data, [self.img], self.radius,
                                      self.bg_frame)
        np.testing.assert_allclose(data, expected)


class TestDistribution(unittest.TestCase):
    def setUp(self):
        self.masses = np.array([1000, 1000, 2000])
        self.most_probable = 1000
        self.peak_data = pd.DataFrame([[10, 10]]*3, columns=["x", "y"])
        self.peak_data["mass"] = self.masses

    def _calc_graph(self, smooth):
        absc = 5000
        x = np.arange(absc, dtype=float)
        m = self.peak_data.loc[0, "mass"]
        y = norm.pdf(x, m, smooth*np.sqrt(m))
        m = self.peak_data.loc[1, "mass"]
        y += norm.pdf(x, m, smooth*np.sqrt(m))
        m = self.peak_data.loc[2, "mass"]
        y += norm.pdf(x, m, smooth*np.sqrt(m))

        return x, y / y.sum()

    def test_init_array(self):
        # Test if it works when using a ndarray as data source
        smth = 1
        x, y = self._calc_graph(smth)
        d = brightness.Distribution(self.masses, x, smooth=smth, cam_eff=1)
        np.testing.assert_allclose([x, y], d.graph)

    def test_init_df(self):
        # Test if it works when using a DataFrame as data source
        # This assumes that the array version works
        absc = 5000
        np.testing.assert_allclose(
            brightness.Distribution(self.peak_data, absc).graph,
            brightness.Distribution(self.masses, absc).graph)

    def test_init_list(self):
        # Test if it works when using a list of DataFrames as data source
        # This assumes that the array version works
        l = [self.peak_data.loc[[0, 1]], self.peak_data.loc[[2]]]
        absc = 5000
        np.testing.assert_allclose(
            brightness.Distribution(l, absc).graph,
            brightness.Distribution(self.masses, absc).graph)

    def test_init_abscissa(self):
        # Test if passing an abscissa as scalar produces the same result as
        # passing it as an array
        d1 = brightness.Distribution(self.masses, 5000)
        d2 = brightness.Distribution(self.masses, np.arange(100, 5001))
        np.testing.assert_allclose(d1.graph[:, 100:], d2.graph)

    def test_init_cam_eff(self):
        # Test the cam_eff parameter in __init__
        eff = 20
        absc = 5000
        d1 = brightness.Distribution(self.masses, absc, cam_eff=eff)
        d2 = brightness.Distribution(self.masses/eff, absc, cam_eff=1)
        np.testing.assert_allclose(d1. graph, d2.graph)

    def test_mean(self):
        # Test calculation of mean
        absc = 5000
        d = brightness.Distribution(self.masses, absc)
        mean = np.sum(d.graph[0]*d.graph[1])
        np.testing.assert_allclose(d.mean(), mean)

    def test_std(self):
        # Test calculation of standard deviation
        absc = 5000
        d = brightness.Distribution(self.masses, absc)
        var = np.sum((d.graph[0] - d.mean())**2 * d.graph[1])
        np.testing.assert_allclose(d.std(), np.sqrt(var))

    def test_most_probable(self):
        # Test calculation of most probable value
        absc = 5000
        d = brightness.Distribution(self.masses, absc)
        np.testing.assert_allclose(d.most_probable(), self.most_probable)

    def test_distribution_func(self):
        # Test the (deprecated) distribution function
        absc = 5000
        smth = 2
        cam_eff = 1
        x, y = brightness.distribution(self.masses, absc, smth)
        d = brightness.Distribution(self.masses, absc, smth, cam_eff)
        np.testing.assert_allclose([x, y], d.graph)


if __name__ == "__main__":
    unittest.main()
