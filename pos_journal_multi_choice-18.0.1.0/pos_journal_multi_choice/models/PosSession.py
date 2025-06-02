from odoo import models, api

class PosSession(models.Model):
    _inherit = "pos.session"


    @api.model
    def _load_pos_data_models(self, config_id):
        data = super()._load_pos_data_models(config_id)
        data += ['account.journal']
        return data


    def _load_pos_data(self, data):
        data = super()._load_pos_data(data)
        
        data['account.journal'] = self.env['account.journal'].search_read([], ['id', 'name'])
        return data
