/** @odoo-module **/

import { ThreadView } from "@mail/views/thread_view/thread_view";
import { patch } from "@web/core/utils/patch";
import { onPatched } from "@odoo/owl";

patch(ThreadView.prototype, 'chatbot_whatsapp.ThreadView', {
    
    // Sobrescribimos el 'setup' del componente para usar hooks del ciclo de vida.
    setup() {
        // Primero, llamamos al setup original para no romper nada.
        this._super(...arguments);

        // onPatched es un "hook" que se ejecuta CADA VEZ que el componente se actualiza/re-renderiza.
        // Es el lugar perfecto para verificar si el div dinámico ya apareció.
        onPatched(() => {
            this.addChatbotButton();
        });

        // También lo llamamos una vez al montar por si el div ya existe desde el principio
        onMounted(() => {
            this.addChatbotButton();
        });
    },

    addChatbotButton() {
        // Selector de nuestro botón. Lo usamos para no añadirlo múltiples veces.
        const buttonSelector = '.o_chatbot_button';
        // Selector del contenedor del otro módulo.
        const targetContainerSelector = '.o-mail-Discuss-headerActions';

        // 1. Verificamos si nuestro botón ya existe. Si es así, no hacemos nada.
        if (this.el.querySelector(buttonSelector)) {
            return;
        }

        // 2. Buscamos el contenedor del otro módulo.
        const targetContainer = this.el.querySelector(targetContainerSelector);
        
        // 3. Si el contenedor EXISTE y nuestro botón NO...
        if (targetContainer) {
            console.log("🔥 [Chatbot] Contenedor encontrado. Creando botón...");
            
            // Creamos el botón desde cero con JavaScript
            const chatbotButton = document.createElement('button');
            chatbotButton.className = 'o_ThreadView_action btn btn-link o_chatbot_button';
            chatbotButton.title = 'Prueba Chatbot';
            chatbotButton.setAttribute('aria-label', 'Prueba Chatbot');
            
            // Creamos el ícono
            const icon = document.createElement('i');
            icon.className = 'fa fa-bug fa-fw';
            icon.setAttribute('role', 'img');
            chatbotButton.appendChild(icon);

            // Añadimos el evento de clic. Importante usar .bind(this)
            // para que dentro de onClickCustomButton, 'this' siga siendo el componente.
            chatbotButton.addEventListener('click', this.onClickCustomButton.bind(this));

            // 4. ¡Insertamos nuestro botón en el contenedor!
            targetContainer.prepend(chatbotButton); // prepend lo añade al principio
        }
    },

    /**
     * Esta función no cambia. Sigue siendo la lógica que se ejecuta al hacer clic.
     */
    onClickCustomButton() {
        alert("¡CLIC DETECTADO en el botón dinámico!");
        console.log("Datos del hilo actual:", this.thread);
    },
});