### V1

- Onboardear a la persona en caso de que sea nueva
    - Validar Email
    - Vincular al contacto
    - Preguntar intencion (consumidor final, b2b o revendedores)
    - Reemplazar la forma de is_cotizado para que empiece a detectar si tiene al menos 1 cotizacion u orden de punto de venta en lugar de identificarlo mediante su lista de precio.
    - Siempre hacer lead. Diferenciar en Calificado en el CRM:
        - Si es nuevo contacto, "Nuevo cliente Whatsapp: *Nombre*"
        - Si es contacto existente, "Pedido Whatsapp: *Nombre*"

- Crear lead y actividad en ese lead con tipo de actividad para que revise y envie la cotizacion o se contacte con el cliente.
    - Nombre de actividad: Iniciativa de venta

- Chequear precio en las ordenes de venta con WhatsApp.

* Analizar pedidos anteriores para saber que producto elegir en caso de que el pedido sea muy generico
    * EJEMPLO: escobillones
    * PROMPT: ahora quiero que cuando el cliente diga que quiere pedir algo de forma GENERICA, busque si esa categoria de producto la pidio anteriormente en algun pedido en el pasado, y elija automaticamente el producto especifico que haya pedido anteriormente. Si no hay historial de esa categoria, que le pase las opciones.

* Que le pregunte en caso de que haya mas de un cliente en el mismo numero

* Manejar todos los demas casos de negocio (b2c, mayoristas)
    * B2C: Trato mas seco, derivar a website
    * mayorista: como en B2B

* Ejecutar el pedido

* Refactor y archivo de configuracion

* Como hacer para derivar al cliente con empleado y que la IA deje de responder. (Para la cotizacion o lo que sea)

### V2

* Escuchar audios

