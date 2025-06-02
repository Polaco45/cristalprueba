from odoo import _, fields, models, api
from odoo.exceptions import UserError

class PosPayment(models.Model):
    _inherit = 'pos.payment'

    payment_reference = fields.Char(string="Payment Reference")
    payment_details = fields.Char(string="Payment Note")

class PosOrder(models.Model):
    _inherit = 'pos.order'

    @api.model
    def _payment_fields(self, order, ui_paymentline):
        result = super(PosOrder, self)._payment_fields(order, ui_paymentline)
        print(">>>>>>>>>result>>>", result)
        result['payment_reference'] = ui_paymentline.get('payment_ref')
        result['payment_details'] = ui_paymentline.get('payment_note')
        return result

