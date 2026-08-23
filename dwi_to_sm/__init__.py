"""DWI -> SM simfile converter.

    from dwi_to_sm import convert_file, autoconvert_tree, dwi_to_sm

    convert_file("song/A.dwi")                 # writes song/A.sm
    autoconvert_tree("C:/Songs")               # bulk: only .dwi-only folders
    sm_text = dwi_to_sm(open("A.dwi").read())  # pure string -> string

Copyright (C) 2026 dwi-to-sm contributors.
Licensed under the GNU General Public License v3 or later; see LICENSE.
"""

from .dwi import DwiChart, DwiError, DwiSong, parse_dwi
from .files import convert_file, convert_tree, read_text
from .folders import (
    AUTOCONVERT_MARKER,
    AUTOCONVERT_TEXT,
    PlannedAction,
    autoconvert_folder,
    autoconvert_tree,
    clear_autoconversions,
    clear_test_outputs,
    find_convertible_folders,
    find_testable_folders,
    is_autoconverted,
    plan_test_tree,
    run_planned_actions,
    scan_folder,
    test_folder,
    test_tree,
)
from .images import Image, choose_banner_background, image_size, list_images, pick_banner_background
from .sm import dwi_to_sm

__version__ = "0.1.0"

__all__ = [
    "AUTOCONVERT_MARKER",
    "AUTOCONVERT_TEXT",
    "DwiChart",
    "DwiError",
    "DwiSong",
    "Image",
    "PlannedAction",
    "autoconvert_folder",
    "autoconvert_tree",
    "choose_banner_background",
    "clear_autoconversions",
    "clear_test_outputs",
    "convert_file",
    "convert_tree",
    "dwi_to_sm",
    "find_convertible_folders",
    "find_testable_folders",
    "image_size",
    "is_autoconverted",
    "list_images",
    "parse_dwi",
    "pick_banner_background",
    "plan_test_tree",
    "read_text",
    "run_planned_actions",
    "scan_folder",
    "test_folder",
    "test_tree",
]
