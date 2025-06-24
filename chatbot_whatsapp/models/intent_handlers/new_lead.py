from odoo import models, api
import re
import logging

_logger = logging.getLogger(__name__)

class NewLeadHandler(models.AbstractModel):
    _name = 'chatbot.whatsapp.new_lead_handler'
    _description = "Manejo de nuevo lead para clientes nuevos vía WhatsApp"

    def _is_valid_email(self, email):
        """
        Valida el formato del correo electrónico con regex básica.
        """
        pattern = r"^[\w\.-]+@[\w\.-]+\.\w{2,}$"
        return re.match(pattern, email)

    @api.model
    def process_new_lead_flow(self, env, record, phone, plain_body, memory_model):
        """
        Detecta si el número no está asociado a partner.
        Si es nuevo, pregunta nombre y email, crea lead.
        Maneja la memoria para el flujo de conversación.
        Devuelve (handled:bool, message:str)
        """
        memory = memory_model.search([('phone', '=', phone)], limit=1)

        # No memoria -> pedimos nombre
        if not memory:
            memory_model.create({
                'phone': phone,
                'last_intent': 'esperando_nombre_nuevo_cliente',
            })
            return True, "¡Hola! Para poder ayudarte, ¿me decís tu *nombre* completo?"

        # Esperando nombre -> guardo nombre, pido email
        if memory.last_intent == 'esperando_nombre_nuevo_cliente':
            memory.write({
                'last_intent': 'esperando_email_nuevo_cliente',
                'data_buffer': plain_body.strip(),
            })
            return True, "Gracias 😊. ¿Cuál es tu *correo electrónico*?"

        # Esperando email -> valido y creo lead
        if memory.last_intent == 'esperando_email_nuevo_cliente':
            email = plain_body.strip()

            if not self._is_valid_email(email):
                return True, "Mmm... ese correo no parece válido 🤔. ¿Podés escribirlo de nuevo?"

            nombre = memory.data_buffer or "Sin nombre"

            lead_vals = {
                'name': f"Nuevo cliente WhatsApp: {nombre}",
                'contact_name': nombre,
                'email_from': email,
                'phone': phone,
                'description': "Nuevo contacto B2B generado automáticamente desde el chatbot de WhatsApp.",
            }

            env['crm.lead'].sudo().create(lead_vals)
            memory.unlink()
            return True, "¡Gracias! Un asesor se va a contactar con vos para cotizarte ✅"

        return False, ""
