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

import re

import numpy as np
import plotly.graph_objs as go
from baseclasses.characterizations import (
    XPS,
    PESSpecsLabProdigyAnalyzerParameters,
    PESSpecsLabProdigySettings,
    PESSpecsLabProdigySourceParameters,
)
from nomad.datamodel.data import ArchiveSection, EntryData
from nomad.datamodel.metainfo.plot import PlotlyFigure, PlotSection
from nomad.metainfo import Quantity, SchemaPackage, Section, SubSection

from nomad_hzb_emil.schema_packages.file_parser.xps_txt_parser import read_xps_txt

m_package = SchemaPackage()


# %% ####################### XPS-ANA-lytics EMIL SE-AID


class SEAID_XPS_ANA_RegionSettings(PESSpecsLabProdigySettings):
    """Acquisition settings for one XPS region (survey or detail spectrum).
    Inherits from SPECS but for the SE-AID XPS ANA-lytics instrument specific file"""

    m_def = Section(label='Acquisition settings')

    number_of_sweeps = Quantity(type=np.dtype(np.int64))
    analyser_mode = Quantity(
        type=str, description='Analyser scan mode, e.g. CAE or CRR.'
    )
    divide_voltages_by_10 = Quantity(type=str)
    aperture = Quantity(type=str)
    excitation_source = Quantity(
        type=str, description='Excitation source as written in the file.'
    )


# file header entry -> quantity of SEAID_XPSRegionSettings
settings_mapping = {
    'transition': 'region',
    'energy_mode': 'scan_variable',
    'start_energy': 'energy_minimum',
    'end_energy': 'energy_maximum',
    'energy_step': 'step_size',
    'dwell_time': 'dwell_time',
    'pass_energy': 'pass_energy',
    'excitation_energy': 'excitation_energy',
    'magnification': 'analyzer_lens_mode',
    'exit_slit': 'analyzer_slit',
    'notes': 'notes',
    'creation_comment': 'comment',
    'number_of_sweeps': 'number_of_sweeps',
    'analyser_mode': 'analyser_mode',
    'divide_voltages_by_10': 'divide_voltages_by_10',
    'aperture': 'aperture',
    'excitation_source': 'excitation_source',
}


def _anode_from_source(excitation_source):
    """'Mg Ka 1253.6 eV normal' -> 'Mg Ka'"""
    match = re.match(r'^\s*([A-Z][a-z]?\s+K[a-zα]+\d?)', excitation_source or '')
    return match.group(1) if match else None


def create_settings(parsed):
    settings = SEAID_XPS_ANA_RegionSettings(
        **{
            target: parsed[key]
            for key, target in settings_mapping.items()
            if parsed.get(key) is not None
        }
    )

    if parsed.get('analyser_workfunction') is not None:
        settings.analyzer_parameters = PESSpecsLabProdigyAnalyzerParameters(
            work_function=parsed['analyser_workfunction']
        )

    source = PESSpecsLabProdigySourceParameters()
    if parsed.get('excitation_energy') is not None:
        source.excitation_energy = parsed['excitation_energy']
    anode = _anode_from_source(parsed.get('excitation_source'))
    if anode:
        source.anode = anode
    if source.m_to_dict():
        settings.source_parameters = source
    return settings


class SEAID_XPSRegion(ArchiveSection):
    """One XPS region (survey or detail spectrum)."""

    m_def = Section(label_quantity='name')

    name = Quantity(type=str, description='Transition / region name.')

    settings = SubSection(section_def=SEAID_XPS_ANA_RegionSettings)

    kinetic_energy = Quantity(type=np.dtype(np.float64), shape=['*'], unit='eV')
    binding_energy = Quantity(
        type=np.dtype(np.float64),
        shape=['*'],
        unit='eV',
        description='Binding energy, calculated as excitation energy minus '
        'kinetic energy (kinetic energies in the file are referenced to the '
        'Fermi level).',
    )
    counts = Quantity(type=np.dtype(np.float64), shape=['*'])


class SEAID_XPS_ANA(XPS, PlotSection, EntryData):
    """XPS ANA-lytics measurement of the SE-AID group."""

    m_def = Section(
        label='SE-AID XPS-ANA',
        links=['http://purl.obolibrary.org/obo/CHMO_0000404'],  # annotation to XPS
        a_eln=dict(
            hide=['lab_id', 'steps', 'results', 'location'],
            properties=dict(
                order=['name', 'data_file', 'datetime', 'samples', 'operator']
            ),
        ),
    )

    regions = SubSection(section_def=SEAID_XPSRegion, repeats=True)

    def read_data_file(self, archive):
        with archive.m_context.raw_file(self.data_file, 'rt') as f:
            parsed_regions = read_xps_txt(f)

        # The "Notes" of the file go into the description of the entry.
        # A description edited in the ELN is kept when the file is read again.
        if not self.description:
            notes = [
                (parsed.get('transition'), parsed['notes'])
                for parsed in parsed_regions
                if parsed.get('notes')
            ]
            if len(parsed_regions) == 1 and notes:
                self.description = notes[0][1]
            elif notes:
                self.description = '\n'.join(
                    f'<p><b>{name}:</b> {text}</p>' for name, text in notes
                )

        regions = []
        for parsed in parsed_regions:
            settings = create_settings(parsed)
            region = SEAID_XPSRegion(name=parsed.get('transition'), settings=settings)
            region.kinetic_energy = parsed.get('kinetic_energy')  # ['kinetic_energy']
            region.binding_energy = parsed.get('binding_energy')  # ['binding_energy']
            region.counts = parsed.get('counts')  # ['counts']
            regions.append(region)
        self.regions = regions

    def make_figures(self):
        figures = []
        for region in self.regions:
            if region.counts is None:
                continue
            use_be = region.binding_energy is not None
            energy = region.binding_energy if use_be else region.kinetic_energy
            if energy is None:
                continue
            fig = go.Figure(
                go.Scatter(
                    x=energy.to('eV').magnitude,
                    y=region.counts,
                    mode='lines',
                    name=region.name,
                )
            )
            fig.update_layout(
                title=region.name,
                xaxis_title=f'{"Binding" if use_be else "Kinetic"} Energy (eV)',
                yaxis_title='Counts',
                template='plotly_white',
                hovermode='closest',
                xaxis=dict(autorange='reversed' if use_be else True),
            )
            figures.append(
                PlotlyFigure(
                    label=region.name or 'XPS spectrum',
                    figure=fig.to_plotly_json(),
                )
            )
        return figures

    def normalize(self, archive, logger):
        if self.data_file:
            try:
                self.read_data_file(archive)
            except Exception as e:
                logger.error('Could not read XPS data file', exc_info=e)

        if self.regions:
            self.figures = self.make_figures()

        super().normalize(archive, logger)


m_package.__init_metainfo__()
