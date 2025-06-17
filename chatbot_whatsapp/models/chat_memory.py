from odoo import models, fields, api
from datetime import timedelta

class ChatbotWhatsAppMemory(models.Model):
    _name = 'chatbot.whatsapp.memory'
    _description = 'Memoria de chat de WhatsApp'

    partner_id = fields.Many2one('res.partner', required=True, index=True)
    last_intent = fields.Char()
    last_variant_id = fields.Many2one('product.product')
    last_qty_suggested = fields.Integer()
    timestamp = fields.Datetime(default=fields.Datetime.now, required=True)

    @api.model
    def clean_old_memory(self):
        expired_time = fields.Datetime.now() - timedelta(minutes=30)
        old_memories = self.sudo().search([('timestamp', '<', expired_time)])
        old_memories.unlink()