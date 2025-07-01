from odoo import models, api
import re
import logging
from ..utils.utils import is_cotizado
from ..config.config import messages_config

_logger = logging.getLogger(__name__)

class WhatsAppOnboardingHandler(models.AbstractModel):
    _name = 'chatbot.whatsapp.onboarding_handler'
    _description = "Onboarding progresivo y forzado de cliente por WhatsApp"

    def _is_valid_email(self, email):
        pattern = r"^[\w\.-]+@[\w\.-]+\.\w+$"
        return re.match(pattern, email)

    def _parse_cliente_tag(self, texto_usuario):
        OPCIONES = {
            '1': "Tipo de Cliente / Consumidor Final", 'consumidor final': "Tipo de Cliente / Consumidor Final",
            '2': "Tipo de Cliente / EMPRESA", 'institucion': "Tipo de Cliente / EMPRESA", 'empresa': "Tipo de Cliente / EMPRESA",
            '3': "Tipo de Cliente / Mayorista", 'mayorista': "Tipo de Cliente / Mayorista",
        }
        return OPCIONES.get(texto_usuario.strip().lower())

    def _check_missing_data(self, partner):
        missing = []
        if not partner or not partner.name or 'WhatsApp:' in partner.name:
            missing.append('nombre')
        if not partner or not partner.email:
            missing.append('email')
        if not partner or not partner.category_id:
            missing.append('tag')
        return missing

    @api.model
    def process_onboarding_flow(self, env, record, phone, plain_body, memory_model):
        partner = env['res.partner'].sudo().search([
            '|', ('phone', 'ilike', phone), ('mobile', 'ilike', phone)
        ], limit=1)
        
        if not partner:
            partner = env['res.partner'].sudo().create({'name': f"WhatsApp: {phone}", 'phone': phone, 'mobile': phone})
        
        memory = memory_model.search([('partner_id', '=', partner.id)], limit=1)
        if not memory:
            memory = memory_model.create({'partner_id': partner.id})

        # --- Lógica de Onboarding Refactorizada ---

        # 1. Si estamos en un flujo de onboarding, lo procesamos.
        current_flow = memory.flow_state
        if current_flow and 'esperando_' in current_flow:
            if current_flow == 'esperando_nombre_nuevo_cliente':
                partner.write({'name': plain_body.strip()})
            
            elif current_flow == 'esperando_email_nuevo_cliente':
                if not self._is_valid_email(plain_body.strip()):
                    return True, "Ese correo no parece válido 🤔. ¿Podrías escribirlo de nuevo?"
                partner.write({'email': plain_body.strip()})
            
            elif current_flow == 'esperando_tipo_cliente':
                tag_name = self._parse_cliente_tag(plain_body)
                if not tag_name:
                    return True, "Opción no válida. Por favor, responde con 1, 2 o 3."
                
                tag = env['res.partner.category'].sudo().search([('name', '=', tag_name)], limit=1) or env['res.partner.category'].sudo().create({'name': tag_name})
                partner.write({'category_id': [(6, 0, [tag.id])]})
                
                if "Consumidor Final" not in tag_name:
                    self._create_crm_lead(env, partner)
            
            # Limpiamos el estado de flujo para que la siguiente verificación se haga desde cero.
            memory.write({'flow_state': False})
            
        # 2. Re-verificamos si falta algo, AHORA.
        missing_data = self._check_missing_data(partner)
        
        # 3. Si falta algo, forzamos el siguiente paso.
        if missing_data:
            next_step = missing_data[0]
            if next_step == 'nombre':
                memory.write({'flow_state': 'esperando_nombre_nuevo_cliente'})
                return True, "¡Hola! Para poder ayudarte, ¿me decís tu *nombre* completo?"
            elif next_step == 'email':
                memory.write({'flow_state': 'esperando_email_nuevo_cliente'})
                return True, f"Gracias, {partner.name.split()[0]} 😊. ¿Cuál es tu *correo electrónico*?"
            elif next_step == 'tag':
                memory.write({'flow_state': 'esperando_tipo_cliente'})
                return True, (
                    "¡Genial! Una última pregunta 😊\n"
                    "¿Qué tipo de cliente sos?\n"
                    "1 - Consumidor final\n"
                    "2 - Institución / Empresa\n"
                    "3 - Mayorista"
                )
        
        # 4. Si NO falta nada y ESTÁBAMOS en un flujo de onboarding, significa que acabamos de terminar.
        if not missing_data and current_flow and 'esperando_' in current_flow:
            memory.unlink() # Se completó, borramos la memoria para evitar estados residuales.
            return True, "¡Ahora sí, gracias! Ya tenemos todos tus datos. ¿En qué te puedo ayudar?"

        # Si no falta nada y no estábamos en onboarding, dejamos que el bot principal continúe.
        return False, ""

    def _create_crm_lead(self, env, partner):
        """Crea una oportunidad (lead) en el CRM para el partner."""
        # Prevenir la creación de leads duplicados para el mismo partner
        if env['crm.lead'].sudo().search_count([('partner_id', '=', partner.id)]):
            _logger.info(f"El partner '{partner.name}' ya tiene una oportunidad en el CRM.")
            return

        lead_vals = {
            'name': f"Nuevo cliente WhatsApp: {partner.name}", 'partner_id': partner.id,
            'contact_name': partner.name, 'email_from': partner.email, 'phone': partner.phone,
        }
        if partner.category_id:
            tag_name = partner.category_id[0].name
            crm_tag = env['crm.tag'].sudo().search([('name', '=', tag_name)], limit=1) or env['crm.tag'].sudo().create({'name': tag_name})
            lead_vals['tag_ids'] = [(6, 0, [crm_tag.id])]

        lead = env['crm.lead'].sudo().create(lead_vals)
        
        activity_type = env['mail.activity.type'].sudo().search([('name', 'ilike', 'Iniciativa de Venta')], limit=1)
        if activity_type:
            env['mail.activity'].sudo().create({
                'res_model_id': env.ref('crm.model_crm_lead').id, 'res_id': lead.id,
                'activity_type_id': activity_type.id, 'summary': 'Seguimiento nuevo contacto WhatsApp',
                'note': f'Contactar al cliente {partner.name} para cotizarlo.',
                'user_id': partner.user_id.id or env.user.id,
            })
        _logger.info(f"✨ Creada oportunidad '{lead.name}' para el partner '{partner.name}'.")