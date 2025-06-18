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
                    'body': text_to_send,
                    'state': 'outgoing',
                    'wa_account_id': to_record.wa_account_id.id if to_record.wa_account_id else False,
                    'create_uid': self.env.ref('base.user_admin').id,
                }
                out = self.env['whatsapp.message'].sudo().create(vals)
                out.sudo().write({'body': text_to_send})
                if hasattr(out, '_send_message'):
                    out._send_message()

            def _send_buttons(to_record, text, buttons):
                payload = {
                    "type": "interactive",
                    "interactive": {
                        "type": "button",
                        "body": {"text": text},
                        "actions": {"buttons": buttons}
                    }
                }
                _logger.info("📤 Enviando botones a WhatsApp:\n%s", payload)
                if hasattr(to_record, 'send_whatsapp_interactive'):
                    to_record.send_whatsapp_interactive(payload)

            # 🚨 TEST MANUAL DE BOTONES
            if plain_body.lower() == "test botones":
                buttons = [
                    {"type": "reply", "reply": {"id": "boton_1", "title": "Opción 1"}},
                    {"type": "reply", "reply": {"id": "boton_2", "title": "Opción 2"}},
                    {"type": "reply", "reply": {"id": "boton_3", "title": "Cancelar"}}
                ]
                _send_buttons(record, "Este es un test de botones. Elegí una opción:", buttons)
                continue

            # ——— Confirmación stock ———
            memory = self.env['chatbot.whatsapp.memory'].sudo().search([
                ('partner_id', '=', partner.id)
            ], order='timestamp desc', limit=1)

            if memory and memory.last_intent == 'esperando_confirmacion_stock':
                ir = getattr(record, 'interactive_reply', None) or {}
                button_id = ir.get('id')
                if button_id == 'confirm_all':
                    variant = memory.last_variant_id
                    qty     = memory.last_qty_suggested
                    order   = create_sale_order(self.env, partner.id, variant.id, qty)
                    memory.unlink()
                    _send_text(record, f"📝 Pedido {order.name} creado: {qty}×{variant.display_name}.")
                    continue
                elif button_id == 'choose_qty':
                    memory.last_intent = 'esperando_nueva_cantidad'
                    _send_text(record, "Perfecto, decime cuántas unidades querés.")
                    continue
                elif button_id == 'cancel_order':
                    memory.unlink()
                    _send_text(record, "Entendido, no genero ningún pedido.")
                    continue

            if memory and memory.last_intent == 'esperando_nueva_cantidad':
                try:
                    new_qty = int(plain_body)
                except ValueError:
                    _send_text(record, "No entiendo ese número. ¿Podés escribir la cantidad en dígitos?")
                    continue
                variant = memory.last_variant_id
                available = variant.qty_available or 0
                if new_qty > available:
                    buttons = [
                        {"type": "reply", "reply": {"id": "confirm_all", "title": f"Sí, quiero las {available}"}},
                        {"type": "reply", "reply": {"id": "choose_qty", "title": "Quiero otra cantidad"}},
                        {"type": "reply", "reply": {"id": "cancel_order", "title": "No, gracias"}}
                    ]
                    _send_buttons(record, f"Sigue siendo más de lo que hay ({available}). ¿Qué querés hacer?", buttons)
                    continue
                order = create_sale_order(self.env, partner.id, variant.id, new_qty)
                memory.unlink()
                _send_text(record, f"📝 Pedido {order.name} creado: {new_qty}×{variant.display_name}.")
                continue

            # ——— Contexto conversación ———
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
            conversation.append({"role": "user", "content": plain_body})

            # ——— Clasificación ———
            api_key = self.env['ir.config_parameter'].sudo().get_param('openai.api_key')
            raw_intent = detect_intention(conversation, api_key) or ""
            intent = raw_intent.lower().strip()
            _logger.info("Intención detectada: %s", intent)

            # ——— Routing ———
            if intent == "crear_pedido":
                result = handle_crear_pedido(
                    self.env,
                    partner,
                    plain_body,
                    send_buttons=lambda text, buttons: _send_buttons(record, text, buttons)
                )
                if result:
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
