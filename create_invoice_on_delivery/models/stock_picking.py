from odoo import models, api

class StockPicking(models.Model):
    _inherit = 'stock.picking'

    @api.model
    def create(self, vals):
        picking = super().create(vals)
        return picking

    def button_validate(self):
        res = super().button_validate()

        for picking in self:
            if picking.picking_type_code == 'outgoing' and picking.state == 'done' and picking.origin:
                sale_order = self.env['sale.order'].search([('name', '=', picking.origin)], limit=1)
                if sale_order:
                    invoice = sale_order._create_invoices()
                    invoice.action_post()  # Validar la factura
        return res
