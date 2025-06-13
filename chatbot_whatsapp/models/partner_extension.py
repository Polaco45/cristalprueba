from odoo import models, fields

class ResPartner(models.Model):
    _inherit = 'res.partner'

    last_requested_product_id = fields.Many2one(
        'product.product', string="Último producto pedido"
    )
    last_requested_qty = fields.Integer(
        string="Última cantidad pedida"
    )
