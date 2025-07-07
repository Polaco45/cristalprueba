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
            variants = lookup_product_variants(env, partner, query, limit=10)
        except UserError:
            return {'message': messages_config['product_query_not_found'].format(query=query)}

        top_variants = variants[:3]
        product_list_str = "\n".join([
            f"{i+1}) *{v['name']}* - ${v['price']:.2f}" 
            for i, v in enumerate(top_variants)
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
            'data_buffer': json.dumps({'products': top_variants, 'qty': None})
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
    
    clean_number = re.sub(r'[^0-9]', '', invoice_number)
    if not clean_number:
        return None

    invoice = env['account.move'].sudo().search([
        ('partner_id', '=', partner.id),
        ('name', 'ilike', f'%{clean_number}%'),
        ('state', '=', 'posted'),
        ('move_type', 'in', ['out_invoice', 'out_refund'])
    ], limit=1)

    return invoice if invoice else None

def offer_recent_invoices(env, partner):
    """
    Busca y ofrece las 5 facturas más recientes.
    """
    _logger.info(f"🧾 No se encontró la factura. Buscando las últimas 5 para {partner.name}.")
    
    invoices = env['account.move'].sudo().search([
        ('partner_id', '=', partner.id),
        ('state', '=', 'posted'),
        ('move_type', 'in', ['out_invoice', 'out_refund'])
    ], order='invoice_date desc, id desc', limit=5)

    if not invoices:
        return {'message': messages_config['no_recent_invoices']}

    invoice_lines = [f"{i+1}) *{inv.name}* del {inv.invoice_date.strftime('%d/%m/%Y')} - ${inv.amount_total:,.2f}" for i, inv in enumerate(invoices)]
    invoice_list_str = "\n".join(invoice_lines)
    
    return {
        'message': messages_config['offer_recent_invoices'].format(invoices=invoice_list_str),
        'flow_state': 'esperando_seleccion_factura',
        'data_buffer': json.dumps({'invoice_ids': invoices.ids})
    }

def handle_solicitar_factura(env, partner, text):
    """
    Inicia el flujo de solicitud de factura.
    """
    return {
        'message': messages_config['ask_for_invoice_number'],
        'flow_state': 'esperando_numero_factura',
        'data_buffer': ''
    }
        
def handle_faq_con_ai(partner, user_text):
    """
    Genera dinámicamente la respuesta a preguntas frecuentes.
    """
    try:
        company = partner.env['res.company'].sudo().search([], limit=1)
        company_name = company.name or "nuestra empresa"
        address = company.partner_id.contact_address or "su sede principal"
        schedule = getattr(company, 'hour_schedule', None) or "Nuestro horario es de lunes a viernes de 9 a 18 hs."
        categories = partner.env['product.category'].sudo().search([], limit=5).mapped('name')
        product_list = ", ".join(categories) if categories else "diversos productos de limpieza"

        prompt = (
            f"Eres un asistente experto de '{company_name}'.\n"
            f"Info: Dirección: {address}. Horario: {schedule}. Productos: {product_list}.\n"
            f"Cliente: \"{user_text}\"\n"
            f"Generá una respuesta amable y completa."
        )

        api_key = partner.env['ir.config_parameter'].sudo().get_param('openai.api_key')
        if not api_key:
            _logger.error("La API key de OpenAI no está configurada.")
            return "Lo siento, no pude procesar tu mensaje en este momento."

        openai.api_key = api_key
        result = openai.ChatCompletion.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "Eres un asistente muy respetuoso y útil."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=250
        )
        return result.choices[0].message.content.strip()

    except Exception as e:
        _logger.error("Error al generar respuesta con AI: %s", e)
        return "Perdón, hubo un problema generando la respuesta."

def handle_respuesta_faq(intent, partner, text):
    """
    Todas las FAQs pasan por handle_faq_con_ai.
    """
    return handle_faq_con_ai(partner, text)