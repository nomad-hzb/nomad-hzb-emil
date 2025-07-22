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


from baseclasses.chemical_energy import (
    GeneralProcess,
)
from baseclasses.helper.utilities import export_lab_id
from nomad.datamodel.data import ArchiveSection, EntryData
from nomad.datamodel.metainfo.basesections import (
    CompositeSystem,
    CompositeSystemReference,
)
from nomad.datamodel.results import Material
from nomad.metainfo import Quantity, SchemaPackage, Section, SubSection
from unidecode import unidecode

m_package = SchemaPackage()


def correct_lab_id(lab_id):
    return lab_id[4:].isdigit() and len(lab_id[4:]) == 4


def get_next_project_sample_number(data, entry_id):
    """Check the lab ids of a project id for project_sample_number (last digits of lab_id) and returns the next higher one"""  # noqa: E501
    project_sample_numbers = []
    for entry in data:
        lab_ids = entry['results']['eln']['lab_ids']
        if entry['entry_id'] == entry_id and correct_lab_id(lab_ids[0]):
            return int(lab_ids[0][4:])
        project_sample_numbers.extend(
            [int(lab_id[4:]) for lab_id in lab_ids if correct_lab_id(lab_id)]
        )
    return max(project_sample_numbers) + 1 if project_sample_numbers else 1


def create_id(archive, lab_id_base):
    from nomad.app.v1.models import MetadataPagination
    from nomad.search import search

    query = {'entry_type': 'Beamline_Sample', 'results.eln.lab_ids': lab_id_base}
    pagination = MetadataPagination()
    pagination.page_size = 9999
    search_result = search(
        owner='all',
        query=query,
        pagination=pagination,
        user_id=archive.metadata.main_author.user_id,
    )
    project_sample_number = get_next_project_sample_number(
        search_result.data, archive.metadata.entry_id
    )

    return f'{lab_id_base}{project_sample_number:04d}'


class Substrate(ArchiveSection):
    substrate_type = Quantity(
        type=str,
        a_eln=dict(
            component='EnumEditQuantity',
            props=dict(
                suggestions=[
                    'glassy carbon',
                    'ITO on glass',
                    'Platinum',
                    'glass',
                    'silicon wafer',
                ]
            ),
        ),
    )

    substrate_dimension = Quantity(
        type=str,
        a_eln=dict(
            component='StringEditQuantity',
        ),
    )


def collectSampleData(archive):
    # This function gets all archives whcih reference this archive.
    # Iterates over them and selects relevant data for the
    # result section of the solarcellsample
    # At the end the synthesis steps are ordered
    # returns a dictionary containing synthesis process, JV and EQE information

    from nomad import files
    from nomad.app.v1.models import MetadataPagination
    from nomad.search import search

    # search for all archives referencing this archive
    query = {
        'entry_references.target_entry_id': archive.metadata.entry_id,
    }
    pagination = MetadataPagination()
    pagination.page_size = 100
    search_result = search(
        owner='all',
        query=query,
        pagination=pagination,
        user_id=archive.metadata.main_author.user_id,
    )
    entry = {}
    for res in search_result.data:
        try:
            # Open Archives
            with files.UploadFiles.get(upload_id=res['upload_id']).read_archive(
                entry_id=res['entry_id']
            ) as arch:
                entry_id = res['entry_id']
                entry.update({entry_id: {}})
                try:
                    entry[entry_id]['elements'] = arch[entry_id]['results']['material'][
                        'elements'
                    ]
                except BaseException:
                    entry[entry_id]['elements'] = []

        except Exception as e:
            print('Error in processing data: ', e)

    return entry


class EMIL_Sample(CompositeSystem, EntryData):
    m_def = Section(
        a_eln=dict(
            properties=dict(
                order=[
                    'name',
                    'lab_id',
                ]
            ),
        ),
    )

    lab_id = Quantity(
        type=str,
        description="""An ID string that is unique at least for the lab that produced this data.""",  # noqa: E501
    )

    parent = SubSection(section_def=CompositeSystemReference)
    substrate = SubSection(section_def=Substrate)

    def normalize(self, archive, logger):
        super().normalize(archive, logger)

        if not self.lab_id:
            author = archive.metadata.main_author
            first_short, last_short = 'S', ''
            try:
                first_short = unidecode(author.first_name)[:2]
                last_short = unidecode(author.last_name)[:2]
            except Exception:
                pass
            self.lab_id = create_id(archive, str(first_short) + str(last_short))
        export_lab_id(archive, self.lab_id)

        if not archive.results.material:
            archive.results.material = Material()
        if not archive.results.material.elements:
            archive.results.material.elements = []

        result_data = collectSampleData(archive)
        for _, process in result_data.items():
            if not process['elements']:
                continue
            archive.results.material.elements.extend(process['elements'])
        archive.results.material.elements = list(set(archive.results.material.elements))


class EMIL_GeneralProcess(GeneralProcess, EntryData):
    m_def = Section(
        a_eln=dict(
            hide=[
                'lab_id',
                'steps',
                'instruments',
                'results',
            ],
            properties=dict(order=[]),
        ),
    )

    def normalize(self, archive, logger):
        super().normalize(archive, logger)


m_package.__init_metainfo__()
