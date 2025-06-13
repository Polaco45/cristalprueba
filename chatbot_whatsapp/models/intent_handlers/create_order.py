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
        raise UserError(f"Lo siento, no hay stock disponible para '{query}'.")
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


def handle_crear_pedido(env, partner, chat_history):
    openai.api_key = get_openai_api_key(env)

    system_msg = {
        "role": "system",
        "content": (
            "Eres un asistente para pedidos de productos de limpieza en WhatsApp. "
            "El cliente puede pedir productos, confirmar cantidades o responder preguntas. "
            "Primero usa lookup_product_variants si hay dudas sobre el producto. "
            "Luego, si hay stock suficiente, crea el pedido. "
            "Si no hay suficiente stock, proponé el stock disponible y esperá confirmación. "
            "Respondé solo con function_call si tenés los datos suficientes."
        )
    }

    # Llamado 1: entendemos el producto y llamamos a lookup_product_variants
    response = openai.ChatCompletion.create(
        model="gpt-4o-mini",
        messages=[system_msg] + chat_history,
        functions=FUNCTIONS,
        function_call="auto",
        temperature=0
    )
    msg = response.choices[0].message

    if not msg.get('function_call'):
        _logger.error("No function_call en primera respuesta: %s", response)
        return msg.get("content", "Perdón, no entendí qué producto querés pedir.")

    if msg['function_call']['name'] != 'lookup_product_variants':
        _logger.error("Esperando lookup_product_variants, vino: %s", msg['function_call']['name'])
        return "Algo salió mal al procesar el producto."

    args = json.loads(msg['function_call']['arguments'])
    try:
        variants_info = lookup_product_variants(env, args['query'])
    except UserError as ue:
        return str(ue)

    # Llamado 2: elegimos variante y cantidad
    followup = openai.ChatCompletion.create(
        model="gpt-4o-mini",
        messages=[system_msg] + chat_history + [
            {"role": "function", "name": 'lookup_product_variants', "content": json.dumps(variants_info)}
        ],
        functions=FUNCTIONS,
        function_call="auto",
        temperature=0
    )
    follow_msg = followup.choices[0].message

    if not follow_msg.get('function_call'):
        content = follow_msg.get('content', '').strip()
        return content or "No entendí qué producto querés. ¿Podés repetir?"

    fn = follow_msg['function_call']
    args2 = json.loads(fn['arguments'])
    product_id = args2.get('product_id')
    requested_qty = args2.get('quantity')

    variant = env['product.product'].browse(product_id)
    available = variant.qty_available or 0
    if requested_qty > available:
        return f"Solo hay {available} unidades de '{variant.display_name}'. ¿Querés pedir esa cantidad en su lugar?"

    order = create_sale_order(env, partner.id, product_id, requested_qty)
    return f"📝 Pedido {order.name} creado: {requested_qty}×{variant.display_name}."
