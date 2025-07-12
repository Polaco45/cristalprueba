# /chatbot_whatsapp/models/whatsapp_chatbot.py

from odoo import models, api
from ..utils.utils import clean_html, normalize_phone, is_cotizado
from .chatbot_processor import ChatbotProcessor
from ..config.config import messages_config
import logging
from datetime import datetime, timedelta

_logger = logging.getLogger(__name__)

class WhatsAppMessage(models.Model):
    _inherit = 'whatsapp.message'

    @api.model_create_multi
    def create(self, vals_list):
        # Obtenemos el ID del usuario bot (Administrador) para comparar.
        bot_user_id = self.env.ref('base.user_admin').id

        # --- LÓGICA DE DETECCIÓN DE INTERVENCIÓN HUMANA (Sin cambios) ---
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

        for record in records:
            # --- 1. FILTRADO INICIAL: Solo procesamos mensajes entrantes ---
            if record.state not in ('received', 'inbound'):
                continue

            plain = clean_html(record.body or "").strip()
            phone = normalize_phone(record.mobile_number or record.phone or "")
            if not (plain and phone):
                continue

            # --- 2. GESTIÓN DE PARTNER Y MEMORIA (Sin cambios) ---
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
            
            # --- 3. VALIDACIÓN DE TAKEOVER (Sin cambios) ---
            if memory.human_takeover and (not memory.takeover_until or memory.takeover_until > datetime.now()):
                _logger.info(f"🤫 Chatbot en pausa para {partner.name}. Mensaje ignorado.")
                memory.sudo().write({'takeover_until': datetime.now() + timedelta(hours=1)})
                continue
            
            if memory.human_takeover and memory.takeover_until and memory.takeover_until <= datetime.now():
                _logger.info(f"🤖 Reactivando chatbot para {partner.name} por expiración de takeover.")
                memory.sudo().write({'human_takeover': False, 'takeover_until': False})

            _logger.info(f"📨 Mensaje nuevo: '{plain}' de {partner.name or 'desconocido'} ({phone})")
            _logger.info(f"🧠 Memoria activa: flow={memory.flow_state}, intent={memory.last_intent_detected}, cart={memory.pending_order_lines}")

            # --- 4. DELEGACIÓN TOTAL AL PROCESADOR ---
            # Se instancia el procesador que ahora contiene TODA la lógica.
            processor = ChatbotProcessor(self.env, record, partner, memory)

            # --- 5. FLUJO DE ONBOARDING (Ahora manejado por el procesador) ---
            # Se sigue verificando aquí para no iniciar el procesador de intenciones si es un flujo de onboarding.
            onboarding_handler = self.env['chatbot.whatsapp.onboarding_handler']
            handled, response_msg = onboarding_handler.process_onboarding_flow(
                self.env, record, phone, plain, self.env['chatbot.whatsapp.memory'].sudo()
            )
            if handled:
                _logger.info("🔄 Flujo de onboarding interceptado. Enviando respuesta.")
                # Se usa el método de envío del procesador para mantener la consistencia.
                processor._send_text(response_msg)
                continue
            
            # --- 6. PROCESAMIENTO PRINCIPAL ---
            # Si no es onboarding, se llama al método principal del procesador
            # que ahora contiene la lógica de B2C, B2B, flujos e intenciones.
            processor.process_message()

        return records