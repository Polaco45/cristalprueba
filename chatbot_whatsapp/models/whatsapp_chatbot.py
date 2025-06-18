from odoo import models, fields, api
from ..utils.nlp import detect_intention
from ..utils.utils import clean_html, normalize_phone
from .intent_handlers.intent_handlers import (
    handle_solicitar_factura,
    handle_respuesta_faq
)
from .intent_handlers.create_order import handle_crear_pedido, create_sale_order
import logging, json

_logger = logging.getLogger(__name__)

class WhatsAppMessage(models.Model):
    _inherit = 'whatsapp.message'

    # --- NUEVOS CAMPOS PARA INTERACTIVO ---
    message_type = fields.Selection(
        selection_add=[('interactive', 'Interactive')],
        ondelete={'interactive': 'cascade'},
        default=None,
        help="Tipo de mensaje para el conector WhatsApp"
    )
    interactive_payload = fields.Text(
        string="Interactive Payload",
        help="JSON que envía WhatsApp para mensajes interactivos (botones)"
    )

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for record in records:
            # Solo procesar inbound
            if record.state not in ('received', 'inbound'):
                continue

            plain = clean_html(record.body or "").strip()
            phone = normalize_phone(record.mobile_number or record.phone or "")
            if not (plain and phone):
                continue

            partner = self.env['res.partner'].sudo().search([
                '|', ('phone','ilike', phone), ('mobile','ilike', phone)
            ], limit=1)
            if not partner:
                continue

            # -- Helpers de envío --
            def _send_text(to_rec, msg):
                vals = {
                    'mobile_number': to_rec.mobile_number,
                    'body': msg,
                    'state': 'outgoing',
                    'wa_account_id': to_rec.wa_account_id.id,
                }
                out = self.env['whatsapp.message'].sudo().create(vals)
                out.sudo().write({'body': msg})
                if hasattr(out, '_send_message'):
                    out._send_message()

            def _send_buttons(to_rec, text, buttons):
                # 1) Construir payload
                payload = {
                    "type": "interactive",
                    "interactive": {
                        "type": "button",
                        "body": {"text": text},
                        "actions": {"buttons": buttons}
                    }
                }
                _logger.info("📤 Payload interactive:\n%s", payload)

                # 2) Crear el registro outgoing marcado como interactive
                vals = {
                    'mobile_number': to_rec.mobile_number,
                    'body': text,
                    'state': 'outgoing',
                    'wa_account_id': to_rec.wa_account_id.id,
                    'message_type': 'interactive',
                    'interactive_payload': json.dumps(payload),
                }
                out = self.env['whatsapp.message'].sudo().create(vals)

                # 3) Enviar interactivo
                if hasattr(out, 'send_whatsapp_interactive'):
                    out.send_whatsapp_interactive(payload)
                    if hasattr(out, '_send_message'):
                        out._send_message()

            # --- Test manual ---
            if plain.lower() == "test botones":
                btns = [
                    {"type": "reply", "reply": {"id": "b1", "title": "Uno"}},
                    {"type": "reply", "reply": {"id": "b2", "title": "Dos"}},
                    {"type": "reply", "reply": {"id": "b3", "title": "Tres"}},
                ]
                _send_buttons(record, "Elige una opción:", btns)
                continue

            # --- Flujo confirmación stock (memoria) ---
            memory = self.env['chatbot.whatsapp.memory'].sudo().search(
                [('partner_id','=',partner.id)],
                order='timestamp desc', limit=1
            )
            if memory and memory.last_intent == 'esperando_confirmacion_stock':
                ir = getattr(record, 'interactive_reply', {}) or {}
                bid = ir.get('id')
                if bid == 'confirm_all':
                    var, qty = memory.last_variant_id, memory.last_qty_suggested
                    order = create_sale_order(self.env, partner.id, var.id, qty)
                    memory.unlink()
                    _send_text(record, f"📝 Pedido {order.name} creado: {qty}×{var.display_name}.")
                    continue
                if bid == 'choose_qty':
                    memory.last_intent = 'esperando_nueva_cantidad'
                    _send_text(record, "Perfecto, decime cuántas unidades querés.")
                    continue
                if bid == 'cancel_order':
                    memory.unlink()
                    _send_text(record, "Entendido, no genero ningún pedido.")
                    continue

            if memory and memory.last_intent == 'esperando_nueva_cantidad':
                try:
                    new_qty = int(plain)
                except ValueError:
                    _send_text(record, "No entiendo ese número. ¿Podés escribir la cantidad en dígitos?")
                    continue
                var = memory.last_variant_id
                avail = var.qty_available or 0
                if new_qty > avail:
                    btns = [
                        {"type": "reply", "reply": {"id": "confirm_all", "title": f"Sí, quiero las {avail}"}},
                        {"type": "reply", "reply": {"id": "choose_qty", "title": "Quiero otra cantidad"}},
                        {"type": "reply", "reply": {"id": "cancel_order", "title": "No, gracias"}}
                    ]
                    _send_buttons(record,
                        f"Sigue siendo más de lo que hay ({avail}). ¿Qué querés hacer?",
                        btns
                    )
                    continue
                order = create_sale_order(self.env, partner.id, var.id, new_qty)
                memory.unlink()
                _send_text(record, f"📝 Pedido {order.name} creado: {new_qty}×{var.display_name}.")
                continue

            # --- Clasificación de intención ---
            hist = self.env['whatsapp.message'].sudo().search([
                ('mobile_number','=',record.mobile_number),
                ('id','<',record.id),
                ('state','in',['received','outgoing'])
            ], order='id desc', limit=3)
            conv = []
            for m in reversed(hist):
                role = "user" if m.state in ("received","inbound") else "assistant"
                c = clean_html(m.body or "").strip()
                if c: conv.append({"role": role, "content": c})
            conv.append({"role":"user","content":plain})
            intent = detect_intention(
                conv,
                self.env['ir.config_parameter'].sudo().get_param('openai.api_key')
            ).lower().strip()
            _logger.info("Intención detectada: %s", intent)

            # --- Routing según intención ---
            if intent == "crear_pedido":
                result = handle_crear_pedido(
                    self.env, partner, plain,
                    send_buttons=lambda t, b: _send_buttons(record, t, b)
                )
                if result:
                    self.env['chatbot.whatsapp.memory'].sudo().search(
                        [('partner_id','=',partner.id)], limit=1
                    ).sudo().unlink()
                    self.env['chatbot.whatsapp.memory'].sudo().create({
                        'partner_id': partner.id,
                        'last_intent': intent,
                    })
                    _send_text(record, result)

            elif intent == "solicitar_factura":
                r = handle_solicitar_factura(partner, plain)
                if r.get('pdf_base64'):
                    _send_text(record, r['message'])
                    fname = f"{partner.name}_factura_{plain.replace(' ','_')}.pdf"
                    record.send_whatsapp_document(r['pdf_base64'], fname, mime_type='application/pdf')
                else:
                    _send_text(record, r['message'])

            elif intent in [
                "consulta_horario","saludo","consulta_producto",
                "ubicacion","agradecimiento"
            ]:
                resp = handle_respuesta_faq(intent, partner, plain)
                _send_text(record, resp)

            else:
                _send_text(record, "Perdón, no entendí eso 😅.")

        return records
