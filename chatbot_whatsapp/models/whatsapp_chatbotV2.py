from odoo import models, fields, api
from ..utils.nlp import detect_intention
from .intent_handlers import (
    handle_crear_pedido,
    handle_confirmar_pedido,
    handle_solicitar_factura,
    handle_respuesta_faq
)

class WhatsAppMessage(models.Model):
    _inherit = 'whatsapp.message'
    
    body = fields.Text()
    phone = fields.Char()

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)

        for record, vals in zip(records, vals_list):
            plain_body = vals.get("body", "").strip()
            phone = vals.get("phone")
            partner = self.env['res.partner'].sudo().search([('phone', 'ilike', phone)], limit=1)

            if not partner:
                continue

            api_key = self.env['ir.config_parameter'].sudo().get_param('openai.api_key')
            intent = detect_intention(plain_body.lower(), api_key)

            # Helper para mandar respuesta
            def _send_text(to_record, text):
                # to_record es el mensaje entrante (record)
                outgoing_vals = {
                    'mobile_number': to_record.mobile_number,
                    'body': text,
                    'state': 'outgoing',
                    'wa_account_id': to_record.wa_account_id.id if to_record.wa_account_id else False,
                    'create_uid': self.env.ref('base.user_admin').id,
                }
                outgoing_msg = self.env['whatsapp.message'].sudo().create(outgoing_vals)
                # si el método de envío real es _send_message(), lo llamamos:
                if hasattr(outgoing_msg, '_send_message'):
                    outgoing_msg._send_message()

            if intent == "crear_pedido":
                result = handle_crear_pedido(partner, plain_body)
                _send_text(record, result)

            elif intent == "confirmar_pedido":
                result = handle_confirmar_pedido(partner, plain_body)
                _send_text(record, result)

            elif intent == "solicitar_factura":
                result = handle_solicitar_factura(partner, plain_body)
                if result.get('pdf_base64'):
                    # Primero enviamos el texto
                    _send_text(record, result['message'])
                    # Luego creamos el documento PDF como attachment
                    filename = f"{partner.name}_factura_{plain_body.strip()}.pdf"
                    pdf_b64 = result['pdf_base64']
                    # Asumimos que existe un método send_whatsapp_document en el modelo
                    # para enviar documentos en base64. Si no, van a tener que implementarlo
                    record.send_whatsapp_document(pdf_b64, filename, mime_type='application/pdf')
                else:
                    _send_text(record, result['message'])

            elif intent in ["consulta_horario", "saludo", "consulta_producto", "ubicacion", "agradecimiento"]:
                response = handle_respuesta_faq(intent, partner, plain_body)
                _send_text(record, response)

            else:
                _send_text(record, "Perdón, no entendí eso 😅. ¿Podés reformular tu consulta?")

        return records
