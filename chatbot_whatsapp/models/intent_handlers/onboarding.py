from odoo import models, api
import re
import logging
from ...utils.utils import is_cotizado

_logger = logging.getLogger(__name__)

class WhatsAppOnboardingHandler(models.AbstractModel):
    _name = 'chatbot.whatsapp.onboarding_handler'
    _description = "Onboarding progresivo de cliente por WhatsApp"

    def _is_valid_email(self, email):
        pattern = r"^[\w\.-]+@[\w\.-]+\.\w{2,}$"
        return re.match(pattern, email)

    def _parse_cliente_tag(self, texto_usuario):
        OPCIONES = {
            '1': "Tipo de Cliente / Consumidor Final",
            'consumidor final': "Tipo de Cliente / Consumidor Final",
            '2': "Tipo de Cliente / EMPRESA",
            'institucion': "Tipo de Cliente / EMPRESA",
            'empresa': "Tipo de Cliente / EMPRESA",
            '2 - institución': "Tipo de Cliente / EMPRESA",
            '3': "Tipo de Cliente / Mayorista",
            'mayorista': "Tipo de Cliente / Mayorista",
        }
        return OPCIONES.get(texto_usuario.strip().lower())

    @api.model
    def process_onboarding_flow(self, env, record, phone, plain_body, memory_model):
        memory = memory_model.search([('phone', '=', phone)], limit=1)
        partner = env['res.partner'].sudo().search([
            '|', ('phone', 'ilike', phone), ('mobile', 'ilike', phone)
        ], limit=1)

        def check_missing_data(p):
            missing = []
            if not p or not p.name:
                missing.append('nombre')
            if not p or not p.email:
                missing.append('email')
            if not p or not p.category_id:
                missing.append('tag')
            return missing

        # Primera vez: determinamos qué falta y creamos la memoria
        if not memory:
            missing = check_missing_data(partner)
            nombre = partner.name or ""
            email = partner.email or ""
            buffer = f"{nombre}|||{email}" if email else nombre

            memory = memory_model.create({
                'phone': phone,
                'partner_id': partner.id if partner else False,
                'last_intent': 'esperando_nombre_nuevo_cliente' if 'nombre' in missing else (
                    'esperando_email_nuevo_cliente' if 'email' in missing else 'esperando_tipo_cliente'
                ),
                'data_buffer': buffer,
            })

            if 'nombre' in missing:
                return True, "¡Hola! Para poder ayudarte, ¿me decís tu *nombre* completo?"
            elif 'email' in missing:
                # Personalizamos el prompt del email si ya está cotizado
                if is_cotizado(partner):
                    return True, "Antes de continuar, necesito tu *correo electrónico* 📧"
                else:
                    return True, "Gracias 😊. ¿Cuál es tu *correo electrónico*?"
            elif 'tag' in missing:
                return True, (
                    "Una última pregunta 😊\n"
                    "¿Qué tipo de cliente sos?\n"
                    "1 - Consumidor final\n"
                    "2 - Institución / Empresa\n"
                    "3 - Mayorista\n"
                    "Podés responder con el número o el texto."
                )
            return False, ""

        # Caso: pedimos nombre primero
        if memory.last_intent == 'esperando_nombre_nuevo_cliente':
            nombre = plain_body.strip()
            memory.write({
                'last_intent': 'esperando_email_nuevo_cliente',
                'data_buffer': nombre,
            })
            if memory.partner_id:
                memory.partner_id.write({'name': nombre})
            # Aquí también personalizamos el prompt del email
            if is_cotizado(partner):
                return True, "Primero necesito tu *correo electrónico* 📧"
            else:
                return True, "Gracias 😊. ¿Cuál es tu *correo electrónico*?"

        # Caso: capturamos email
        if memory.last_intent == 'esperando_email_nuevo_cliente':
            email = plain_body.strip()
            if not self._is_valid_email(email):
                return True, "Mmm... ese correo no parece válido 🤔. ¿Podés escribirlo de nuevo?"

            nombre = memory.data_buffer.strip()
            tipo_cliente_cache = None
            if "|||" in nombre:
                partes = nombre.split("|||")
                if len(partes) == 2:
                    nombre = partes[0].strip()
                    posible_tag = self._parse_cliente_tag(partes[1].strip())
                    if posible_tag:
                        tipo_cliente_cache = posible_tag

            memory.write({
                'last_intent': 'esperando_tipo_cliente',
                'data_buffer': f"{nombre}|||{email}",
            })
            if memory.partner_id:
                memory.partner_id.write({'email': email})

            partner = memory.partner_id
            if partner and partner.category_id:
                # Ya tiene tag: evaluamos cotización
                esta_cotizado = is_cotizado(partner)
                # Quitamos default pricelist para evitar confusiones
                partner.write({'property_product_pricelist': False})

                if not esta_cotizado:
                    env['crm.lead'].sudo().create({
                        'name': f"Nuevo cliente WhatsApp: {nombre.strip()}",
                        'contact_name': nombre.strip(),
                        'email_from': email.strip(),
                        'phone': phone,
                        'partner_id': partner.id,
                        'description': "Nuevo contacto B2B generado automáticamente desde el chatbot de WhatsApp.",
                    })

                memory.unlink()
                if not esta_cotizado:
                    return True, "¡Ahora sí! Ya tenemos todo 🙌. Un asesor te va a contactar para cotizarte 😊"
                else:
                    return True, "¡Ahora sí! Ya tenemos todo 🙌"

            # Si falta tag, seguimos pidiendo categoría
            return True, (
                "Una última pregunta 😊\n"
                "¿Qué tipo de cliente sos?\n"
                "1 - Consumidor final\n"
                "2 - Institución / Empresa\n"
                "3 - Mayorista\n"
                "Podés responder con el número o el texto."
            )

        # Caso: capturamos tipo de cliente
        if memory.last_intent == 'esperando_tipo_cliente':
            tipo_etiqueta = self._parse_cliente_tag(plain_body)
            if not tipo_etiqueta:
                # Si ya está cotizado usamos un tono más suave
                if is_cotizado(memory.partner_id):
                    return True, (
                        "Antes de seguir, necesito saber qué *tipo de cliente* sos 😊.\n"
                        "Respondé con:\n"
                        "1 - Consumidor final\n"
                        "2 - Institución / Empresa\n"
                        "3 - Mayorista"
                    )
                # Si no está cotizado, mensaje más estándar
                return True, (
                    "No entendí esa opción 🤔. Por favor respondé con:\n"
                    "1 - Consumidor final\n"
                    "2 - Institución / Empresa\n"
                    "3 - Mayorista"
                )

            data_parts = memory.data_buffer.split("|||")
            if len(data_parts) != 2 or not data_parts[1].strip():
                memory.write({'last_intent': 'esperando_email_nuevo_cliente'})
                # Mensaje personalizado si ya cotizado
                if is_cotizado(memory.partner_id):
                    return True, "Primero necesito tu *correo electrónico* 📧"
                else:
                    return True, "Me faltó tu correo electrónico. ¿Podés escribirme tu *email* por favor?"

            nombre, email = data_parts
            partner = memory.partner_id

            # Creamos o actualizamos partner
            if not partner:
                partner = env['res.partner'].sudo().create({
                    'name': nombre.strip(),
                    'phone': phone,
                    'email': email.strip(),
                    'company_type': 'company',
                })
            else:
                partner.write({
                    'name': nombre.strip(),
                    'email': email.strip(),
                    'company_type': 'company',
                })

            # Asignamos la categoría
            tag = env['res.partner.category'].sudo().search([('name', '=', tipo_etiqueta)], limit=1)
            if not tag:
                tag = env['res.partner.category'].sudo().create({'name': tipo_etiqueta})
            partner.category_id = [(4, tag.id)]

            # Creamos lead si es cliente nuevo
            if not is_cotizado(partner):
                env['crm.lead'].sudo().create({
                    'name': f"Nuevo cliente WhatsApp: {nombre.strip()}",
                    'contact_name': nombre.strip(),
                    'email_from': email.strip(),
                    'phone': phone,
                    'partner_id': partner.id,
                    'description': "Nuevo contacto B2B generado automáticamente desde el chatbot de WhatsApp.",
                    'tag_ids': [(6, 0, [tag.id])],
                })

            # Limpiamos pricelist por defecto y memoria
            partner.write({'property_product_pricelist': False})
            memory.unlink()

            if not is_cotizado(partner):
                return True, "¡Ahora sí! Ya tenemos todo 🙌. Un asesor te va a contactar para cotizarte 😊"
            else:
                return True, "¡Ahora sí! Ya tenemos todo 🙌"

        return False, ""
