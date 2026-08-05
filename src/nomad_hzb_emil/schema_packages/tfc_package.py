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

import os

import pandas as pd
import plotly.graph_objs as go
from baseclasses.characterizations import (
    XRFComposition,
    XRFLayer,
    XRFLibrary,
    XRFSingleLibraryMeasurement,
)
from baseclasses.chemical_energy import Equipment
from baseclasses.helper.utilities import convert_datetime, set_sample_reference
from baseclasses.vapour_based_deposition import MultiTargetSputtering
from nomad.datamodel.data import EntryData
from nomad.datamodel.metainfo.plot import PlotlyFigure, PlotSection
from nomad.metainfo import SchemaPackage, Section

m_package = SchemaPackage()

# %% ####################### Entities


class TFC_Equipment(Equipment, EntryData):
    """
    Custom metadata schema for equipment/instrument
    at HZB Thin-Film Catalysts and Reactors group.
    """

    m_def = Section(
        links=['https://w3id.org/nfdi4cat/voc4cat_0000187'],
        a_eln=dict(
            hide=['users', 'origin', 'elemental_composition', 'components'],
            properties=dict(order=['name', 'lab_id', 'producer', 'location']),
        ),
    )


# %% ####################### Deposition


class Prevac_Sputtering(MultiTargetSputtering, PlotSection, EntryData):
    """
    Custom metadata schema for (multitarget) Sputtering deposition
    (thin-film) sample synthesis at HZB Thin-Film Catalysts and Reactors group.
    """

    m_def = Section(
        links=[
            'https://w3id.org/nfdi4cat/voc4cat_0000020',
            'http://purl.obolibrary.org/obo/CHMO_0001364',
        ],
        a_eln=dict(
            hide=[
                'layer',
                'batch',
                'present',
                'positon_in_experimental_plan',
                'end_time',
                'instruments',
                'steps',
                'location',
            ],
            properties=dict(
                order=[
                    'name',
                    'data_file',
                    'datetime',
                    'substrate',
                    'sample_owner',
                    'process_user',
                    'holder',
                    'sample_lab_label',
                ]
            ),
        ),
    )

    def make_targets_process_table(self):
        target_names = [target.name for target in self.targets]
        if len(target_names) == 0:
            return None
        value_list = [''] * (len(target_names) * 3 + 2)
        value_list[0] = 'Flow Rate (ml/min)'
        value_list[1] = 'Substrate Temperature (°C)'
        value_list[2] = 'Power (W)'
        start_idx_bias_u = len(target_names) + 2
        start_idx_bias_i = len(target_names) * 2 + 2
        value_list[start_idx_bias_u] = 'Bias U (V)'
        value_list[start_idx_bias_i] = 'Bias I (A)'
        color_list = ['white'] * (len(target_names) * 3 + 2)
        color_list[1] = 'lightgrey'
        color_list[start_idx_bias_u:start_idx_bias_i] = ['lightgrey'] * len(
            target_names
        )
        flow_rates = [
            [process.flow_rate.magnitude] for process in self.process_properties
        ]
        substrate_temperatures = [
            [process.substrate_temperature.magnitude]
            for process in self.process_properties
        ]
        target_power = [
            process.power.magnitude.tolist() for process in self.process_properties
        ]
        target_bias_u = [
            process.bias_voltage.magnitude.tolist() for process in self.observables
        ]
        target_bias_i = [
            process.bias_current.magnitude.tolist() for process in self.observables
        ]
        cells = [
            flow + substr_temp + power + bias_u + bias_i
            for flow, substr_temp, power, bias_u, bias_i in zip(
                flow_rates,
                substrate_temperatures,
                target_power,
                target_bias_u,
                target_bias_i,
            )
        ]
        header_values = ['', 'Targets'] + [
            f'Step {i + 1}' for i in range(len(target_power))
        ]
        fig = go.Figure(
            data=[
                go.Table(
                    header=dict(
                        values=header_values,
                        fill_color='grey',
                        line_color='darkslategray',
                        font=dict(color='white'),
                    ),
                    cells=dict(
                        values=[value_list, ['', ''] + target_names * 3, *cells],
                        fill_color=[color_list * len(header_values)],
                        line_color='darkslategray',
                    ),
                )
            ]
        )
        return fig

    def normalize(self, archive, logger):
        if self.data_file:
            with archive.m_context.raw_file(self.data_file, 'rb') as f:
                xls_file = pd.ExcelFile(f)
                information_df = pd.read_excel(
                    xls_file, sheet_name='Information', header=0, index_col=0
                )
                information_values = information_df['Value'].where(
                    pd.notna(information_df['Value']), None
                )
                self.name = (
                    information_values.get('Process')
                    if self.name is None
                    else self.name
                )
                self.datetime = (
                    information_values.get('Date')
                    if self.datetime is None
                    else self.datetime
                )
                self.sample_lab_label = information_values.get('Sample Lab label')
                self.holder = information_values.get('Holder')
                self.substrate = information_values.get('Substrate')
                self.sample_owner = information_values.get('Sample Owner')
                self.process_user = information_values.get('Process user')

                if not self.samples:
                    sample_id = information_values.get('Sample ID (NOMAD)')
                    sample_id = (
                        self.data_file.split('.')[0][:8]
                        if sample_id is None
                        else sample_id
                    )
                    set_sample_reference(archive, self, sample_id, None)

                if self.samples:
                    for s in self.samples:
                        s.normalize(archive, logger)

                if not self.targets:
                    target_df = pd.read_excel(
                        xls_file, sheet_name='Source_Configuration', header=0
                    )
                    from baseclasses.helper.archive_builder.prevac_archive import (
                        get_target_properties,
                    )

                    self.targets = get_target_properties(target_df)
                num_targets = len(self.targets)
                if not self.process_properties:
                    parameters_df = pd.read_excel(
                        xls_file, sheet_name='Parameters', header=1, index_col=0
                    )
                    from baseclasses.helper.archive_builder.prevac_archive import (
                        get_process_properties,
                    )

                    self.process_properties = get_process_properties(
                        parameters_df, num_targets
                    )
                if not self.observables:
                    observables_df = pd.read_excel(
                        xls_file, sheet_name='Observables', header=1, index_col=0
                    )
                    self.description = observables_df.loc['Notes', 'Steps']
                    from baseclasses.helper.archive_builder.prevac_archive import (
                        get_observables,
                    )

                    self.observables = get_observables(observables_df, num_targets)

        fig1 = self.make_targets_process_table()
        if fig1:
            self.figures = [
                PlotlyFigure(
                    label='Table for Target & Process View',
                    figure=fig1.to_plotly_json(),
                ),
            ]
        super().normalize(archive, logger)
        archive.results.properties.optoelectronic = None


# %%######################## Measurements


def load_XRF_txt(input_file):
    names_line, units_line, data_line = (next(input_file) for _ in range(3))

    # A column boundary is where data_line has a space AND names_line
    # also has a space at that position (end of a name/value token in both).
    boundaries = [0]
    in_token = False
    for i, char in enumerate(data_line):
        if char != ' ':
            in_token = True
        elif in_token and names_line[i] == ' ':
            boundaries.append(i)
            in_token = False
    boundaries.append(-1)

    columns = []
    last_name = ''
    for start, end in zip(boundaries, boundaries[1:]):
        name = names_line[start:end].strip() or last_name
        unit = units_line[start:end].strip()
        columns.append((name, unit))
        last_name = name

    input_file.seek(0)
    for decimal in (',', '.'):
        try:
            return pd.read_csv(
                input_file,
                names=columns,
                header=None,
                skiprows=2,
                sep=r'\s{2,}',
                decimal=decimal,
                index_col=0,
                engine='python',
            )
        except Exception:
            input_file.seek(0)

    raise ValueError("Could not parse file with ',' or '.' as decimal separator")


def _spx_files_in(archive, data_folder: str) -> list[str]:
    """Sorted basenames of all .spx files in data_folder."""
    return sorted(
        os.path.basename(file.path)
        for file in archive.m_context.upload_files.raw_listdir(data_folder)
        if file.path.endswith('.spx')
    )


def _read_single_spx(archive, path: str):
    """Parse one .spx file, returning (measurement_data, position_xyz, energy)."""
    from nomad_hzb_emil.schema_packages.file_parser.xrf_spx_parser import (
        read as xrf_read,
    )

    with archive.m_context.raw_file(path, 'rb') as f:
        _, energy, measurement_data, positions, _, _ = xrf_read([f])
    return measurement_data, positions[:, 0], energy


def _layers_from_composition_row(measurement_row) -> tuple[list, set[str]]:
    """Build XRFLayer entries + the set of material names for one composition row.

    `measurement_row` is indexed by (layer_name, quantity), e.g.
    ('L1', 'Cu at%') -> 12.3, ('L1', 'Thickness [nm]') -> 150.
    """
    layer_data: dict[str, dict] = {}
    material_names: set[str] = set()

    for (layer_name, quantity), value in measurement_row.items():
        entry = layer_data.setdefault(layer_name, {})
        if 'Thick' in quantity or 'Dicke' in quantity:
            entry['thickness'] = value
            continue
        if '%' not in quantity:
            continue
        entry.setdefault('composition', []).append(
            XRFComposition(amount=float(value), name=quantity)
        )
        material_names.add(quantity)

    layers = [
        XRFLayer(
            layer=name,
            composition=data.get('composition'),
            thickness=data.get('thickness'),
        )
        for name, data in layer_data.items()
    ]
    return layers, material_names


class TFC_XRFLibrary(XRFLibrary, EntryData, PlotSection):
    m_def = Section(
        label='XRF Measurement Library',
        a_eln=dict(
            hide=['instruments', 'steps', 'results', 'lab_id'],
            properties=dict(
                order=[
                    'name',
                ]
            ),
        ),
    )

    def get_xrf_overview(self, logger):
        overview_list = []
        try:
            for single_library in self.measurements:
                library_dict = {
                    'x': single_library.get('position_x'),
                    'y': single_library.get('position_y'),
                }
                for layer in single_library.get('layer') or []:
                    if layer.get('thickness') is None:
                        # this is the substrate
                        continue
                    library_dict[f'{layer.get("layer")} Thickness [nm]'] = layer.get(
                        'thickness'
                    )
                    for composition in layer.get('composition'):
                        library_dict[composition.get('name')] = composition.get(
                            'amount'
                        )
                overview_list.append(library_dict)
            return pd.DataFrame(overview_list)
        except (IndexError, KeyError) as e:
            logger.debug(f'The XRF Library does not have the expected structure. {e}')

    def make_library_overview_table(self, overview_df):
        fig = go.Figure(
            data=[
                go.Table(
                    header=dict(
                        values=list(overview_df.columns),
                        fill_color='grey',
                        line_color='darkslategray',
                        font=dict(color='white'),
                    ),
                    cells=dict(
                        values=[overview_df[col] for col in overview_df.columns],
                        line_color='darkslategray',
                    ),
                )
            ]
        )
        return fig

    def make_library_plot(self, overview_df, characteristic):
        fig = go.Figure()
        fig.add_trace(
            go.Scatter(
                x=overview_df['x'],
                y=overview_df['y'],
                mode='markers',
                marker=dict(
                    size=30,
                    color=overview_df[characteristic],
                    colorscale='Viridis',
                    colorbar=dict(title=characteristic),
                    showscale=True,
                ),
                text=overview_df[characteristic],
                hovertemplate=f'x: %{{x}}<br>y: %{{y}}<br>{characteristic}: %{{text}}<extra></extra>',  # noqa: E501
            )
        )
        fig.update_layout(
            title=dict(text=f'Library Overview {characteristic}', y=1.0, yanchor='top'),
            xaxis_title='X-Position (0.1mm)',
            yaxis_title='Y-Position (0.1mm)',
            xaxis=dict(
                showgrid=False,
                scaleanchor='y',
                side='top',
            ),
            yaxis=dict(
                showgrid=False,
                fixedrange=True,
                range=[max(overview_df['y']), min(overview_df['y'])],
            ),
            plot_bgcolor='white',
            paper_bgcolor='white',
            margin=dict(l=10, r=10, t=80, b=10),
            hovermode='closest',
        )
        return fig

    def normalize(self, archive, logger):
        if not self.samples and self.data_folder is not None:
            set_sample_reference(
                archive, self, self.data_folder.split('/')[-1].split('_')[0]
            )

        if self.composition_file and self.data_folder:
            files = _spx_files_in(archive, self.data_folder)
            if not files:
                return

            with archive.m_context.raw_file(self.composition_file, 'rt') as txt_file:
                composition_data = load_XRF_txt(txt_file)

            measurements = []
            material_names: set[str] = set()

            for spx_file in files:
                spx_path = os.path.join(self.data_folder, spx_file)
                measurement_data, position_xyz, energy = _read_single_spx(
                    archive, spx_path
                )

                if self.datetime is None:
                    self.datetime = convert_datetime(
                        measurement_data['DateTime'].iat[0],
                        datetime_format='%Y-%d-%mT%H:%M:%S.%f',
                        utc=False,
                    )

                if self.energy is None:
                    self.energy = energy

                composition_row = composition_data.loc[os.path.splitext(spx_file)[0]]
                layers, row_material_names = _layers_from_composition_row(
                    composition_row
                )
                material_names |= row_material_names

                measurements.append(
                    XRFSingleLibraryMeasurement(
                        data_file=[spx_path],
                        position_x=position_xyz[0],
                        position_y=position_xyz[1],
                        position_z=position_xyz[2],
                        layer=layers,
                        name=f'{round(position_xyz[0], 5)},{round(position_xyz[1], 5)}',
                        description=measurement_data.round(4)
                        .T.rename_axis(None)
                        .to_html(header=False),
                    )
                )

            self.measurements = measurements
            self.material_names = ','.join(sorted(material_names))

        overview_df = self.get_xrf_overview(logger)
        fig1 = self.make_library_overview_table(overview_df)
        library_figures = [
            PlotlyFigure(label='XRF Overview', figure=fig1.to_plotly_json())
        ]
        for characteristic in overview_df.columns:
            if characteristic in ('x', 'y'):
                continue
            fig = self.make_library_plot(overview_df, characteristic)
            json_fig = PlotlyFigure(
                label=f'Library Overview {characteristic}',
                figure=fig.to_plotly_json(),
            )
            library_figures.append(json_fig)
        self.figures = library_figures

        super().normalize(archive, logger)


# %%######################## Generic Entries
# %%######################## Analysis
m_package.__init_metainfo__()
