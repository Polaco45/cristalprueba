# models/chat_memory.py

from odoo import models, fields, api
from datetime import timedelta

class ChatbotWhatsAppMemory(models.Model):
    _name = 'chatbot.whatsapp.memory'
    _description = 'Memoria de chat de WhatsApp'

    partner_id         = fields.Many2one('res.partner', index=True)
    phone              = fields.Char(help="Teléfono temporal para nuevos clientes")
    last_intent        = fields.Char()
    last_variant_id    = fields.Many2one('product.product')
    last_qty_suggested = fields.Integer()
    data_buffer        = fields.Text(help="Para guardar datos intermedios (nombre, email)")
    timestamp          = fields.Datetime(default=fields.Datetime.now, required=True)

    @api.model
    def clean_old_memory(self):
        expired_time = fields.Datetime.now() - timedelta(minutes=30)
        old = self.sudo().search([('timestamp', '<', expired_time)])
        old.unlink()
