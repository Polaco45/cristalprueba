# models/intent_handlers.py

import re
import logging
import openai
from ..config.config import general_config
import base64
from odoo import _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

def handle_crear_pedido(partner, text):
    """
    Extrae el producto y la cantidad desde el texto, crea un pedido de venta en estado 'borrador'.
    Luego, pide confirmación al usuario.
    """
    # Extraer cantidad (opcional)
    cantidad_match = re.search(r'(\d+)', text)
    cantidad = int(cantidad_match.group(1)) if cantidad_match else 1

    # Extraer nombre de producto (simplificado, se podría mejorar con embeddings o NLP)
    producto_match = re.search(r'(lavandina|detergente|pisos|desinfectante|limpiador)', text, re.IGNORECASE)
    producto = producto_match.group(1) if producto_match else None

    if not producto:
        return "¿Qué producto querés? Por ejemplo: 'Quiero 2 botellas de lavandina'."

    # Buscar producto en Odoo
    product = partner.env['product.product'].sudo().search([
        ('name', 'ilike', producto)
    ], limit=1)

    if not product:
        return f"No encontré el producto *{producto}*. ¿Podés describirlo mejor?"

    # Crear pedido en estado borrador
    order = partner.env['sale.order'].sudo().create({
        'partner_id': partner.id,
        'order_line': [(0, 0, {
            'product_id': product.id,
            'product_uom_qty': cantidad,
            'price_unit': product.list_price
        })]
    })

    return (
        f"📝 Pedido generado con *{cantidad} x {product.name}*. "
        f"Si querés confirmarlo, respondé con: *Confirmar pedido {order.name}*"
    )

# --- CONFIRMAR PEDIDO --------------------------------------------------

def handle_confirmar_pedido(partner, text):
    """
    Confirma un pedido si el cliente responde con 'Confirmar pedido SO123'
    """
    match = re.search(r'(SO\d+)', text, re.IGNORECASE)
    if not match:
        return "¿Podés decirme el número del pedido que querés confirmar? Ej: 'Confirmar pedido SO123'"

    order_name = match.group(1).upper()
    order = partner.env['sale.order'].sudo().search([
        ('name', '=', order_name),
        ('partner_id', '=', partner.id)
    ], limit=1)

    if not order:
        return f"No encontré el pedido *{order_name}*. ¿Estás seguro que ese es el número correcto?"

    if order.state != 'draft':
        return f"El pedido *{order.name}* ya fue confirmado antes."

    try:
        order.action_confirm()
        return f"✅ Pedido *{order.name}* confirmado. ¡Gracias por tu compra!"
    except Exception as e:
        _logger.error("Error al confirmar pedido %s: %s", order.name, e)
        return "⚠️ Hubo un error al confirmar el pedido. Intentá de nuevo más tarde."


def handle_solicitar_factura(partner, text):
    """
    1) Busca en el texto un número de factura (al menos 4 dígitos).
    2) Busca el registro account.move correspondiente.
    3) Si lo encuentra, genera el PDF de esa factura y lo codifica en base64.
    4) Devuelve un diccionario con dos claves:
         - 'message': texto para enviar por WhatsApp.
         - 'pdf_base64': el contenido en base64 del PDF (si existiera).
       El flujo que envía WhatsApp debe detectar si existe 'pdf_base64' y, en ese caso,
       enviarlo como adjunto.
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
        # 3) Generar el PDF de la factura (report 'account.account_invoices' es el QWeb PDF por defecto)
        #    Dependiendo de tu versión de Odoo, puede cambiar el XML ID del reporte.
        report_action = partner.env.ref('account.account_invoices')  # XML ID del informe de facturas
        pdf_content, content_type = report_action.sudo()._render_qweb_pdf([invoice.id])
        # pdf_content es un binario; lo codificamos en base64 para transporte
        pdf_base64 = base64.b64encode(pdf_content).decode('utf-8')

        # 4) Construir el mensaje para el usuario
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
    Genera dinámicamente la respuesta a preguntas frecuentes (horarios, productos, ubicación, etc.)
    usando OpenAI. Para ello, recopila datos básicos de la empresa (nombre, dirección, horario, catálogo).
    """
    try:
        # 1) Obtener datos generales de la empresa (res.company) – asumimos que hay sólo una.
        company = partner.env['res.company'].sudo().search([], limit=1)
        company_name = company.name or "nuestra empresa"
        address = company.partner_id.contact_address or "su sede principal"
        # 2) Asumir que el campo "horario" está en campos personalizados de res.company
        #    (Ejemplo: company.hour_schedule, si lo tuvieses). Si no existe, poner texto genérico.
        schedule = getattr(company, 'hour_schedule', None)
        if not schedule:
            schedule = "Nuestro horario es de lunes a viernes de 9 a 18 hs."

        # 3) Obtener lista de categorías de productos o un par de ejemplos
        categories = partner.env['product.category'].sudo().search([], limit=5).mapped('name')
        if categories:
            product_list = ", ".join(categories)
        else:
            product_list = "diversos productos de limpieza (pisos, vidrios, cocinas, etc.)"

        # 4) Construir prompt dinámico para OpenAI
        prompt = (
            f"Eres un asistente experto de atención al cliente para la empresa '{company_name}'.\n\n"
            f"Información relevante sobre la empresa:\n"
            f"- Dirección: {address}\n"
            f"- Horario de atención: {schedule}\n"
            f"- Tipos de productos: {product_list}\n\n"
            f"El cliente hace la siguiente consulta:\n"
            f"\"{user_text}\"\n\n"
            f"Generá una respuesta amable, precisa y completa, basándote en la información anterior.\n"
            f"Si la consulta no coincide exactamente con lo que tenemos, brindá orientación general."
        )

        openai.api_key = general_config['openai']['api_key']
        result = openai.ChatCompletion.create(
            model=general_config['openai']['model'],
            messages=[
                {"role": "system", "content": "Eres un asistente muy respetuoso y útil."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=250
        )
        respuesta = result.choices[0].message.content.strip()
        return respuesta

    except Exception as e:
        _logger.error("Error al generar respuesta con AI: %s", e)
        return "Perdón, hubo un problema generando la respuesta. Intentá de nuevo más tarde."

def handle_respuesta_faq(intent, partner, text):
    """
    Antes usábamos respuestas estáticas; ahora derivaremos todas las FAQs a handle_faq_con_ai.
    El parámetro 'intent' permanece para posibles rutas condicionales (si quisieras tratar algunas
    respuestas de forma distinta). Por simplicidad, todas pasan por AI.
    """
    return handle_faq_con_ai(partner, text)
