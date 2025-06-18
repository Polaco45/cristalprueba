import json
import logging
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
    },
    {
        "name": "create_sale_order",
        "description": "Crea un pedido de venta en borrador",
        "parameters": {
            "type": "object",
            "properties": {
                "partner_id": {"type": "integer"},
                "product_id": {"type": "integer"},
                "quantity": {"type": "integer"}
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

def handle_crear_pedido(env, partner, text, conversation=None):
    openai.api_key = get_openai_api_key(env)

    system_msg = {
        "role": "system",
        "content": (
            "Eres un asistente experto en pedidos para una tienda de productos de limpieza. "
            "El cliente puede pedir productos mencionando nombre y cantidad. "
            "Debes seguir estos pasos:\n"
            "1. Usa 'lookup_product_variants' para encontrar el producto.\n"
            "2. Si la cantidad solicitada es mayor al stock, informa al cliente y espera confirmación.\n"
            "3. Si el cliente ya confirmó una cantidad sugerida, crea el pedido.\n\n"
            "Debes usar los mensajes anteriores para entender si se trata de una confirmación o una nueva solicitud.\n"
            "Siempre responde usando 'function_call'."
        )
    }

    messages = [system_msg]
    if conversation:
        messages += conversation
    else:
        messages.append({"role": "user", "content": text})

    # 1) Buscar variantes
    resp = openai.ChatCompletion.create(
        model="gpt-4o-mini",
        messages=messages,
        functions=FUNCTIONS,
        function_call="auto",
        temperature=0
    )
    msg = resp.choices[0].message
    if msg.get('function_call', {}).get('name') != 'lookup_product_variants':
        return "No entendí qué producto querés."

    args = json.loads(msg.function_call.arguments)
    try:
        variants = lookup_product_variants(env, args['query'])
    except UserError as ue:
        return str(ue)

    # 2) Elección y cantidad
    messages += [
        {"role": "function", "name": "lookup_product_variants", "content": json.dumps(variants)}
    ]
    follow = openai.ChatCompletion.create(
        model="gpt-4o-mini",
        messages=messages,
        functions=FUNCTIONS,
        function_call="auto",
        temperature=0
    )
    fmsg = follow.choices[0].message
    if not fmsg.get('function_call'):
        return fmsg.get('content', "No entendí tu elección.")

    params = json.loads(fmsg.function_call.arguments)
    pid = params['product_id']
    qty = params['quantity']
    variant = env['product.product'].browse(pid)
    avail = variant.qty_available or 0

    if qty > avail:
        # guardar memoria para confirmar luego
        env['chatbot.whatsapp.memory'].sudo().create({
            'partner_id': partner.id,
            'last_intent': 'esperando_confirmacion_stock',
            'last_variant_id': variant.id,
            'last_qty_suggested': avail
        })
        return f"Solo hay {avail} unidades de '{variant.display_name}'. ¿Querés esa cantidad?"

    order = create_sale_order(env, partner.id, pid, qty)
    return f"📝 Pedido {order.name} creado: {qty}×{variant.display_name}."

