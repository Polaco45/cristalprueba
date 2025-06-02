import logging
from odoo import api, fields, models


class PosOrder(models.Model):
    _inherit = "pos.order"

    invoice_journal_id = fields.Many2one(
        "account.journal", "Invoice Journal ",
    )
    custom_journal_id =fields.Integer(string="Journal Custom")
    
    def _prepare_invoice_vals(self):
        values = super(PosOrder, self)._prepare_invoice_vals()
        if self.invoice_journal_id:
            self.write({"invoice_journal_id": self.custom_journal_id})
            values["journal_id"] = self.custom_journal_id
        return values
    
    
    
    @api.model
    def _process_order(self, order, existing_order):
        if order.get("custom_journal_id"):
            order.update({
				'invoice_journal_id': order.get("custom_journal_id"),
			})
        res = super(PosOrder, self)._process_order(order, existing_order)
        return res
