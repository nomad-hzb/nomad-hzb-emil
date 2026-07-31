"""Regression test for xrf_spx_parser.py against a real sample .spx file.

Complements test_xrf_spx_parser.py's synthetic-XML tests: those give tight
control over edge cases (missing elements, ambiguous dates, small grids)
that are hard to find naturally in one real file; this test instead checks
that the parser still produces sane, correctly-typed output against an
actual Bruker-generated file, which may contain structure a hand-written
template doesn't anticipate.
"""

import pytest

from nomad_hzb_emil.schema_packages.file_parser import xrf_spx_parser

FIXTURE_PATH = 'tests/data/XRF/01.spx'


@pytest.fixture
def sample_root():
    with open(FIXTURE_PATH, 'rb') as f:
        return xrf_spx_parser._parse_spx(f)


def test_spx_file_parses_without_error(sample_root):
    hardware = xrf_spx_parser.get_spectrum_hardware_params(sample_root)
    settings = xrf_spx_parser.get_system_settings(sample_root)
    header = xrf_spx_parser.get_spectrum_header(sample_root)
    position = xrf_spx_parser.get_position(sample_root)
    channels = xrf_spx_parser.get_channels(
        sample_root, channel_count=header['ChannelCount']
    )

    assert hardware['RealTime'] > 0
    assert settings['Voltage'] > 0
    assert header['ChannelCount'] > 0
    assert position.shape in {(2,), (3,)}
    assert len(channels) == header['ChannelCount']


def test_spx_file_read_end_to_end():
    with open(FIXTURE_PATH, 'rb') as f:
        dataset = xrf_spx_parser.read([f])

    assert len(dataset.spectra) == 1
    assert dataset.measurement_data.shape[0] == 1
    assert dataset.positions.shape == (3, 1)
