# addons/chatbot_whatsapp/models/intent_handlers/create_order.py
import json
import logging
import openai
import re
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
                "query": { "type": "string", "description": "Término de búsqueda libre" }
            },
            "required": ["query"]
        },
    },
    {
        "name": "create_sale_order",
        "description": "Crea un pedido de venta en borrador",
        "parameters": {
            "type": "object",
            "properties": {
                "partner_id": { "type": "integer" },
                "product_id": { "type": "integer" },
                "quantity": { "type": "integer" }
            },
            "required": ["partner_id", "product_id", "quantity"]
        }
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
        { 'id': v.id, 'name': v.display_name, 'stock': v.qty_available, 'price': v.list_price }
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

def handle_crear_pedido(env, partner, text):
    openai.api_key = get_openai_api_key(env)
    plain = text.strip().lower()

    if plain in ["sí", "si", "dale", "ok", "claro"] and partner.last_requested_product_id and partner.last_requested_qty:
        prod = partner.last_requested_product_id
        qty  = partner.last_requested_qty
        order = create_sale_order(env, partner.id, prod.id, qty)
        partner.last_requested_product_id = False
        partner.last_requested_qty = 0
        return f"📝 Pedido {order.name} creado: {qty}×{prod.display_name}."

    system_msg = {"role": "system", "content": (
        "Eres un asistente para pedidos de productos de limpieza. "
        "Primero usa lookup_product_variants para buscar variantes con stock. "
        "Luego, si la cantidad solicitada está disponible, llama a create_sale_order. "
        "Si no, informa al usuario la cantidad máxima y espera confirmación. "
        "Siempre devuelve un function_call cuando tengas todos los datos necesarios."
    )}

    resp = openai.ChatCompletion.create(
        model="gpt-4o-mini",
        messages=[system_msg, {"role": "user", "content": text}],
        functions=FUNCTIONS,
        function_call="auto",
        temperature=0
    )
    msg = resp.choices[0].message

    if not msg.get('function_call'):
        _logger.error("No function_call en primera respuesta: %s", resp)
        return "Perdón, no entendí qué producto querés pedir."

    if msg['function_call']['name'] != 'lookup_product_variants':
        _logger.error("Esperando lookup_product_variants, vino: %s", msg['function_call']['name'])
        return "Algo salió mal al procesar el producto."

    args = json.loads(msg['function_call']['arguments'])
    try:
        variants_info = lookup_product_variants(env, args['query'])
    except UserError as ue:
        return str(ue)

    followup = openai.ChatCompletion.create(
        model="gpt-4o-mini",
        messages=[
            system_msg,
            {"role": "user", "content": text},
            {"role": "function", "name": "lookup_product_variants", "content": json.dumps(variants_info)}
        ],
        functions=FUNCTIONS,
        function_call="auto",
        temperature=0
    )
    follow_msg = followup.choices[0].message

    if not follow_msg.get('function_call'):
        content = follow_msg.get('content', '').strip()
        if content:
            m = re.search(r"Solo hay (\d+) unidades", content)
            if m:
                qty_offered = int(m.group(1))
                prod_id = variants_info[0]['id']
                partner.last_requested_product_id = prod_id
                partner.last_requested_qty = qty_offered
            return content
        _logger.error("No function_call ni content en followup: %s", followup)
        return "No entendí qué variante elegiste. ¿Podés indicar el producto y cantidad?"

    fn2 = follow_msg['function_call']
    args2 = json.loads(fn2['arguments'])
    product_id    = args2.get('product_id')
    requested_qty = args2.get('quantity')

    variant = env['product.product'].browse(product_id)
    available = variant.qty_available or 0
    if requested_qty > available:
        partner.last_requested_product_id = product_id
        partner.last_requested_qty = available
        return f"Lo siento, sólo hay {available} unidades de '{variant.display_name}'. ¿Querés pedir esa cantidad en su lugar?"

    order = create_sale_order(env, partner.id, product_id, requested_qty)
    return f"📝 Pedido {order.name} creado: {requested_qty}×{variant.display_name}."
