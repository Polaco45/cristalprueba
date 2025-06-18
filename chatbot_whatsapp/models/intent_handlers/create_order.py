# models/intent_handlers/create_order.py

import json
import logging
import re
import openai
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

def get_openai_api_key(env):
    return env['ir.config_parameter'].sudo().get_param('openai.api_key')

FUNCTIONS = [
    {
        "name": "lookup_product_variants",
        "description": "Busca variantes de producto en Odoo",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Término de búsqueda libre"}
            },
            "required": ["query"]
        },
    }
]

def lookup_product_variants(env, query, limit=5):
    Product = env['product.product'].sudo()
    variants = Product.search([
        '|', ('name', 'ilike', query), ('display_name', 'ilike', query)
    ], limit=limit)
    in_stock = [v for v in variants if (v.qty_available or 0) > 0]
    if not in_stock:
        raise UserError(f"No hay stock disponible para '{query}'.")
    return [
        {'id': v.id, 'name': v.display_name, 'stock': v.qty_available, 'price': v.list_price}
        for v in in_stock
    ]

def create_sale_order(env, partner_id, product_id, quantity):
    order = env['sale.order'].sudo().create({
        'partner_id': partner_id,
        'order_line': [(0, 0, {
            'product_id': product_id,
            'product_uom_qty': quantity,
            'price_unit': env['product.product'].browse(product_id).list_price,
        })]
    })
    return order

def handle_crear_pedido(env, partner, text, send_buttons=None):
    """
    1) Usa GPT para buscar variantes disponibles.
    2) Extrae la cantidad del texto con regex.
    3) Si qty > stock → crea memoria y devuelve texto con 3 opciones numeradas.
    4) Si qty <= stock → crea pedido y devuelve texto.
    """
    openai.api_key = get_openai_api_key(env)

    # 1) function_call para buscar variantes
    system_msg = {
        "role": "system",
        "content": (
            "Eres un asistente para pedidos de productos de limpieza.\n"
            "Cuando recibas un texto, devuelve un function_call 'lookup_product_variants' "
            "con el parámetro 'query' igual al nombre del producto solicitado."
        )
    }
    resp = openai.ChatCompletion.create(
        model="gpt-4o-mini",
        messages=[system_msg, {"role": "user", "content": text}],
        functions=FUNCTIONS,
        function_call="auto",
        temperature=0,
        max_tokens=50
    )
    msg = resp.choices[0].message
    if msg.get('function_call', {}).get('name') != 'lookup_product_variants':
        return "No entendí qué producto querés."

    args = json.loads(msg.function_call.arguments)
    try:
        variants = lookup_product_variants(env, args['query'])
    except UserError as ue:
        return str(ue)

    # Nos quedamos con la primera variante en stock
    variant = variants[0]
    pid   = variant['id']
    avail = int(variant['stock'])
    name  = variant['name']

    # 2) Extraer cantidad
    m = re.search(r'\b(\d+)\b', text)
    if not m:
        return "¿Cuántas unidades querés?"
    qty = int(m.group(1))

    # 3) Si pide más de lo disponible → memoria + texto con opciones
    if qty > avail:
        env['chatbot.whatsapp.memory'].sudo().create({
            'partner_id': partner.id,
            'last_intent': 'esperando_confirmacion_stock',
            'last_variant_id': pid,
            'last_qty_suggested': avail
        })
        return (
            f"Solo hay {avail} unidades de “{name}”.\n"
            "Respondé con:\n"
            "1) Sí, quiero las {avail}\n"
            "2) Quiero otra cantidad\n"
            "3) No, gracias"
        )

    # 4) Si alcanza stock → crear pedido
    order = create_sale_order(env, partner.id, pid, qty)
    return f"📝 Pedido {order.name} creado: {qty}×{name}."
