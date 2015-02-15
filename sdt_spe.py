# -*- coding: utf-8 -*-

"""Tools to deal with SPE files as created by the SDT-control software"""

import collections
import configparser
import io
import logging

try:
    import OpenImageIO as oiio
except:
    oiio = None

_logger = logging.getLogger(__name__)

extra_metadata_begin = "### Begin extra metadata ###"
extra_metadata_end = "### End extra metadata ###"
extra_metadata_version = (1, 0) #(major, minor)
excluded_metadata = ["DateTime"] #metadata that is saved otherwise anyways

def read_spe_metadata(spec):
    """Read metadata from an SPE file

    Converts the SDT specific metadata to a :collections.OrderedDict:. This
    requires that the SPE file was opened using the SPE plugin version >= 1.4.

    :param spec: The :OpenImageIO.ImageSpec: of the SPE file.

    :returns: A :collections.OrderedDict: containing the metadata
    """
    data = collections.OrderedDict()
    for attr in spec.extra_attribs:
        if attr.name not in excluded_metadata:
            data[attr.name] = attr.value

    return data

def read_imagedesc_metadata(ini):
    """Read metadata from ini-file-like string

    Converts the ini-file-like string to a :collections.OrderedDict:.

    :param ini: Either the string itself or a :OpenImageIO.ImageDesc:
    whose "ImageDescription" attribute is the string.

    :returns: A :collections.OrderedDict: containing the metadata. All values
    are strings and may need conversion.
    """
    if isinstance(ini, str):
        inistr = ini
    elif oiio is not None:
        if isinstance(ini, oiio.ImageSpec):
            inistr = ini.get_attribute("ImageDescription")
    else:
        raise TypeError("Expected str or OpenImageIO.ImageSpec")

    start_pos = inistr.find(extra_metadata_begin)
    if start_pos != -1:
        #extra_metadata_begin string was found. Discard anything before that
        #and the string itself
        inistr = inistr[start_pos+len(extra_metadata_begin):]
    end_pos = inistr.find(extra_metadata_end)
    if end_pos != -1:
        #extra_metadata_end string was found. Discard anything after that
        #and the string itself
        inistr = inistr[:end_pos]

    cp = configparser.ConfigParser(dict_type = collections.OrderedDict)
    #do not transform the keys to lowercase
    cp.optionxform = str
    cp.read_string(inistr)
    return collections.OrderedDict(cp["metadata"])


def metadata_to_ini_string(metadata):
    """Convert the metadata dicts to ini-file type string

    Use this function to convert the :OrderedDict: created by
    :read_spe_metadata: or :read_imagedesc_metadata: into ini-file like
    strings that can be saved to the ImageDescription of a converted file.

    :param metadata: (ordered) dictionary of metadata

    :returns: ini-file like string of metadata
    """
    cp = configparser.ConfigParser(dict_type = collections.OrderedDict)
    #do not transform the keys to lowercase
    cp.optionxform = str
    #create the dict of dicts required by the config parser
    toplevel_dict = collections.OrderedDict()
    toplevel_dict["metadata"] = metadata
    #also save some version information in case something changes in the
    #future
    toplevel_dict["version"] = \
        {"version": "{}.{}".format(extra_metadata_version[0],
                                   extra_metadata_version[1])}
    cp.read_dict(toplevel_dict)
    strio = io.StringIO()
    cp.write(strio)
    return "{}\n{}\n{}".format(extra_metadata_begin,
                               strio.getvalue(),
                               extra_metadata_end)
