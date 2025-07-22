// chatbot_whatsapp/static/src/js/chatbot_toggle_button.js
odoo.define('chatbot_whatsapp.toggle_button', function (require) {
    "use strict";

    // YA NO REQUERIMOS NADA DE @mail, evitando el error.
    const { Component, hooks } = require("@odoo/owl");
    const { useService } = require("@web/core/utils/hooks");

    // Usaremos un componente genérico y lo montaremos en un intervalo.
    // Es menos elegante que el parche, pero mucho más resistente a errores de dependencia.
    
    // Función que intenta añadir el botón
    function tryToAddButton() {
        const targetContainer = document.querySelector('.o-mail-Discuss-headerActions');
        const buttonExists = document.querySelector('.o_chatbot_button');

        // Si el contenedor existe y el botón aún no...
        if (targetContainer && !buttonExists) {
            console.log("🔥 [Chatbot Alternativo] Contenedor encontrado. Inyectando botón.");

            const chatbotButton = document.createElement('button');
            chatbotButton.className = 'o_ThreadView_action btn btn-link o_chatbot_button';
            chatbotButton.title = 'Prueba Chatbot';
            chatbotButton.innerHTML = '<i class="fa fa-bug fa-fw" role="img"></i>';

            chatbotButton.onclick = () => {
                alert("¡CLIC DETECTADO (Método Alternativo)!");
                // Aquí necesitaríamos una forma de obtener el 'threadId' si es necesario,
                // lo cual puede ser más complejo sin el contexto del componente.
            };
            
            targetContainer.prepend(chatbotButton);
        }
    }

    // Usamos un intervalo para buscar el contenedor periódicamente.
    // Esto asegura que encontraremos el div dinámico cuando aparezca.
    setInterval(tryToAddButton, 1000); // Revisa cada segundo
});