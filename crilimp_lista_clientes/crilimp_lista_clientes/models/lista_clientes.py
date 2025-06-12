from odoo import models, fields, api
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta

class ResPartner(models.Model):
    _inherit = 'res.partner'

    def actualizar_lista_precios_clientes(self):
        hoy = fields.Date.today()
        primero_mes = hoy.replace(day=1)
        primero_mes_anterior = (primero_mes - relativedelta(months=1)).replace(day=1)
        ultimo_mes_anterior = primero_mes - timedelta(days=1)

        lista_clientes = self.env.ref('product.list0')  # ID 19
        lista_institucional = self.env.ref('product.list1')  # ID 20
        usuario_operario = self.env['res.users'].browse(155)

        clientes = self.env['res.partner'].search([
            ('customer_rank', '>', 0),
            ('company_type', '=', 'company'),
            ('active', '=', True)
        ])

        for cliente in clientes:
            if not cliente.property_product_pricelist:
                continue

            ventas_mes_actual = self.env['sale.order'].search([
                ('partner_id', '=', cliente.id),
                ('state', 'in', ['sale', 'done']),
                ('date_order', '>=', primero_mes),
                ('date_order', '<=', hoy),
            ])
            total_actual = sum(ventas_mes_actual.mapped('amount_total'))

            if total_actual >= 200000 and cliente.property_product_pricelist.id != lista_institucional.id:
                cliente.property_product_pricelist = lista_institucional
                continue

            if hoy.day != 1:
                continue

            if cliente.create_date.date() >= primero_mes_anterior:
                continue

            ventas_mes_anterior = self.env['sale.order'].search([
                ('partner_id', '=', cliente.id),
                ('state', 'in', ['sale', 'done']),
                ('date_order', '>=', primero_mes_anterior),
                ('date_order', '<=', ultimo_mes_anterior),
            ])
            total_anterior = sum(ventas_mes_anterior.mapped('amount_total'))

            if total_anterior < 160000:
                if cliente.property_product_pricelist.id != lista_clientes.id:
                    cliente.property_product_pricelist = lista_clientes
            elif total_anterior < 200000:
                self.env['mail.activity'].create({
                    'res_model_id': self.env['ir.model']._get('res.partner').id,
                    'res_id': cliente.id,
                    'user_id': usuario_operario.id,
                    'activity_type_id': self.env.ref('mail.mail_activity_data_todo').id,
                    'summary': 'Revisar lista de precios',
                    'note': 'Cliente casi alcanza el mínimo mensual. Revisar si corresponde mantener lista.',
                    'date_deadline': hoy,
                })