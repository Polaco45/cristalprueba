from odoo import models, api
from ..utils.nlp import detect_intention
from ..utils.utils import clean_html, normalize_phone
from .intent_handlers.intent_handlers import (
    handle_solicitar_factura,
    handle_respuesta_faq
)
from .intent_handlers.create_order import handle_crear_pedido, create_sale_order
import logging

_logger = logging.getLogger(__name__)

class WhatsAppMessage(models.Model):
    _inherit = 'whatsapp.message'

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)

        for record in records:
            if record.state not in ('received', 'inbound'):
                continue

            plain_body = clean_html(record.body or "").strip()
            raw_phone  = record.mobile_number or record.phone or ""
            phone      = normalize_phone(raw_phone)

            if not plain_body or not phone:
                continue

            partner = self.env['res.partner'].sudo().search([
                '|', ('phone','ilike', phone), ('mobile','ilike', phone)
            ], limit=1)
            if not partner:
                continue

            def _send_text(to_record, text_to_send):
                vals = {
                    'mobile_number': to_record.mobile_number,
                    'body':          text_to_send,
                    'state':         'outgoing',
                    'wa_account_id': to_record.wa_account_id.id if to_record.wa_account_id else False,
                    'create_uid':    self.env.ref('base.user_admin').id,
                }
                out = self.env['whatsapp.message'].sudo().create(vals)
                out.sudo().write({'body': text_to_send})
                if hasattr(out, '_send_message'):
                    out._send_message()

            # ——— Contexto de confirmación de stock ———
            memory = self.env['chatbot.whatsapp.memory'].sudo().search([
                ('partner_id', '=', partner.id)
            ], order='timestamp desc', limit=1)
            if memory and memory.last_intent == 'esperando_confirmacion_stock':
                if plain_body.lower() in ['sí', 'si', 'dale', 'ok', 'bueno', 'va', 'de una']:
                    variant = memory.last_variant_id
                    qty     = memory.last_qty_suggested
                    order   = create_sale_order(self.env, partner.id, variant.id, qty)
                    memory.unlink()
                    _send_text(record, f"📝 Pedido {order.name} creado: {qty}×{variant.display_name}.")
                    continue

            # ——— Armar historial de conversación ———
            history_records = self.env['whatsapp.message'].sudo().search([
                ('mobile_number', '=', record.mobile_number),
                ('id', '<', record.id),
                ('state', 'in', ['received', 'outgoing'])
            ], order='id desc', limit=3)

            conversation = []
            for msg in reversed(history_records):
                role = "user" if msg.state in ("received", "inbound") else "assistant"
                content = clean_html(msg.body or "").strip()
                if content:
                    conversation.append({"role": role, "content": content})

            # Añadir el mensaje actual como último mensaje del usuario
            conversation.append({"role": "user", "content": plain_body})

            # ——— Detectar intención con contexto ———
            api_key    = self.env['ir.config_parameter'].sudo().get_param('openai.api_key')
            raw_intent = detect_intention(conversation, api_key) or ""
            intent     = raw_intent.lower().strip()
            _logger.info("Intención detectada: %s", intent)

            # ——— Routers de intención ———
            if intent == "crear_pedido":
                result = handle_crear_pedido(self.env, partner, plain_body)
                self.env['chatbot.whatsapp.memory'].sudo().search(
                    [('partner_id', '=', partner.id)], limit=1
                ).sudo().unlink()
                self.env['chatbot.whatsapp.memory'].sudo().create({
                    'partner_id': partner.id,
                    'last_intent': intent,
                })
                _send_text(record, result)

            elif intent == "solicitar_factura":
                r = handle_solicitar_factura(partner, plain_body)
                if r.get('pdf_base64'):
                    _send_text(record, r['message'])
                    fname = f"{partner.name}_factura_{plain_body.replace(' ','_')}.pdf"
                    if hasattr(record, 'send_whatsapp_document'):
                        record.send_whatsapp_document(r['pdf_base64'], fname, mime_type='application/pdf')
                else:
                    _send_text(record, r['message'])

            elif intent in ["consulta_horario", "saludo", "consulta_producto", "ubicacion", "agradecimiento"]:
                resp = handle_respuesta_faq(intent, partner, plain_body)
                _send_text(record, resp)

            else:
                _send_text(record, "Perdón, no entendí eso 😅. ¿Podés reformular tu consulta?")

        return records
