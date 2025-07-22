from nomad.config.models.plugins import ParserEntryPoint


class EMILGeneralProcessParserEntryPoint(ParserEntryPoint):
    def load(self):
        from nomad_hzb_emil.parsers.emil_general_parser import (
            EMILGeneralProcessParser,
        )

        return EMILGeneralProcessParser(**self.dict())


emil_general_process_parser = EMILGeneralProcessParserEntryPoint(
    name='EMILGeneralProcessParser',
    description='Parser for general files starting with a sample id',
    mainfile_name_re=r'^.*[A-Z][a-z][A-Z][a-z]\d{4}(-.*)?\.(?!.*\.*pynb$|.*\.*py$|.*\.*archive\.json$|.*\.*json$)[a-zA-Z0-9.]+$',
)
