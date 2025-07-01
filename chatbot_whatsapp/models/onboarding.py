from odoo import models, api
import re
import logging
from ..utils.utils import is_cotizado

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
        # En onboarding, la memoria se busca por 'phone' porque el partner puede no existir aún
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

            # CORRECCIÓN: Usar 'flow_state' en lugar de 'last_intent'
            flow_state = 'esperando_nombre_nuevo_cliente' if 'nombre' in missing else (
                'esperando_email_nuevo_cliente' if 'email' in missing else 'esperando_tipo_cliente'
            )

            if 'tag' not in missing:
                flow_state = 'finalizado'

            memory = memory_model.create({
                'phone': phone,
                'partner_id': partner.id if partner else False,
                'flow_state': flow_state,
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

        # CORRECCIÓN: Leer y escribir en 'flow_state'
        if memory.flow_state == 'esperando_nombre_nuevo_cliente':
            nombre = plain_body.strip()
            memory.write({
                'flow_state': 'esperando_email_nuevo_cliente',
                'data_buffer': nombre,
            })
            if memory.partner_id:
                memory.partner_id.write({'name': nombre})
            return True, "Gracias 😊. ¿Cuál es tu *correo electrónico*?"

        # CORRECCIÓN: Leer y escribir en 'flow_state'
        if memory.flow_state == 'esperando_email_nuevo_cliente':
            email = plain_body.strip()
            if not self._is_valid_email(email):
                return True, "Mmm... ese correo no parece válido 🤔. ¿Podés escribirlo de nuevo?"

            nombre = memory.data_buffer.strip()
            
            memory.write({
                'flow_state': 'esperando_tipo_cliente',
                'data_buffer': f"{nombre}|||{email}",
            })
            if memory.partner_id:
                memory.partner_id.write({'email': email})

            partner = memory.partner_id
            if partner and partner.category_id:
                # Si ya tiene categoría, el onboarding para este dato ha terminado.
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

        # CORRECCIÓN: Leer y escribir en 'flow_state'
        if memory.flow_state == 'esperando_tipo_cliente':
            tipo_etiqueta = self._parse_cliente_tag(plain_body)
            if not tipo_etiqueta:
                # Si ya está cotizado y se equivoca, no insistimos.
                if is_cotizado(memory.partner_id):
                    return False, ""
                else:
                    return True, (
                        "No entendí esa opción 🤔. Por favor respondé con:\n"
                        "1 - Consumidor final\n"
                        "2 - Institución / Empresa\n"
                        "3 - Mayorista"
                    )

            data_parts = memory.data_buffer.split("|||")
            if len(data_parts) != 2 or not data_parts[1].strip():
                memory.write({'flow_state': 'esperando_email_nuevo_cliente'})
                return True, "Me faltó tu correo electrónico. ¿Podés escribirme tu *email* por favor?"

            nombre, email = data_parts
            partner = memory.partner_id

            partner_vals = {
                'name': nombre.strip(),
                'phone': phone,
                'email': email.strip(),
                'company_type': 'company',
            }
            if not partner:
                partner = env['res.partner'].sudo().create(partner_vals)
            else:
                partner.write(partner_vals)

            tag = env['res.partner.category'].sudo().search([('name', '=', tipo_etiqueta)], limit=1)
            if not tag:
                tag = env['res.partner.category'].sudo().create({'name': tipo_etiqueta})
            partner.category_id = [(6, 0, [tag.id])] # Reemplaza las etiquetas existentes

            # Lógica de CRM
            if not is_cotizado(partner):
                lead_tag = env['crm.tag'].sudo().search([('name', '=', tipo_etiqueta)], limit=1)
                if not lead_tag:
                    lead_tag = env['crm.tag'].sudo().create({'name': tipo_etiqueta})
                
                lead = env['crm.lead'].sudo().create({
                    'name': f"Nuevo cliente WhatsApp: {nombre.strip()}",
                    'contact_name': nombre.strip(),
                    'email_from': email.strip(),
                    'phone': phone,
                    'partner_id': partner.id,
                    'tag_ids': [(6, 0, [lead_tag.id])],
                })
                
                activity_type = env['mail.activity.type'].sudo().search([('name', 'ilike', 'Iniciativa de Venta')], limit=1)
                if activity_type:
                    env['mail.activity'].sudo().create({
                        'res_model_id': env['ir.model']._get_id('crm.lead'),
                        'res_id': lead.id,
                        'activity_type_id': activity_type.id,
                        'summary': 'Seguimiento nuevo contacto',
                        'note': 'Contactar al cliente para cotizarlo.',
                        'user_id': partner.user_id.id or env.user.id,
                    })
            
            memory.unlink()

            if not is_cotizado(partner):
                return True, "¡Ahora sí! Ya tenemos todo 🙌. Un asesor te va a contactar para cotizarte 😊"
            else:
                return True, "¡Ahora sí! Ya tenemos todo 🙌"

        return False, ""