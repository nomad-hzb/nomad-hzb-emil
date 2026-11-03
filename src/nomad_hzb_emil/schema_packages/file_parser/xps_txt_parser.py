#
# Copyright The NOMAD Authors.
#
# This file is part of NOMAD. See https://nomad-lab.eu for further info.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
"""
Reader for XPS text exports with a '#'-commented key/value header followed by
two whitespace separated columns (energy, counts), e.g.

    # Transition                      Mg survey
    # Energy Mode                     KE
    # Start Energy in eV              218.5
    ...
    # Kinetic Energy in eV         Counts
    # --------------------         ------
    218.500                    86827.1573

A file may contain several regions; every region starts with a '# Transition'
line.
"""

import re

import numpy as np

# Header keys as written in the file -> (attribute name, type)
HEADER_KEYS = {
    'Transition': ('transition', str),
    'Notes': ('notes', str),
    'Creation Comment': ('creation_comment', str),
    'Energy Mode': ('energy_mode', str),
    'Start Energy in eV': ('start_energy', float),
    'End Energy in eV': ('end_energy', float),
    'Energy Step in eV': ('energy_step', float),
    'Number Of Sweeps': ('number_of_sweeps', int),
    'Dwell Time per Sweep in s': ('dwell_time', float),
    'Analyser Mode': ('analyser_mode', str),
    'Pass Energy in eV/Retard Ratio': ('pass_energy', float),
    'Magnification': ('magnification', str),
    'Divide Voltages By 10': ('divide_voltages_by_10', str),
    'Excitation Source': ('excitation_source', str),
    'Excitation Energy in eV': ('excitation_energy', float),
    'Analyser Workfunction in eV': ('analyser_workfunction', float),
    'Aperture': ('aperture', str),
    'Exit Slit': ('exit_slit', str),
}

# Header keys are separated from their values by at least two spaces.
_HEADER_LINE = re.compile(r'^#\s?(?P<key>\S.*?)(?:\s{2,}(?P<value>.*))?$')
_DATA_LINE = re.compile(r'^\s*[-+]?\d')


def _convert(value, type_):
    if value is None or value == '':
        return None
    try:
        return type_(value)
    except ValueError:
        return value if type_ is str else None


def _parse_region(lines):
    header, extra, column_names, data = {}, {}, [], []
    for line in lines:
        if line.startswith('#'):
            match = _HEADER_LINE.match(line.rstrip())
            if not match:
                continue
            key, value = match.group('key').strip(), match.group('value')
            value = value.strip() if value else ''
            if key in HEADER_KEYS:
                name, type_ = HEADER_KEYS[key]
                header[name] = _convert(value, type_)
            elif set(key) <= set('- '):
                continue
            elif 'Energy' in key and 'Counts' in value:
                column_names = [key, value]
            elif key:
                extra[key] = value
        elif _DATA_LINE.match(line):
            data.append([float(v) for v in line.split()[:2]])

    data = np.array(data, dtype=float).reshape(-1, 2)
    energy_column = column_names[0] if column_names else ''
    energy_is_binding = 'Binding' in energy_column or (
        not energy_column and header.get('energy_mode', '').upper() == 'BE'
    )

    hv = header.get('excitation_energy')
    energy, counts = data[:, 0], data[:, 1]
    if energy_is_binding:
        binding_energy = energy
        kinetic_energy = hv - energy if hv is not None else None
    else:
        kinetic_energy = energy
        # Kinetic energies in these exports are already referenced to the
        # Fermi level (analyser workfunction applied by the acquisition
        # software), so BE = hv - KE.
        binding_energy = hv - energy if hv is not None else None

    return {
        **header,
        'additional_header': extra,
        'column_names': column_names,
        'kinetic_energy': kinetic_energy,
        'binding_energy': binding_energy,
        'counts': counts,
    }


def parse_xps_txt(text):
    """Parse the content of an XPS text export.

    Returns a list with one dict per region.
    """
    lines = text.splitlines()
    starts = [i for i, line in enumerate(lines) if line.startswith('# Transition')]
    if not starts:
        starts = [0]
    starts.append(len(lines))
    return [
        _parse_region(lines[start:end]) for start, end in zip(starts[:-1], starts[1:])
    ]


def read_xps_txt(file_obj):
    text = file_obj.read()
    if isinstance(text, bytes):
        text = text.decode('utf-8', errors='replace')
    return parse_xps_txt(text)
