import os

import pandas as pd
import pytest
from nomad.client import normalize_all, parse


@pytest.fixture(
    params=[
        'tfc_sputtering.xlsx',

    ]
)
def parsed_archive(request):
    """
    Sets up data for testing and cleans up after the test.
    """
    rel_file = os.path.join('tests', 'data', request.param)
    file_archive = parse(rel_file)[0]
    measurement = os.path.join(
        'tests', 'data', request.param + '.archive.json')
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
    print(measurement_archive)
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


def get_multiple_archives(file_base):
    file_name = os.path.join('tests', 'data', file_base)
    parse(file_name)[0]
    measurement_archive_list = []
    for file in os.listdir(os.path.join('tests/data')):
        if 'archive.json' not in file or file_base.replace('#', 'run') not in file:
            continue
        measurement = os.path.join('tests', 'data', file)
        measurement_archive = parse(measurement)[0]
        if os.path.exists(measurement):
            os.remove(measurement)
            measurement_archive_list.append(measurement_archive)
            normalize_all(measurement_archive)
    return measurement_archive_list


def test_tfc_sputtering_parser():
    file = 'tfc_sputtering.xlsx'
    archive = get_archive(file)
    assert archive.data
    assert archive.data.targets
    assert archive.data.process_properties
    assert archive.data.observables
    assert archive.data.holder == '6" Wafer'
    assert archive.data.process_properties[0].sputter_pressure.magnitude == 0.0167
    assert archive.data.targets[0].name == '1) Al'
    assert archive.data.observables[0].temperature.magnitude == 25
