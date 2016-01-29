import sys

import pims
from scipy.io import loadmat
import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from sdt.loc.prepare_peakposition import locate
import sdt.data
import sdt.pims


def main(pkcfile, img_file, frame_nos):
    pkc = sdt.data.load(pkcfile)
    frames = pims.open(img_file)

    par = loadmat(pkcfile, squeeze_me=True, struct_as_record=False)["par"]
    imsize = par.fitimsize[0] // 2
    thresh = par.threshold_red
    diameter = 2.885390082  # FWHM is 2, thus sigma = 2/log(2)

    max_radius = 2  # don't consider anything farther apart a pair
    pos_cols = ["x", "y"]
    data_cols = ["size", "mass", "bg"]

    diffs = []

    for f in frames:
        if frame_nos is not None and f.frame_no not in frame_nos:
            continue

        print("frame {}:".format(f.frame_no))
        new_pkc = locate(f, diameter, thresh, imsize)
        cur_pkc = pkc[pkc["frame"] == f.frame_no]

        # find pairs
        xold, yold = cur_pkc[pos_cols].as_matrix().T
        xnew, ynew = new_pkc[pos_cols].as_matrix().T

        dx = xold[:, np.newaxis] - xnew[np.newaxis, :]
        dy = yold[:, np.newaxis] - ynew[np.newaxis, :]
        dr2 = dx**2 + dy**2
        idx_old = np.arange(dr2.shape[0])
        idx_new = np.argmin(dr2, axis=1)  # find closest
        idx_mask = (dr2[idx_old, idx_new] < max_radius)
        idx_old = idx_old[idx_mask]
        idx_new = idx_new[idx_mask]

        pos_mat_old = cur_pkc.iloc[idx_old][pos_cols].as_matrix()
        pos_mat_new = new_pkc.iloc[idx_new][pos_cols].as_matrix()
        diff_pos = pos_mat_old - pos_mat_new
        data_mat_old = cur_pkc.iloc[idx_old][data_cols].as_matrix()
        data_mat_new = new_pkc.iloc[idx_new][data_cols].as_matrix()
        diff_data = (data_mat_old - data_mat_new)/data_mat_old

        diff = pd.DataFrame(np.hstack((diff_pos, diff_data)),
                            columns=pos_cols+data_cols)
        diff["frame"] = f.frame_no
        diffs.append(diff)

        # plot
        fig = plt.figure()
        plt.title("frame {}".format(f.frame_no))
        plt.imshow(f, cmap="gray", interpolation="none")
        plt.plot(new_pkc["x"], new_pkc["y"], linestyle="none", marker="x",
                 color="r")
        plt.plot(cur_pkc["x"], cur_pkc["y"], linestyle="none", marker="+",
                 color="b")
        fig.show()

        # print statistics
        print("""pkc has {pkc_cnt} peaks, python algorithm found {py_cnt}.
{pair_cnt} peaks could be correlated.""".format(
            fno=f.frame_no, pkc_cnt=len(cur_pkc), py_cnt=len(new_pkc),
            pair_cnt=len(diff)))

        print(diff)
        print("")


def print_help():
    print("""Usage: {} <pkcfile> <imagestack> [<frame_numbers>])

<pkcfile>: path to the .pkc file generated by MATLAB prepare_peakposition
<imagestack>: path image stack to analyze and compare to the .pkc file
<frame_numbers>: optional, comma separated list of frames to plot
    If not specified, all frames will be compared""".format(
        sys.argv[0]))


if __name__ == "__main__":
    if len(sys.argv) not in (3, 4):
        print_help()
        sys.exit(1)

    if len(sys.argv) == 4:
        try:
            frame_nos = list(map(int, sys.argv[3].split(",")))
        except Exception:
            print("Error processing frame number list\n")
            print_help()
            sys.exit(2)
    else:
        frame_nos = None

    main(sys.argv[1], sys.argv[2], frame_nos)

    print("Press return to quit…")
    input()


# interesting stuff:
# - 2016-01-22 - Long exposure/POPC 18 018ms/pMHC_AF647_200k_000_.{pkc,SPE}
#   peak at (43, 103), MATLAB seems to be wrong, possibly due to large
#   IMSIZE (4)