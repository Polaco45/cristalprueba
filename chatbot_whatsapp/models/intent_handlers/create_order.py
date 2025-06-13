import json
import logging
import openai
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

from ..models.partner_extension import ResPartner  # para actualizar campos
from ..config.config import general_config

# -----------------------
# Configuración de OpenAI
# -----------------------

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

# -----------------------
# Manejo de petición
# -----------------------

def handle_crear_pedido(env, partner, text):
    openai.api_key = get_openai_api_key(env)

    system_msg = {"role": "system", "content": (
        "Eres un asistente para pedidos de productos de limpieza."
        " Primero usa lookup_product_variants para buscar variantes con stock."
        " Luego, si la cantidad solicitada está disponible, llama a create_sale_order."  
        " Si no, informa al usuario la cantidad máxima y espera confirmación."
        " Siempre devuelve un function_call cuando tengas todos los datos necesarios."
    )}

    # Primera llamada: buscar variantes
    resp = openai.ChatCompletion.create(
        model=general_config['openai']['model'],
        messages=[system_msg, {"role": "user", "content": text}],
        functions=FUNCTIONS,
        function_call="auto",
        temperature=0
    )
    msg = resp.choices[0].message

    if not msg.get('function_call') or msg['function_call']['name'] != 'lookup_product_variants':
        _logger.error("No lookup_product_variants en primera respuesta: %s", resp)
        return "Perdón, no entendí qué producto querés pedir."

    args = json.loads(msg['function_call']['arguments'])
    try:
        variants_info = lookup_product_variants(env, args['query'])
    except UserError as ue:
        return str(ue)

    # Segunda llamada: elegir variante y cantidad
    followup = openai.ChatCompletion.create(
        model=general_config['openai']['model'],
        messages=[
            system_msg,
            {"role": "user", "content": text},
            {"role": "function", "name": 'lookup_product_variants', "content": json.dumps(variants_info)}
        ],
        functions=FUNCTIONS,
        function_call="auto",
        temperature=0
    )
    follow_msg = followup.choices[0].message

    if not follow_msg.get('function_call'):
        return follow_msg.get('content', "").strip() or "No entendí tu pedido."

    fn2 = follow_msg['function_call']
    args2 = json.loads(fn2['arguments'])
    product_id = args2.get('product_id')
    requested_qty = args2.get('quantity')

    variant = env['product.product'].browse(product_id)
    available = variant.qty_available or 0
    if requested_qty > available:
        # Guardar contexto para confirmación futura
        partner.write({
            'last_requested_product_id': product_id,
            'last_requested_qty': available
        })
        return f"Lo siento, sólo hay {available} unidades de '{variant.display_name}'. ¿Querés esa cantidad?"

    # Guardar contexto y crear pedido directo
    partner.write({
        'last_requested_product_id': product_id,
        'last_requested_qty': requested_qty
    })
    order = create_sale_order(env, partner.id, product_id, requested_qty)
    return f"📝 Pedido {order.name} creado: {requested_qty}×{variant.display_name}."