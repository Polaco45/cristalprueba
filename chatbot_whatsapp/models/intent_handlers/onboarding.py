# onboarding.py
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

        if not memory:
            missing = check_missing_data(partner)
            nombre = partner.name or ""
            email = partner.email or ""
            buffer = f"{nombre}|||{email}" if email else nombre

            if not missing:
                return False, ""

            last_intent = 'esperando_nombre_nuevo_cliente' if 'nombre' in missing else (
                'esperando_email_nuevo_cliente' if 'email' in missing else 'esperando_tipo_cliente'
            )

            # Si ya tiene tag, evitamos preguntar tipo de cliente
            if 'tag' not in missing:
                last_intent = 'finalizado'

            memory = memory_model.create({
                'phone': phone,
                'partner_id': partner.id if partner else False,
                'last_intent': last_intent,
                'data_buffer': buffer,
            })

            if 'nombre' in missing:
                return True, "¡Hola! Para poder ayudarte, ¿me decís tu *nombre* completo?"
            elif 'email' in missing:
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

        if memory.last_intent == 'esperando_nombre_nuevo_cliente':
            nombre = plain_body.strip()
            memory.write({
                'last_intent': 'esperando_email_nuevo_cliente',
                'data_buffer': nombre,
            })
            if memory.partner_id:
                memory.partner_id.write({'name': nombre})
            return True, "Gracias 😊. ¿Cuál es tu *correo electrónico*?"

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
                # Ya tiene tipo de cliente
                partner.write({'property_product_pricelist': False})

                # Aquí diferenciamos creación de lead según cotizado
                if not is_cotizado(partner):
                    env['crm.lead'].sudo().create({
                        'name': f"Nuevo cliente Whatsapp: {nombre.strip()}",
                        'contact_name': nombre.strip(),
                        'email_from': email.strip(),
                        'phone': phone,
                        'partner_id': partner.id,
                        'description': "Nuevo contacto B2B generado automáticamente desde el chatbot de WhatsApp.",
                    })

                memory.unlink()
                if not is_cotizado(partner):
                    return True, "¡Ahora sí! Ya tenemos todo 🙌. Un asesor te va a contactar para cotizarte 😊"
                else:
                    return True, "¡Ahora sí! Ya tenemos todo 🙌"

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
                if is_cotizado(memory.partner_id):
                    return False, ""  # No preguntar si ya está cotizado
                else:
                    return True, (
                        "No entendí esa opción 🤔. Por favor respondé con:\n"
                        "1 - Consumidor final\n"
                        "2 - Institución / Empresa\n"
                        "3 - Mayorista"
                    )

            data_parts = memory.data_buffer.split("|||")
            if len(data_parts) != 2 or not data_parts[1].strip():
                memory.write({'last_intent': 'esperando_email_nuevo_cliente'})
                return True, "Me faltó tu correo electrónico. ¿Podés escribirme tu *email* por favor?"

            nombre, email = data_parts
            partner = memory.partner_id

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

            tag = env['res.partner.category'].sudo().search([('name', '=', tipo_etiqueta)], limit=1)
            if not tag:
                tag = env['res.partner.category'].sudo().create({'name': tipo_etiqueta})
            partner.category_id = [(4, tag.id)]

            lead_tag = env['crm.tag'].sudo().search([('name', '=', tipo_etiqueta)], limit=1)
            if not lead_tag:
                lead_tag = env['crm.tag'].sudo().create({'name': tipo_etiqueta})

            # Crear lead CRM siempre, con diferencia en el nombre según cotizado
            if not is_cotizado(partner):
                env['crm.lead'].sudo().create({
                    'name': f"Nuevo cliente Whatsapp: {nombre.strip()}",
                    'contact_name': nombre.strip(),
                    'email_from': email.strip(),
                    'phone': phone,
                    'partner_id': partner.id,
                    'description': "Nuevo contacto B2B generado automáticamente desde el chatbot de WhatsApp.",
                    'tag_ids': [(6, 0, [lead_tag.id])],
                })

            partner.write({'property_product_pricelist': False})
            memory.unlink()

            if not is_cotizado(partner):
                return True, "¡Ahora sí! Ya tenemos todo 🙌. Un asesor te va a contactar para cotizarte 😊"
            else:
                return True, "¡Ahora sí! Ya tenemos todo 🙌"

        return False, ""
