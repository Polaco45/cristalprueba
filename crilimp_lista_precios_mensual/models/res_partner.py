from odoo import models, fields, api
from datetime import timedelta
from dateutil.relativedelta import relativedelta

class ResPartner(models.Model):
    _inherit = 'res.partner'

    @api.model
    def actualizar_lista_precios_mensual(self):
        hoy = fields.Date.today()
        primero_mes = hoy.replace(day=1)
        primero_mes_anterior = (primero_mes - relativedelta(months=1)).replace(day=1)
        ultimo_mes_anterior = primero_mes - timedelta(days=1)

        # Listas de precios
        lista_clientes = self.env['product.pricelist'].search([('name', 'ilike', 'Clientes')], limit=1)
        lista_institucional = self.env['product.pricelist'].search([('name', 'ilike', 'Institucional')], limit=1)

        # Umbrales y tolerancia
        umbral_clientes = 100000
        umbral_institucional = 200000
        tolerancia = 0.20

        operario = self.env['res.users'].browse(155)
        activity_type = self.env.ref('mail.mail_activity_data_todo')

        partners = self.search([
            ('customer_rank', '>', 0),
            ('is_company', '=', True),
            ('active', '=', True),
        ])
        for p in partners:
            pricelist = p.property_product_pricelist
            if not pricelist:
                continue

            # Ventas mes actual
            ventas = self.env['sale.order'].search([
                ('partner_id', '=', p.id),
                ('state', 'in', ['sale', 'done']),
                ('date_order', '>=', primero_mes),
                ('date_order', '<=', hoy),
            ])
            total = sum(ventas.mapped('amount_total'))

            # Siempre subir si supera umbral
            if total >= umbral_institucional and pricelist != lista_institucional:
                p.property_product_pricelist = lista_institucional
                continue
            if total >= umbral_clientes and pricelist == lista_clientes:
                p.property_product_pricelist = lista_institucional
                continue

            # Solo en día 1 puede bajar o revisar
            if hoy.day != 1:
                continue
            # No bajar si cliente creado en el mes anterior o éste
            if p.create_date.date() >= primero_mes_anterior:
                continue

            ventas_ant = self.env['sale.order'].search([
                ('partner_id', '=', p.id),
                ('state', 'in', ['sale', 'done']),
                ('date_order', '>=', primero_mes_anterior),
                ('date_order', '<=', ultimo_mes_anterior),
            ])
            total_ant = sum(ventas_ant.mapped('amount_total'))

            # Democión con tolerancia
            if total_ant < umbral_clientes * (1 - tolerancia):
                p.property_product_pricelist = lista_clientes
            elif umbral_clientes * (1 - tolerancia) <= total_ant < umbral_clientes:
                # Crear actividad de revisión
                self.env['mail.activity'].create({
                    'res_model_id': self.env['ir.model']._get('res.partner').id,
                    'res_id': p.id,
                    'user_id': operario.id,
                    'activity_type_id': activity_type.id,
                    'summary': 'Revisar lista de precios',
                    'note': 'Ventas mes anterior cercanas al mínimo. Decidir si baja lista.',
                    'date_deadline': hoy,
                })
