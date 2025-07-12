# chatbot_whatsapp/models/whatsapp_chatbot.py

from odoo import models, api
from ..utils.utils import clean_html, normalize_phone
from .chatbot_processor import ChatbotProcessor
import logging
from datetime import datetime, timedelta

_logger = logging.getLogger(__name__)

class WhatsAppMessage(models.Model):
    _inherit = 'whatsapp.message'

    @api.model_create_multi
    def create(self, vals_list):
        """
        Sobrecarga del método create para:
        1. Detectar intervenciones humanas y pausar el bot.
        2. Procesar mensajes entrantes y delegarlos al ChatbotProcessor.
        """
        bot_user_id = self.env.ref('base.user_admin').id

        # --- LÓGICA DE DETECCIÓN DE INTERVENCIÓN HUMANA (SIN CAMBIOS) ---
        # Esta parte se mantiene para pausar el bot cuando un agente responde.
        for vals in vals_list:
            creator_id = vals.get('create_uid')
            if vals.get('state') in ('outgoing', 'sent') and creator_id and creator_id != bot_user_id:
                phone = normalize_phone(vals.get('mobile_number', ''))
                partner = self.env['res.partner'].sudo().search(['|', ('phone', 'ilike', phone), ('mobile', 'ilike', phone)], limit=1)
                if partner:
                    memory = self.env['chatbot.whatsapp.memory'].sudo().search([('partner_id', '=', partner.id)], limit=1)
                    if memory:
                        takeover_duration_hours = 1
                        _logger.info(f"👤 Intervención humana (Usuario ID: {creator_id}) detectada para {partner.name}. Pausando chatbot por {takeover_duration_hours} hs.")
                        memory.sudo().write({
                            'human_takeover': True,
                            'takeover_until': datetime.now() + timedelta(hours=takeover_duration_hours)
                        })

        records = super().create(vals_list)

        # --- PROCESAMIENTO DE MENSAJES ENTRANTES ---
        for record in records:
            # Solo procesamos mensajes nuevos que recibimos.
            if record.state not in ('received', 'inbound'):
                continue

            plain_text = clean_html(record.body or "").strip()
            phone = normalize_phone(record.mobile_number or record.phone or "")
            if not (plain_text and phone):
                continue

            # 1. BUSCAR O CREAR PARTNER Y MEMORIA
            partner = self.env['res.partner'].sudo().search([
                '|', ('phone', 'ilike', phone), ('mobile', 'ilike', phone)
            ], limit=1)
            
            if not partner:
                partner = self.env['res.partner'].sudo().create({
                    'name': f"WhatsApp: {phone}", 'phone': phone, 'mobile': phone
                })
                _logger.info(f"👤 Creado nuevo partner para {phone}")

            memory = self.env['chatbot.whatsapp.memory'].sudo().search([('partner_id', '=', partner.id)], limit=1)
            if not memory:
                memory = self.env['chatbot.whatsapp.memory'].sudo().create({'partner_id': partner.id})

            # 2. VERIFICAR PAUSA POR INTERVENCIÓN HUMANA
            if memory.human_takeover:
                if not memory.takeover_until or memory.takeover_until > datetime.now():
                    _logger.info(f"🤫 Chatbot en pausa para {partner.name}. Mensaje ignorado.")
                    memory.sudo().write({'takeover_until': datetime.now() + timedelta(hours=1)}) # Refresca la pausa
                    continue
                else:
                    _logger.info(f"🤖 Reactivando chatbot para {partner.name} por expiración de takeover.")
                    memory.sudo().write({'human_takeover': False, 'takeover_until': False})

            _logger.info(f"📨 Mensaje nuevo: '{plain_text}' de {partner.name or 'desconocido'} ({phone})")
            _logger.info(f"🧠 Memoria activa: flow={memory.flow_state}, intent={memory.last_intent_detected}, cart={memory.pending_order_lines}")

            # 3. DELEGAR AL PROCESADOR
            # Creamos una instancia del procesador y le pasamos todo el contexto.
            # El procesador se encargará de toda la lógica y de enviar la respuesta.
            processor = ChatbotProcessor(self.env, record, partner, memory, plain_text)
            processor.process_message()

        return records