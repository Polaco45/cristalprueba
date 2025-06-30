from odoo import models, fields, api
from datetime import timedelta

class ChatbotWhatsappMemory(models.Model):
    _name = 'chatbot.whatsapp.memory'
    _description = 'Memoria chatbot WhatsApp'

    partner_id = fields.Many2one('res.partner', string='Partner', required=True)
    flow_state = fields.Char(string='Flow State')
    last_intent_detected = fields.Char(string='Última intención detectada')
    last_variant_id = fields.Many2one('product.product', string='Última variante seleccionada')
    last_qty_suggested = fields.Integer(string='Última cantidad sugerida')
    data_buffer = fields.Text(string='Datos temporales JSON')

    timestamp = fields.Datetime(string='Timestamp', default=fields.Datetime.now)  # CORREGIDO
    @api.model
    def clean_old_memory(self):
        expired_time = fields.Datetime.now() - timedelta(minutes=30)
        old = self.sudo().search([('timestamp', '<', expired_time)])
        old.unlink()
