from odoo import models, api
from ..utils.utils import clean_html, normalize_phone, is_cotizado
from .onboarding import WhatsAppOnboardingHandler
from .chatbot_processor import ChatbotProcessor  # <-- Importamos el nuevo procesador
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

            partner = self.env['res.partner'].sudo().search([
                '|', ('phone', 'ilike', phone), ('mobile', 'ilike', phone)
            ], limit=1)

            memory_model = self.env['chatbot.whatsapp.memory'].sudo()
            memory = memory_model.search([('partner_id', '=', partner.id)], limit=1)
            if not memory:
                memory = memory_model.create({'partner_id': partner.id})

            _logger.info(f"📨 Mensaje nuevo: '{plain}' de {partner.name if partner else 'desconocido'} ({phone})")
            _logger.info(f"🧠 Memoria activa: flow={memory.flow_state}, intent={memory.last_intent_detected}, cart={memory.pending_order_lines}")
            
            # Flujo de Onboarding
            onboarding_handler = self.env['chatbot.whatsapp.onboarding_handler']
            handled, response_msg = onboarding_handler.process_onboarding_flow(
                self.env, record, phone, plain, memory_model
            )
            if handled:
                _logger.info("🔄 Flujo de onboarding interceptado")
                record.wa_account_id.send_message(partner, response_msg)
                continue

            # Cliente sin cotización
            if not is_cotizado(partner):
                _logger.info("🚫 Usuario sin cotización")
                record.wa_account_id.send_message(partner, messages_config['onboarding_unquoted'])
                continue

            # --- DELEGACIÓN AL PROCESADOR CENTRAL ---
            processor = ChatbotProcessor(self.env, record, partner, memory)
            processor.process_message()

        return records