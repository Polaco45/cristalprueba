from odoo import models, fields

class DeliveryCarrier(models.Model):
    _inherit = 'delivery.carrier'

    discount_percent = fields.Float("Descuento (%)")
