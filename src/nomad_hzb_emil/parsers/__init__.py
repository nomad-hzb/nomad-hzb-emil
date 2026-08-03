from nomad.config.models.plugins import ParserEntryPoint


class EMILGeneralProcessParserEntryPoint(ParserEntryPoint):
    def load(self):
        from nomad_hzb_emil.parsers.emil_general_parser import (
            EMILGeneralProcessParser,
        )

        return EMILGeneralProcessParser(**self.model_dump())


class PrevacSputteringParserEntryPoint(ParserEntryPoint):
    def load(self):
        from nomad_hzb_emil.parsers.tfc_parser import TFCSputteringParser

        return TFCSputteringParser(**self.model_dump())


class TFCXRFLibraryParserEntryPoint(ParserEntryPoint):
    def load(self):
        from nomad_hzb_emil.parsers.tfc_parser import TFCXRFParser

        return TFCXRFParser(**self.model_dump())


emil_general_process_parser = EMILGeneralProcessParserEntryPoint(
    name='EMILGeneralProcessParser',
    description='Parser for general files starting with a sample id',
    mainfile_name_re=r'^.*[A-Z][a-z][A-Z][a-z]\d{4}(-.*)?\.(?!.*\.*pynb$|.*\.*py$|.*\.*archive\.json$|.*\.*json$)[a-zA-Z0-9.]+$',
)


prevac_sputtering_parser = PrevacSputteringParserEntryPoint(
    name='PrevacSputteringParser',
    description='Parse xlsx files with sputtering information. '
    'Files are defined for the Prevac sputtering machine at EMIL.',
    mainfile_name_re=r'.+\.xlsx',
    mainfile_mime_re=r'^(application\/vnd\.(openxmlformats-officedocument\.spreadsheetml\.sheet|oasis\.opendocument\.spreadsheet))$',
    mainfile_contents_dict={
        'Parameters': {'__has_all_keys': ['Process/Steps  (i.e., layer)']},
        'Observables': {'__has_all_keys': ['Sputtering', 'Values']},
        # '__comment_symbol': '#',
    },
)

tfc_xrf_parser = TFCXRFLibraryParserEntryPoint(
    name='TFCXRFParser',
    description='Parse txt files with XRF. '
    'Files are defined for the Thin Film Catalysis Group '
    'and later combined with spx files that are located the same directory.',
    mainfile_name_re=r'.*\.txt',
    mainfile_contents_re=r'((([\s\S]*\bBasis\b)([\s\S]*\bSpektrum\b)([\s\S]*\bDicke\b)([\s\S]*\bBase\b)([\s\S]*\bMittelwert\b)([\s\S]*\bStd\sAbw\.?\b)([\s\S]*\bStd\sAbw\.\srel\.\s\[%\]).*)|(([\s\S]*\bSubstrate\b)([\s\S]*\bSpectrum\b)([\s\S]*\bThickn\.?\b)([\s\S]*\bBase\b)([\s\S]*\bMean\svalue\b)([\s\S]*\bStd dev\.?\b)([\s\S]*\bStd\sdev\.\srel\.\s\[%\]).*))',  # noqa: E501
)
