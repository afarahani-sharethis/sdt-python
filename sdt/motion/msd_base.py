# SPDX-FileCopyrightText: 2020 Lukas Schrangl <lukas.schrangl@tuwien.ac.at>
#
# SPDX-License-Identifier: BSD-3-Clause

"""Base functions for MSD-related things"""
from collections import OrderedDict
import math

import numpy as np
import pandas as pd

from .. import config, helper


def _displacements(particle_data, n_lag, disp_list):
    """Do the actual calculation of displacements

    Calculate all possible displacements for each coordinate and each lag time
    for a single particle.

    Parameters
    ----------
    particle_data : numpy.ndarray
        First column is the frame number, the other columns are particle
        coordinates. Has to be sorted according to ascending frame number.
    n_lag : int
        Maximum number of time lags to consider.
    disp_list : list of lists of numpy.arrays, shape(m, n)
        Results will be appended to the list. For the i-th lag time, the
        displacements (a 2D numpy.ndarray where each column stands for a
        coordinate and each row for one displacement data set) will be appended
        to the i-th list entry. If the entry does not exist, it will be
        created.

        After calling this function for each particle, the items of
        disp_list can for example turned into one large array containing all
        coordinate displacements using :py:func:`numpy.concatenate`.
    """
    ndim = particle_data.shape[1] - 1

    # fill gaps with NaNs
    frames = np.round(particle_data[:, 0]).astype(int)
    start = frames[0]
    end = frames[-1]
    pdata = np.full((end - start + 1, ndim), np.NaN)
    pdata[frames - start] = particle_data[:, 1:]

    # there can be at most len(pdata) - 1 steps
    n_lag = round(min(len(pdata)-1, n_lag))

    for i in range(1, n_lag + 1):
        # calculate coordinate differences for each time lag
        disp = pdata[i:] - pdata[:-i]
        try:
            disp_list[i-1].append(disp)
        except IndexError:
            if i - 1 != len(disp_list):
                # something is really wrong — this should never happen
                raise RuntimeError("Displacement list index skipped.")
            disp_list.append([disp])


def _square_displacements(disp_list, pixel_size=1):
    """Calculate square displacements

    Parameters
    ----------
    disp_list : list
        Coordinate displacements as generated by :py:func:`_displacements`.
    pixel_size : float, optional
        Pixel size; multiply coordinates by this factor. Defaults to 1
        (no scaling).

    Returns
    -------
    list of numpy.ndarrays, shape(n)
        The i-th list entry is the 1D-array of square displacements for the
        i-th lag time.
    """
    sd_list = []
    px_sz_sq = pixel_size * pixel_size
    for d in disp_list:
        # For each time lag, concatenate the coordinate differences
        # Check if concatenation is necessary for performance gain
        if len(d) == 1:
            d = d[0]
        else:
            d = np.concatenate(d)
        # calculate square displacements
        d = np.sum(d**2, axis=1)
        # get rid of NaNs from gaps
        d = d[~np.isnan(d)]
        if not math.isclose(pixel_size, 1):
            d = d * px_sz_sq
        sd_list.append(d)
    return sd_list


@config.set_columns
def _all_square_displacements(data, n_lag, ensemble, e_name="ensemble",
                              pixel_size=1, columns={}):
    """Calculate all square displacements for a dataset

    Parameters
    ----------
    data : pandas.DataFrame or iterable of pandas.DataFrame
        Tracking data. Either a single DataFrame or a collection of
        DataFrames.
    n_lag : int or inf
        Number of lag times (time steps) to consider at most.
    ensemble : bool
        Whether to calculate the MSDs for the whole data set or for each
        trajectory individually.
    pixel_size : float, optional
        Pixel size; multiply coordinates by this factor. Defaults to 1
        (no scaling).

    Returns
    -------
    dict of particle -> list of numpy.ndarray
        The particle id is either `e_name` if ``ensemble=True`` was passed or
        the numeric id of each particle taken from `data` if `data` is a single
        DataFrame or a tuple identifying the DataFrame and the particle.
        The dict's value's i-th entry is an array of square displacements for
        the i-th lag time.

    Other parameters
    ----------------
    e_name : str, optional
        If the `ensemble` parameter is `True`, use this as the name for
        the dataset. It shows up in the MSD DataFrame (see
        :py:meth:`get_msd`) and in plots. Defaults to "ensemble".
    columns : dict, optional
        Override default column names as defined in
        :py:attr:`config.columns`. Relevant names are `coords`, `particle`,
        and `time`. This means, if your DataFrame has coordinate columns
        "x", "y", and "z" and the time column "alt_frame", set
        ``columns={"coords": ["x", "y", "z"], "time": "alt_frame"}``.
    """
    _omit_file_label = False
    if isinstance(data, pd.DataFrame):
        data = {0: data}
        # Only one file, there is no need for a MultiIndex etc.
        _omit_file_label = True
    elif not isinstance(data, dict):
        data = OrderedDict([(i, d) for i, d in enumerate(data)])

    _square_disp = OrderedDict()
    ensemble_disp_list = []
    for file, trc in data.items():
        trc_sorted = trc.sort_values([columns["particle"],
                                      columns["time"]])
        trc_split = helper.split_dataframe(
            trc_sorted, columns["particle"],
            [columns["time"]] + columns["coords"], sort=False)
        if ensemble:
            for p, trc_p in trc_split:
                _displacements(trc_p, n_lag, ensemble_disp_list)
        else:
            for p, trc_p in trc_split:
                disp_list = []
                _displacements(trc_p, n_lag, disp_list)
                if _omit_file_label:
                    key = p
                else:
                    key = (file, p)
                _square_disp[key] = _square_displacements(disp_list,
                                                          pixel_size)
    if ensemble:
        _square_disp[e_name] = _square_displacements(
            ensemble_disp_list, pixel_size)

    return _square_disp


class MsdData:
    """Collection of data related to MSD analysis"""
    def __init__(self, frame_rate, data, means=None, errors=None):
        """Parameters
        ----------
        frame_rate : float
            Set the :py:attr:`frame_rate` attribute
        data : dict of particle id -> :obj:`numpy.ndarray`
            Set the :py:attr:`data` attribute
        means : None or dict of particle id -> :obj:`numpy.ndarray`, optional
            If not `None`, set the :py:attr:`means` attribute. Otherwise,
            calculate from :obj:`data`. Defaults to `None`.
        errors : None or dict of particle id -> :obj:`numpy.ndarray`, optional
            If not `None`, set the :py:attr:`errors` attribute. Otherwise,
            calculate from :obj:`data`. Defaults to `None`.
        """
        self.data = data
        """obj:`dict` of particle id -> :obj:`numpy.ndarray` : Full MSD dataset

        The array is 2D. The i-th row contains MSDs for the i-th lag time and
        the j-th column data of the j-th bootstrapped dataset.
        """

        self.frame_rate = frame_rate
        """float : frame rate"""

        self.means = means
        """obj:`dict` of particle id -> :obj:`numpy.ndarray` : MSDs

        1D arrays contain MSDs for each lag time.
        """
        if means is None:
            self.means = OrderedDict(
                [(k, np.mean(v, axis=1)) for k, v in data.items()])

        self.errors = errors
        """obj:`dict` of particle id -> :obj:`numpy.ndarray` : standard errors

        1D arrays contain standard errors for MSD for each time lag.
        """
        if errors is None:
            # Use corrected sample std as a less biased estimator of the
            # population std
            err = []
            for k, v in data.items():
                if v.shape[1] > 1:
                    # bootstrapping was done
                    e = np.std(v, axis=1, ddof=1)
                else:
                    # no bootstrapping, no error
                    e = np.full(v.shape[0], np.NaN)
                err.append((k, e))
            self.errors = OrderedDict(err)

    def get_lagtimes(self, n):
        """Get first `n` lag times

        The i-th lag time is :math:`(i + 1) / r`, where :math:`r` is the frame
        rate.

        Parameters
        ----------
        n : int
            Number of lag times

        Returns
        -------
        numpy.ndarray, shape(n)
            Lag times in ascending order
        """
        return np.arange(1, n + 1) / self.frame_rate

    def get_data(self, data, series=True):
        """Return data as a Series or DataFrame

        Parameters
        ----------
        data : {"means", "errors"}
            Which dataset to return
        series : bool, optional
            If `False` return a DataFrame even if there is only a single
            particle/esemble. Defaults to `True`.

        Returns
        -------
        pandas.Series or pandas.DataFrame
            One particle per row, one lag time per column. If there is only one
            row, return a :py:class:`pandas.Series`, unless
            ``series=False`` was specified.
        """
        data = getattr(self, data)
        if len(data) == 1 and series:
            name, res = next(iter(data.items()))
            ret = pd.Series(res, name=name)
            ret.index = pd.Index(self.get_lagtimes(len(ret)), name="lagt")

            return ret

        # pd.DataFrame.from_dict does not create a MultiIndex
        ret = pd.DataFrame(list(data.values()))

        ret.index = pd.Index(list(data.keys()))
        if isinstance(ret.index, pd.MultiIndex):
            ret.index.names = ("file", "particle")
        else:
            ret.index.name = "particle"

        ret.columns = pd.Index(self.get_lagtimes(ret.shape[1]), name="lagt")
        return ret
