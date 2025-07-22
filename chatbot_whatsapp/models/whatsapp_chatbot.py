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
        # Evitar bucles si el mensaje ya viene del bot
        if self.env.context.get('from_wa_bot'):
            return super().create(vals_list)

        bot_partner_id = self.env.ref('base.user_admin').partner_id.id
        
        # Recorrer todos los mensajes que se están creando
        for vals in vals_list:
            author_id = vals.get('author_id')
            model = vals.get('model')
            res_id = vals.get('res_id')
            body = vals.get('body', '')

            # Continuar solo si es un mensaje de un empleado en un canal de chat
            if not (model == 'discuss.channel' and author_id and res_id):
                continue

            author_partner = self.env['res.partner'].browse(author_id)
            if author_partner.id == bot_partner_id or not author_partner.user_ids:
                continue

            # Es un mensaje de un empleado, verificar si es en un canal de WhatsApp
            plain_body = clean_html(body).strip()
            channel = self.env['discuss.channel'].browse(res_id)

            if channel.channel_type == 'whatsapp':
                # --- Identificar al cliente (partner) en el canal ---
                partner_to_manage = self.env['res.partner']
                if hasattr(channel, 'whatsapp_number') and channel.whatsapp_number:
                    customer_phone = normalize_phone(channel.whatsapp_number)
                    if customer_phone:
                        partner_to_manage = self.env['res.partner'].sudo().search([
                            '|', ('phone', '=', customer_phone), ('mobile', '=', customer_phone)
                        ], limit=1)
                
                if not partner_to_manage:
                    customer_partners = channel.channel_partner_ids.filtered(
                        lambda p: not p.user_ids and p.id != self.env.ref('base.partner_root').id
                    )
                    if len(customer_partners) == 1:
                        partner_to_manage = customer_partners

                if partner_to_manage:
                    memory = self.env['chatbot.whatsapp.memory'].sudo().search(
                        [('partner_id', '=', partner_to_manage.id)], limit=1
                    )
                    if not memory:
                        memory = self.env['chatbot.whatsapp.memory'].sudo().create({
                            'partner_id': partner_to_manage.id
                        })

                    is_command = False
                    # --- LÓGICA PARA COMANDOS /on y /off ---
                    if plain_body.lower() == '/off':
                        memory.sudo().write({'human_takeover': True, 'takeover_until': False})
                        _logger.info(f"🤖 Chatbot DESACTIVADO para {partner_to_manage.name} por {author_partner.name}")
                        # Transformar en nota interna
                        vals['body'] = "<em>Comando '/off' procesado. El chatbot está ahora <strong>desactivado</strong>.</em>"
                        vals['message_type'] = 'notification'
                        vals['subtype_id'] = self.env.ref('mail.mt_note').id
                        is_command = True
                    
                    elif plain_body.lower() == '/on':
                        memory.sudo().write({'human_takeover': False, 'takeover_until': False})
                        _logger.info(f"🤖 Chatbot ACTIVADO para {partner_to_manage.name} por {author_partner.name}")
                        # Transformar en nota interna
                        vals['body'] = "<em>Comando '/on' procesado. El chatbot está ahora <strong>activado</strong>.</em>"
                        vals['message_type'] = 'notification'
                        vals['subtype_id'] = self.env.ref('mail.mt_note').id
                        is_command = True
                    
                    # --- Lógica de intervención humana automática (si no es un comando) ---
                    if not is_command:
                        # Solo pausar si el bot no está ya desactivado permanentemente con /off
                        # La condición `memory.takeover_until` permite que un mensaje de un humano reinicie el contador de 1 hora.
                        if not memory.human_takeover or memory.takeover_until:
                            takeover_duration_hours = 1
                            memory.sudo().write({
                                'human_takeover': True,
                                'takeover_until': datetime.now() + timedelta(hours=takeover_duration_hours),
                            })
                            _logger.info(f"🤫 Pausando chatbot para {partner_to_manage.name} por 1 hora debido a intervención de {author_partner.name}")

        # Crear todos los mensajes (originales o modificados)
        return super(MailMessage, self).create(vals_list)