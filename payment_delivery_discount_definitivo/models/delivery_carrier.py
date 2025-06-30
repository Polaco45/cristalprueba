from odoo import models, fields

class DeliveryCarrier(models.Model):
    _inherit = 'delivery.carrier'

    discount_percent = fields.Float(string='Descuento (%)')
    discount_product_id = fields.Many2one(
        'product.product', string='Producto de descuento',
        help='Producto que representa la línea de descuento en el pedido'
    )
