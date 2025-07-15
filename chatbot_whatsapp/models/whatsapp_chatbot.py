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
                        # CAMBIO A 1 MINUTO
                        'takeover_until': now + timedelta(minutes=1)
                    })
                    _logger.info("🤖 Chatbot pausado automáticamente por 1 minuto para esperar al asesor.")
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

        for vals in vals_list:
            author_id = vals.get('author_id')
            model = vals.get('model')
            res_id = vals.get('res_id')

            # Continuar solo si es un mensaje en un canal de Odoo de un autor real
            if not (model == 'discuss.channel' and author_id and res_id):
                continue

            author_partner = self.env['res.partner'].browse(author_id)
            if author_partner.id == bot_partner_id:
                continue

            # La intervención humana solo ocurre cuando un empleado (usuario interno) escribe.
            if author_partner.user_ids:
                channel = self.env['discuss.channel'].browse(res_id)
                if channel.channel_type == 'whatsapp':

                    partner_to_pause = self.env['res.partner']

                    # --- LÓGICA MEJORADA ---
                    # MÉTODO 1 (Principal y más fiable): Buscar al cliente por el número de WhatsApp asociado al canal.
                    if hasattr(channel, 'whatsapp_number') and channel.whatsapp_number:
                        customer_phone = normalize_phone(channel.whatsapp_number)
                        if customer_phone:
                            partner_to_pause = self.env['res.partner'].sudo().search([
                                '|', ('phone', '=', customer_phone), ('mobile', '=', customer_phone)
                            ], limit=1)
                            _logger.info(f"Cliente identificado por número de canal WA: {customer_phone} -> {partner_to_pause.name}")

                    # MÉTODO 2 (Respaldo): Si el método 1 falla, intentar la lógica anterior de miembros del canal.
                    if not partner_to_pause:
                        _logger.info("No se encontró cliente por número de canal, intentando por miembros del canal.")
                        customer_partners = channel.channel_partner_ids.filtered(
                            lambda p: not p.user_ids and p.id != self.env.ref('base.partner_root').id
                        )
                        if len(customer_partners) == 1:
                            partner_to_pause = customer_partners

                    # Si encontramos un cliente por cualquiera de los dos métodos, pausamos el bot para él.
                    if partner_to_pause:
                        memory = self.env['chatbot.whatsapp.memory'].sudo().search(
                            [('partner_id', '=', partner_to_pause.id)], limit=1
                        )
                        if memory and not memory.human_takeover:
                            # CAMBIO A 1 MINUTO
                            takeover_duration_minutes = 1
                            _logger.info(
                                f"👤 Intervención humana de '{author_partner.name}' detectada. "
                                f"Pausando chatbot para el cliente '{partner_to_pause.name}' por {takeover_duration_minutes} minuto(s)."
                            )
                            memory.sudo().write({
                                'human_takeover': True,
                                'takeover_until': datetime.now() + timedelta(minutes=takeover_duration_minutes),
                                'flow_state': False, # Reiniciar el flujo del chatbot
                            })
                        elif memory:
                             _logger.info(f"Intervención humana detectada, pero el chatbot para '{partner_to_pause.name}' ya estaba en pausa.")
                        else:
                            _logger.info(f"Cliente '{partner_to_pause.name}' no tiene memoria de chatbot para pausar.")
                    else:
                        # Si ninguno de los dos métodos funcionó, registramos el fallo.
                        _logger.warning(
                            f"Intervención humana de '{author_partner.name}' en canal WA {channel.id}, "
                            f"pero NO se pudo identificar al partner cliente para pausar (ni por número ni por miembros)."
                        )

        return super(MailMessage, self).create(vals_list)