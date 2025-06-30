from odoo import models, fields

class PaymentAcquirer(models.Model):
    _inherit = 'payment.acquirer'

    discount_percent = fields.Float("Descuento (%)", default=0.0)
    discount_product_id = fields.Many2one('product.product', string="Producto de descuento")
