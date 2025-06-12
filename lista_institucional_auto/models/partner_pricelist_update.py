from odoo import models, api
from datetime import date

class ResPartner(models.Model):
    _inherit = 'res.partner'

    @api.model
    def actualizar_lista_institucional(self):
        hoy = date.today()
        inicio_mes = hoy.replace(day=1)

        lista_institucional = self.env['product.pricelist'].browse(20)

        clientes = self.env['res.partner'].search([('customer_rank', '>', 0)])
        for cliente in clientes:
            ventas = self.env['sale.order'].search([
                ('partner_id', '=', cliente.id),
                ('state', 'in', ['sale', 'done']),
                ('date_order', '>=', inicio_mes),
                ('date_order', '<=', hoy)
            ])
            total = sum(ventas.mapped('amount_total'))
            if total >= 100000 and cliente.property_product_pricelist.id != lista_institucional.id:
                cliente.property_product_pricelist = lista_institucional
