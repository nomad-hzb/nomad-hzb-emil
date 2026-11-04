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
        ('AnVe0001-xps_Mg_survey.txt', 'AnVe0001'),
        ('AnVe0001.txt', 'AnVe0001'),
        ('61-123-468_xps.txt', '61-123-468'),
        ('CT-61-123-xps.txt', 'CT-61-123'),
        ('xps_Mg_survey.txt', None),
        ('AnVe00012-xps.txt', None),
    ],
)
def test_sample_id_from_file_name(file_name, sample_id):
    assert get_sample_id_from_file_name(file_name) == sample_id


def test_xps_parser(patch_archive_context):
    file_archive, archive = parse_xps('xps_Mg_survey.txt', patch_archive_context)
    assert file_archive.metadata.entry_name == 'XPS Raw xps_Mg_survey'

    data = archive.data
    assert data.m_def.name == 'SEAID_XPS_ANA'
    assert data.name == 'xps_Mg_survey'
    assert data.method == 'X-ray photoelectron spectroscopy'
    assert not data.samples
    assert len(data.instruments) == 1
    assert data.instruments[0].name == 'XPS-ANAlytics'
    assert data.instruments[0].lab_id == 'XPS-ANAlytics'
    # points to the instrument entry set in se_aid_parser.py
    assert data.instruments[0].m_to_dict()['reference'].startswith('../uploads/')
    assert len(data.regions) == 1

    region = data.regions[0]
    assert region.name == 'Mg survey'
    settings = region.settings
    assert settings.m_def.name == 'SEAID_XPS_ANA_RegionSettings'
    # quantities inherited from PESSpecsLabProdigySettings
    assert settings.region == 'Mg survey'
    assert settings.scan_variable == 'KE'
    assert settings.energy_minimum.to('eV').magnitude == 218.5
    assert settings.energy_maximum.to('eV').magnitude == 1258.6
    assert settings.step_size.to('eV').magnitude == 0.2
    assert settings.dwell_time.to('s').magnitude == 0.1
    assert settings.pass_energy.to('eV').magnitude == 200
    assert settings.excitation_energy.to('eV').magnitude == 1253.6
    assert settings.analyzer_lens_mode == 'high'
    assert settings.analyzer_slit == '5 x 11 mm'
    assert settings.comment is None
    assert settings.analyzer_parameters.work_function.to('eV').magnitude == 4.5
    assert settings.source_parameters.anode == 'Mg Ka'
    assert settings.source_parameters.excitation_energy.to('eV').magnitude == 1253.6
    # quantities added in SEAID_XPSRegionSettings
    assert settings.number_of_sweeps == 3
    assert settings.analyser_mode == 'CAE'
    assert settings.divide_voltages_by_10 == 'off'
    assert settings.aperture == '4'
    assert settings.excitation_source == 'Mg Ka 1253.6 eV normal'
    assert len(region.counts) == 5202
    assert region.binding_energy[0].to('eV').magnitude == pytest.approx(1035.1)
    assert len(data.figures) == 1


def test_xps_parser_links_sample(patch_archive_context, monkeypatch):
    calls = []
    monkeypatch.setattr(
        'nomad_hzb_emil.parsers.se_aid_parser.set_sample_reference',
        lambda archive, entry, sample_id, upload_id: calls.append(sample_id),
    )
    parse_xps('AnVe0001-xps_Mg_survey.txt', patch_archive_context)
    assert calls == ['AnVe0001']


def test_xps_notes_go_to_description(patch_archive_context):
    _, archive = parse_xps('xps_Mg_survey.txt', patch_archive_context)
    # the example file has an empty "Notes" line
    assert archive.data.description is None

    # a description written in the ELN is kept when the file is read again
    archive.data.description = 'edited in the ELN'
    normalize_all(archive)
    assert archive.data.description == 'edited in the ELN'
    assert len(archive.data.regions[0].counts) == 5202


def test_xps_file_notes_fill_description(patch_archive_context):
    _, archive = parse_xps('xps_with_notes.txt', patch_archive_context)
    assert archive.data.description == 'first test of Mg anode'


def test_read_xps_txt_incomplete_file():
    # header entries missing or empty, broken data lines
    with open(os.path.join(DATA_DIR, 'xps_incomplete.txt')) as f:
        regions = read_xps_txt(f)
    region = regions[0]
    assert region['transition'] == 'O 1s'
    assert region['energy_mode'] is None
    assert region.get('excitation_energy') is None
    assert len(region['counts']) == 3
    assert region['binding_energy'] is None


def test_xps_parser_incomplete_file(patch_archive_context):
    _, archive = parse_xps('xps_incomplete.txt', patch_archive_context)
    region = archive.data.regions[0]
    assert region.name == 'O 1s'
    assert region.settings.pass_energy.to('eV').magnitude == 20
    assert region.settings.analyzer_parameters is None
    assert region.binding_energy is None
    assert len(region.counts) == 3
    # without binding energies the spectrum is plotted over kinetic energy
    assert len(archive.data.figures) == 1
