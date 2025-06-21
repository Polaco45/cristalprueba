# models/intent_handlers/new_customer.py

import logging
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

def handle_new_customer(env, record, phone, plain_text, send_text):
    """
    Flujo de datos para clientes nuevos:
    1) Pregunta nombre
    2) Pregunta email
    3) Crea Lead en CRM
    """
    Memory = env['chatbot.whatsapp.memory'].sudo()
    mem = Memory.search([('phone', '=', phone)], limit=1)

    # 1: pedir nombre
    if not mem:
        mem = Memory.create({
            'phone': phone,
            'last_intent': 'esperando_nombre_nuevo_cliente'
        })
        send_text(record, "¡Hola! Soy tu asistente. ¿Me decís tu *nombre* completo para empezar?")
        return True

    # 2: recibo nombre, pido email
    if mem.last_intent == 'esperando_nombre_nuevo_cliente':
        mem.write({
            'last_intent': 'esperando_email_nuevo_cliente',
            'data_buffer': plain_text.strip()
        })
        send_text(record, f"¡Genial, {plain_text.strip()}! Ahora, ¿cuál es tu *correo electrónico*?")
        return True

    # 3: recibo email, creo Lead y cierro memoria
    if mem.last_intent == 'esperando_email_nuevo_cliente':
        nombre = mem.data_buffer
        email  = plain_text.strip()
        try:
            lead = env['crm.lead'].sudo().create({
                'name': f"Nuevo contacto WhatsApp: {nombre}",
                'contact_name': nombre,
                'email_from': email,
                'phone': phone,
                'description': "Lead generado automáticamente desde chatbot B2B WhatsApp."
            })
        except Exception as e:
            _logger.error("Error creando CRM Lead: %s", e)
            send_text(record, "Lo siento, hubo un error creando tu contacto. Por favor intentá más tarde.")
            mem.unlink()
            return True

        send_text(record, "¡Gracias! Un asesor humano te contactará a la brevedad para cotizarte. ✅")
        mem.unlink()
        return True

    return False
