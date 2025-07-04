import re
import logging
import openai
import base64
from odoo import _
from odoo.exceptions import UserError
from ...config.config import messages_config, prompts_config, general_config


_logger = logging.getLogger(__name__)

def handle_saludo(env, partner):
    """
    Genera un saludo dinámico y variado utilizando la IA.
    Si la llamada a la IA falla, utiliza un mensaje de fallback.
    """
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
            temperature=0.7, # Usamos una temperatura mayor a 0 para obtener variedad
        )
        return resp.choices[0].message.content

    except Exception as e:
        _logger.error(f"❌ Error al generar saludo con IA: {e}. Usando fallback.")
        # En caso de error, se envía el saludo hardcodeado para no fallar.
        fallback_template = messages_config.get('greeting_fallback', "¡Hola! ¿En qué puedo ayudarte?")
        return fallback_template.format(partner_name=partner_name)

def handle_solicitar_factura(partner, text):
    """
    1) Busca en el texto un número de factura (al menos 4 dígitos).
    2) Busca el registro account.move correspondiente.
    3) Si lo encuentra, genera el PDF de esa factura y lo codifica en base64.
    4) Devuelve un dict con:
         - 'message': texto para enviar por WhatsApp.
         - 'pdf_base64': el contenido en base64 del PDF (si existe).
    """
    # 1) Extraer número de factura
    number_match = re.search(r'\d{4,}', text)
    if not number_match:
        return {
            'message': "¿Me podrías dar el número de factura que necesitás?",
            'pdf_base64': None,
        }

    # 2) Buscar invoice en Odoo
    invoice = partner.env['account.move'].sudo().search([
        ('partner_id', '=', partner.id),
        ('name', 'ilike', number_match.group())
    ], limit=1)

    if not invoice:
        return {
            'message': "No encontré esa factura 🧾",
            'pdf_base64': None,
        }

    try:
        # 3) Generar el PDF de la factura
        report_action = partner.env.ref('account.account_invoices')
        pdf_content, content_type = report_action.sudo()._render_qweb_pdf([invoice.id])
        pdf_base64 = base64.b64encode(pdf_content).decode('utf-8')

        # 4) Construir el mensaje
        mensaje = _("Aquí está tu factura *%s*. Te la envío en formato PDF adjunto.") % invoice.name
        return {
            'message': mensaje,
            'pdf_base64': pdf_base64,
        }

    except Exception as e:
        _logger.error("Error generando PDF de factura %s: %s", invoice.name, e)
        return {
            'message': "Hubo un error al generar la factura. Intentá de nuevo más tarde.",
            'pdf_base64': None,
        }

def handle_faq_con_ai(partner, user_text):
    """
    Genera dinámicamente la respuesta a preguntas frecuentes
    (horarios, productos, ubicación, etc.) usando OpenAI.
    """
    try:
        # 1) Obtener datos de res.company
        company = partner.env['res.company'].sudo().search([], limit=1)
        company_name = company.name or "nuestra empresa"
        address = company.partner_id.contact_address or "su sede principal"
        schedule = getattr(company, 'hour_schedule', None) or "Nuestro horario es de lunes a viernes de 9 a 18 hs."
        categories = partner.env['product.category'].sudo().search([], limit=5).mapped('name')
        product_list = ", ".join(categories) if categories else "diversos productos de limpieza (pisos, vidrios, cocinas, etc.)"

        # 2) Construir prompt
        prompt = (
            f"Eres un asistente experto de atención al cliente para la empresa '{company_name}'.\n\n"
            f"Información relevante sobre la empresa:\n"
            f"- Dirección: {address}\n"
            f"- Horario de atención: {schedule}\n"
            f"- Tipos de productos: {product_list}\n\n"
            f"El cliente hace la siguiente consulta:\n"
            f"\"{user_text}\"\n\n"
            f"Generá una respuesta amable, precisa y completa, basándote en la información anterior."
        )

        # 3) Obtener API key directamente de Odoo
        api_key = partner.env['ir.config_parameter'].sudo().get_param('openai.api_key')
        if not api_key:
            _logger.error("La API key de OpenAI no está configurada en ir.config_parameter.")
            return _("Lo siento, no pude procesar tu mensaje en este momento. 😔")

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
        return _("Perdón, hubo un problema generando la respuesta. Intentá de nuevo más tarde.")

def handle_respuesta_faq(intent, partner, text):
    """
    Todas las FAQs pasan por handle_faq_con_ai.
    """
    return handle_faq_con_ai(partner, text)