from odoo import models, fields, api
from datetime import timedelta

class WhatsAppMemory(models.Model):
    _name = 'chatbot.whatsapp.memory'
    _description = 'Memoria del chatbot de WhatsApp'

    phone = fields.Char(index=True)
    partner_id = fields.Many2one('res.partner')

    # last_intent = fields.Char()  # [DEPRECATED] Reemplazado por `last_intent_detected`
    last_intent_detected = fields.Char()  # 🆕 Intención global NLP
    flow_state = fields.Char()  # 🆕 Estado actual del flujo conversacional

    last_variant_id = fields.Many2one('product.product')
    last_qty_suggested = fields.Integer()
    data_buffer = fields.Text()
    timestamp = fields.Datetime(auto_now_add=True)

    @api.model
    def clean_old_memory(self):
        expired_time = fields.Datetime.now() - timedelta(minutes=30)
        old = self.sudo().search([('timestamp', '<', expired_time)])
        old.unlink()
