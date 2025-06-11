import json
import logging
import openai
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

# -----------------------
# Configuración de OpenAI
# -----------------------

def get_openai_api_key(env):
    return env['ir.config_parameter'].sudo().get_param('openai.api_key')

# Esquemas de función para OpenAI (partner_id implícito)
FUNCTIONS = [
    {
        "name": "lookup_product_variants",
        "description": "Busca variantes de producto en Odoo",
        "parameters": {
            "type": "object",
            "properties": {"query": {"type": "string", "description": "Término de búsqueda"}},
            "required": ["query"]
        }
    },
    {
        "name": "create_sale_order",
        "description": "Crea un pedido de venta en borrador para el partner implícito",
        "parameters": {
            "type": "object",
            "properties": {
                "product_id": {"type": "integer"},
                "quantity": {"type": "integer"}
            },
            "required": ["product_id", "quantity"]
        }
    }
]

# -----------------------
# Funciones Odoo
# -----------------------

def lookup_product_variants(env, query, limit=5):
    Product = env['product.product'].sudo()
    variants = Product.search([
        '|', ('name', 'ilike', query), ('display_name', 'ilike', query)
    ], limit=limit)
    in_stock = [v for v in variants if (v.qty_available or 0) > 0]
    if not in_stock:
        raise UserError(f"Lo siento, no hay stock disponible para '{query}'.")
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

# -----------------------
# Manejo de petición
# -----------------------

def handle_crear_pedido(env, partner, text):
    openai.api_key = get_openai_api_key(env)
    system_msg = {
        'role': 'system',
        'content': (
            'Eres un asistente que recibe pedidos de venta. ' +
            'Usa lookup_product_variants para buscar variantes y ' +
            'create_sale_order para crear el pedido.'
        )
    }

    # Paso 1: lookup
    resp = openai.ChatCompletion.create(
        model='gpt-4o-mini',
        messages=[system_msg, {'role': 'user', 'content': text}],
        functions=FUNCTIONS,
        function_call='auto',
        temperature=0
    )
    msg = resp.choices[0].message
    if not msg.get('function_call') or msg['function_call']['name'] != 'lookup_product_variants':
        _logger.error('Paso 1 falló: %s', msg)
        return msg.get('content', 'Perdón, no entendí el producto.')

    args = json.loads(msg['function_call']['arguments'])
    try:
        variants = lookup_product_variants(env, args['query'])
    except UserError as ue:
        return str(ue)

    # Paso 2: selección de variante y cantidad
    followup = openai.ChatCompletion.create(
        model='gpt-4o-mini',
        messages=[
            system_msg,
            {'role': 'function', 'name': 'lookup_product_variants', 'content': json.dumps(variants)}
        ],
        functions=FUNCTIONS,
        function_call='auto',
        temperature=0
    )
    follow = followup.choices[0].message
    if not follow.get('function_call'):
        return follow.get('content', 'No entendí la variante y cantidad.')

    params = json.loads(follow['function_call']['arguments'])
    product_id = params.get('product_id')
    qty = params.get('quantity')
    variant = env['product.product'].browse(product_id)
    available = variant.qty_available or 0
    if qty > available:
        return f"Lo siento, sólo hay {available} unidades de '{variant.display_name}'. ¿Querés esa cantidad?"

    # Paso 3: creación
    order = create_sale_order(env, partner.id, product_id, qty)
    return f"📝 Pedido {order.name} creado: {qty}×{variant.display_name}."