from odoo import models, api
import re
import logging

_logger = logging.getLogger(__name__)

class NewLeadHandler(models.AbstractModel):
    _name = 'chatbot.whatsapp.new_lead_handler'
    _description = "Manejo de nuevo lead para clientes nuevos vía WhatsApp"

    def _is_valid_email(self, email):
        pattern = r"^[\w\.-]+@[\w\.-]+\.\w{2,}$"
        return re.match(pattern, email)

    @api.model
    def process_new_lead_flow(self, env, record, phone, plain_body, memory_model):
        memory = memory_model.search([('phone', '=', phone)], limit=1)
        plain = plain_body.strip().lower()

        TYPE_OPTIONS = {
            '1': 'Tipo de Cliente / Consumidor Final',
            'consumidor final': 'Tipo de Cliente / Consumidor Final',
            '2': 'Tipo de Cliente / EMPRESA',
            'institucion': 'Tipo de Cliente / EMPRESA',
            'empresa': 'Tipo de Cliente / EMPRESA',
            '3': 'Tipo de Cliente / Mayorista',
            'mayorista': 'Tipo de Cliente / Mayorista',
        }

        if not memory:
            memory_model.create({
                'phone': phone,
                'last_intent': 'esperando_nombre_nuevo_cliente',
            })
            return True, "¡Hola! Para poder ayudarte, ¿me decís tu *nombre* completo?"

        if memory.last_intent == 'esperando_nombre_nuevo_cliente':
            memory.write({
                'last_intent': 'esperando_email_nuevo_cliente',
                'data_buffer': plain_body.strip(),
            })
            return True, "Gracias 😊. ¿Cuál es tu *correo electrónico*?"

        if memory.last_intent == 'esperando_email_nuevo_cliente':
            if not self._is_valid_email(plain_body.strip()):
                return True, "Mmm... ese correo no parece válido 🤔. ¿Podés escribirlo de nuevo?"
            memory.write({
                'last_intent': 'esperando_tipo_cliente',
                'data_buffer': f"{memory.data_buffer}|{plain_body.strip()}"
            })
            return True, (
                "¡Última pregunta! ¿Qué tipo de cliente sos?\n"
                "Seleccioná un número o escribí la opción:\n"
                "1 - Consumidor final\n"
                "2 - Institución\n"
                "3 - Mayorista"
            )

        if memory.last_intent == 'esperando_tipo_cliente':
            etiqueta = TYPE_OPTIONS.get(plain)
            if not etiqueta:
                return True, (
                    "Perdón, no entendí tu respuesta. Por favor respondé con:\n"
                    "1 - Consumidor final\n"
                    "2 - Institución\n"
                    "3 - Mayorista"
                )

            nombre, email = (memory.data_buffer or "").split("|")

            # Crear partner
            partner = env['res.partner'].sudo().create({
                'name': nombre.strip(),
                'phone': phone,
                'email': email.strip(),
                'company_type': 'company',
            })

            # Aplicar etiqueta
            tag = env['res.partner.category'].sudo().search([('name', '=', etiqueta)], limit=1)
            if tag:
                partner.category_id = [(4, tag.id)]

            # Crear lead
            lead_vals = {
                'name': f"Nuevo cliente WhatsApp: {nombre.strip()}",
                'contact_name': nombre.strip(),
                'email_from': email.strip(),
                'phone': phone,
                'partner_id': partner.id,
                'description': "Nuevo contacto B2B generado automáticamente desde el chatbot de WhatsApp.",
            }

            env['crm.lead'].sudo().create(lead_vals)

            memory.write({'partner_id': partner.id})
            memory.unlink()

            return True, "¡Gracias! Registramos tu contacto ✅. Un asesor se va a comunicar con vos pronto."

        return False, ""
