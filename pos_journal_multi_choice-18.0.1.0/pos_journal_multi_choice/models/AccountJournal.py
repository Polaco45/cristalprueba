
from odoo import models, api


class AccountJournal(models.Model):
    _name = 'account.journal'
    _inherit = ['account.journal', 'pos.load.mixin']



    @api.model
    def _load_pos_data_fields(self, config_id):
        return []
    

    
    @api.model
    def _load_pos_data_domain(self, data):
        return [('id', 'in', data['pos.config']['data'][0]['invoice_journal_ids'])]