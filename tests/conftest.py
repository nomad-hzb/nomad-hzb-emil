import os
from contextlib import contextmanager
from types import SimpleNamespace

import pytest

TEST_DIR = 'tests/data'


@contextmanager
def raw_file(path, mode='rt', *args, **kwargs):
    with open(os.path.join(TEST_DIR, path), mode, *args, **kwargs) as f:
        yield f


@pytest.fixture
def patch_archive_context(monkeypatch):
    def patch(archive):
        monkeypatch.setattr(
            archive,
            'm_context',
            SimpleNamespace(
                raw_file=raw_file,
                upload_files=SimpleNamespace(
                    raw_listdir=lambda folder: os.scandir(f'{TEST_DIR}/{folder}' or '.')
                ),
            ),
        )

    return patch


@pytest.fixture(autouse=True)
def set_monkey_patch(monkeypatch):
    def mockreturn_search(*args):
        return None

    monkeypatch.setattr(
        'nomad_hzb_emil.schema_packages.tfc_package.set_sample_reference',
        mockreturn_search,
    )
    monkeypatch.setattr(
        'nomad_hzb_emil.parsers.emil_general_parser.update_general_process_entries',
        mockreturn_search,
    )
