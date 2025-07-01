from odoo import models, fields, api
from datetime import timedelta

class WhatsAppMemory(models.Model):
    _name = 'chatbot.whatsapp.memory'
    _description = 'Memoria del chatbot de WhatsApp'

    phone = fields.Char(index=True)
    partner_id = fields.Many2one('res.partner', string="Cliente")

    # Estado y contexto
    last_intent_detected = fields.Char(string="Última Intención Detectada")
    flow_state = fields.Char(string="Estado del Flujo")
    data_buffer = fields.Text(string="Buffer de Datos Temporales")
    timestamp = fields.Datetime(string="Última Actividad", default=fields.Datetime.now, required=True)

    # Contexto específico del pedido
    last_variant_id = fields.Many2one('product.product', string="Última Variante Seleccionada")
    last_qty_suggested = fields.Integer(string="Última Cantidad Sugerida")
    
    # Carrito de Compras
    pending_order_lines = fields.Text(string="Líneas de Pedido Pendientes (JSON)", default='[]')

    _sql_constraints = [
        ('partner_id_unique', 'unique(partner_id)', 'Solo puede existir un registro de memoria por cliente.')
    ]

    @api.model
    def clean_old_memory(self):
        # Limpia memorias inactivas por más de 30 minutos para evitar que queden carritos abandonados.
        expired_time = fields.Datetime.now() - timedelta(minutes=30)
        old_memory_records = self.sudo().search([('timestamp', '<', expired_time)])
        if old_memory_records:
            _logger.info(f"🗑️ Limpiando {len(old_memory_records)} registros de memoria expirados.")
            old_memory_records.unlink()

    def write(self, vals):
        # Actualiza el timestamp en cada escritura para mantener la sesión activa
        if 'timestamp' not in vals:
            vals['timestamp'] = fields.Datetime.now()
        return super(WhatsAppMemory, self).write(vals)