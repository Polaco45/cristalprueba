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
            email = plain_body.strip()

            if not self._is_valid_email(email):
                return True, "Mmm... ese correo no parece válido 🤔. ¿Podés escribirlo de nuevo?"

            nombre = memory.data_buffer or "Sin nombre"

            # 🔧 Crear res.partner (contacto)
            partner = env['res.partner'].sudo().create({
                'name': nombre,
                'phone': phone,
                'email': email,
                'company_type': 'company',
            })

            # ✅ Crear lead vinculado a ese partner
            lead_vals = {
                'name': f"Nuevo cliente WhatsApp: {nombre}",
                'contact_name': nombre,
                'email_from': email,
                'phone': phone,
                'partner_id': partner.id,
                'description': "Nuevo contacto B2B generado automáticamente desde el chatbot de WhatsApp.",
            }

            env['crm.lead'].sudo().create(lead_vals)

            # 🔄 Actualizamos memoria con el partner para futuras referencias
            memory.write({'partner_id': partner.id})
            memory.unlink()

            return True, "¡Gracias! Un asesor se va a contactar con vos para cotizarte ✅"

        return False, ""
