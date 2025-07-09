### Glosary
**"-"** = DONE
**"*"** = TO DO

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

- Como hacemos si el cliente en el mismo mensaje dijo que quiere mas de una cosa, o como vamos guardando varios productos en el pedido antes de mandarlo. Y luego mandarlo cuando le preguntemos al cliente si quiere algo mas y nos diga que no.
    - EJEMPLO de mas de un pedido en mismo mensaje: 
            yo: quiero un escobillon Y un blem 
            chatbot: perfecto, algo mas?
            yo: no, gracias!
            chatbot: pedido creado..... etc, etc
    - EJEMPLO de varias cosas en el pedido: yo: quiero 3 escobillon crilimp
               chatbot: perfecto, algo mas?
               yo: ah si, quiero blem
               chatbot: cuantos?
               yo: 3
               chatbot: genial, algo mas?
               yo: nono, eso esta bien
               chatbot: pedido creado.... etc, etc

- Modificacion del pedido

- Refactor y archivo de configuracion

- Arreglar onboarding

- Mejorar prompt en pedidos y consultas de pedidos
   - quiero escobas
   - No encontramos ningún producto que coincida con 'escobas'.
   - quiero pedir escobillones
   - No encontramos ningún producto que coincida con 'escobas'.

- Direcciones de entrega
    - Cuando hay mas de una direccion, preguntar a cual.

- Manejar saludo

- Manejar agradecimiento

- Manejar consultas de producto

- Que aparezcan los mensajes de WhatsApp en Odoo

- Terminar de manejar factura (USAR API DE WHATSAPP PARA ESTA TAREA)

* Manejar todos los demas casos de negocio (b2c, mayoristas)
    * B2C: Trato mas seco, derivar a website
    * mayorista: como en B2B

* Como hacer para derivar al cliente con empleado y que la IA deje de responder. (Para la cotizacion o lo que sea)

* QA, ROMPER COSAS y DETALLES

### V2

* Detectar inteligentemente la direccion de entrega en caso de que el usuario la mencione sin haberle preguntado.

* Mas inteligencia contextual 
    * PUSH: Como te fue con lo que pediste hace unos dias?
    
    * Que se pueda pedir lo mismo que antes
        * Revisar ordenes pasadas y copiar el pedido
    
    * Cancelacion de pedidos

    * Analizar pedidos anteriores para saber que producto elegir en caso de que el pedido sea muy generico
        * EJEMPLO: escobillones
        * Pedido bajado a tierra: quiero que cuando el cliente diga que quiere pedir algo de forma GENERICA, busque si esa categoria de producto la pidio anteriormente en algun pedido en el pasado, y elija automaticamente el producto especifico que haya pedido anteriormente. Si no hay historial de esa categoria, que le pase las opciones.

* Si no entiende / la intencion del usuario es otra, que lleve la conversacion como un vendedor

* Escuchar audios

* Pedir direccion

* Consultas sobre medios de pago

* Recomendar productos relacionados luego de que se haya agregado algo al carrito

* Mostrar ofertas