# models/whatsapp_chatbot.py

from odoo import models, api
from ..utils.nlp import detect_intention
from ..utils.utils import clean_html, normalize_phone
from .intent_handlers.create_order import handle_crear_pedido, create_sale_order
from .intent_handlers.intent_handlers import (
    handle_solicitar_factura,
    handle_respuesta_faq
)
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

            plain = clean_html(record.body or "").strip()
            phone = normalize_phone(record.mobile_number or record.phone or "")
            if not (plain and phone):
                continue

            partner = self.env['res.partner'].sudo().search([
                '|', ('phone','ilike', phone), ('mobile','ilike', phone)
            ], limit=1)
            if not partner:
                continue

            def _send_text(to_rec, msg):
                vals = {
                    'mobile_number': to_rec.mobile_number,
                    'body': msg,
                    'state': 'outgoing',
                    'wa_account_id': to_rec.wa_account_id.id if to_rec.wa_account_id else False,
                    'create_uid': self.env.ref('base.user_admin').id,
                }
                out = self.env['whatsapp.message'].sudo().create(vals)
                out.sudo().write({'body': msg})
                if hasattr(out, '_send_message'):
                    out._send_message()

            # — Flujo de confirmación stock (1/2/3 o literal) —
            memory = self.env['chatbot.whatsapp.memory'].sudo().search(
                [('partner_id','=',partner.id)],
                order='timestamp desc', limit=1
            )
            if memory and memory.last_intent == 'esperando_confirmacion_stock':
                choice = plain.strip().lower()

                # 1) Confirmar todo
                if choice in ('1', '1)', 'sí', 'si', f'sí, quiero las {memory.last_qty_suggested}',
                              f'si, quiero las {memory.last_qty_suggested}'):
                    var = memory.last_variant_id
                    qty = memory.last_qty_suggested
                    order = create_sale_order(self.env, partner.id, var.id, qty)
                    memory.unlink()
                    _send_text(record, f"📝 Pedido {order.name} creado: {qty}×{var.display_name}.")
                    continue

                # 2) Otra cantidad
                if choice in ('2', '2)', 'quiero otra cantidad'):
                    memory.last_intent = 'esperando_nueva_cantidad'
                    _send_text(record, "Perfecto, decime cuántas unidades querés.")
                    continue

                # 3) Cancelar
                if choice in ('3', '3)', 'no', 'no gracias', 'no, gracias'):
                    memory.unlink()
                    _send_text(record, "Entendido, no genero ningún pedido.")
                    continue

                # Respuesta inválida: reenviamos contexto + opciones
                var = memory.last_variant_id
                avail = memory.last_qty_suggested
                name = var.display_name
                _send_text(record,
                    f"Solo hay {avail} unidades de “{name}”.\n"
                    "Respondé con:\n"
                    f"1) Sí, quiero las {avail}\n"
                    "2) Quiero otra cantidad\n"
                    "3) No, gracias"
                )
                continue

            # — Flujo nueva cantidad tras "2) Quiero otra cantidad" —
            if memory and memory.last_intent == 'esperando_nueva_cantidad':
                try:
                    new_qty = int(plain)
                except ValueError:
                    _send_text(record, "No entiendo ese número. ¿Podés escribir la cantidad en dígitos?")
                    continue
                var = memory.last_variant_id
                avail = var.qty_available or 0
                if new_qty > avail:
                    # Volvemos al flujo de confirmación
                    memory.write({'last_intent': 'esperando_confirmacion_stock', 'last_qty_suggested': avail})
                    name = var.display_name
                    _send_text(record,
                        f"Sigue siendo más de lo que hay ({avail}).\n"
                        "Respondé con:\n"
                        f"1) Sí, quiero las {avail}\n"
                        "2) Quiero otra cantidad\n"
                        "3) No, gracias"
                    )
                    continue
                order = create_sale_order(self.env, partner.id, var.id, new_qty)
                memory.unlink()
                _send_text(record, f"📝 Pedido {order.name} creado: {new_qty}×{var.display_name}.")
                continue

            # — Contexto para clasificación de intenciones —
            history = self.env['whatsapp.message'].sudo().search([
                ('mobile_number','=',record.mobile_number),
                ('id','<',record.id),
                ('state','in',['received','outgoing'])
            ], order='id desc', limit=3)
            conv = []
            for m in reversed(history):
                role = "user" if m.state in ("received","inbound") else "assistant"
                c = clean_html(m.body or "").strip()
                if c:
                    conv.append({"role": role, "content": c})
            conv.append({"role":"user","content":plain})

            intent = detect_intention(
                conv,
                self.env['ir.config_parameter'].sudo().get_param('openai.api_key')
            ).lower().strip()
            _logger.info("Intención detectada: %s", intent)

            # — Routing principal —
            if intent == "crear_pedido":
                result = handle_crear_pedido(
                    self.env, partner, plain, send_buttons=None
                )
                if result:
                    # guardamos intención y enviamos
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

            elif intent in ["consulta_horario","saludo","consulta_producto","ubicacion","agradecimiento"]:
                resp = handle_respuesta_faq(intent, partner, plain)
                _send_text(record, resp)

            else:
                _send_text(record, "Perdón, no entendí eso 😅.")

        return records
