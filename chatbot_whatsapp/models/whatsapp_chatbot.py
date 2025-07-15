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

            memory = self.env['chatbot.whatsapp.memory'].sudo().search([
                ('partner_id', '=', partner.id)
            ], limit=1)
            if not memory:
                memory = self.env['chatbot.whatsapp.memory'].sudo().create({
                    'partner_id': partner.id
                })

            now = datetime.now()
            if memory.human_takeover and memory.takeover_until and memory.takeover_until > now:
                _logger.info(f"🤫 Chatbot en pausa para {partner.name}. Ignorando.")
                continue
            if memory.human_takeover and memory.takeover_until and memory.takeover_until <= now:
                _logger.info(f"🔁 Reactivando chatbot para {partner.name}")
                memory.sudo().write({
                    'human_takeover': False,
                    'takeover_until': False
                })

            _logger.info(f"📨 Nuevo mensaje '{plain}' de {partner.name} ({phone})")

            def _send_text(to_rec, msg):
                bot_id = self.env.ref('base.user_admin').id
                vals = {
                    'mobile_number': to_rec.mobile_number,
                    'body': msg,
                    'state': 'outgoing',
                    'wa_account_id': to_rec.wa_account_id.id,
                    'create_uid': bot_id,
                }
                out = self.env['whatsapp.message'].sudo().create(vals)
                out.sudo().write({'body': msg})
                if hasattr(out, '_send_message'):
                    out._send_message()
                _logger.info(f"✅ Enviado: '{msg}'")

            onboard = self.env['chatbot.whatsapp.onboarding_handler']
            handled, resp = onboard.process_onboarding_flow(
                self.env, record, phone, plain,
                self.env['chatbot.whatsapp.memory'].sudo()
            )
            if handled:
                _send_text(record, resp)
                continue

            b2c_tag = "Tipo de Cliente / Consumidor Final"
            is_b2c = partner.category_id and any(t.name == b2c_tag for t in partner.category_id)

            if not is_b2c and not is_cotizado(partner):
                if not memory.human_takeover:
                    _send_text(record, messages_config['onboarding_unquoted'])
                    memory.sudo().write({
                        'human_takeover': True,
                        'takeover_until': now + timedelta(hours=1)
                    })
                    _logger.info("🤖 Pausado por falta de cotización")
                else:
                    _logger.info(f"🤫 Ya está en pausa para {partner.name}")
                continue

            ChatbotProcessor(self.env, record, partner, memory).process_message()
        return records

class MailMessage(models.Model):
    _inherit = 'mail.message'

    @api.model_create_multi
    def create(self, vals_list):
        if self.env.context.get('from_wa_bot'):
            return super().create(vals_list)

        bot_id = self.env.ref('base.user_admin').partner_id.id
        public_id = self.env.ref('base.partner_root').id

        for vals in vals_list:
            if vals.get('model') != 'discuss.channel' or not vals.get('author_id'):
                continue
            if vals['author_id'] == bot_id:
                continue

            channel = self.env['discuss.channel'].browse(vals['res_id'])
            if channel.channel_type != 'whatsapp':
                continue

            # Obtener clientes y empleados en el canal
            partners = channel.channel_partner_ids.filtered(
                lambda p: p.id not in (bot_id, public_id)
            )
            if not partners:
                continue

            # Empleado = quien manda; Cliente = la otra persona
            author = self.env['res.partner'].browse(vals['author_id'])
            client_partners = partners.filtered(lambda p: p.id != author.id)
            target = client_partners and client_partners[0] or author

            memory = self.env['chatbot.whatsapp.memory'].sudo().search([
                ('partner_id', '=', target.id)
            ], limit=1)
            if not memory:
                continue

            memory.sudo().write({
                'human_takeover': True,
                'takeover_until': datetime.now() + timedelta(hours=1),
                'flow_state': False
            })
            _logger.info(f"👤 {author.name} intervino. Pausado chatbot para {target.name} por 1 h.")

        return super().create(vals_list)