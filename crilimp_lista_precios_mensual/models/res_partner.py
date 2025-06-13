from odoo import models, fields, api
from datetime import timedelta
from dateutil.relativedelta import relativedelta

class ResPartner(models.Model):
    _inherit = 'res.partner'

    @api.model
    def actualizar_lista_precios_mensual(self):
        hoy = fields.Date.today()
        # límites de periodo
        primero_mes = hoy.replace(day=1)
        primero_mes_ant = (primero_mes - relativedelta(months=1)).replace(day=1)
        ultimo_mes_ant = primero_mes - timedelta(days=1)

        # parámetros
        umbral  = 200000
        toler   = 0.20
        lista_cli = self.env['product.pricelist'].search([('name','ilike','Clientes')], limit=1)
        lista_ins = self.env['product.pricelist'].search([('name','ilike','Institucional')], limit=1)
        # operador "Luca de Química Cristal"
        oper    = self.env['res.users'].search([('name','=','Luca de Química Cristal')], limit=1)
        act_t   = self.env.ref('mail.mail_activity_data_todo')

        # selecciono sólo companies con ventas
        partners = self.search([('customer_rank','>',0), ('active','=',True)])
        for p in partners:
            pricelist = p.property_product_pricelist
            if not pricelist:
                continue

            # 1) Subida inmediata: ventas desde inicio de mes hasta hoy
            ventas_act = self.env['sale.order'].search([
                ('partner_id','=',p.id),
                ('state','in',['sale','done']),
                ('date_order','>=', primero_mes),
                ('date_order','<=', hoy),
            ])
            tot_act = sum(ventas_act.mapped('amount_total'))
            if tot_act >= umbral and pricelist != lista_ins:
                p.property_product_pricelist = lista_ins
                continue

            # 2) Sólo el día 1 chequeo democión / actividad
            if hoy.day != 1:
                continue
            # ignoro clientes dados de alta en el mes anterior o este
            if p.create_date.date() >= primero_mes_ant:
                continue

            ventas_ant = self.env['sale.order'].search([
                ('partner_id','=',p.id),
                ('state','in',['sale','done']),
                ('date_order','>=', primero_mes_ant),
                ('date_order','<=', ultimo_mes_ant),
            ])
            tot_ant = sum(ventas_ant.mapped('amount_total'))

            # si cayó más de 20% (tot_ant < umbral * (1 - toler)), baja a Clientes
            if tot_ant < umbral * (1 - toler):
                p.property_product_pricelist = lista_cli

            # si está entre 80% y 100% del umbral → crear actividad de revisión
            elif umbral * (1 - toler) <= tot_ant < umbral and pricelist == lista_ins:
                self.env['mail.activity'].create({
                    'res_model_id': self.env['ir.model']._get('res.partner').id,
                    'res_id': p.id,
                    'user_id': oper.id,
                    'activity_type_id': act_t.id,
                    'summary': 'Revisar lista de precios',
                    'note': 'Ventas mes anterior (<200k) dentro de tolerancia 20%. Confirmar si baja lista.',
                    'date_deadline': hoy,
                })
