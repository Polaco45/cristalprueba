from odoo import api, fields, models

class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    pos_invoice_journal_ids = fields.Many2many(
        related="pos_config_id.invoice_journal_ids", 
        string="Journals Available in POS",
        readonly=False
    )

    pos_default_journal_id = fields.Many2one(
        related='pos_config_id.default_journal_id',
        string="Default POS Journal",
        domain='[("id", "in", pos_invoice_journal_ids)]', 
        readonly=False
    )
