from odoo import models, fields

class PaymentProvider(models.Model):
    _inherit = 'payment.provider'

    discount_percent = fields.Float(string="Descuento (%) para la web")
    discount_product_id = fields.Many2one('product.product', string="Producto de descuento")