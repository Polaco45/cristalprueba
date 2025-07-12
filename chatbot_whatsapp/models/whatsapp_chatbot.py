from odoo import models, api
from ..utils.utils import clean_html, normalize_phone, is_cotizado
from .onboarding import WhatsAppOnboardingHandler
from .chatbot_processor import ChatbotProcessor
from ..config.config import messages_config
import logging
from datetime import datetime, timedelta

_logger = logging.getLogger(__name__)

class WhatsAppMessage(models.Model):
    _inherit = 'whatsapp.message'

    @api.model_create_multi
    def create(self, vals_list):
        # Mantenemos la lógica original para procesar los mensajes
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

            if not partner:
                partner = self.env['res.partner'].sudo().create({
                    'name': f"WhatsApp: {phone}", 'phone': phone, 'mobile': phone
                })
                _logger.info(f"👤 Creado nuevo partner para {phone}")

            memory = self.env['chatbot.whatsapp.memory'].sudo().search([('partner_id', '=', partner.id)], limit=1)

            if not memory:
                memory = self.env['chatbot.whatsapp.memory'].sudo().create({'partner_id': partner.id})

            if memory.human_takeover and (not memory.takeover_until or memory.takeover_until > datetime.now()):
                _logger.info(f"🤫 Chatbot en pausa para {partner.name}. Mensaje ignorado.")
                # Extendemos el tiempo de takeover si el humano sigue hablando
                memory.sudo().write({'takeover_until': datetime.now() + timedelta(hours=1)})
                continue

            if memory.human_takeover and memory.takeover_until and memory.takeover_until <= datetime.now():
                _logger.info(f"🤖 Reactivando chatbot para {partner.name} por expiración de takeover.")
                memory.sudo().write({'human_takeover': False, 'takeover_until': False})

            _logger.info(f"📨 Mensaje nuevo: '{plain}' de {partner.name or 'desconocido'} ({phone})")
            _logger.info(f"🧠 Memoria activa: flow={memory.flow_state}, intent={memory.last_intent_detected}, cart={memory.pending_order_lines}")

            def _send_text(to_record, text_to_send):
                bot_user_id = self.env.ref('base.user_admin').id
                _logger.info(f"🚀 Preparando para enviar mensaje: '{text_to_send}'")
                vals = {
                    'mobile_number': to_record.mobile_number,
                    'body': text_to_send,
                    'state': 'outgoing',
                    'wa_account_id': to_record.wa_account_id.id if to_record.wa_account_id else False,
                    'create_uid': bot_user_id,
                }
                outgoing_msg = self.env['whatsapp.message'].sudo().create(vals)
                outgoing_msg.sudo().write({'body': text_to_send})
                if hasattr(outgoing_msg, '_send_message'):
                    outgoing_msg._send_message()
                _logger.info(f"✅ Mensaje '{outgoing_msg.id}' procesado para envío.")

            onboarding_handler = self.env['chatbot.whatsapp.onboarding_handler']
            handled, response_msg = onboarding_handler.process_onboarding_flow(
                self.env, record, phone, plain, self.env['chatbot.whatsapp.memory'].sudo()
            )
            if handled:
                _logger.info("🔄 Flujo de onboarding interceptado")
                _send_text(record, response_msg)
                continue

            b2c_tag_name = "Tipo de Cliente / Consumidor Final"
            is_b2c = partner.category_id and any(tag.name == b2c_tag_name for tag in partner.category_id)

            if not is_b2c and not is_cotizado(partner):
                _logger.info("🚫 Usuario B2B/Mayorista sin cotización")
                _send_text(record, messages_config['onboarding_unquoted'])
                continue

            processor = ChatbotProcessor(self.env, record, partner, memory)
            processor.process_message()

        return records

class MailMessage(models.Model):
    _inherit = 'mail.message'

    @api.model_create_multi
    def create(self, vals_list):
        """
        Sobrecargamos el `create` de `mail.message` para detectar
        cuando un humano responde en un canal de WhatsApp.
        """
        bot_user_id = self.env.ref('base.user_admin').id

        for vals in vals_list:
            # Nos interesa si el mensaje es de un humano y está en un canal de discusión
            author_id = vals.get('author_id')
            model = vals.get('model')
            res_id = vals.get('res_id')

            if model == 'discuss.channel' and author_id and author_id != bot_user_id:
                channel = self.env['discuss.channel'].browse(res_id)
                
                # Verificamos si es un canal de WhatsApp y obtenemos el partner
                if channel.channel_type == 'whatsapp':
                    partner = channel.channel_partner_ids.filtered(lambda p: p.id != self.env.ref('base.partner_root').id)
                    if partner:
                        memory = self.env['chatbot.whatsapp.memory'].sudo().search([('partner_id', '=', partner.id)], limit=1)
                        if memory:
                            takeover_duration_hours = 1
                            _logger.info(f"👤 Intervención humana detectada en canal de WhatsApp para {partner.name}. Pausando chatbot por {takeover_duration_hours} hs.")
                            memory.sudo().write({
                                'human_takeover': True,
                                'takeover_until': datetime.now() + timedelta(hours=takeover_duration_hours)
                            })

        return super().create(vals_list)