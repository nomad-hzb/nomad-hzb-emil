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

from baseclasses.helper.utilities import (
    create_archive,
    get_entry_id_from_file_name,
    get_reference,
    set_sample_reference,
)
from nomad.datamodel import EntryArchive
from nomad.datamodel.data import (
    EntryData,
)
from nomad.datamodel.metainfo.annotations import (
    ELNAnnotation,
)
from nomad.datamodel.metainfo.basesections import (
    Activity,
    InstrumentReference,
)
from nomad.metainfo import (
    Quantity,
)
from nomad.parsing import MatchingParser

from nomad_hzb_emil.schema_packages.se_aid_package import SEAID_XPS_ANA

# Same sample id formats as the EMIL general process parser:
# CaTe0001 (EMIL), 61-123-468 (ASCEND wafer), CT-61-123 (ASCEND batch)
SAMPLE_ID_RE = re.compile(
    r'^(?P<sample_id>[A-Z][a-z][A-Z][a-z]\d{4}|\d{2}-\d{3}-\d{3}|[A-Z]{2}-\d{2}-\d{3})'
    r'(?=[-_.]|$)'
)


# All files recognised by this parser come from this instrument.
# NOMAD links the measurement to the instrument entry whose lab_id matches
# XPS_INSTRUMENT_LAB_ID. If no such entry exists on the installation, only a
# warning is logged and the instrument is kept by name.
XPS_instrument_name = 'XPS-ANAlytics'
XPS_instrument_LabID = 'XPS-ANAlytics'  # lab ID of the instrument entry in EMIL Oasis
XPS_instrument_uploadID = 'vXP9c-6ORy2L06k4OlYC-w'
#'vXP9c-6ORy2L06k4OlYC-w' #local test: _4NALKYSRLuZLz_RbFJU7Q
XPS_instrument_entryID = 'jgXBc7awwGMxhdlqyO3SpE4uUJSC'
# real: 'jgXBc7awwGMxhdlqyO3SpE4uUJSC' #local test: 'V38oAnKeTzEOfZVQzDQGzhlZadme'


def get_sample_id_from_file_name(file_name):
    """Return the sample id at the start of the file name, or None."""
    match = SAMPLE_ID_RE.match(file_name)
    return match.group('sample_id') if match else None


class ParsedSEAIDXPSFile(EntryData):
    activity = Quantity(
        type=Activity,
        a_eln=ELNAnnotation(
            component='ReferenceEditQuantity',
        ),
    )


class SEAIDXPSParser(MatchingParser):
    def parse(self, mainfile: str, archive: EntryArchive, logger) -> None:
        file_path = mainfile.rsplit('/raw/', maxsplit=1)[-1]
        file_name = file_path.split('/')[-1]

        entry = SEAID_XPS_ANA()
        entry.name = file_name.rsplit('.', 1)[0]
        entry.data_file = file_path
        entry.instruments = [
            InstrumentReference(
                name=XPS_instrument_name,
                lab_id=XPS_instrument_LabID,
                reference=get_reference(
                    XPS_instrument_uploadID, XPS_instrument_entryID
                ),
            )
        ]

        # Link the sample if the file name starts with a sample id,
        # otherwise the sample can be added manually in the ELN.
        sample_id = get_sample_id_from_file_name(file_name)
        if sample_id:
            set_sample_reference(archive, entry, sample_id, None)

        archive.metadata.entry_name = file_name
        file_name_archive = f'{file_name}.archive.json'
        create_archive(entry, archive, file_name_archive)

        eid = get_entry_id_from_file_name(file_name_archive, archive)
        ref = get_reference(archive.metadata.upload_id, eid)
        archive.data = ParsedSEAIDXPSFile(activity=ref)
        archive.metadata.entry_name = f'XPS Raw {file_name.rsplit(".", 1)[0]}'
