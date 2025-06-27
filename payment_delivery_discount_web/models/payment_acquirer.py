from odoo import models, fields

class PaymentAcquirer(models.Model):
    _inherit = 'payment.acquirer'

    discount_percent = fields.Float("Descuento (%)")
