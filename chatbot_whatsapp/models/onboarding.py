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
        memory = memory_model.search([('phone', '=', phone)], limit=1)
        partner = env['res.partner'].sudo().search([
            '|', ('phone', 'ilike', phone), ('mobile', 'ilike', phone)
        ], limit=1)

        def check_missing_data(p):
            missing = []
            # Se considera el nombre faltante si no existe o es el nombre por defecto.
            if not p or not p.name or "WhatsApp:" in p.name:
                missing.append('nombre')
            if not p or not p.email:
                missing.append('email')
            if not p or not p.category_id:
                missing.append('tag')
            return missing

        # Si no hay memoria, es la primera interacción.
        if not memory:
            missing = check_missing_data(partner)
            
            if not missing:
                return False, ""

            flow_state = 'esperando_nombre_nuevo_cliente' if 'nombre' in missing else (
                'esperando_email_nuevo_cliente' if 'email' in missing else 'esperando_tipo_cliente'
            )

            # Usamos el partner existente si hay, sino lo dejamos para crearlo después.
            memory = memory_model.create({
                'phone': phone,
                'partner_id': partner.id if partner else False,
                'flow_state': flow_state,
                'data_buffer': partner.name if partner and "WhatsApp:" not in partner.name else '',
            })
            
            # Preguntar por el primer dato que falta.
            if 'nombre' in missing:
                return True, "¡Hola! Para poder ayudarte, ¿me decís tu *nombre* completo?"
            elif 'email' in missing:
                return True, f"¡Hola {partner.name}! Para continuar, ¿cuál es tu *correo electrónico*?"
            elif 'tag' in missing:
                return True, (
                    "¡Genial! Una última pregunta 😊\n"
                    "¿Qué tipo de cliente sos?\n"
                    "1 - Consumidor final\n"
                    "2 - Institución / Empresa\n"
                    "3 - Mayorista"
                )

        # Si ya hay una memoria, continuamos el flujo.
        flow = memory.flow_state
        
        if flow == 'esperando_nombre_nuevo_cliente':
            nombre = plain_body.strip()
            memory.write({
                'flow_state': 'esperando_email_nuevo_cliente',
                'data_buffer': nombre,
            })
            if memory.partner_id:
                memory.partner_id.write({'name': nombre})
            return True, "Gracias 😊. ¿Cuál es tu *correo electrónico*?"

        if flow == 'esperando_email_nuevo_cliente':
            email = plain_body.strip()
            if not self._is_valid_email(email):
                return True, "Mmm... ese correo no parece válido 🤔. ¿Podés escribirlo de nuevo?"

            nombre = memory.data_buffer or (partner.name if partner else '')
            memory.write({
                'flow_state': 'esperando_tipo_cliente',
                'data_buffer': f"{nombre}|||{email}",
            })
            if memory.partner_id:
                memory.partner_id.write({'email': email})

            if memory.partner_id and memory.partner_id.category_id:
                memory.unlink()
                return True, "¡Perfecto! Ya actualizamos tus datos. ¿En qué te puedo ayudar?"

            return True, (
                "¡Genial! Una última pregunta 😊\n"
                "¿Qué tipo de cliente sos?\n"
                "1 - Consumidor final\n"
                "2 - Institución / Empresa\n"
                "3 - Mayorista"
            )

        if flow == 'esperando_tipo_cliente':
            tipo_etiqueta = self._parse_cliente_tag(plain_body)
            if not tipo_etiqueta:
                return True, (
                    "No entendí esa opción 🤔. Por favor respondé con:\n"
                    "1, 2 o 3."
                )

            data_parts = (memory.data_buffer or "|||").split("|||")
            nombre, email = (data_parts[0], data_parts[1]) if len(data_parts) == 2 else ('', '')

            partner_vals = {'name': nombre, 'email': email, 'phone': phone, 'mobile': phone}
            if not partner:
                partner = env['res.partner'].sudo().create(partner_vals)
                memory.write({'partner_id': partner.id})
            else:
                partner.write(partner_vals)

            tag = env['res.partner.category'].sudo().search([('name', '=', tipo_etiqueta)], limit=1)
            if not tag:
                tag = env['res.partner.category'].sudo().create({'name': tipo_etiqueta})
            partner.category_id = [(6, 0, [tag.id])]
            
            if "Consumidor Final" not in tipo_etiqueta:
                lead_tag = env['crm.tag'].sudo().search([('name', '=', tipo_etiqueta)], limit=1)
                if not lead_tag:
                    lead_tag = env['crm.tag'].sudo().create({'name': tipo_etiqueta})
                
                # Crear oportunidad en CRM si no es consumidor final
                lead_vals = {
                    'name': f"Nuevo cliente WhatsApp: {nombre}",
                    'partner_id': partner.id,
                    'contact_name': nombre,
                    'email_from': email,
                    'phone': phone,
                    'tag_ids': [(6, 0, [lead_tag.id])],
                }
                lead = env['crm.lead'].sudo().create(lead_vals)
                
                # Crear actividad para el equipo de ventas
                activity_type = env['mail.activity.type'].sudo().search([('name', 'ilike', 'Iniciativa de Venta')], limit=1)
                if activity_type:
                    env['mail.activity'].sudo().create({
                        'res_model_id': env['ir.model']._get_id('crm.lead'),
                        'res_id': lead.id,
                        'activity_type_id': activity_type.id,
                        'summary': 'Seguimiento nuevo contacto WhatsApp',
                        'note': f'Contactar al cliente {nombre} para cotizarlo.',
                        'user_id': partner.user_id.id or env.user.id,
                    })
            
            memory.unlink()
            if not is_cotizado(partner):
                return True, "¡Ahora sí! Ya tenemos todo 🙌. Un asesor te va a contactar para cotizarte 😊"
            else:
                return True, "¡Ahora sí! Ya tenemos todo 🙌. ¿En qué te puedo ayudar?"

        return False, ""