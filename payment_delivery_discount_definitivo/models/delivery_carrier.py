from odoo import models, fields

class DeliveryCarrier(models.Model):
    _inherit = 'delivery.carrier'

    discount_percent = fields.Float("Descuento (%)", default=0.0)
    discount_product_id = fields.Many2one('product.product', string="Producto de descuento")
