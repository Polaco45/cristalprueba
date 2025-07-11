import logging
import openai
import base64
import re
import json
from odoo.exceptions import UserError
from ...config.config import messages_config, prompts_config, general_config
from .create_order import lookup_product_variants

_logger = logging.getLogger(__name__)

def handle_consulta_producto(env, partner, text):
    """
    Maneja la consulta de un producto, devolviendo un diccionario con el mensaje, 
    el nuevo estado del flujo y el buffer de datos.
    """
    try:
        openai.api_key = env['ir.config_parameter'].sudo().get_param('openai.api_key')
        
        extraction_prompt = prompts_config['product_extraction_system_prompt']
        resp = openai.ChatCompletion.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": extraction_prompt},
                {"role": "user", "content": text}
            ],
            temperature=0,
        )
        query = resp.choices[0].message.content.strip()
        _logger.info(f"🔍 Consulta de producto. Query extraído: '{query}'")

        try:
            variants = lookup_product_variants(env, partner, query)
        except UserError:
            return {'message': messages_config['product_query_not_found'].format(query=query)}

        product_list_str = "\n".join([
            f"{i+1}) *{v['name']}* - ${v['price']:.2f}" 
            for i, v in enumerate(variants)
        ])

        response_prompt = prompts_config['product_query_response_system_prompt']
        final_response_resp = openai.ChatCompletion.create(
            model=general_config['openai']['model'],
            messages=[
                {"role": "system", "content": response_prompt},
                {"role": "user", "content": f"Aquí están las opciones que encontré:\n{product_list_str}"}
            ],
            temperature=0.7,
        )
        
        return {
            'message': final_response_resp.choices[0].message.content,
            'flow_state': 'esperando_seleccion_producto',
            'data_buffer': json.dumps({'products': variants, 'qty': None})
        }

    except Exception as e:
        _logger.error(f"❌ Error en handle_consulta_producto: {e}")
        return {'message': messages_config['error_processing']}

def handle_saludo(env, partner):
    """Genera un saludo dinámico y variado utilizando la IA."""
    partner_name = partner.name if partner and 'WhatsApp:' not in partner.name else 'qué tal'
    try:
        openai.api_key = env['ir.config_parameter'].sudo().get_param('openai.api_key')
        system_prompt = prompts_config['greeting_system_prompt']
        resp = openai.ChatCompletion.create(
            model=general_config['openai']['model'],
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"El nombre del cliente es: {partner_name}"}
            ],
            temperature=0.7,
        )
        return resp.choices[0].message.content
    except Exception as e:
        _logger.error(f"❌ Error al generar saludo con IA: {e}. Usando fallback.")
        fallback_template = messages_config.get('greeting_fallback', "¡Hola! ¿En qué puedo ayudarte?")
        return fallback_template.format(partner_name=partner_name)
    
def handle_agradecimiento_cierre(env, partner, text):
    """Genera una respuesta de cierre dinámica usando IA, basada en el mensaje real del usuario."""
    partner_name = partner.name if partner and 'WhatsApp:' not in partner.name else ''
    try:
        openai.api_key = env['ir.config_parameter'].sudo().get_param('openai.api_key')
        system_prompt = prompts_config['closing_response_system_prompt']
        user_message_for_gpt = f"El cliente, llamado {partner_name}, respondió: '{text}'"
        resp = openai.ChatCompletion.create(
            model=general_config['openai']['model'],
            messages=[
                {"role": "system", "content": system_prompt.format(partner_name=partner_name)},
                {"role": "user", "content": user_message_for_gpt}
            ],
            temperature=0.7,
        )
        return resp.choices[0].message.content
    except Exception as e:
        _logger.error(f"❌ Error al generar respuesta de cierre con IA: {e}. Usando fallback.")
        fallback_template = messages_config.get('closing_fallback', "¡De nada! 😊")
        return fallback_template.format(partner_name=partner_name)

def find_invoice_by_number(env, partner, invoice_number):
    """
    Busca una factura por número.
    Devuelve el objeto de la factura si la encuentra, sino devuelve None.
    """
    _logger.info(f"🧾 Buscando factura que contenga: '{invoice_number}' para {partner.name}")
    
    clean_number = invoice_number.strip()
    if not clean_number:
        return None

    invoice = env['account.move'].sudo().search([
        ('partner_id', '=', partner.id),
        ('name', 'ilike', f'%{clean_number}%'),
        ('state', '=', 'posted'),
        ('move_type', 'in', ['out_invoice', 'out_refund'])
    ], limit=1)

    return invoice if invoice else None

def handle_solicitar_factura(env, partner, text):
    """
    Busca y ofrece directamente las 5 facturas más recientes,
    e inicia el flujo de selección o búsqueda.
    """
    _logger.info(f"🧾 Iniciando flujo de factura para {partner.name}. Ofreciendo recientes.")
    
    invoices = env['account.move'].sudo().search([
        ('partner_id', '=', partner.id),
        ('state', '=', 'posted'),
        ('move_type', 'in', ['out_invoice', 'out_refund'])
    ], order='invoice_date desc, id desc', limit=5)

    if not invoices:
        # Si no hay facturas, pide el número directamente
        return {
            'message': messages_config['no_recent_invoices'],
            'flow_state': 'esperando_numero_factura', # Usamos un flujo separado para este caso
            'data_buffer': ''
        }

    invoice_lines = [f"{i+1}) *{inv.name}* del {inv.invoice_date.strftime('%d/%m/%Y')} - ${inv.amount_total:,.2f}" for i, inv in enumerate(invoices)]
    invoice_list_str = "\n".join(invoice_lines)
    
    return {
        'message': messages_config['invoice_direct_offer_or_search'].format(invoices=invoice_list_str),
        'flow_state': 'esperando_seleccion_o_numero_factura', # Nuevo estado de flujo
        'data_buffer': json.dumps({'invoice_ids': invoices.ids})
    }
        
def handle_faq_con_ai(env, partner, user_text, conv_history):
    """
    Genera dinámicamente la respuesta a preguntas frecuentes usando IA.
    """
    _logger.info(f"🧠 Entrando en handle_faq_con_ai para el partner: {partner.name}. Pregunta: '{user_text}'")
    try:
        company_name = "Química Cristal"
        address = "San Martín 2350"
        schedule = "Lunes a Viernes de 8:30 a 12:30 y 15:30 a 19:30, Sábados de 9:00 a 13:00"
        product_examples = "lavandinas, detergentes, escobas, desengrasantes, y mucho más"
        chatbot_capabilities = "puedo ayudarte a crear pedidos, consultar productos, solicitar facturas, y darte información sobre nuestros horarios y dirección."

        system_prompt_template = prompts_config['faq_system_prompt']
        
        system_prompt = system_prompt_template.format(
            company_name=company_name,
            address=address,
            schedule=schedule,
            product_examples=product_examples,
            chatbot_capabilities=chatbot_capabilities
        )

        # Construye la lista de mensajes, comenzando con el prompt del sistema
        messages = [{"role": "system", "content": system_prompt}]
        # Agrega el historial de la conversación
        messages.extend(conv_history)

        _logger.info(f"📝 Mensajes para FAQ con IA: {messages}")

        api_key = env['ir.config_parameter'].sudo().get_param('openai.api_key')
        if not api_key:
            _logger.error("La API key de OpenAI no está configurada.")
            return messages_config['error_processing']

        openai.api_key = api_key
        result = openai.ChatCompletion.create(
            model="gpt-4o-mini",
            messages=messages,
            temperature=0.5,
            max_tokens=200
        )
        
        response_text = result.choices[0].message.content.strip()
        _logger.info(f"✅ Respuesta de FAQ con IA generada exitosamente: '{response_text}'")
        return response_text

    except Exception as e:
        _logger.error("❌ Error al generar respuesta de FAQ con IA: %s", e, exc_info=True)
        return messages_config['error_processing']

def handle_respuesta_faq(intent, partner, text, conv_history):
    """
    Todas las FAQs pasan por handle_faq_con_ai.
    """
    _logger.info(f"Redirecting informational query to AI handler. User: {partner.name}, Text: '{text}'")
    env = intent
    return handle_faq_con_ai(env, partner, text, conv_history)