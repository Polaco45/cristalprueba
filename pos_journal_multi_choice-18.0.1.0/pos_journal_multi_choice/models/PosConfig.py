from odoo import models, fields, api

class PosConfig(models.Model):
    _inherit = "pos.config"

    invoice_journal_ids = fields.Many2many(
        "account.journal",
        "pos_config_invoice_journal_rel",
        "config_id",
        "journal_id",
        string="Accounting Invoice Journal",
        help="Invoice journals for Electronic invoices."
    )

    default_journal_id = fields.Many2one(
        'account.journal', 
        string='Default Journal'
    )
