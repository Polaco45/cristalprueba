from odoo import models, api
from ..utils.nlp import detect_intention 
from ..utils.utils import clean_html, normalize_phone
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
        # Creamos primero los registros entrantes
        records = super().create(vals_list)

        for record in records:
            # 1) Solo procesamos los que llegan como 'received'
            if record.state != 'received':
                continue

            # 2) Limpiamos el HTML antes de procesar texto
            plain_body = clean_html(record.body or "").strip()
            raw_phone  = record.mobile_number or record.phone or ""
            phone = normalize_phone(raw_phone)

            # Si no hay texto limpio o no hay teléfono, saltamos
            if not plain_body or not phone:
                _logger.info(
                    "WhatsAppMessage.create: salto porque body='%s' o phone='%s' no válido",
                    plain_body, raw_phone
                )
                continue

            # 3) Buscamos el partner normalizando número
            partner = self.env['res.partner'].sudo().search([
                '|', ('phone', 'ilike', phone), ('mobile', 'ilike', phone)
            ], limit=1)
            if not partner:
                _logger.info("WhatsAppMessage.create: No partner para '%s'", phone)
                continue

            # 4) Detectamos intención y normalizamos el string (quitamos "Intención:")
            api_key = self.env['ir.config_parameter'].sudo().get_param('openai.api_key')
            raw_intent = detect_intention(plain_body.lower(), api_key) or ""
            intent = raw_intent.lower().replace("intención:", "").strip()

            _logger.info(
                "WhatsAppMessage.create: partner_id=%s intent='%s' text='%s'",
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
                else:
                    _logger.warning("WhatsAppMessage: _send_message() no existe en whatsapp.message")

            # 5) Enviamos respuesta según la intención limpia
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
