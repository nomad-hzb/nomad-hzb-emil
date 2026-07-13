from nomad.config.models.plugins import SchemaPackageEntryPoint


class EMILPackageEntryPoint(SchemaPackageEntryPoint):
    def load(self):
        from nomad_hzb_emil.schema_packages.emil_lab_package import m_package

        return m_package


emil_package_entry_point = EMILPackageEntryPoint(
    name='EMIL Lab package',
    description='Package for HZB EMIL Lab.',
)


class TFCPackageEntryPoint(SchemaPackageEntryPoint):
    def load(self):
        from nomad_hzb_emil.schema_packages.tfc_package import (
            m_package,
        )

        return m_package


tfc_schema_package = TFCPackageEntryPoint(
    name='TFC',
    description='Package for Thin Film Catalysts Group',
)
