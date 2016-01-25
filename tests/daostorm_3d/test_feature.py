import unittest
import os

import numpy as np

from sdt.locate.daostorm_3d import feature


path, f = os.path.split(os.path.abspath(__file__))
data_path = os.path.join(path, "data_feature")
img_path = os.path.join(path, "data_find")


class Test(unittest.TestCase):
    def test_make_margin(self):
        img = np.arange(16).reshape((4, 4))
        img_with_margin = feature.make_margin(img, 2)
        expected = np.array([[  5.,   4.,   4.,   5.,   6.,   7.,   7.,   6.],
                             [  1.,   0.,   0.,   1.,   2.,   3.,   3.,   2.],
                             [  1.,   0.,   0.,   1.,   2.,   3.,   3.,   2.],
                             [  5.,   4.,   4.,   5.,   6.,   7.,   7.,   6.],
                             [  9.,   8.,   8.,   9.,  10.,  11.,  11.,  10.],
                             [ 13.,  12.,  12.,  13.,  14.,  15.,  15.,  14.],
                             [ 13.,  12.,  12.,  13.,  14.,  15.,  15.,  14.],
                             [  9.,   8.,   8.,   9.,  10.,  11.,  11.,  10.]])
        np.testing.assert_allclose(img_with_margin, expected)

    def test_locate_2dfixed(self):
        orig = np.load(os.path.join(data_path, "locate_2dfixed.npz"))["peaks"]
        frame = np.load(os.path.join(img_path, "beads.npz"))["img"]
        peaks = feature.locate(frame, 4., 300., 5)
        np.testing.assert_allclose(peaks, orig)
