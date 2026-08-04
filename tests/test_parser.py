import os
from datetime import datetime, timezone

import pytest
from nomad.client import normalize_all, parse


@pytest.fixture(
    params=[
        'prevac_sputtering.xlsx',
        'CaTe0001-generalprocess.txt',
        'CT-61-123-generalprocess.txt',
        '61-123-468-generalprocess.txt',
    ]
)
def parsed_archive(request):
    """
    Sets up data for testing and cleans up after the test.
    """
    rel_file = os.path.join('tests', 'data', request.param)
    file_archive = parse(rel_file)[0]
    measurement = os.path.join('tests', 'data', request.param + '.archive.json')
    assert file_archive.data.activity
    archive_json = ''
    for file in os.listdir(os.path.join('tests/data')):
        if 'archive.json' not in file or request.param.replace('#', 'run') not in file:
            continue
        archive_json = file
        measurement = os.path.join('tests', 'data', archive_json)
        measurement_archive = parse(measurement)[0]

        if os.path.exists(measurement):
            os.remove(measurement)
    yield measurement_archive

    assert archive_json


def test_normalize_all(parsed_archive):
    normalize_all(parsed_archive)


def get_archive(file_base):
    file_name = os.path.join('tests', 'data', file_base)
    parse(file_name)[0]
    for file in os.listdir(os.path.join('tests/data')):
        if 'archive.json' not in file or file_base.replace('#', 'run') not in file:
            continue
        measurement = os.path.join('tests', 'data', file)
        measurement_archive = parse(measurement)[0]

        if os.path.exists(measurement):
            os.remove(measurement)
        break
    normalize_all(measurement_archive)
    return measurement_archive


def test_prevac_sputtering_parser():
    file = 'prevac_sputtering.xlsx'
    archive = get_archive(file)
    assert archive.data
    assert archive.data.targets
    assert archive.data.process_properties
    assert archive.data.observables
    assert archive.data.holder == '6" Wafer'
    assert archive.data.process_properties[0].sputter_pressure.magnitude == 0.0167
    assert archive.data.targets[0].name == '1) Al'
    assert archive.data.observables[0].temperature.magnitude == 25


def test_xrf_parser(patch_archive_context):
    file = 'tests/data/XRF/quant.txt'
    archive_file = 'tests/data/XRF/quant.txt.archive.json'
    file_archive = parse(file)[0]
    assert file_archive.data
    assert file_archive.data.activity
    archive = parse(archive_file)[0]
    patch_archive_context(archive)
    normalize_all(archive)
    assert archive.data
    assert archive.data.name.startswith('XRF')
    assert archive.data.datetime == datetime(2026, 7, 9, 8, 5, 32, tzinfo=timezone.utc)
    assert archive.data.data_folder == os.path.dirname(os.path.abspath(file))
    assert archive.data.method == 'XRF'
    assert len(archive.data.energy) == 4096
    assert len(archive.data.measurements) == 9
    assert archive.data.measurements[0].position_x.to('mm').magnitude == 96.65
    assert archive.data.measurements[0].position_y.to('mm').magnitude == 142.82
    assert archive.data.measurements[0].position_z.to('mm').magnitude == 126.707
    assert len(archive.data.measurements[0].layer) == 3
    assert archive.data.measurements[0].layer[0].layer == 'Substrate'
    assert archive.data.measurements[0].layer[0].composition[0].name == 'Si [%]'
    assert archive.data.measurements[0].layer[0].composition[0].amount == 100
    assert archive.data.measurements[8].position_x.to('mm').magnitude == 95.01
    assert archive.data.measurements[8].position_y.to('mm').magnitude == 10.41
    assert archive.data.measurements[8].position_z.to('mm').magnitude == 126.707
    assert len(archive.data.measurements[8].layer) == 3
    assert archive.data.measurements[8].layer[2].layer == 'Layer 2'
    assert archive.data.measurements[8].layer[2].thickness.to('nm').magnitude == 54.2
    assert archive.data.measurements[8].layer[2].composition[0].name == 'Ni [at%]'
    assert archive.data.measurements[8].layer[2].composition[0].amount == 91.8
    assert archive.data.measurements[8].layer[2].composition[1].name == 'Cu [at%]'
    assert archive.data.measurements[8].layer[2].composition[1].amount == 8.2

    # remove archive file that is created during parsing
    # we cannot use get_archive here because the XRF files are stored in a subfolder
    assert os.path.exists(archive_file)
    os.remove(archive_file)
