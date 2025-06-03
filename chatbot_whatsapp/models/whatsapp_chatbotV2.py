from odoo import models, api
from ..utils.nlp import detect_intention, normalize_phone
from .intent_handlers import (
    handle_crear_pedido,
    handle_confirmar_pedido,
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

        for record, vals in zip(records, vals_list):
            # 1) Si el registro no viene como "received", saltamos
            if vals.get('state') != 'received':
                continue

            # 2) Procesamos solo los entrantes
            plain_body = (vals.get("body") or "").strip()
            raw_phone = vals.get("mobile_number") or vals.get("phone") or ""
            phone = normalize_phone(raw_phone)

            partner = self.env['res.partner'].sudo().search([
                '|', ('phone', 'ilike', phone), ('mobile', 'ilike', phone)
            ], limit=1)
            if not partner:
                _logger.info("WhatsAppMessage.create: No partner for phone='%s'", phone)
                continue

            api_key = self.env['ir.config_parameter'].sudo().get_param('openai.api_key')
            intent = detect_intention(plain_body.lower(), api_key)
            _logger.info(
                "WhatsAppMessage.create: partner_id=%s intent=%s text='%s'",
                partner.id, intent, plain_body
            )

            def _send_text(to_record, text):
                outgoing_vals = {
                    'mobile_number': to_record.mobile_number,
                    'body': text,
                    'state': 'outgoing',
                    'wa_account_id': to_record.wa_account_id.id if to_record.wa_account_id else False,
                    'create_uid': self.env.ref('base.user_admin').id,
                }
                outgoing_msg = self.env['whatsapp.message'].sudo().create(outgoing_vals)
                if hasattr(outgoing_msg, '_send_message'):
                    outgoing_msg._send_message()

            # 3) Según la intención, enviamos la respuesta
            if intent == "crear_pedido":
                result = handle_crear_pedido(partner, plain_body)
                _send_text(record, result)

            elif intent == "confirmar_pedido":
                result = handle_confirmar_pedido(partner, plain_body)
                _send_text(record, result)

            elif intent == "solicitar_factura":
                result = handle_solicitar_factura(partner, plain_body)
                if result.get('pdf_base64'):
                    _send_text(record, result['message'])
                    filename = f"{partner.name}_factura_{plain_body.replace(' ', '_')}.pdf"
                    pdf_b64 = result['pdf_base64']
                    if hasattr(record, 'send_whatsapp_document'):
                        record.send_whatsapp_document(pdf_b64, filename, mime_type='application/pdf')
                    else:
                        _logger.warning("WhatsAppMessage: send_whatsapp_document() no existe")
                else:
                    _send_text(record, result['message'])

            elif intent in ["consulta_horario", "saludo", "consulta_producto", "ubicacion", "agradecimiento"]:
                response = handle_respuesta_faq(intent, partner, plain_body)
                _send_text(record, response)

            else:
                _send_text(record, "Perdón, no entendí eso 😅. ¿Podés reformular tu consulta?")

        return records
