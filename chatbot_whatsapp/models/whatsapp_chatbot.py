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
            # Solo procesamos mensajes entrantes
            if record.state not in ('received', 'inbound'):
                continue

            plain = clean_html(record.body or "").strip()
            phone = normalize_phone(record.mobile_number or record.phone or "")
            if not (plain and phone):
                continue

            partner_tuples = self.env['res.partner'].sudo().name_search(
                name=phone,
                args=[],          
                operator='ilike',
                limit=1
            )
            if partner_tuples:
                partner = self.env['res.partner'].browse(partner_tuples[0][0])
            else:
                partner = self.env['res.partner'].sudo().create({
                    'name':   f"WhatsApp: {phone}",
                    'phone':  phone,
                    'mobile': phone,
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

            # --- LÓGICA CORREGIDA DE PAUSA Y REACTIVACIÓN ---
            now = datetime.now()

            # NUEVO: Si está en takeover INDEFINIDO (por comando /off) -> ignorar mensaje.
            if memory.human_takeover and not memory.takeover_until:
                _logger.info(f"🤫 Chatbot DESACTIVADO INDEFINIDAMENTE para {partner.name}. Mensaje ignorado.")
                continue

            # Si está en takeover TEMPORAL (por intervención de empleado) y aún no venció → ignorar.
            if memory.human_takeover and memory.takeover_until and memory.takeover_until > now:
                _logger.info(f"🤫 Chatbot en pausa temporal para {partner.name}. Mensaje ignorado.")
                continue

            # Si estaba en takeover TEMPORAL pero la fecha de pausa ya pasó → reactivar.
            if memory.human_takeover and memory.takeover_until and memory.takeover_until <= now:
                _logger.info(f"🔁 Reactivando chatbot para {partner.name}, pausa temporal vencida.")
                memory.sudo().write({
                    'human_takeover': False,
                    'takeover_until': False
                })
            
            _logger.info(f"📨 Mensaje nuevo: '{plain}' de {partner.name} ({phone})")
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

            # 1) Flujo de onboarding
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
        if self.env.context.get('from_wa_bot'):
            return super().create(vals_list)

        note_subtype_id = self.env.ref('mail.mt_note').id
        processed_vals_list = []

        for vals in vals_list:
            author_id = vals.get('author_id')
            model = vals.get('model')
            res_id = vals.get('res_id')
            body = vals.get('body', '')

            if not (model == 'discuss.channel' and author_id and res_id):
                processed_vals_list.append(vals)
                continue

            author_partner = self.env['res.partner'].browse(author_id)
            if not author_partner.user_ids:
                processed_vals_list.append(vals)
                continue
            
            # El autor es un empleado, se procesa la lógica.
            plain_body = clean_html(body).strip().lower()
            channel = self.env['discuss.channel'].browse(res_id)
            is_command = False

            if channel.channel_type == 'whatsapp':
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
                    memory = self.env['chatbot.whatsapp.memory'].sudo().search([('partner_id', '=', partner_to_manage.id)], limit=1)
                    if not memory:
                        memory = self.env['chatbot.whatsapp.memory'].sudo().create({'partner_id': partner_to_manage.id})

                    # --- Lógica de Comandos: Transformar en Nota Interna ---
                    if plain_body == '/off':
                        memory.sudo().write({'human_takeover': True, 'takeover_until': False})
                        log_msg = f"🤖 Chatbot DESACTIVADO INDEFINIDAMENTE para {partner_to_manage.name}."
                        _logger.info(log_msg)
                        
                        vals['body'] = log_msg
                        vals['subtype_id'] = note_subtype_id
                        vals['message_type'] = 'comment'
                        is_command = True
                    
                    elif plain_body == '/on':
                        memory.sudo().write({'human_takeover': False, 'takeover_until': False})
                        log_msg = f"✅ Chatbot ACTIVADO para {partner_to_manage.name}."
                        _logger.info(log_msg)

                        vals['body'] = log_msg
                        vals['subtype_id'] = note_subtype_id
                        vals['message_type'] = 'comment'
                        is_command = True

                    # --- Lógica de intervención humana si NO es un comando ---
                    if not is_command:
                        _logger.info(f"🤫 Pausando chatbot para {partner_to_manage.name} por intervención de {author_partner.name}")
                        memory.sudo().write({
                            'human_takeover': True,
                            'takeover_until': datetime.now() + timedelta(hours=1),
                            'flow_state': False,
                        })

            processed_vals_list.append(vals)

        return super(MailMessage, self).create(processed_vals_list)