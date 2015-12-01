# -*- coding: utf-8 -*-
"""The `motion` module provides tools for evaluation of diffusion data.

Attributes
----------
pos_colums : list of str
    Names of the columns describing the x and the y coordinate of the features
    in pandas.DataFrames. Defaults to ["x", "y"].
t_column : str
    Name of the column containing frame numbers. Defaults to "frame".
trackno_column : str
    Name of the column containing track numbers. Defaults to "particle".
"""
import pandas as pd
import numpy as np
import collections
import warnings

from . import exp_fit


pos_columns = ["x", "y"]
t_column = "frame"
trackno_column = "particle"


def _prepare_traj(data, t_column=t_column):
    """Prepare data for use with `_displacements`

    Does sorting according to the frame number and also sets the frame number
    as index of the DataFrame. This is not included in `_displacements`, since
    it can be called on the whole tracking DataFrame and does not have to be
    called for each single trajectory (yielding a performance increase).

    Parameters
    ----------
    data : pandas.DataFrame
        Tracking data
    t_column : str, optional
        Name of the column containing frame numbers. Defaults to the
        `t_column` of the module.

    Returns
    -------
    pandas.DataFrame
        `data` ready to use for _displacements (one has to the data into
        single trajectories, though).
    """
    # do not work on the original data
    data = data.copy()
    # sort here, not in loop
    data.sort_values(t_column, inplace=True)
    # set the index, needed later for reindexing, but do not do the loop
    fnos = data[t_column].astype(int)
    data.set_index(fnos, inplace=True)
    return data


def _displacements(particle_data, max_lagtime,
                   pos_columns=pos_columns, disp_dict=None):
    """Do the actual calculation of displacements

    Calculate all possible displacements for each lag time for one particle.

    Parameters
    ----------
    particle_data : pandas.DataFrame
        Tracking data of one single particle/trajectory that has been prepared
        with `_prepare_traj`.
    max_lagtime : int
        Maximum number of time lags to consider.
    pos_columns : list of str, optional
        Names of the columns describing the x and the y coordinate of the
        features. Defaults to the `pos_columns` attribute of the module.
    disp_dict : None or dict, optional
        If a dict is given, results will be appended to the dict. For each
        lag time, the displacements (a 2D numpy.ndarray where each column
        stands for a coordinate and each row for one displacement data set)
        will be appended using ``disp_dict[lag_time].append(displacements)``.
        If it is None, the displacement data will be returned (see `Returns`
        section) as a numpy.ndarray. Defaults to None.

    Returns
    -------
    numpy.ndarray or None
        If `disp_dict` is not None, return None (since data will be written to
        `disp_dict`). If `disp_dict` is None, return a 3D numpy.ndarray.
        The first index is the lag time (index 0 means 1st lag time etc.),
        the second index the displacement data set index and the third the
        coordinate index.
    """
    # fill gaps with NaNs
    idx = particle_data.index
    start_frame = idx[0]
    end_frame = idx[-1]
    frame_list = list(range(start_frame, end_frame + 1))
    pdata = particle_data.reindex(frame_list)
    pdata = pdata[pos_columns].as_matrix()

    max_lagtime = round(min(len(pdata), max_lagtime))

    if isinstance(disp_dict, dict):
        for i in range(1, max_lagtime):
            # calculate coordinate differences for each time lag
            disp = pdata[:-i] - pdata[i:]
            # append to output structure
            try:
                disp_dict[i].append(disp)
            except KeyError:
                disp_dict[i] = [disp]
    else:
        ret = np.empty((max_lagtime - 1, max_lagtime - 1, len(pos_columns)))
        for i in range(1, max_lagtime):
            # calculate coordinate differences for each time lag
            padding = np.full((i-1, len(pos_columns)), np.nan)
            # append to output structure
            ret[i-1] = np.vstack((pdata[i:] - pdata[:-i], padding))

        return ret


def msd(traj, pixel_size, fps, max_lagtime=100, pos_columns=pos_columns,
        t_column=t_column, trackno_column=trackno_column):
    """Calculate mean displacements from tracking data for one particle

    This calculates the mean displacement (<x>) for each coordinate, the mean
    square displacement (<x^2>) for each coordinate and the total mean square
    displacement (<x_1^2 + x_2^2 + ... + x_n^2) for one particle/trajectory

    Parameters
    ----------
    traj : pandas.DataFrame
        Tracking data of one single particle/trajectory
    pixel_size : float
        width of a pixel in micrometers
    fps : float
        Frames per second
    max_lagtime : int, optional
        Maximum number of time lags to consider. Defaults to 100.
    pos_columns : list of str, optional
        Names of the columns describing the x and the y coordinate of the
        features. Defaults to the `pos_columns` attribute of the module.
    t_column : str, optional
        Name of the column containing frame numbers. Defaults to the
        `t_column` of the module.
    trackno_column : str, optional
        Name of the column containing track numbers. Defaults to the
        `trackno_column` attribute of the module.

    Returns
    -------
    pandas.DataFrame([0, ..., n])
        For each lag time and each particle/trajectory return the calculated
        mean square displacement.
    """
    # check if traj is empty
    cols = (["<{}>".format(p) for p in pos_columns] +
            ["<{}^2>".format(p) for p in pos_columns] +
            ["msd", "lagt"])
    if not len(traj):
        return pd.DataFrame(columns=cols)

    # calculate displacements
    traj = _prepare_traj(traj)
    disp = _displacements(traj, max_lagtime, pos_columns=pos_columns)

    # time lag steps
    idx = np.arange(1, disp.shape[0] + 1)
    # calculate means; mean x and y displacement
    m_disp = np.nanmean(disp, axis=1) * pixel_size
    # square x and y displacements
    sds = disp**2 * pixel_size**2
    # mean square x and y displacements
    msds = np.nanmean(sds, axis=1)
    # mean absolute square displacement
    msd = np.sum(msds, axis=1)[:, np.newaxis]
    # time lags
    lagt = (idx/fps)[:, np.newaxis]

    ret = pd.DataFrame(np.hstack((m_disp, msds, msd, lagt)), columns=cols)
    ret.index = pd.Index(idx, name="lagt")
    return ret


def imsd(data, pixel_size, fps, max_lagtime=100, pos_columns=pos_columns,
         t_column=t_column, trackno_column=trackno_column):
    """Calculate mean square displacements from tracking data for each particle

    Parameters
    ----------
    data : pandas.DataFrame
        Tracking data
    pixel_size : float
        width of a pixel in micrometers
    fps : float
        Frames per second
    max_lagtime : int, optional
        Maximum number of time lags to consider. Defaults to 100.
    pos_columns : list of str, optional
        Names of the columns describing the x and the y coordinate of the
        features. Defaults to the `pos_columns` attribute of the module.
    t_column : str, optional
        Name of the column containing frame numbers. Defaults to the
        `t_column` of the module.
    trackno_column : str, optional
        Name of the column containing track numbers. Defaults to the
        `trackno_column` attribute of the module.

    Returns
    -------
    pandas.DataFrame([0, ..., n])
        For each lag time and each particle/trajectory return the calculated
        mean square displacement.
    """
    # check if traj is empty
    if not len(data):
        return pd.DataFrame()

    traj = _prepare_traj(data)
    traj_grouped = traj.groupby(trackno_column)
    disps = []
    for pn, pdata in traj_grouped:
        disp = _displacements(pdata, max_lagtime)
        sds = np.sum(disp**2 * pixel_size**2, axis=2)
        disps.append(np.nanmean(sds, axis=1))

    ret = pd.DataFrame(disps).T
    ret.columns = traj_grouped.groups.keys()
    ret.index = pd.Index(np.arange(1, len(ret)+1)/fps, name="lagt")
    return ret


def all_displacements(data, max_lagtime=100,
                      pos_columns=pos_columns, t_column=t_column,
                      trackno_column=trackno_column):
    """Calculate all displacements

    For each lag time calculate all possible displacements for each trajectory
    and each coordinate.

    Parameters
    ----------
    data : list of pandas.DataFrames or pandas.DataFrame
        Tracking data
    max_lagtime : int, optional
        Maximum number of time lags to consider. Defaults to 100.
    pos_columns : list of str, optional
        Names of the columns describing the x and the y coordinate of the
        features. Defaults to the `pos_columns` attribute of the module.
    t_column : str, optional
        Name of the column containing frame numbers. Defaults to the
        `t_column` of the module.
    trackno_column : str, optional
        Name of the column containing track numbers. Defaults to the
        `trackno_column` attribute of the module.

    Returns
    -------
    collections.OrderedDict
        The keys of the dict are the number of lag times (if divided by the
        frame rate, this yields the actual lag time). The values are lists of
        numpy.ndarrays where each column stands for a coordinate and each row
        for one displacement data set. Displacement values are in pixels.
    """
    if isinstance(data, pd.DataFrame):
        data = [data]

    disp_dict = collections.OrderedDict()

    for traj in data:
        # check if traj is empty
        if not len(traj):
            continue

        traj = _prepare_traj(traj, t_column=t_column)
        traj_grouped = traj.groupby(trackno_column)

        for pn, pdata in traj_grouped:
            _displacements(pdata, max_lagtime, pos_columns=pos_columns,
                           disp_dict=disp_dict)

    return disp_dict


def all_square_displacements(disp_dict, pixel_size, fps):
    """Calculate square displacements from coordinate displacements

    Use the result of `all_displacements` to calculate the square
    displacements, i. e. the sum of the squares of the coordinate displacements
    (dx_1^2 + dx_2^2 + ... + dx_n^2).

    Parameters
    ----------
    disp_dict : dict
        The result of a call to `all_displacements`
    pixel_size : float
        width of a pixel in micrometers
    fps : float
        Frames per second

    Returns
    -------
    collections.OrderedDict
        The keys of the dict are the number of lag times in seconds.
        The values are lists numpy.ndarrays containing square displacements
        in μm.
    """
    sd_dict = collections.OrderedDict()
    for k, v in disp_dict.items():
        # for each time lag, concatenate the coordinate differences
        v = np.concatenate(v)
        # calculate square displacements
        v = np.sum(v**2, axis=1) * pixel_size**2
        # get rid of NaNs from the reindexing
        v = v[~np.isnan(v)]
        sd_dict[k/fps] = v

    return sd_dict


def emsd_from_square_displacements(sd_dict):
    """Calculate mean square displacements from square displacements

    Use the results of `all_square_displacements` for this end.

    Parameters
    ----------
    sd_dict : dict
        The result of a call to `all_square_displacements`

    Returns
    -------
    pandas.DataFrame([msd, stderr, lagt])
        For each lag time return the calculated mean square displacement and
        standard error.
    """
    ret = collections.OrderedDict()  # will be turned into a DataFrame
    idx = list(sd_dict.keys())
    sval = sd_dict.values()
    ret["msd"] = [sd.mean() for sd in sval]
    with warnings.catch_warnings():
        # if len of sd is 1, sd.std(ddof=1) will raise a RuntimeWarning
        warnings.simplefilter("ignore", RuntimeWarning)
        ret["stderr"] = [sd.std(ddof=1)/np.sqrt(len(sd)) for sd in sval]
    #TODO: Quian errors
    ret["lagt"] = idx
    ret = pd.DataFrame(ret)
    ret.index = pd.Index(idx, name="lagt")
    ret.sort_values("lagt", inplace=True)
    return ret


def emsd(data, pixel_size, fps, max_lagtime=100, pos_columns=pos_columns,
         t_column=t_column, trackno_column=trackno_column):
    """Calculate ensemble mean square displacements from tracking data

    This is equivalent to consecutively calling `all_displacements`,
    `all_square_displacements`, and `emsd_from_square_displacements`.

    Parameters
    ----------
    data : list of pandas.DataFrames or pandas.DataFrame
        Tracking data
    pixel_size : float
        width of a pixel in micrometers
    fps : float
        Frames per second
    max_lagtime : int, optional
        Maximum number of time lags to consider. Defaults to 100.
    pos_columns : list of str, optional
        Names of the columns describing the x and the y coordinate of the
        features. Defaults to the `pos_columns` attribute of the module.
    t_column : str, optional
        Name of the column containing frame numbers. Defaults to the
        `t_column` of the module.
    trackno_column : str, optional
        Name of the column containing track numbers. Defaults to the
        `trackno_column` attribute of the module.

    Returns
    -------
    pandas.DataFrame([msd, stderr, lagt])
        For each lag time return the calculated mean square displacement and
        standard error.
    """
    disp_dict = all_displacements(data, max_lagtime,
                                  pos_columns, t_column, trackno_column)
    sd_dict = all_square_displacements(disp_dict, pixel_size, fps)
    return emsd_from_square_displacements(sd_dict)


def fit_msd(emsd, lags=2):
    """Get the diffusion coefficient and positional accuracy from MSDs

    Fit a linear function to the tlag-vs.-MSD graph

    Parameters
    ----------
    emsd : DataFrame([lagt, msd])
        MSD data as computed by `emsd`
    lags : int, optional
        Use the first `tlags` lag times for fitting only. Defaults to 2.

    Returns
    -------
    D : float
        Diffusion coefficient
    pa : float
        Positional accuracy
    """
    # TODO: illumination time correction
    # msdplot.m:365

    if lags == 2:
        k = ((emsd["msd"].iloc[1] - emsd["msd"].iloc[0]) /
             (emsd["lagt"].iloc[1] - emsd["lagt"].iloc[0]))
        d = emsd["msd"].iloc[0] - k*emsd["lagt"].iloc[0]
    else:
        k, d = np.polyfit(emsd["lagt"].iloc[0:lags],
                          emsd["msd"].iloc[0:lags], 1)

    D = k/4
    d = complex(d) if d < 0. else d
    pa = np.sqrt(d)/2.

    # TODO: resample to get the error of D
    # msdplot.m:403

    return D, pa


def plot_msd(emsd, D, pa, max_lagtime=100, show_legend=True, ax=None):
    """Plot lag time vs. MSD and the fit as calculated by `fit_msd`.

    Parameters
    ----------
    emsd : DataFrame([lagt, msd, stderr])
        MSD data as computed by `emsd`. If the stderr column is not present,
        no error bars will be plotted.
    D : float
        Diffusion coefficient (see `fit_msd`)
    pa : float
        Positional accuracy (see `fit_msd`)
    max_lagtime : int, optional
        Maximum number of time lags to plot. Defaults to 100.
    show_legend : bool, optional
        Whether to show the legend (the values of the diffusion coefficient D
        and the positional accuracy) in the plot. Defaults to True.
    ax : matplotlib.axes.Axes or None, optional
        If given, use this axes object to draw the plot. If None, use the
        result of `matplotlib.pyplot.gca`.
    """
    import matplotlib as mpl
    import matplotlib.pyplot as plt
    if ax is None:
        ax = plt.gca()

    emsd = emsd.iloc[:int(max_lagtime)]
    ax.set_xlabel("lag time [s]")
    ax.set_ylabel("MSD [$\mu$m$^2$]")
    if "stderr" in emsd.columns:
        ax.errorbar(emsd["lagt"], emsd["msd"], yerr=emsd["stderr"], fmt="o")
    else:
        ax.plot(emsd["lagt"], emsd["msd"], linestyle="none", marker="o")

    k = 4*D
    d = 4*pa**2
    if isinstance(d, complex):
        d = d.real
    x = np.linspace(0, emsd["lagt"].max(), num=2)
    y = k*x + d
    ax.plot(x, y)

    if show_legend:
        # This can be improved
        if isinstance(pa, complex):
            pa = pa.real
        fake_artist = mpl.lines.Line2D([0], [0], linestyle="none")
        ax.legend([fake_artist]*2, ["D: {:.3} $\mu$m$^2$/s".format(float(D)),
                                    "PA: {:.3} $\mu$m".format(float(pa))],
                  loc=0)


def _fit_cdf_model(x, y, num_exp, poly_order, initial_guess=None):
    r"""Variant of `exp_fit.fit` for the model of the CDF

    Determine the best parameters :math:`\alpha, \beta_k, \lambda_k` by fitting
    :math:`\alpha + \sum_{k=1}^p \beta_k \text{e}^{\lambda_k t}` to the data
    using a modified Prony's method. Additionally, there are the constraints
    :math:`\sum_{k=1}^p -\beta_k = 1` and :math:`\alpha = 1`.

    Parameters
    ----------
    x : numpy.ndarray
        Abscissa (x-axis) data
    y : numpy.ndarray
        CDF function values corresponding to `x`.
    num_exp : int
        Number of exponential functions (``p``) in the
        sum
    poly_order : int
        For calculation, the sum of exponentials is approximated by a sum
        of Legendre polynomials. This parameter gives the degree of the
        highest order polynomial.

    Returns
    -------
    mant_coeff : numpy.ndarray
        Mantissa coefficients (:math:`\beta_k`)
    exp_coeff : numpy.ndarray
        List of exponential coefficients (:math:`\lambda_k`)
    ode_coeff : numpy.ndarray
        Optimal coefficienst of the ODE involved in calculating the exponential
        coefficients.

    Other parameters
    ----------------
    initial_guess : numpy.ndarray or None, optional
        An initial guess for determining the parameters of the ODE (if you
        don't know what this is about, don't bother). The array is 1D and has
        `num_exp` + 1 entries. If None, use ``numpy.ones(num_exp + 1)``.
        Defaults to None.

    Notes
    -----
    Since :math:`\sum_{i=1}^p -\beta_i = 1` and :math:`\alpha = 1`, assuming
    :math:`\lambda_k` already known (since they are gotten by fitting the
    coefficients of the ODE), there is only the constrained linear least
    squares problem

    ..math:: 1 + \sum_{k=1}^{p-1} \beta_k \text{e}^{\lambda_k t} +
        (-1 - \sum_{k=1}^{p-1} \beta_k) \text{e}^{\lambda_p t} = y

    left to solve. This is equivalent to

    ..math:: \sum_{k=1}^{p-1} \beta_k
        (\text{e}^{\lambda_k t} - \text{e}^{\lambda_p t}) =
        y - 1 + \text{e}^{\lambda_p t},

    which yields :math:`\beta_1, …, \beta_{p-1}`. :math:`\beta_p` can then be
    determined from the constraint.
    """
    # get exponent coefficients as usual
    exp_coeff, ode_coeff = exp_fit.get_exponential_coeffs(
        x, y, num_exp, poly_order, initial_guess)
    # Solve the equivalent linear lsq problem (see notes section of the
    # docstring).
    V = np.exp(np.outer(x, exp_coeff[:-1]))
    restr = np.exp(x*exp_coeff[-1])
    V -= restr.reshape(-1, 1)
    lsq = np.linalg.lstsq(V, y - 1 + restr)
    lsq = lsq[0]
    # Also recover the last mantissa coefficient from the constraint
    mant_coeff = np.hstack((lsq, -1 - lsq.sum()))

    return mant_coeff, exp_coeff, ode_coeff


def emsd_from_square_displacements_cdf(sd_dict, num_frac=2, poly_order=30):
    r"""Fit the CDF of square displacements to an exponential model

    The cumulative density function (CDF) of square displacements is the
    sum

    .. math:: 1 - \sum_{i=1}^n \beta_i e^{-\frac{r^2}{4 D \Delta t_i}},

    where :math:`n` is the number of diffusing species, :math:`\beta_i` the
    fraction of th i-th species, :math:`r^2` the square displacement and
    :math:`D` the diffusion coefficient. By fitting to the measured CDF, these
    parameters can be extracted.

    Parameters
    ----------
    sd_dict : dict
        The result of a call to `all_square_displacements`
    num_frac : int
        The number of species
    poly_order : int
        For calculation, the sum of exponentials is approximated by a
        polynomial. This parameter gives the degree of the polynomial.

    Returns
    -------
    list of pandas.DataFrames([lagt, msd, fraction])
        For each species, the DataFrame contains for each lag time the msd,
        the fraction.
    """
    lagt = []
    fractions = []
    msd = []
    for tl, s in sd_dict.items():
        y = np.linspace(0, 1, len(s), endpoint=True)
        s = np.sort(s)

        b, l, _ = _fit_cdf_model(s, y, num_frac, poly_order)
        lagt.append(tl)
        fractions.append(-b)
        msd.append(-1./l)

    ret = []
    for i in range(num_frac):
        r = collections.OrderedDict()
        r["lagt"] = lagt
        r["msd"] = [m[i] for m in msd]
        r["fraction"] = [f[i] for f in fractions]
        r = pd.DataFrame(r)
        r.sort_values("lagt", inplace=True)
        r.reset_index(inplace=True, drop=True)
        ret.append(r)

    return ret


def emsd_cdf(data, pixel_size, fps, num_frac=2, max_lagtime=10, poly_order=30,
             pos_columns=pos_columns, t_column=t_column,
             trackno_column=trackno_column):
    r"""Calculate ensemble mean square displacements from tracking data CDF

    Fit the model cumulative density function to the measured CDF of tracking
    data. For details, see the documentation of
    `emsd_from_square_displacements_cdf`.

    This is equivalent to consecutively calling `all_displacements`,
    `all_square_displacements`, and `emsd_from_square_displacements_cdf`.

    Parameters
    ----------
    data : list of pandas.DataFrames or pandas.DataFrame
        Tracking data
    pixel_size : float
        width of a pixel in micrometers
    fps : float
        Frames per second
    num_frac : int, optional
        The number of diffusing species. Defaults to 2
    max_lagtime : int, optional
        Maximum number of time lags to consider. Defaults to 100.
    poly_order : int, optional
        For calculation, the sum of exponentials is approximated by a
        polynomial. This parameter gives the degree of the polynomial.
        Defaults to 30.

    Returns
    -------
    list of pandas.DataFrames([lagt, msd, fraction])
        For each species, the DataFrame contains for each lag time the msd,
        the fraction.

    Other parameters
    ----------------
    pos_columns : list of str, optional
        Names of the columns describing the x and the y coordinate of the
        features. Defaults to the `pos_columns` attribute of the module.
    t_column : str, optional
        Name of the column containing frame numbers. Defaults to the
        `t_column` of the module.
    trackno_column : str, optional
        Name of the column containing track numbers. Defaults to the
        `trackno_column` attribute of the module.
    """
    disp_dict = all_displacements(data, max_lagtime, pos_columns, t_column,
                                  trackno_column)
    sd_dict = all_square_displacements(disp_dict, pixel_size, fps)
    return emsd_from_square_displacements_cdf(sd_dict, num_frac, poly_order)


def plot_cdf_results(msds):
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(1, len(msds)+1)

    for i, f in enumerate(msds):
        tlags = f["lagt"]
        ax[0].scatter(tlags, f["fraction"])
        ax[i+1].scatter(tlags, f["msd"])
        D, pa = fit_msd(f, len(f))
        print(D, pa)
        ax[i+1].plot(tlags, 4*pa**2 + 4*D*tlags)

    fig.tight_layout()
