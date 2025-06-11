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

# Defino los schemas que OpenAI podrá invocar
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
    """
    Devuelve hasta `limit` variantes cuyo nombre o descripción coincida con `query`
    y que tengan stock disponible (>0).
    """
    Product = env['product.product'].sudo()
    # Buscar coincidencias
    variants = Product.search([
        '|', ('name', 'ilike', query), ('display_name', 'ilike', query)
    ], limit=limit)
    # Filtrar por stock
    in_stock = [v for v in variants if v.qty_available > 0]
    if not in_stock:
        raise UserError("No hay stock disponible para ninguna variante.")
    return [
        {
            'id': v.id,
            'name': v.display_name,
            'stock': v.qty_available,
            'price': v.list_price
        }
        for v in in_stock
    ]


def create_sale_order(env, partner_id, product_id, quantity):
    """
    Valida stock y crea pedido en borrador para la variante indicada.
    """
    partner = env['res.partner'].browse(partner_id)
    variant = env['product.product'].browse(product_id)

    if variant.qty_available < quantity:
        raise UserError(f"Stock insuficiente ({variant.qty_available} disponibles)")

    order = env['sale.order'].sudo().create({
        'partner_id': partner.id,
        'order_line': [(0, 0, {
            'product_id': variant.id,
            'product_uom_qty': quantity,
            'price_unit': variant.list_price,
        })]
    })
    return order

# -----------------------
# Manejo de petición
# -----------------------

def handle_crear_pedido(env, partner, text):
    """
    Usa Function Calling de OpenAI para extraer intención y datos,
    luego invoca las funciones Odoo definidas.
    """
    # Configuración de API
    openai.api_key = get_openai_api_key(env)

    system_msg = {
        "role": "system",
        "content": (
            "Eres un asistente que recibe pedidos de venta. "
            "Puedes invocar lookup_product_variants para buscar variantes "
            "y create_sale_order para crear el pedido."
        )
    }

    # Primer llamado para detección de intención y variante
    resp = openai.ChatCompletion.create(
        model="gpt-4o-mini",
        messages=[system_msg, {"role": "user", "content": text}],
        functions=FUNCTIONS,
        function_call="auto",
        temperature=0
    )

    msg = resp.choices[0].message

    # Procesar function_call
    if msg.get('function_call'):
        name = msg['function_call']['name']
        args = json.loads(msg['function_call']['arguments'])

        if name == 'lookup_product_variants':
            # Buscar variantes con stock
            variants_info = lookup_product_variants(env, args['query'])
            # Reenvío resultado al LLM para elegir variante y qty
            followup = openai.ChatCompletion.create(
                model="gpt-4o-mini",
                messages=[
                    system_msg,
                    {"role": "function", "name": name, "content": json.dumps(variants_info)}
                ],
                functions=FUNCTIONS,
                function_call="auto",
                temperature=0
            )
            fn2 = followup.choices[0].message['function_call']
            args2 = json.loads(fn2['arguments'])
            # Creamos el pedido
            order = create_sale_order(env, partner.id, args2['product_id'], args2['quantity'])
            return f"📝 Pedido {order.name} creado: {args2['quantity']}×{order.order_line.product_id.display_name}."

    _logger.error("No se pudo interpretar el pedido: %s", text)
    return "Perdón, no entendí qué querés pedir. ¿Podés reformularlo?"
