import os

import numpy as np
import pytest
from nomad.client import normalize_all, parse

from nomad_hzb_emil.parsers.se_aid_parser import get_sample_id_from_file_name
from nomad_hzb_emil.schema_packages.file_parser.xps_txt_parser import read_xps_txt

DATA_DIR = os.path.join('tests', 'data', 'SEAID')


def parse_xps(file_name, patch_archive_context):
    file = os.path.join(DATA_DIR, file_name)
    archive_file = f'{file}.archive.json'
    file_archive = parse(file)[0]
    assert file_archive.data
    assert file_archive.data.activity
    try:
        archive = parse(archive_file)[0]
        patch_archive_context(archive)
        normalize_all(archive)
    finally:
        # remove archive file that is created during parsing
        if os.path.exists(archive_file):
            os.remove(archive_file)
    return file_archive, archive


def test_read_xps_txt():
    with open(os.path.join(DATA_DIR, 'xps_Mg_survey.txt')) as f:
        regions = read_xps_txt(f)
    assert len(regions) == 1
    region = regions[0]
    assert region['transition'] == 'Mg survey'
    assert region['energy_mode'] == 'KE'
    assert region['number_of_sweeps'] == 3
    assert region['pass_energy'] == 200
    assert region['excitation_source'] == 'Mg Ka 1253.6 eV normal'
    assert region['exit_slit'] == '5 x 11 mm'
    assert region['notes'] is None
    assert len(region['counts']) == 5202
    assert region['kinetic_energy'][0] == 218.5
    assert region['counts'][0] == pytest.approx(86827.1573)
    assert np.allclose(region['binding_energy'], 1253.6 - region['kinetic_energy'])


@pytest.mark.parametrize(
    'file_name, sample_id',
    [
        ('CaTe0001-xps_Mg_survey.txt', 'CaTe0001'),
        ('CaTe0001.txt', 'CaTe0001'),
        ('61-123-468_xps.txt', '61-123-468'),
        ('CT-61-123-xps.txt', 'CT-61-123'),
        ('xps_Mg_survey.txt', None),
        ('CaTe00012-xps.txt', None),
    ],
)
def test_sample_id_from_file_name(file_name, sample_id):
    assert get_sample_id_from_file_name(file_name) == sample_id


def test_xps_parser(patch_archive_context):
    file_archive, archive = parse_xps('xps_Mg_survey.txt', patch_archive_context)
    assert file_archive.metadata.entry_name == 'XPS Raw xps_Mg_survey'

    data = archive.data
    assert data.m_def.name == 'SEAID_XPS'
    assert data.name == 'xps_Mg_survey'
    assert data.method == 'X-ray photoelectron spectroscopy'
    assert not data.samples
    assert len(data.instruments) == 1
    assert data.instruments[0].name == 'XPS-ANAlytics'
    assert data.instruments[0].lab_id == 'XPS-ANAlytics'
    assert len(data.regions) == 1

    region = data.regions[0]
    assert region.name == 'Mg survey'
    assert region.settings.start_energy.to('eV').magnitude == 218.5
    assert region.settings.end_energy.to('eV').magnitude == 1258.6
    assert region.settings.energy_step.to('eV').magnitude == 0.2
    assert region.settings.dwell_time.to('s').magnitude == 0.1
    assert region.settings.analyser_mode == 'CAE'
    assert region.settings.excitation_energy.to('eV').magnitude == 1253.6
    assert region.settings.analyser_workfunction.to('eV').magnitude == 4.5
    assert len(region.counts) == 5202
    assert region.binding_energy[0].to('eV').magnitude == pytest.approx(1035.1)
    assert len(data.figures) == 1


def test_xps_parser_links_sample(patch_archive_context, monkeypatch):
    calls = []
    monkeypatch.setattr(
        'nomad_hzb_emil.parsers.se_aid_parser.set_sample_reference',
        lambda archive, entry, sample_id, upload_id: calls.append(sample_id),
    )
    parse_xps('CaTe0001-xps_Mg_survey.txt', patch_archive_context)
    assert calls == ['CaTe0001']
