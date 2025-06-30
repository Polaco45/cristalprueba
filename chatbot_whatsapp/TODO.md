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

- Resolver siguiente bug:
    -   yo: quiero blem
        chatbot: ¡Perfecto! Elegiste “[CM0042] Blem Aero x 400Cc Original”. ¿Cuántas unidades querés?
        yo: 2
        chatbot: No entendí qué producto querés.

* Como hacemos si el cliente en el mismo mensaje dijo que quiere mas de una cosa, o como vamos guardando varios productos en el pedido antes de mandarlo. Y luego mandarlo cuando le preguntemos al cliente si quiere algo mas y nos diga que no.
    * EJEMPLO de mas de un pedido en mismo mensaje: yo: quiero un escobillon Y un blem 
                                                    chatbot: perfecto, algo mas?
                                                    yo: no, gracias!
                                                    chatbot: pedido creado..... etc, etc
    * EJEMPLO de varias cosas en el pedido: yo: quiero 3 escobillon crilimp
               chatbot: perfecto, algo mas?
               yo: ah si, quiero blem
               chatbot: cuantos?
               yo: 3
               chatbot: genial, algo mas?
               yo: nono, eso esta bien
               chatbot: pedido creado.... etc, etc

* Que le pregunte en caso de que haya mas de un cliente en el mismo numero

* Manejar todos los demas casos de negocio (b2c, mayoristas)
    * B2C: Trato mas seco, derivar a website
    * mayorista: como en B2B

* Refactor y archivo de configuracion

* Manejar saludo y prompt

* Mejorar prompt en pedidos y consultas de pedidos

* Terminar de manejar factura

* Como hacer para derivar al cliente con empleado y que la IA deje de responder. (Para la cotizacion o lo que sea)

### V2

* Analizar pedidos anteriores para saber que producto elegir en caso de que el pedido sea muy generico
    * EJEMPLO: escobillones
    * PROMPT: ahora quiero que cuando el cliente diga que quiere pedir algo de forma GENERICA, busque si esa categoria de producto la pidio anteriormente en algun pedido en el pasado, y elija automaticamente el producto especifico que haya pedido anteriormente. Si no hay historial de esa categoria, que le pase las opciones.

* Cancelacion de pedidos

* Que se pueda pedir lo mismo que antes
    * Revisar ordenes pasadas y copiar el pedido

* Si no entiende / la intencion del usuario es otra, que lleve la conversacion como un vendedor

* Escuchar audios

