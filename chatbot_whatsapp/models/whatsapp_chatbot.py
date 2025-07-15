# -*- coding: utf-8 -*-
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

            memory = self.env['chatbot.whatsapp.memory'].sudo().search(
                [('partner_id', '=', partner.id)], limit=1
            )
            if not memory:
                memory = self.env['chatbot.whatsapp.memory'].sudo().create({
                    'partner_id': partner.id
                })

            now = datetime.now()

            # 1) Si está en pausa y aún no venció → ignorar
            if memory.human_takeover and memory.takeover_until and memory.takeover_until > now:
                _logger.info(f"🤫 Chatbot en pausa para {partner.name}. Mensaje ignorado.")
                continue

            # 2) Si el takeover expiró → reactivar
            if memory.human_takeover and memory.takeover_until and memory.takeover_until <= now:
                _logger.info(f"🔁 Reactivando chatbot para {partner.name}.")
                memory.sudo().write({
                    'human_takeover': False,
                    'takeover_until': False
                })

            _logger.info(f"📨 Mensaje nuevo: '{plain}' de {partner.name} ({phone})")
            _logger.info(f"🧠 Memoria: flow={memory.flow_state}, intent={memory.last_intent_detected}")

            def _send_text(to_record, text_to_send):
                bot_uid = self.env.ref('base.user_admin').id
                _logger.info(f"🚀 Enviando: '{text_to_send}'")
                vals = {
                    'mobile_number': to_record.mobile_number,
                    'body': text_to_send,
                    'state': 'outgoing',
                    'wa_account_id': to_record.wa_account_id.id if to_record.wa_account_id else False,
                    'create_uid': bot_uid,
                }
                outgoing = self.env['whatsapp.message'].sudo().create(vals)
                outgoing.sudo().write({'body': text_to_send})
                if hasattr(outgoing, '_send_message'):
                    outgoing._send_message()
                _logger.info(f"✅ Mensaje enviado (id {outgoing.id}).")

            # Onboarding
            onboarding = self.env['chatbot.whatsapp.onboarding_handler']
            handled, resp = onboarding.process_onboarding_flow(
                self.env, record, phone, plain, self.env['chatbot.whatsapp.memory'].sudo()
            )
            if handled:
                _logger.info("🔄 Onboarding interceptado")
                _send_text(record, resp)
                continue

            # B2C / Cotización
            b2c_tag = "Tipo de Cliente / Consumidor Final"
            is_b2c = partner.category_id and any(t.name == b2c_tag for t in partner.category_id)
            if not is_b2c and not is_cotizado(partner):
                if not memory.human_takeover:
                    _logger.info("🚫 B2B sin cotización. Pausando.")
                    _send_text(record, messages_config['onboarding_unquoted'])
                    memory.sudo().write({
                        'human_takeover': True,
                        'takeover_until': now + timedelta(hours=1)
                    })
                else:
                    _logger.info(f"🤫 Ya estaba en pausa para {partner.name}.")
                continue

            # Procesamiento normal
            processor = ChatbotProcessor(self.env, record, partner, memory)
            processor.process_message()

        return records


class MailMessage(models.Model):
    _inherit = 'mail.message'

    @api.model_create_multi
    def create(self, vals_list):
        # Ignorar mensajes generados por el bot
        if self.env.context.get('from_wa_bot'):
            return super().create(vals_list)

        bot_pid = self.env.ref('base.user_admin').partner_id.id

        for vals in vals_list:
            author = vals.get('author_id')
            model = vals.get('model')

            # Solo consideramos intervenciones en canales de tipo WhatsApp
            if model == 'discuss.channel' and author and author != bot_pid:
                # 1) Buscamos el último whatsapp.message entrante (inbound)
                last_msg = self.env['whatsapp.message'].sudo().search([
                    ('state', '=', 'inbound')
                ], order='create_date desc', limit=1)

                if last_msg and last_msg.mobile_number:
                    # 2) Normalizamos el número y buscamos el partner
                    phone = normalize_phone(last_msg.mobile_number)
                    partner = self.env['res.partner'].sudo().search([
                        '|', ('phone', 'ilike', phone), ('mobile', 'ilike', phone)
                    ], limit=1)
                    if partner:
                        # 3) Pausamos la memoria de ese partner
                        memory = self.env['chatbot.whatsapp.memory'].sudo().search([
                            ('partner_id', '=', partner.id)
                        ], limit=1)
                        if memory:
                            takeover_hours = 1
                            human_name = self.env['res.partner'].browse(author).name
                            _logger.info(
                                f"👤 Intervención humana de '{human_name}'. "
                                f"Pausando chatbot para '{partner.name}' por {takeover_hours} hs."
                            )
                            memory.sudo().write({
                                'human_takeover': True,
                                'takeover_until': datetime.now() + timedelta(hours=takeover_hours),
                                'flow_state': False,
                            })

        return super().create(vals_list)
