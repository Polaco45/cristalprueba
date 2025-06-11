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
    y que tengan stock disponible (>0). Si qty_available es None o 0, se considera sin stock.
    """
    Product = env['product.product'].sudo()
    variants = Product.search([
        '|', ('name', 'ilike', query), ('display_name', 'ilike', query)
    ], limit=limit)
    # Filtrar por stock
    in_stock = [v for v in variants if (v.qty_available or 0) > 0]
    if not in_stock:
        raise UserError(f"Lo siento, no hay stock disponible para '{query}'.")
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
    Crea pedido en borrador para la variante indicada sin validar stock (previamente validado).
    """
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
    """
    Usa Function Calling de OpenAI para extraer intención y datos,
    luego invoca las funciones Odoo definidas.

    - Si no hay stock de variantes, informa.
    - Si la cantidad solicitada excede stock, informa stock disponible y pregunta si desea esa cantidad.
    - Si está todo OK, crea el pedido.
    """
    openai.api_key = get_openai_api_key(env)

    system_msg = {
        "role": "system",
        "content": (
            "Eres un asistente que recibe pedidos de venta. "
            "Puedes invocar lookup_product_variants para buscar variantes "
            "y create_sale_order para crear el pedido."
        )
    }

    # Primer llamado: intención y búsqueda de variantes
    resp = openai.ChatCompletion.create(
        model="gpt-4o-mini",
        messages=[system_msg, {"role": "user", "content": text}],
        functions=FUNCTIONS,
        function_call="auto",
        temperature=0
    )
    msg = resp.choices[0].message

    # Si invoca lookup_product_variants
    if msg.get('function_call') and msg['function_call']['name'] == 'lookup_product_variants':
        args = json.loads(msg['function_call']['arguments'])
        # 1. Búsqueda de variantes con stock
        try:
            variants_info = lookup_product_variants(env, args['query'])
        except UserError as ue:
            return str(ue)

        # 2. LLM decide variante y qty
        followup = openai.ChatCompletion.create(
            model="gpt-4o-mini",
            messages=[
                system_msg,
                {"role": "function", "name": 'lookup_product_variants', "content": json.dumps(variants_info)}
            ],
            functions=FUNCTIONS,
            function_call="auto",
            temperature=0
        )
        fn2 = followup.choices[0].message['function_call']
        args2 = json.loads(fn2['arguments'])
        product_id = args2['product_id']
        requested_qty = args2['quantity']

        # 3. Validar vs stock y responder
        variant = env['product.product'].browse(product_id)
        available = variant.qty_available or 0
        if requested_qty > available:
            # Proponer usar todo el stock disponible
            return f"Lo siento, sólo hay {available} unidades de '{variant.display_name}'. ¿Querés pedir esa cantidad en su lugar?"

        # 4. Crear pedido
        order = create_sale_order(env, partner.id, product_id, requested_qty)
        return f"📝 Pedido {order.name} creado: {requested_qty}×{variant.display_name}."

    _logger.error("No se pudo interpretar el pedido: %s", text)
    return "Perdón, no entendí qué querés pedir. ¿Podés reformularlo?"
