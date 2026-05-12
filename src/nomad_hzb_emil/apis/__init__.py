from nomad.config.models.plugins import APIEntryPoint


class DataUploadAPIEntryPoint(APIEntryPoint):
    def load(self):
        from nomad_hzb_emil.apis.data_upload_api import app
        return app


data_upload_api_entry_point = DataUploadAPIEntryPoint(
    prefix = 'data-upload',
    name = 'Data Upload API',
    description = 'API for uploading data in a more sample connected way.',
)