from odoo import models, api
from ..utils.utils import clean_html, normalize_phone, is_cotizado
from .onboarding import WhatsAppOnboardingHandler
from .chatbot_processor import ChatbotProcessor
from ..config.config import messages_config
import logging

_logger = logging.getLogger(__name__)

class WhatsAppMessage(models.Model):
    _inherit = 'whatsapp.message'

    def send_custom_message(self, partner, text, pdf_base64=None, filename=None):
        """
        Función centralizada y mejorada para enviar mensajes desde el chatbot.
        Decide si enviar solo texto o un archivo con pie de foto.
        """
        _logger.info(f"🚀 Iniciando envío para {partner.name}. PDF presente: {bool(pdf_base64)}")

        # Preparar los valores base para el mensaje
        vals = {
            'mobile_number': partner.phone or partner.mobile,
            'body': text,
            'state': 'outgoing',
            'wa_account_id': self.env.context.get('active_wa_account_id') or self.env['whatsapp.account'].search([], limit=1).id,
            'create_uid': self.env.ref('base.user_admin').id,
        }

        # Crear el registro del mensaje de WhatsApp
        try:
            outgoing_msg = self.env['whatsapp.message'].sudo().create(vals)
            _logger.info(f"✅ Registro de mensaje creado: ID {outgoing_msg.id}")

            # Si hay un PDF, creamos el adjunto y lo VINCULAMOS al mensaje
            if pdf_base64 and filename:
                self.env['ir.attachment'].sudo().create({
                    'name': filename,
                    'datas': pdf_base64,
                    'res_model': 'whatsapp.message',
                    'res_id': outgoing_msg.id,
                    'mimetype': 'application/pdf',
                })
                _logger.info(f"📎 Adjunto PDF creado y vinculado al mensaje {outgoing_msg.id}")

            # Llamamos al método de envío UNA SOLA VEZ
            if hasattr(outgoing_msg, '_send_message'):
                outgoing_msg._send_message()
            
            _logger.info(f"✅ Mensaje {outgoing_msg.id} procesado para envío a WhatsApp.")
            return True

        except Exception as e:
            _logger.error(f"❌ Error fatal durante el envío a WhatsApp: {e}", exc_info=True)
            return False

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
            
            # --- FUNCIÓN DE ENVÍO RESTAURADA A LA VERSIÓN FUNCIONAL ---
            def _send_text(to_record, text_to_send):
                _logger.info(f"🚀 Preparando para enviar mensaje: '{text_to_send}'")
                vals = {
                    'mobile_number': to_record.mobile_number,
                    'body': text_to_send,
                    'state': 'outgoing',
                    'wa_account_id': to_record.wa_account_id.id if to_record.wa_account_id else False,
                    'create_uid': self.env.ref('base.user_admin').id,
                }
                # 1. Se crea el mensaje
                outgoing_msg = self.env['whatsapp.message'].sudo().create(vals)
                
                # 2. Se vuelve a escribir el body (paso clave de la versión anterior)
                outgoing_msg.sudo().write({'body': text_to_send})
                
                # 3. Se intenta enviar inmediatamente
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
            processor = ChatbotProcessor(self.env, record, partner, memory)
            processor.process_message()

        return records