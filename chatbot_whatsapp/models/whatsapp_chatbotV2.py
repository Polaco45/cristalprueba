from odoo import models, fields, api
from ..utils.nlp import detect_intention
from .intent_handlers import (
    handle_crear_pedido,
    handle_confirmar_pedido,  # <- NUEVO
    handle_solicitar_factura,
    handle_respuesta_faq
)

class WhatsAppMessage(models.Model):
    _inherit = 'whatsapp.message'
    
    body = fields.Text()
    phone = fields.Char()

    @api.model_create_multi
    def create(self, vals):
        record = super().create(vals)
        plain_body = vals.get("body", "").strip()
        phone = vals.get("phone")
        partner = self.env['res.partner'].sudo().search([('phone', 'ilike', phone)], limit=1)

        if not partner:
            return record

        api_key = self.env['ir.config_parameter'].sudo().get_param('openai.api_key')
        intent = detect_intention(plain_body.lower(), api_key)

        if intent == "crear_pedido":
            result = handle_crear_pedido(partner, plain_body)
            record.send_whatsapp_response(result)

        elif intent == "confirmar_pedido":
            result = handle_confirmar_pedido(partner, plain_body)
            record.send_whatsapp_response(result)

        elif intent == "solicitar_factura":
            result = handle_solicitar_factura(partner, plain_body)
            if result.get('pdf_base64'):
                record.send_whatsapp_response(result['message'])
                filename = f"{partner.name}_factura_{plain_body.strip()}.pdf"
                pdf_b64 = result['pdf_base64']
                record.send_whatsapp_document(pdf_b64, filename, mime_type='application/pdf')
            else:
                record.send_whatsapp_response(result['message'])

        elif intent in ["consulta_horario", "saludo", "consulta_producto", "ubicacion", "agradecimiento"]:
            response = handle_respuesta_faq(intent, partner, plain_body)
            record.send_whatsapp_response(response)

        else:
            record.send_whatsapp_response("Perdón, no entendí eso 😅. ¿Podés reformular tu consulta?")

        return record
