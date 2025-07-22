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
                        # CAMBIO A 1 HORA
                        'takeover_until': now + timedelta(hours=1)
                    })
                    _logger.info("🤖 Chatbot pausado automáticamente por 1 hora para esperar al asesor.")
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
        # Ignorar mensajes generados por el bot para evitar bucles
        if self.env.context.get('from_wa_bot'):
            return super().create(vals_list)

        bot_partner_id = self.env.ref('base.user_admin').partner_id.id

        for vals in vals_list:
            author_id = vals.get('author_id')
            model = vals.get('model')
            res_id = vals.get('res_id')
            body = clean_html(vals.get('body', '')).strip()

            if not (model == 'discuss.channel' and author_id and res_id and body):
                continue

            author_partner = self.env['res.partner'].browse(author_id)
            if author_partner.id == bot_partner_id or not author_partner.user_ids:
                continue

            channel = self.env['discuss.channel'].browse(res_id)
            if channel.channel_type != 'whatsapp':
                continue

            # --- NUEVA LÓGICA PARA COMANDOS /on y /off ---
            # Identificar al partner cliente del canal
            customer_partner = channel.channel_partner_ids.filtered(
                lambda p: not p.user_ids and p.id != self.env.ref('base.partner_root').id
            )
            if not customer_partner:
                _logger.warning(f"No se pudo identificar al partner cliente en el canal {channel.id}")
                continue
            
            customer_partner = customer_partner[0]

            memory = self.env['chatbot.whatsapp.memory'].sudo().search(
                [('partner_id', '=', customer_partner.id)], limit=1
            )
            if not memory:
                _logger.info(f"El cliente '{customer_partner.name}' no tiene memoria de chatbot para modificar.")
                continue

            # Comprobar si es un comando
            if body.lower() == '/off':
                _logger.info(f"🤖 Comando /off recibido. Desactivando chatbot para {customer_partner.name}.")
                memory.sudo().write({
                    'human_takeover': True,
                    'takeover_until': datetime.now() + timedelta(days=3650) # Desactivado por 10 años
                })
                # IMPORTANTE: No llamamos a super() para que el mensaje no se envíe
                return self.env['mail.message'] # Devolvemos un recordset vacío
            
            elif body.lower() == '/on':
                _logger.info(f"🤖 Comando /on recibido. Reactivando chatbot para {customer_partner.name}.")
                memory.sudo().write({
                    'human_takeover': False,
                    'takeover_until': False,
                })
                # IMPORTANTE: No llamamos a super()
                return self.env['mail.message'] # Devolvemos un recordset vacío
            
            # --- FIN DE LA NUEVA LÓGICA ---

            # Lógica original para pausar el bot temporalmente con cualquier mensaje del empleado
            takeover_duration_hours = 1
            log_action = "Pausando"
            if memory.human_takeover:
                log_action = "Reiniciando pausa para"

            _logger.info(
                f"👤 Intervención humana de '{author_partner.name}' detectada. "
                f"{log_action} chatbot del cliente '{customer_partner.name}' por {takeover_duration_hours} hora(s)."
            )
            memory.sudo().write({
                'human_takeover': True,
                'takeover_until': datetime.now() + timedelta(hours=takeover_duration_hours),
                'flow_state': False, # Resetea cualquier flujo activo
            })

        return super(MailMessage, self).create(vals_list)