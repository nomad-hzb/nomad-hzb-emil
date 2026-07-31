# This file is based on code by Michael Götte
# (see nomad-chemical-energy plugin https://github.com/nomad-hzb/nomad-chemical-energy/blob/cfb7d9b5ac066e9d415c6d5da770434c100c927f/src/nomad_chemical_energy/schema_packages/file_parser/xrf_spx_parser.py).
# Refactored by Carla Terboven and Claude Sonnet 5.

"""Parser for Bruker M4 XRF spectrum files (.spx).

An .spx file is an XML document. This module extracts, per file:
  - hardware/system/header metadata
  - the stage position (explicit, or reverse-engineered from an
    undocumented base64-encoded binary blob)
  - the raw channel spectrum (and, optionally, fit results)

`read()` combines several files from a raster scan into a single
in-memory dataset, additionally reconstructing the (x, y) scan grid
from the recorded absolute positions.
"""

import base64
import struct
import xml.etree.ElementTree as ET
from typing import NamedTuple

import numpy as np
import pandas as pd

# --------------------------------------------------------------------------
# Constants
# --------------------------------------------------------------------------

# 1-indexed atomic number -> element symbol
PERIODIC_TABLE: list[str] = [
    'H',
    'He',
    'Li',
    'Be',
    'B',
    'C',
    'N',
    'O',
    'F',
    'Ne',
    'Na',
    'Mg',
    'Al',
    'Si',
    'P',
    'S',
    'Cl',
    'Ar',
    'K',
    'Ca',
    'Sc',
    'Ti',
    'V',
    'Cr',
    'Mn',
    'Fe',
    'Co',
    'Ni',
    'Cu',
    'Zn',
    'Ga',
    'Ge',
    'As',
    'Se',
    'Br',
    'Kr',
    'Rb',
    'Sr',
    'Y',
    'Zr',
    'Nb',
    'Mo',
    'Tc',
    'Ru',
    'Rh',
    'Pd',
    'Ag',
    'Cd',
    'In',
    'Sn',
    'Sb',
    'Te',
    'I',
    'Xe',
    'Cs',
    'Ba',
    'La',
    'Ce',
    'Pr',
    'Nd',
    'Pm',
    'Sm',
    'Eu',
    'Gd',
    'Tb',
    'Dy',
    'Ho',
    'Er',
    'Tm',
    'Yb',
    'Lu',
    'Hf',
    'Ta',
    'W',
    'Re',
    'Os',
    'Ir',
    'Pt',
    'Au',
    'Hg',
    'Tl',
    'Pb',
    'Bi',
    'Po',
    'At',
    'Rn',
    'Fr',
    'Ra',
    'Ac',
    'Th',
    'Pa',
    'U',
    'Np',
    'Pu',
    'Am',
    'Cm',
    'Bk',
    'Cf',
    'Es',
    'Fm',
    'Md',
    'No',
    'Lr',
    'Rf',
    'Db',
    'Sg',
    'Bh',
    'Hs',
    'Mt',
    'Ds',
    'Rg',
    'Cn',
    'Nh',
    'Fl',
    'Mc',
    'Lv',
    'Ts',
    'Og',
]
ATOMIC_SYMBOL: dict[int, str] = dict(enumerate(PERIODIC_TABLE, start=1))

DEFAULT_CHANNEL_COUNT = 4096  # Bruker sometimes omits trailing zero channels
XML_ENCODING = 'WINDOWS-1252'

# Offset/length (in bytes) of the packed (x, y, z) position doubles inside
# the decoded 'RTREM' blob. Found experimentally -- not documented by Bruker.
_POSITION_BYTE_OFFSET = 121
_POSITION_STRUCT_FORMAT = '<ddd'  # little-endian x, y, z as float64
_POSITION_BYTE_LENGTH = struct.calcsize(_POSITION_STRUCT_FORMAT)

_GRID_EPSILON = 0.01  # mm; distances below this are treated as "no movement"
_GRID_STEP_TOLERANCE = 0.03  # relative tolerance when matching step sizes


class SpxParseError(Exception):
    """Raised when an .spx file is missing an element this parser needs."""


class GridReconstructionError(Exception):
    """Raised when the scan grid can't be reconstructed from positions."""


# --------------------------------------------------------------------------
# Small XML helpers
# --------------------------------------------------------------------------


def _require(node: ET.Element, path: str) -> ET.Element:
    """`node.find(path)`, raising SpxParseError instead of returning None."""
    found = node.find(path)
    if found is None:
        raise SpxParseError(f'Missing expected element at path: {path!r}')
    return found


def _extract(node: ET.Element, fields: dict) -> dict:
    """Extract several scalar fields from `node` in one pass.

    :param fields: maps output key -> (relative xpath, type-caster callable),
        e.g. {'Voltage': ('Voltage', int)}.
    Raises SpxParseError if any path is missing, naming which one.
    """
    result = {}
    for key, (path, caster) in fields.items():
        child = _require(node, path)
        try:
            result[key] = caster(child.text)
        except (TypeError, ValueError) as exc:
            raise SpxParseError(
                f'Could not parse field {key!r} at {path!r}: {exc}'
            ) from exc
    return result


def _read_padded_channels(text: str, length: int, dtype) -> np.ndarray:
    """Parse a comma-separated channel string, zero-padded to `length`."""
    values = text.split(',')
    if len(values) > length:
        raise SpxParseError(
            f'Channel data longer ({len(values)}) than expected ({length})'
        )
    values += ['0'] * (length - len(values))
    return np.array(values, dtype=dtype)


# --------------------------------------------------------------------------
# Metadata extraction
# --------------------------------------------------------------------------

_HARDWARE_HEADER_PATH = (
    "./ClassInstance/[@Type='TRTSpectrum']"
    '/TRTHeaderedClass'
    "/ClassInstance/[@Type='TRTSpectrumHardwareHeader']"
)
_HARDWARE_FIELDS: dict = {  # {output_key: (xpath, caster)}
    'RealTime': ('RealTime', float),
    'LifeTime': ('LifeTime', float),
    'DeadTime': ('DeadTime', float),
    'ZeroPeakPosition': ('ZeroPeakPosition', int),
    'ZeroPeakFrequency': ('ZeroPeakFrequency', int),
    'PulseDensity': ('PulseDensity', int),
    'Amplification': ('Amplification', lambda t: int(float(t))),
    'ShapingTime': ('ShapingTime', int),
    'DetectorCount': ('DetectorCount', int),
    'SelectedDetectors': ('SelectedDetectors', str),
}


def get_spectrum_hardware_params(data_root: ET.Element) -> dict:
    """Return the hardware parameters recorded for this spectrum."""
    node = _require(data_root, _HARDWARE_HEADER_PATH)
    return _extract(node, _HARDWARE_FIELDS)


_XRF_HEADER_PATH = (
    "./ClassInstance/[@Type='TRTSpectrum']"
    '/TRTHeaderedClass'
    "/ClassInstance/[@Type='TRTXrfHeader']"
)
_SYSTEM_SETTINGS_FIELDS: dict = {  # {output_key: (xpath, caster)}
    'TubeType': ('TubeType', str),
    'TubeNumber': ('TubeNumber', str),
    'TubeProdDate': ('TubeProdDate', str),
    'Voltage': ('Voltage', int),
    'Current': ('Current', int),
    'Anode': ('Anode', int),
    'TubeIncidentAngle': ('TubeIncidentAngle', float),
    'TubeTakeOffAngle': ('TubeTakeOffAngle', float),
    'TubeWindow,AtomicNumber': ('TubeWindow/AtomicNumber', int),
    'TubeWindow,Thickness': ('TubeWindow/Thickness', lambda t: int(float(t))),
    'Optic': ('Optic', str),
    'SpotSize': ('SpotSize', lambda t: int(float(t))),
    'ExcitationAngle': ('ExcitationAngle', float),
    'DetectionAngle': ('DetectionAngle', float),
    'ExcitationPathLength': ('ExcitationPathLength', float),
    'DetectionPathLength': ('DetectionPathLength', float),
    'SolidAngleDetection': ('SolidAngleDetection', float),
    'AzimutAngleAbs': ('AzimutAngleAbs', float),
    'DetAzimutAngle': ('DetAzimutAngle', float),
    'ChamberPressure': ('ChamberPressure', float),
    'TiltAngle': ('TiltAngle', float),
    'DetSpotSize': ('DetSpotSize', float),
    'Atmosphere': ('Atmosphere', str),
}


def get_system_settings(data_root: ET.Element) -> dict:
    """Return the XRF system settings (tube, optics, geometry, ...)."""
    node = _require(data_root, _XRF_HEADER_PATH)
    return _extract(node, _SYSTEM_SETTINGS_FIELDS)


_SPECTRUM_HEADER_PATH = (
    "./ClassInstance/[@Type='TRTSpectrum']/ClassInstance/[@Type='TRTSpectrumHeader']"
)
_SPECTRUM_HEADER_SCALAR_FIELDS: dict = {  # {output_key: (xpath, caster)}
    'ChannelCount': ('ChannelCount', int),
    'CalibAbs': ('CalibAbs', float),
    'CalibLin': ('CalibLin', float),
    'SigmaAbs': ('SigmaAbs', float),
    'SigmaLin': ('SigmaLin', float),
}


def get_spectrum_header(data_root: ET.Element) -> dict:
    """Return spectrum-level metadata: timestamp, channel/energy calibration."""
    node = _require(data_root, _SPECTRUM_HEADER_PATH)
    result = _extract(node, _SPECTRUM_HEADER_SCALAR_FIELDS)
    date_text = _require(node, 'Date').text
    time_text = _require(node, 'Time').text
    result['DateTime'] = pd.to_datetime(f'{date_text} {time_text}').strftime(
        '%Y-%m-%dT%H:%M:%S.%f'
    )
    return result


# --------------------------------------------------------------------------
# Position / grid reconstruction
# --------------------------------------------------------------------------

_EXPLICIT_POSITION_PATH = (
    "./ClassInstance/[@Type='TRTSpectrum']"
    '/TRTHeaderedClass'
    "/ClassInstance/[@Type='TRTAxesHeader']"
    '/AxesParameter/'
)
_ENCODED_POSITION_PATH = (
    "./ClassInstance/[@Type='TRTSpectrum']"
    '/TRTHeaderedClass'
    "/ClassInstance/[@Type='TRTUnknownHeader']/[@Name='RTREM']"
    '/Data'
)


def get_position(data_root: ET.Element) -> np.ndarray:
    """Return the (x, y, z) stage position for this spectrum, in mm.

    Positions are usually stored explicitly. When absent, they're recovered
    from an undocumented base64-encoded blob: the three position floats are
    packed as little-endian doubles starting at a fixed byte offset within
    the decoded data (found experimentally; see module constants).
    """
    explicit_nodes = data_root.findall(_EXPLICIT_POSITION_PATH)
    if explicit_nodes:
        return np.array([float(node.attrib['AxisPosition']) for node in explicit_nodes])

    position_node = _require(data_root, _ENCODED_POSITION_PATH)
    decoded = base64.b64decode(position_node.text.encode('ascii'))
    start = _POSITION_BYTE_OFFSET
    end = start + _POSITION_BYTE_LENGTH
    if len(decoded) < end:
        raise SpxParseError(
            f'Decoded position blob is too short ({len(decoded)} bytes, need {end})'
        )
    return np.array(struct.unpack(_POSITION_STRUCT_FORMAT, decoded[start:end]))


def _fit_first_scanned_axis(step_diffs: np.ndarray, rough_step: float) -> np.ndarray:
    """Reconstruct positions for the axis that was scanned first (fast axis).

    Most consecutive differences equal the (precise) step size; a larger
    "carriage return" jump appears once per line. The number of points per
    line is derived from the spacing between those carriage-return jumps.
    """
    tol = _GRID_STEP_TOLERANCE
    in_step = (step_diffs > (1 - tol) * rough_step) & (
        step_diffs < (1 + tol) * rough_step
    )
    step_positions = np.where(in_step)[0]
    step_size = np.mean(step_diffs[step_positions])

    if len(step_diffs) == len(step_positions):
        # Single line/column: no carriage-return jumps at all.
        points_per_line = len(step_diffs) + 1
    else:
        carriage_return_step = np.median(np.delete(step_diffs, step_positions))
        in_carriage_return = (step_diffs > (1 - tol) * carriage_return_step) & (
            step_diffs < (1 + tol) * carriage_return_step
        )
        carriage_return_positions = np.where(in_carriage_return)[0]

        if np.std(np.diff(carriage_return_positions)) >= _GRID_EPSILON:
            raise GridReconstructionError(
                'Carriage-return spacing is inconsistent; cannot infer points per line'
            )
        points_per_line = int(np.mean(np.diff(carriage_return_positions)))

    return np.linspace(0, step_size * (points_per_line - 1), points_per_line)


def _fit_second_scanned_axis(step_diffs: np.ndarray) -> np.ndarray:
    """Reconstruct positions for the axis scanned second (slow axis).

    Most differences are ~0 (no movement within a line); the nonzero
    differences mark line/column changes and give the step size directly.
    """
    moved = np.abs(step_diffs) >= _GRID_EPSILON
    step_diffs = step_diffs[moved]
    if len(step_diffs) == 0:
        return np.zeros(1)  # single line/column: this axis never moved

    rough_step = np.median(step_diffs)
    in_step = (step_diffs > 0.9 * rough_step) & (step_diffs < 1.1 * rough_step)
    step_size = np.mean(step_diffs[in_step])
    num_lines = np.count_nonzero(in_step) + 1
    return np.linspace(0, step_size * (num_lines - 1), num_lines)


def create_grid(positions: np.ndarray) -> tuple[list[np.ndarray], bool]:
    """Reconstruct the (x, y) scan grid from absolute measurement positions.

    :param positions: shape (2, n) array of absolute x/y positions, one
        column per measurement.
    :return: ([x_positions, y_positions], x_was_scanned_first)
    """
    diffs = np.abs(np.diff(positions))
    rough_step_x = float(np.median(diffs[0]))
    rough_step_y = float(np.median(diffs[1]))

    if rough_step_x < _GRID_EPSILON:  # x barely moves -> y was the fast axis
        x_first = False
        y_array = _fit_first_scanned_axis(diffs[1], rough_step_y)
        x_array = _fit_second_scanned_axis(diffs[0])
    else:
        x_first = True
        x_array = _fit_first_scanned_axis(diffs[0], rough_step_x)
        y_array = _fit_second_scanned_axis(diffs[1])

    return [np.round(x_array, 2), np.round(y_array, 2)], x_first


# --------------------------------------------------------------------------
# Spectrum / fit-result extraction
# --------------------------------------------------------------------------

_CHANNELS_PATH = "./ClassInstance/[@Type='TRTSpectrum']/Channels"


def get_channels(
    data_root: ET.Element, channel_count: int = DEFAULT_CHANNEL_COUNT
) -> np.ndarray:
    """Return the (zero-padded) raw spectrum counts."""
    node = _require(data_root, _CHANNELS_PATH)
    return _read_padded_channels(node.text, channel_count, dtype=int)


_RESULTS_PATH = (
    "./ClassInstance/[@Type='TRTSpectrum']/ClassInstance/[@Type='TRTResult']"
)


def is_results_in_file(data_root: ET.Element) -> bool:
    """Whether this .spx file contains fit results (ROI/deconvolution/layers)."""
    return data_root.find(_RESULTS_PATH) is not None


_FIT_BACKGROUND_PATH = (
    "./ClassInstance/[@Type='TRTSpectrum']"
    '/ChildClassInstances'
    "/ClassInstance/[@Type='TRTXRFMultiQuantificationResults']"
    '/TRTSpectrumQuantificationResults'
    "/ClassInstance/[@Type='TRTSpectrumList']"
    '/ChildClassInstances'
    "/ClassInstance/[@Type='TRTSpectrum'][@Name='Background']"
    '/Channels'
)


def get_fit_bkg(
    data_root: ET.Element, channel_count: int = DEFAULT_CHANNEL_COUNT
) -> np.ndarray:
    """Return the (zero-padded) fitted background counts."""
    node = _require(data_root, _FIT_BACKGROUND_PATH)
    return _read_padded_channels(node.text, channel_count, dtype=float)


_LAYER_RESULTS_PATH = (
    "./ClassInstance/[@Type='TRTSpectrum']"
    "/ClassInstance/[@Type='TRTLayerResultList'][@Name='LayerResults']"
    '/ChildClassInstances'
    "/ClassInstance/[@Type='TRTLayerResult']"
)


def get_fit_layer_composition(data_root: ET.Element) -> tuple[list[dict], list[dict]]:
    """Return (per-element layer results, per-layer physical properties)."""
    layer_results: list[dict] = []
    layer_props: list[dict] = []

    for layer_node in data_root.findall(_LAYER_RESULTS_PATH):
        layer_name = layer_node.get('Name')

        for element_node in layer_node.findall('TRTResult/Result'):
            atomic_number = int(_require(element_node, 'Atom').text)
            result = {
                'LayerName': layer_name,
                'Element': ATOMIC_SYMBOL[atomic_number],
            }
            result.update({child.tag: child.text for child in element_node})
            layer_results.append(result)

        thickness_error_node = layer_node.find('ThicknessError')
        layer_props.append(
            {
                'LayerName': layer_name,
                'Density': float(_require(layer_node, 'Density').text),
                'Thickness': float(_require(layer_node, 'Thickness').text),
                'ThicknessError': (
                    float(thickness_error_node.text)
                    if thickness_error_node is not None
                    else float('nan')
                ),
            }
        )

    return layer_results, layer_props


_ROI_RESULTS_PATH = (
    "./ClassInstance/[@Type='TRTSpectrum']"
    "/ClassInstance/[@Type='TRTResult'][@Name='Results']"
    '/RoiResults'
)


def get_roi_results(data_root: ET.Element) -> list[dict]:
    """Return one dict per region-of-interest result."""
    return [
        {detail.tag: detail.text for detail in roi_node}
        for roi_node in data_root.findall(_ROI_RESULTS_PATH)
    ]


_DECONVOLUTION_RESULTS_PATH = (
    "./ClassInstance/[@Type='TRTSpectrum']"
    '/ChildClassInstances'  # NOTE: original code was missing this leading '/'
    "/ClassInstance/[@Type='TRTXRFMultiQuantificationResults']"
    '/TRTSpectrumQuantificationResults'
    "/ClassInstance/[@Type='TRTDeconvolutionResultList']"
)


def get_deconvolution_results(data_root: ET.Element) -> tuple[str, list[dict]]:
    """Return (deconvolution method name, one dict per fluorescence line)."""
    main_node = _require(data_root, _DECONVOLUTION_RESULTS_PATH)
    method = _require(main_node, 'DeconvMethod').text

    results = []
    for result_node in main_node.findall(
        "ChildClassInstances/ClassInstance/[@Type='TRTDeconvolutionResult']"
    ):
        element = ATOMIC_SYMBOL[int(_require(result_node, 'Element').text)]
        for line in result_node.findall('Line'):
            line_type, energy, counts = line.text.split(',')
            results.append(
                {
                    'Element': element,
                    'Line': line_type,
                    'Energy': energy,
                    'Counts': counts,
                }
            )

    return method, results


# --------------------------------------------------------------------------
# Top-level: read a batch of .spx files
# --------------------------------------------------------------------------


class SpxDataset(NamedTuple):
    """Combined result of parsing a batch of .spx files from one raster scan."""

    spectra: list[np.ndarray]
    energy_axis: np.ndarray
    measurement_data: pd.DataFrame
    positions: np.ndarray  # shape (2, n): absolute x/y per measurement
    grid_axes: list[np.ndarray]  # [x_positions, y_positions], relative, deduped
    grid_shape: tuple[int, int, str]  # (len_x, len_y, numpy reshape order)


def _parse_spx(spx_file_obj) -> ET.Element:
    """Parse an .spx file object directly, without touching disk."""
    tree = ET.parse(spx_file_obj, parser=ET.XMLParser(encoding=XML_ENCODING))
    return tree.getroot()


def read(file_obj_paths: list) -> SpxDataset:
    """Parse a batch of .spx files from a single raster scan into one dataset.

    :param file_obj_paths: file-like objects (opened in binary mode) for
        each .spx file in the scan, in acquisition order.
    """
    measurement_rows: list[dict] = []
    positions: list[np.ndarray] = []
    spectra: list[np.ndarray] = []

    for idx, spx_file_obj in enumerate(file_obj_paths):
        root = _parse_spx(spx_file_obj)

        info = {
            **get_spectrum_hardware_params(root),
            **get_system_settings(root),
            **get_spectrum_header(root),
            'idx': idx,
        }
        measurement_rows.append(info)
        positions.append(get_position(root))
        spectra.append(get_channels(root, channel_count=info['ChannelCount']))

        # Fit results (ROI / deconvolution / layers) are read the same way
        # via is_results_in_file() + get_roi_results() / get_deconvolution_results()
        # / get_fit_layer_composition() / get_fit_bkg() when present, but
        # aggregating them into the returned dataset is not yet wired up here.

    measurement_data = pd.DataFrame(measurement_rows).set_index('idx')

    positions_array = np.array(positions).T  # shape (2, n)
    grid_axes, x_first = create_grid(positions_array)

    channel_numbers = np.arange(measurement_data['ChannelCount'].iat[0])
    energy_axis = (
        measurement_data['CalibAbs'].mean()
        + channel_numbers * measurement_data['CalibLin'].mean()
    )

    if x_first:
        len_x, len_y, order = len(grid_axes[0]), len(grid_axes[1]), 'F'
    else:
        len_x, len_y, order = len(grid_axes[1]), len(grid_axes[0]), 'C'

    return SpxDataset(
        spectra=spectra,
        energy_axis=energy_axis,
        measurement_data=measurement_data,
        positions=positions_array,
        grid_axes=grid_axes,
        grid_shape=(len_x, len_y, order),
    )
