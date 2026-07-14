import pytest


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
