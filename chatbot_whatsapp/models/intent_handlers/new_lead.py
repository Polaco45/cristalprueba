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

    def _parse_cliente_tag(self, texto_usuario):
        """
        Devuelve la etiqueta correspondiente a la opción del usuario.
        """
        OPCIONES = {
            '1': "Tipo de Cliente / Consumidor Final",
            'consumidor final': "Tipo de Cliente / Consumidor Final",
            '2': "Tipo de Cliente / EMPRESA",
            'institucion': "Tipo de Cliente / EMPRESA",
            'empresa': "Tipo de Cliente / EMPRESA",
            '3': "Tipo de Cliente / Mayorista",
            'mayorista': "Tipo de Cliente / Mayorista",
        }
        normalizado = texto_usuario.strip().lower()
        return OPCIONES.get(normalizado)

    @api.model
    def process_new_lead_flow(self, env, record, phone, plain_body, memory_model):
        memory = memory_model.search([('phone', '=', phone)], limit=1)

        if not memory:
            memory_model.create({
                'phone': phone,
                'last_intent': 'esperando_nombre_nuevo_cliente',
            })
            return True, "¡Hola! Para poder ayudarte, ¿me decís tu *nombre* completo?"

        if memory.last_intent == 'esperando_nombre_nuevo_cliente':
            memory.write({
                'last_intent': 'esperando_email_nuevo_cliente',
                'data_buffer': plain_body.strip(),  # Guardamos nombre
            })
            return True, "Gracias 😊. ¿Cuál es tu *correo electrónico*?"

        if memory.last_intent == 'esperando_email_nuevo_cliente':
            email = plain_body.strip()
            if not self._is_valid_email(email):
                return True, "Mmm... ese correo no parece válido 🤔. ¿Podés escribirlo de nuevo?"
            memory.write({
                'last_intent': 'esperando_tipo_cliente',
                'data_buffer': f"{memory.data_buffer.strip()}|||{email}",  # Guardamos nombre y email
            })
            return True, (
                "Una última pregunta 😊\n"
                "¿Qué tipo de cliente sos?\n"
                "1 - Consumidor final\n"
                "2 - Institución / Empresa\n"
                "3 - Mayorista\n"
                "Podés responder con el número o el texto."
            )

        if memory.last_intent == 'esperando_tipo_cliente':
            tipo_etiqueta = self._parse_cliente_tag(plain_body)
            if not tipo_etiqueta:
                return True, (
                    "No entendí esa opción 🤔. Por favor respondé con:\n"
                    "1 - Consumidor final\n"
                    "2 - Institución / Empresa\n"
                    "3 - Mayorista"
                )

            nombre, email = memory.data_buffer.split("|||")
            partner = env['res.partner'].sudo().create({
                'name': nombre.strip(),
                'phone': phone,
                'email': email.strip(),
                'company_type': 'company',
            })

            # Buscar o crear etiqueta
            tag = env['res.partner.category'].sudo().search([
                ('name', '=', tipo_etiqueta)
            ], limit=1)
            if not tag:
                tag = env['res.partner.category'].sudo().create({'name': tipo_etiqueta})

            partner.category_id = [(4, tag.id)]

            env['crm.lead'].sudo().create({
                'name': f"Nuevo cliente WhatsApp: {nombre.strip()}",
                'contact_name': nombre.strip(),
                'email_from': email.strip(),
                'phone': phone,
                'partner_id': partner.id,
                'description': "Nuevo contacto B2B generado automáticamente desde el chatbot de WhatsApp.",
            })

            memory.unlink()
            return True, "¡Gracias! Un asesor se va a contactar con vos para cotizarte ✅"

        return False, ""
