from odoo import models, fields

class ResPartner(models.Model):
    _inherit = 'res.partner'

    last_requested_product_id = fields.Many2one(
        'product.product', string="Último producto pedido",
        help="Producto que se le ofreció al cliente cuando hubo falta de stock"
    )
    last_requested_qty = fields.Integer(
        string="Última cantidad pedida",
        help="Cantidad máxima disponible que se ofreció al cliente"
    )
