from nomad.config.models.plugins import ParserEntryPoint


class EMILGeneralProcessParserEntryPoint(ParserEntryPoint):
    def load(self):
        from nomad_hzb_emil.parsers.emil_general_parser import (
            EMILGeneralProcessParser,
        )

        return EMILGeneralProcessParser(**self.dict())


class TFCSputteringParserEntryPoint(ParserEntryPoint):
    def load(self):
        from nomad_hzb_emil.parsers.tfc_parser import TFCSputteringParser

        return TFCSputteringParser(**self.dict())


emil_general_process_parser = EMILGeneralProcessParserEntryPoint(
    name='EMILGeneralProcessParser',
    description='Parser for general files starting with a sample id',
    mainfile_name_re=r'^.*[A-Z][a-z][A-Z][a-z]\d{4}(-.*)?\.(?!.*\.*pynb$|.*\.*py$|.*\.*archive\.json$|.*\.*json$)[a-zA-Z0-9.]+$',
)


tfc_sputtering_parser = TFCSputteringParserEntryPoint(
    name='TFCSputteringParser',
    description='Parse xlsx files with sputtering information. Files are defined for the Thin Film Catalysis Group.',
    mainfile_name_re=r'.+\.xlsx',
    mainfile_mime_re=r'^(application\/vnd\.(openxmlformats-officedocument\.spreadsheetml\.sheet|oasis\.opendocument\.spreadsheet))$',
    mainfile_contents_dict={
        'Parameters': {'__has_all_keys': ['Process/Steps  (i.e., layer)']},
        'Observables': {'__has_all_keys': ['Sputtering', 'Values']},
        # '__comment_symbol': '#',
    },
)
