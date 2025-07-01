from odoo import models, api
from ..utils.utils import clean_html, normalize_phone, is_cotizado
from .onboarding import WhatsAppOnboardingHandler
from .chatbot_processor import ChatbotProcessor
from ..config.config import messages_config
import logging

_logger = logging.getLogger(__name__)

class WhatsAppMessage(models.Model):
    _inherit = 'whatsapp.message'

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)

        for record in records:
            if record.state not in ('received', 'inbound'):
                continue

            plain = clean_html(record.body or "").strip()
            phone = normalize_phone(record.mobile_number or record.phone or "")
            if not (plain and phone):
                continue
            
            # --- FUNCIÓN DE ENVÍO BASADA EN TU VERSIÓN ANTERIOR FUNCIONAL ---
            def _send_text(to_record, text_to_send):
                _logger.info(f"🚀 Preparando para enviar mensaje: '{text_to_send}'")
                # Crear y enviar el mensaje en el mismo flujo
                vals = {
                    'mobile_number': to_record.mobile_number,
                    'body': text_to_send,
                    'state': 'outgoing',
                    'wa_account_id': to_record.wa_account_id.id if to_record.wa_account_id else False,
                    'create_uid': self.env.ref('base.user_admin').id,
                }
                # Se crea el mensaje...
                outgoing_msg = self.env['whatsapp.message'].sudo().create(vals)
                # ...y se intenta enviar inmediatamente.
                if hasattr(outgoing_msg, '_send_message'):
                    outgoing_msg._send_message()
                _logger.info(f"✅ Mensaje '{outgoing_msg.id}' procesado para envío.")

            partner = self.env['res.partner'].sudo().search([
                '|', ('phone', 'ilike', phone), ('mobile', 'ilike', phone)
            ], limit=1)

            if not partner:
                partner = self.env['res.partner'].sudo().create({
                    'name': f"WhatsApp: {phone}",
                    'phone': phone,
                    'mobile': phone
                })
                _logger.info(f"👤 Creado nuevo partner para {phone}")

            memory_model = self.env['chatbot.whatsapp.memory'].sudo()
            memory = memory_model.search([('partner_id', '=', partner.id)], limit=1)
            if not memory:
                memory = memory_model.create({'partner_id': partner.id})

            _logger.info(f"📨 Mensaje nuevo: '{plain}' de {partner.name or 'desconocido'} ({phone})")
            _logger.info(f"🧠 Memoria activa: flow={memory.flow_state}, intent={memory.last_intent_detected}, cart={memory.pending_order_lines}")
            
            onboarding_handler = self.env['chatbot.whatsapp.onboarding_handler']
            handled, response_msg = onboarding_handler.process_onboarding_flow(
                self.env, record, phone, plain, memory_model
            )
            if handled:
                _logger.info("🔄 Flujo de onboarding interceptado")
                _send_text(record, response_msg)
                continue

            if not is_cotizado(partner):
                _logger.info("🚫 Usuario sin cotización")
                _send_text(record, messages_config['onboarding_unquoted'])
                continue

            # --- DELEGACIÓN AL PROCESADOR CENTRAL ---
            # Ahora se le pasa el `record` para que el procesador sepa a quién responder.
            processor = ChatbotProcessor(self.env, record, partner, memory)
            processor.process_message()

        return records