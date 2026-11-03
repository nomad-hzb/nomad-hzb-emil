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

import numpy as np
import plotly.graph_objs as go
from baseclasses.characterizations import XPS
from nomad.datamodel.data import ArchiveSection, EntryData
from nomad.datamodel.metainfo.plot import PlotlyFigure, PlotSection
from nomad.metainfo import Quantity, SchemaPackage, Section, SubSection

from nomad_hzb_emil.schema_packages.file_parser.xps_txt_parser import read_xps_txt

m_package = SchemaPackage()


# %% ####################### XPS


class SEAID_XPSRegionSettings(ArchiveSection):
    """Acquisition settings of one XPS region as written in the file header."""

    m_def = Section(label='Acquisition settings')

    energy_mode = Quantity(
        type=str, description='Energy scale used for acquisition (KE or BE).'
    )
    start_energy = Quantity(type=np.dtype(np.float64), unit='eV')
    end_energy = Quantity(type=np.dtype(np.float64), unit='eV')
    energy_step = Quantity(type=np.dtype(np.float64), unit='eV')
    number_of_sweeps = Quantity(type=np.dtype(np.int64))
    dwell_time = Quantity(
        type=np.dtype(np.float64), unit='s', description='Dwell time per sweep.'
    )
    analyser_mode = Quantity(type=str, description='e.g. CAE or CRR.')
    pass_energy = Quantity(
        type=np.dtype(np.float64),
        description='Pass energy in eV (CAE) or retard ratio (CRR).',
    )
    magnification = Quantity(type=str)
    divide_voltages_by_10 = Quantity(type=str)
    excitation_source = Quantity(type=str)
    excitation_energy = Quantity(type=np.dtype(np.float64), unit='eV')
    analyser_workfunction = Quantity(type=np.dtype(np.float64), unit='eV')
    aperture = Quantity(type=str)
    exit_slit = Quantity(type=str)
    notes = Quantity(type=str)
    creation_comment = Quantity(type=str)


class SEAID_XPSRegion(ArchiveSection):
    """One XPS region (survey or detail spectrum)."""

    m_def = Section(label_quantity='name')

    name = Quantity(type=str, description='Transition / region name.')

    settings = SubSection(section_def=SEAID_XPSRegionSettings)

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


class SEAID_XPS(XPS, PlotSection, EntryData):
    """XPS measurement of the SE-AID group."""

    m_def = Section(
        label='SE-AID XPS',
        links=['http://purl.obolibrary.org/obo/CHMO_0000404'],
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

        settings_names = set(SEAID_XPSRegionSettings.m_def.all_quantities)
        regions = []
        for parsed in parsed_regions:
            settings = SEAID_XPSRegionSettings(
                **{
                    key: value
                    for key, value in parsed.items()
                    if key in settings_names and value is not None
                }
            )
            region = SEAID_XPSRegion(name=parsed.get('transition'), settings=settings)
            region.kinetic_energy = parsed['kinetic_energy']
            region.binding_energy = parsed['binding_energy']
            region.counts = parsed['counts']
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
