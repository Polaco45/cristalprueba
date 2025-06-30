from odoo import models, fields, api
from datetime import timedelta

class WhatsAppMemory(models.Model):
    _name = 'chatbot.whatsapp.memory'
    _description = 'Memoria del chatbot de WhatsApp'

    phone = fields.Char(index=True)
    partner_id = fields.Many2one('res.partner')

    last_intent_detected = fields.Char()
    flow_state = fields.Char()

    last_variant_id = fields.Many2one('product.product')
    last_qty_suggested = fields.Integer()
    data_buffer = fields.Text()  # Acá almacenamos cosas como {"cart": [...], "products": [...]}

    timestamp = fields.Datetime(default=fields.Datetime.now)

    @api.model
    def clean_old_memory(self):
        expired_time = fields.Datetime.now() - timedelta(minutes=30)
        old = self.sudo().search([('timestamp', '<', expired_time)])
        old.unlink()

    @api.model
    def update_memory(self, memory_id, values):
        """Método helper para actualizar la memoria y renovar el timestamp"""
        memory = self.browse(memory_id)
        values['timestamp'] = fields.Datetime.now()
        return memory.write(values)
