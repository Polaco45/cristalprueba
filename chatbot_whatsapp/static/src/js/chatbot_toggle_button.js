odoo.define('chatbot_whatsapp.toggle_button', function () {
    'use strict';

    // Este console.log nos confirmará que el archivo correcto se está ejecutando.
    console.log("✅ [Chatbot Alternativo] Módulo JS cargado correctamente.");

    // Función que busca el contenedor e inyecta el botón.
    function tryToAddButton() {
        // El contenedor dinámico del otro módulo.
        const targetContainer = document.querySelector('.o-mail-Discuss-headerActions');
        // Usamos una clase propia para verificar si nuestro botón ya existe.
        const buttonExists = document.querySelector('.o_chatbot_button');

        // Si encontramos el contenedor y nuestro botón todavía no ha sido añadido...
        if (targetContainer && !buttonExists) {
            console.log("🔥 [Chatbot Alternativo] Contenedor encontrado. Inyectando botón...");

            // 1. Creamos el botón
            const chatbotButton = document.createElement('button');
            chatbotButton.className = 'o_ThreadView_action btn btn-link o_chatbot_button';
            chatbotButton.title = 'Prueba Chatbot';
            chatbotButton.innerHTML = '<i class="fa fa-bug fa-fw" role="img"></i>';

            // 2. Le asignamos la acción de clic
            chatbotButton.onclick = () => {
                alert("¡CLIC DETECTADO (Método Alternativo)!");
                // Aquí la lógica de tu clic
            };
            
            // 3. Lo añadimos al DOM, al principio del contenedor.
            targetContainer.prepend(chatbotButton);
        }
    }

    // Establecemos un "vigilante" que ejecuta la función tryToAddButton cada segundo.
    // Esto asegura que encontraremos el contenedor dinámico tan pronto como aparezca.
    setInterval(tryToAddButton, 1000);
});