from odoo import models, api
from ..utils.nlp import detect_intention
from ..utils.utils import clean_html, normalize_phone
from .intent_handlers.intent_handlers import handle_solicitar_factura, handle_respuesta_faq
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

            plain = clean_html(record.body or "").strip()
            phone = normalize_phone(record.mobile_number or record.phone or "")
            if not plain or not phone:
                continue

            partner = self.env['res.partner'].sudo().search([
                '|', ('phone','ilike', phone), ('mobile','ilike', phone)
            ], limit=1)
            if not partner:
                continue

            def _send(to_rec, text):
                vals = {
                    'mobile_number': to_rec.mobile_number,
                    'body':          text,
                    'state':         'outgoing',
                    'wa_account_id': to_rec.wa_account_id.id if to_rec.wa_account_id else False,
                    'create_uid':    self.env.ref('base.user_admin').id,
                }
                msg = self.env['whatsapp.message'].sudo().create(vals)
                msg.sudo().write({'body': text})
                if hasattr(msg, '_send_message'):
                    msg._send_message()

            # ——— Revisión de contexto ———
            mem = self.env['chatbot.whatsapp.memory'].sudo().search(
                [('partner_id', '=', partner.id)],
                order='timestamp desc', limit=1
            )
            if mem and mem.last_intent == 'esperando_confirmacion_stock':
                if plain.lower() in ['sí','si','dale','ok','bueno','va','de una']:
                    var = mem.last_variant_id
                    qty = mem.last_qty_suggested
                    order = create_sale_order(self.env, partner.id, var.id, qty)
                    mem.unlink()
                    _send(record, f"📝 Pedido {order.name} creado: {qty}×{var.display_name}.")
                    continue

            # ——— Procesamiento estándar ———
            api_key = self.env['ir.config_parameter'].sudo().get_param('openai.api_key')
            intent  = detect_intention(plain.lower(), api_key)
            _logger.info("Intent: %s", intent)

            if intent == "crear_pedido":
                res = handle_crear_pedido(self.env, partner, plain)
                _send(record, res)

            elif intent == "solicitar_factura":
                r = handle_solicitar_factura(partner, plain)
                if r.get('pdf_base64'):
                    _send(record, r['message'])
                    name = f"{partner.name}_{plain.replace(' ','_')}.pdf"
                    if hasattr(record, 'send_whatsapp_document'):
                        record.send_whatsapp_document(r['pdf_base64'], name, mime_type='application/pdf')
                else:
                    _send(record, r['message'])

            elif intent in ["consulta_horario","saludo","consulta_producto","ubicacion","agradecimiento"]:
                resp = handle_respuesta_faq(intent, partner, plain)
                _send(record, resp)

            else:
                _send(record, "Perdón, no entendí eso 😅. ¿Podés reformular?")
        return records
