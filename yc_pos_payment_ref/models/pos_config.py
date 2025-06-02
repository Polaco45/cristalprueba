from odoo import _, fields, models, api
from odoo.exceptions import UserError

class PosConfig(models.Model):
    _inherit = 'pos.config'

    payment_reference_detail = fields.Boolean(string="Allow Payment Reference Details")
    payment_ref_method_ids = fields.Many2many('pos.payment.method', 'payment_ref_method_rel', string="Allow Payment Reference for Payment Methods")

class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    payment_reference_detail_settings = fields.Boolean(string="Allow Payment Reference Details", related='pos_config_id.payment_reference_detail', readonly=False)
    payment_ref_method_ids_settings = fields.Many2many('pos.payment.method', 'payment_ref_method_setting_rel', string="Allow Payment Reference for Payment Methods", related='pos_config_id.payment_ref_method_ids', readonly=False)
