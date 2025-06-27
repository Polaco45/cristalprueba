from odoo import models, api
from ..utils.nlp import detect_intention
from ..utils.utils import clean_html, normalize_phone, is_cotizado
from .intent_handlers.create_order import handle_crear_pedido, create_sale_order
from .intent_handlers.onboarding import WhatsAppOnboardingHandler
from .intent_handlers.intent_handlers import (
    handle_solicitar_factura,
    handle_respuesta_faq
)
import logging
import json

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

            def _send_text(to_rec, text_to_send):
                vals = {
                    'mobile_number': to_rec.mobile_number,
                    'body': text_to_send,
                    'state': 'outgoing',
                    'wa_account_id': to_rec.wa_account_id.id if to_rec.wa_account_id else False,
                    'create_uid': self.env.ref('base.user_admin').id,
                }
                out = self.env['whatsapp.message'].sudo().create(vals)
                out.sudo().write({'body': text_to_send})
                if hasattr(out, '_send_message'):
                    out._send_message()

            partner = self.env['res.partner'].sudo().search([
                '|', ('phone','ilike', phone), ('mobile','ilike', phone)
            ], limit=1)

            memory_model = self.env['chatbot.whatsapp.memory'].sudo()

            onboarding_handler = self.env['chatbot.whatsapp.onboarding_handler']
            handled, response_msg = onboarding_handler.process_onboarding_flow(
                self.env, record, phone, plain, memory_model
            )
            if handled:
                _send_text(record, response_msg)
                continue

            if not is_cotizado(partner):
                _logger.info("🚫 Cliente no cotizado — se detiene el flujo NLP")
                _send_text(record, "Gracias por escribirnos 😊. Un asesor te va a contactar para cotizarte. ¡Te escribimos pronto!")
                continue

            memory = memory_model.search([('partner_id','=', partner.id)], order='timestamp desc', limit=1)

            if memory and memory.last_intent == 'esperando_confirmacion_stock':
                choice = plain.lower().strip()
                if choice in ('1','1)','sí','si'):
                    var = memory.last_variant_id
                    qty = memory.last_qty_suggested
                    order = create_sale_order(self.env, partner.id, var.id, qty)
                    memory.unlink()
                    _send_text(record, f"📝 Pedido {order.name} creado: {qty}×{var.display_name}.")
                    continue
                if choice in ('2','2)','quiero otra cantidad'):
                    memory.write({'last_intent': 'esperando_nueva_cantidad'})
                    _send_text(record, "Perfecto, decime cuántas unidades querés.")
                    continue
                if choice in ('3','3)','no','no gracias'):
                    memory.unlink()
                    _send_text(record, "Entendido, no genero ningún pedido.")
                    continue
                var = memory.last_variant_id
                avail = memory.last_qty_suggested
                _send_text(record,
                    f"Solo hay {avail} unidades de “{var.display_name}”.\n"
                    "Respondé con:\n1) Sí\n2) Otra cantidad\n3) No"
                )
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
                    memory.write({'last_intent': 'esperando_confirmacion_stock', 'last_qty_suggested': avail})
                    _send_text(record,
                        f"Sigue siendo más de lo que hay ({avail}).\n"
                        "Respondé con:\n1) Sí\n2) Otra cantidad\n3) No"
                    )
                    continue
                order = create_sale_order(self.env, partner.id, var.id, new_qty)
                memory.unlink()
                _send_text(record, f"📝 Pedido {order.name} creado: {new_qty}×{var.display_name}.")
                continue

            # Armado del contexto para el intent predictor
            history = self.env['whatsapp.message'].sudo().search([
                ('mobile_number','=', record.mobile_number),
                ('id','<=', record.id),
                ('state','in',['received','inbound','outgoing','sent'])
            ], order='id desc', limit=6)

            conv = []

            if memory:
                ctx = f"Contexto actual: última intención '{memory.last_intent}'."
                if memory.last_variant_id:
                    ctx += f" Producto sugerido: {memory.last_variant_id.display_name}."
                if memory.last_qty_suggested:
                    ctx += f" Cantidad sugerida: {memory.last_qty_suggested}."
                conv.append({"role": "system", "content": ctx})

            for msg in reversed(history):
                text = clean_html(msg.body or "").strip()
                if not text or text.lower() in ("ok", "gracias", "dale"):
                    continue
                if msg.state in ("received", "inbound"):
                    conv.append({"role": "user", "content": text})
                else:
                    conv.append({"role": "assistant", "content": text})

            _logger.info("🧠 Conversación enviada:\n%s", json.dumps(conv, indent=2, ensure_ascii=False))

            intent = detect_intention(
                conv,
                self.env['ir.config_parameter'].sudo().get_param('openai.api_key')
            ).lower().strip()
            _logger.info("Intención detectada: %s", intent)

            # 🔄 Guardamos la intención detectada en memoria
            if memory:
                memory.write({'last_intent': intent})
            else:
                memory_model.create({
                    'partner_id': partner.id,
                    'last_intent': intent,
                })

            # Routing
            if intent == "crear_pedido":
                result = handle_crear_pedido(self.env, partner, plain)
                if result:
                    _send_text(record, result)

            elif intent == "solicitar_factura":
                r = handle_solicitar_factura(partner, plain)
                _send_text(record, r['message'])
                if r.get('pdf_base64') and hasattr(record, 'send_whatsapp_document'):
                    fname = f"{partner.name}_factura_{plain.replace(' ','_')}.pdf"
                    record.send_whatsapp_document(r['pdf_base64'], fname, mime_type='application/pdf')

            elif intent in ["consulta_horario", "saludo", "consulta_producto", "ubicacion", "agradecimiento"]:
                resp = handle_respuesta_faq(intent, partner, plain)
                _send_text(record, resp)

            else:
                _send_text(record, "Perdón, no entendí eso 😅. ¿Podés reformular tu consulta?")

        return records
