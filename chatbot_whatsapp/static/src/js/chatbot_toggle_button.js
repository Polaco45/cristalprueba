// chatbot_whatsapp/static/src/js/chatbot_toggle_button.js

odoo.define('chatbot_whatsapp.toggle_button', function (require) {
    "use strict";

    console.log("✅ [Chatbot] Archivo chatbot_toggle_button.js cargado con odoo.define.");

    const { patch } = require("@web/core/utils/patch");
    // La siguiente línea puede fallar si el módulo 'mail' no está listo.
    // odoo.define se asegura de que espere.
    const { ThreadView } = require('@mail/views/thread_view/thread_view');
    const { onPatched, onMounted } = require("@odoo/owl");

    patch(ThreadView.prototype, 'chatbot_whatsapp.ThreadView.ToggleButton', {
    
        setup() {
            this._super(...arguments);
            console.log("⏳ [Chatbot] setup del parche ejecutado.");

            onPatched(() => {
                this.addChatbotButton();
            });
    
            onMounted(() => {
                this.addChatbotButton();
            });
        },
    
        addChatbotButton() {
            const buttonSelector = '.o_chatbot_button';
            const targetContainerSelector = '.o-mail-Discuss-headerActions';
    
            if (this.el.querySelector(buttonSelector)) {
                return;
            }
    
            const targetContainer = this.el.querySelector(targetContainerSelector);
            
            if (targetContainer) {
                console.log("🔥 [Chatbot] Contenedor encontrado. Creando botón...");
                
                const chatbotButton = document.createElement('button');
                chatbotButton.className = 'o_ThreadView_action btn btn-link o_chatbot_button';
                chatbotButton.title = 'Prueba Chatbot';
                chatbotButton.setAttribute('aria-label', 'Prueba Chatbot');
                
                const icon = document.createElement('i');
                icon.className = 'fa fa-bug fa-fw';
                icon.setAttribute('role', 'img');
                chatbotButton.appendChild(icon);
    
                chatbotButton.addEventListener('click', this.onClickCustomButton.bind(this));
    
                targetContainer.prepend(chatbotButton);
            }
        },
    
        onClickCustomButton() {
            alert("¡CLIC DETECTADO!");
            console.log("Datos del hilo actual:", this.thread);
        },
    });
});