from odoo import models, fields, api
from datetime import timedelta

class WhatsAppMemory(models.Model):
    _name = 'chatbot.whatsapp.memory'
    _description = 'Memoria del chatbot de WhatsApp'
    _order = 'timestamp desc'

    phone = fields.Char(index=True)
    partner_id = fields.Many2one('res.partner', ondelete='cascade')

    # --- ESTADO DEL FLUJO ---
    flow_state = fields.Char(index=True)
    last_intent_detected = fields.Char()
    
    # --- BUFFER DE DATOS ---
    order_lines_buffer = fields.Text(default='[]') # Carrito de compras en formato JSON
    data_buffer = fields.Text() # Buffer para datos temporales (ej. selección de variantes)

    # --- DATOS TEMPORALES PARA UN SOLO PRODUCTO ---
    last_variant_id = fields.Many2one('product.product')
    last_qty_suggested = fields.Integer()

    timestamp = fields.Datetime(default=fields.Datetime.now, required=True)

    @api.model
    def clean_old_memory(self):
        # Limpia memorias inactivas de más de 30 minutos
        expired_time = fields.Datetime.now() - timedelta(minutes=30)
        old_memory_records = self.search([
            ('timestamp', '<', expired_time),
            ('flow_state', '=', False) # Solo limpia las que no están en un flujo activo
        ])
        old_memory_records.unlink()