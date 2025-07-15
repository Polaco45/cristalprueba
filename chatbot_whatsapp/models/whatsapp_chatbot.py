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
            # Solo mensajes entrantes
            if record.state not in ('received', 'inbound'):
                continue

            plain = clean_html(record.body or "").strip()
            phone = normalize_phone(record.mobile_number or record.phone or "")
            if not (plain and phone):
                continue

            # Buscar o crear partner por número
            partner = self.env['res.partner'].sudo().search([
                '|', ('phone', 'ilike', phone), ('mobile', 'ilike', phone)
            ], limit=1)
            if not partner:
                partner = self.env['res.partner'].sudo().create({
                    'name': f"WhatsApp: {phone}", 'phone': phone, 'mobile': phone
                })
                _logger.info(f"👤 Creado nuevo partner para {phone}")

            # Cargar o crear memoria de chatbot
            memory = self.env['chatbot.whatsapp.memory'].sudo().search(
                [('partner_id', '=', partner.id)], limit=1
            )
            if not memory:
                memory = self.env['chatbot.whatsapp.memory'].sudo().create({
                    'partner_id': partner.id
                })

            # --- LÓGICA DE PAUSA Y REACTIVACIÓN ---
            now = datetime.now()

            # 1) Si está en takeover y aún no venció → ignorar
            if memory.human_takeover and memory.takeover_until and memory.takeover_until > now:
                _logger.info(f"🤫 Chatbot en pausa para {partner.name} por intervención humana. Mensaje ignorado.")
                continue

            # 2) Si estaba en takeover pero expiró → reactivar
            if memory.human_takeover and memory.takeover_until and memory.takeover_until <= now:
                _logger.info(f"🔁 Reactivando chatbot para {partner.name}, takeover vencido.")
                memory.sudo().write({
                    'human_takeover': False,
                    'takeover_until': False
                })

            _logger.info(f"📨 Mensaje nuevo: '{plain}' de {partner.name} ({phone})")
            _logger.info(f"🧠 Memoria activa: flow={memory.flow_state}, intent={memory.last_intent_detected}, cart={memory.pending_order_lines}")

            # Función interna para envío
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

            # 1) Flujo de onboarding (bienvenida / permisos)
            onboarding_handler = self.env['chatbot.whatsapp.onboarding_handler']
            handled, response_msg = onboarding_handler.process_onboarding_flow(
                self.env, record, phone, plain, self.env['chatbot.whatsapp.memory'].sudo()
            )
            if handled:
                _logger.info("🔄 Flujo de onboarding interceptado")
                _send_text(record, response_msg)
                continue

            # 2) Validación B2C / cotización
            b2c_tag_name = "Tipo de Cliente / Consumidor Final"
            is_b2c = partner.category_id and any(tag.name == b2c_tag_name for tag in partner.category_id)

            if not is_b2c and not is_cotizado(partner):
                if not memory.human_takeover:
                    _logger.info("🚫 Usuario B2B sin cotización. Notificando y pausando.")
                    _send_text(record, messages_config['onboarding_unquoted'])
                    memory.sudo().write({
                        'human_takeover': True,
                        'takeover_until': now + timedelta(hours=1)
                    })
                    _logger.info(f"🤖 Chatbot pausado automáticamente por 1 hs para esperar al asesor.")
                else:
                    _logger.info(f"🤫 Chatbot ya está en pausa para {partner.name}, ignorando mensaje.")
                continue

            # 3) Procesamiento normal
            processor = ChatbotProcessor(self.env, record, partner, memory)
            processor.process_message()

        return records


class MailMessage(models.Model):
    _inherit = 'mail.message'

    @api.model_create_multi
    def create(self, vals_list):
        # Ignorar mensajes generados por el bot en este flujo para evitar bucles
        if self.env.context.get('from_wa_bot'):
            return super().create(vals_list)

        bot_partner_id = self.env.ref('base.user_admin').partner_id.id
        public_partner_id = self.env.ref('base.partner_root').id

        for vals in vals_list:
            author_id = vals.get('author_id')
            model = vals.get('model')
            res_id = vals.get('res_id')

            # Continuar solo si es un mensaje en un canal de Odoo de un autor real
            if not (model == 'discuss.channel' and author_id and res_id):
                continue

            # Obtener el autor y verificar que no sea el propio bot
            author_partner = self.env['res.partner'].browse(author_id)
            if author_partner.id == bot_partner_id:
                continue

            # Verificar si el mensaje es de un empleado (usuario interno) en un canal de WhatsApp
            is_internal_user = any(user.has_group('base.group_user') for user in author_partner.user_ids)

            if is_internal_user:
                channel = self.env['discuss.channel'].browse(res_id)
                if channel.channel_type == 'whatsapp':

                    # --- LÓGICA MEJORADA ---
                    # 1. Identificar a TODOS los partners del canal que son empleados (usuarios internos).
                    all_partners_in_channel = channel.channel_partner_ids
                    employee_partners = all_partners_in_channel.filtered(
                        lambda p: any(user.has_group('base.group_user') for user in p.user_ids)
                    )
                    employee_partner_ids = employee_partners.ids

                    # 2. El cliente es el partner que NO es un empleado y tampoco es el bot o el usuario público.
                    customer_partner = all_partners_in_channel.filtered(
                        lambda p: p.id not in employee_partner_ids and p.id not in (bot_partner_id, public_partner_id)
                    )
                    
                    # 3. Si encontramos un único cliente, pausamos el bot para él.
                    if len(customer_partner) == 1:
                        partner_to_pause = customer_partner
                        memory = self.env['chatbot.whatsapp.memory'].sudo().search(
                            [('partner_id', '=', partner_to_pause.id)], limit=1
                        )
                        if memory and not memory.human_takeover:
                            takeover_duration = 1  # horas
                            _logger.info(
                                f"👤 Intervención humana de '{author_partner.name}' detectada. "
                                f"Pausando chatbot para el cliente '{partner_to_pause.name}' por {takeover_duration} hs."
                            )
                            memory.sudo().write({
                                'human_takeover': True,
                                'takeover_until': datetime.now() + timedelta(hours=takeover_duration),
                                'flow_state': False,  # Reiniciar el flujo del chatbot
                            })
                    else:
                        _logger.warning(
                            f"Intervención humana de '{author_partner.name}' en canal WA {channel.id}, "
                            f"pero no se pudo identificar un único partner cliente para pausar. Se encontraron {len(customer_partner)}."
                        )

        return super(MailMessage, self).create(vals_list)