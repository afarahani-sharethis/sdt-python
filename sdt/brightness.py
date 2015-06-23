# -*- coding: utf-8 -*-
"""
Find signal brightness

Attributes:
    pos_colums (list of str): Names of the columns describing the x and the y
        coordinate of the features in pandas.DataFrames. Defaults to
        ["x", "y"].
    t_column (str): Name of the column containing frame numbers. Defaults
        to "frame".
    mass_column (str): Name of the column describing the integrated intensities
        ("masses") of the features. Defaults to "mass".
    bg_column (str): Name of the column describing background per pixel.
        Defaults to "background".
    bg_dev_column (str): Name of the column describing background deviation per
        pixel. Defaults to "bg_deviation".
"""
import numpy as np


pos_columns = ["x", "y"]
t_column = "frame"
mass_column = "mass"
bg_column = "background"
bg_dev_column = "bg_deviation"


def _get_raw_brightness_single(data, frames, diameter=5, bg_frame=1):
    """Determine brightness by counting pixel values for a single particle

    This is called using numpy.apply_along_axis on the whole dataset.

    Args:
        data (list): First entry is the frame number, other entries are
            particle coordinates.
        frames (list of numpy.arrays): Raw image data
        diameter (int): Length of the box in which pixel values are summed up.
            Has to be an odd number.
        bg_frame (int, optional): Width of frame (in pixels) for background
            determination.

    Returns:
        list whose first entry is the brightness, second entry is the
        background per pixel, third entry is the deviation of the background.
    """
    frameno = int(data[0])
    pos = np.round(data[1:]) #round to nearest pixel value
    ndim = len(pos) #number of dimensions; this could does not only work in 2D
    fr = frames[frameno] #current image
    sz = np.floor(diameter/2.)
    start = pos - sz - bg_frame
    end = pos + sz + bg_frame + 1

    #this gives the pixels of the signal box plus background frame
    signal_region = fr[ [slice(s, e) for s, e in zip(reversed(start),
                                                     reversed(end))] ]

    if (signal_region.shape != end - start).any():
        #The signal was too close to the egde of the image, we could not read
        #all the pixels we wanted
        mass = np.NaN
        background_intensity = np.NaN
    elif bg_frame == 0 or bg_frame is None:
        #no background correction
        mass = signal_region.sum()
        background_intensity = 0
        background_std = 0
    else:
        #signal region without background frame (i. e. only the actual signal)
        signal_slice = [slice(bg_frame, -bg_frame)]*ndim
        uncorr_intensity = signal_region[signal_slice].sum()
        #TODO: threshold uncorr intensity?

        #background correction: Only take frame pixels
        signal_region[signal_slice] = 0
        background_pixels = signal_region[signal_region.nonzero()]
        background_intensity = np.mean(background_pixels)
        background_std = np.std(background_pixels)
        mass = uncorr_intensity - background_intensity * diameter**ndim

    return [mass, background_intensity, background_std]

def get_raw_brightness(positions, frames, diameter, bg_frame=2,
                       pos_columns=pos_columns,
                       t_column=t_column, mass_column=mass_column,
                       bg_column=bg_column, bg_dev_column=bg_dev_column):
    """Determine particle brightness by counting pixel values

    Around each localization, all brightness values in a  `diameter` times
    `diameter` square are added up. Additionally, background is locally
    determined by calculating the mean brightness in a frame of `bg_frame`
    pixels width around this box. This background is subtracted from the
    signal brightness.

    Args:
        positions (pandas.DataFrame): Localization data. Brightness,
            background, and background deviation columns are added and/or
            replaced directly in this object.
        frames (list of numpy.arrays): Raw image data
        diameter (int): Length of the box in which pixel values are summed up.
            Has to be an odd number.
        bg_frame (int, optional): Width of frame (in pixels) for background
            determination. Defaults to 2.
        pos_columns (list of str, optional): Sets the `pos_columns` attribute.
                Defaults to the `pos_columns` attribute of the module.
        t_column (str, optional): Name of the column containing frame numbers.
            Defaults to the `frameno_column` of the module.
        mass_column (str, optional): Name of the column describing the
            integrated intensities ("masses") of the features. Defaults to the
            `mass_column` attribute of the module.
        bg_column (str, optional): Name of the column containing the background
            intensity per pixel. Defaults to the `bg_column` attribute of the
            module.
        bg_dev_column (str, optional): Name of the column describing background
            deviation per pixel. Defaults to the `bg_dev_column` attribute of
            the module.
    """
    #convert to numpy array for performance reasons
    t_pos_matrix = positions[[t_column] + pos_columns].as_matrix()
    brightness = np.apply_along_axis(_get_raw_brightness_single, 1,
                                     t_pos_matrix,
                                     frames, diameter, bg_frame)

    positions[mass_column] = brightness[:,0]
    positions[bg_column] = brightness[:,1]
    positions[bg_dev_column] = brightness[:,2]