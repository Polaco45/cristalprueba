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
        # Obtenemos el ID del usuario bot (Administrador) UNA VEZ para comparar
        bot_user_id = self.env.ref('base.user_admin').id

        # --- NUEVA LÓGICA DE DETECCIÓN BASADA EN create_uid ---
        for vals in vals_list:
            # Si el mensaje es saliente y el creador (create_uid) NO es el bot, es un humano.
            # El create_uid puede no estar en vals si lo envía un usuario público, así que lo manejamos con .get()
            creator_id = vals.get('create_uid')
            
            if vals.get('state') in ('outgoing', 'sent') and creator_id and creator_id != bot_user_id:
                phone = normalize_phone(vals.get('mobile_number', ''))
                partner = self.env['res.partner'].sudo().search(['|', ('phone', 'ilike', phone), ('mobile', 'ilike', phone)], limit=1)
                if partner:
                    memory = self.env['chatbot.whatsapp.memory'].sudo().search([('partner_id', '=', partner.id)], limit=1)
                    if memory:
                        # Reducimos la duración del takeover a 1 hora
                        takeover_duration_hours = 1
                        _logger.info(f"👤 Intervención humana (Usuario ID: {creator_id}) detectada para {partner.name}. Pausando chatbot por {takeover_duration_hours} hs.")
                        memory.sudo().write({
                            'human_takeover': True,
                            'takeover_until': datetime.now() + timedelta(hours=takeover_duration_hours)
                        })

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
                memory.sudo().write({'takeover_until': datetime.now() + timedelta(hours=1)})
                continue
            
            if memory.human_takeover and memory.takeover_until and memory.takeover_until <= datetime.now():
                _logger.info(f"🤖 Reactivando chatbot para {partner.name} por expiración de takeover.")
                memory.sudo().write({'human_takeover': False, 'takeover_until': False})

            _logger.info(f"📨 Mensaje nuevo: '{plain}' de {partner.name or 'desconocido'} ({phone})")
            _logger.info(f"🧠 Memoria activa: flow={memory.flow_state}, intent={memory.last_intent_detected}, cart={memory.pending_order_lines}")
            
            # La función _send_text ahora no necesita el with_context, pero lo dejamos por si acaso
            def _send_text(incoming_record, text_to_send):
                """
                Envía una respuesta utilizando el método nativo de Odoo 'message_post',
                asegurando que el mensaje aparezca en el chatter.
                """
                _logger.info(f"🚀 Preparando para enviar mensaje a través del canal: '{text_to_send}'")
                
                # --- INICIO DE LA CORRECCIÓN ---
                # 1. Obtenemos el canal a través del `mail.message` asociado al mensaje de WhatsApp.
                #    El mensaje de WhatsApp (`incoming_record`) no tiene un `channel_id` directo.
                mail_message = incoming_record.mail_message_id
                if not mail_message or mail_message.model != 'discuss.channel' or not mail_message.res_id:
                    _logger.error(f"❌ No se pudo determinar el canal de discusión para el mensaje de WhatsApp {incoming_record.id}. No se puede enviar la respuesta.")
                    return
                
                channel = self.env['discuss.channel'].browse(mail_message.res_id)
                # --- FIN DE LA CORRECCIÓN ---

                if not channel:
                    _logger.error(f"❌ No se encontró un canal de discusión para el mensaje {incoming_record.id}. No se puede enviar la respuesta.")
                    return

                # 2. El autor de un mensaje en el chatter debe ser un 'res.partner'.
                # Obtenemos el partner asociado al usuario Administrador.
                bot_partner_id = self.env.ref('base.user_admin').partner_id.id

                # 3. Publicamos en el canal. Odoo se encarga del resto.
                # El 'author_id' asegura que el mensaje aparezca como enviado por el Bot/Empresa.
                channel.sudo().message_post(
                    body=text_to_send,
                    author_id=bot_partner_id,
                    message_type='comment',
                    subtype_xmlid='mail.mt_comment'
                )
                _logger.info(f"✅ Mensaje posteado en el canal '{channel.name}' para envío.")
            
            # El resto del código que llama a _send_text no necesita cambios.
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