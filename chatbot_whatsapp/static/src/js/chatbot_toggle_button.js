/** @odoo-module */

import { patch } from "@web/core/utils/patch";
// 🎯 Importamos el nuevo componente 'Discuss' de Odoo 18
import { Discuss } from "@mail/core/common/discuss";
import { onMounted, onPatched } from "@odoo/owl";

patch(Discuss.prototype, {
    setup() {
        // Llamamos al setup original
        super.setup(...arguments);
        // Usamos los hooks para renderizar nuestro botón
        onMounted(() => this._renderChatbotButton());
        onPatched(() => this._renderChatbotButton());
    },

    async _renderChatbotButton() {
        // La lógica de búsqueda y renderizado es la misma
        const container = this.el.querySelector('#chatbot_toggle_container');

        // La forma de acceder al thread puede haber cambiado. 'this.thread' es lo más probable.
        if (!container || this.thread?.type !== 'channel') {
            if (container) container.innerHTML = "";
            return;
        }

        const channelId = this.thread.id;
        if (!channelId) {
            if (container) container.innerHTML = "";
            return;
        }

        container.innerHTML = '<i class="fa fa-spinner fa-spin"/>';

        const result = await this.env.services.rpc({
            model: 'discuss.channel',
            method: 'get_chatbot_status',
            args: [channelId],
        });
        
        const currentContainer = this.el.querySelector('#chatbot_toggle_container');
        if (!currentContainer) return;

        const isPaused = result.status === 'paused';
        const button = document.createElement("button");
        button.className = `btn btn-sm ${isPaused ? "btn-success" : "btn-warning"}`;
        button.innerHTML = `<i class="fa ${isPaused ? "fa-play" : "fa-pause"} me-1"></i> ${isPaused ? "Reanudar Chatbot" : "Pausar Chatbot"}`;

        button.addEventListener("click", () => {
            this._onToggleChatbotClick(isPaused, channelId);
        });
        
        currentContainer.innerHTML = "";
        currentContainer.appendChild(button);
    },

    _onToggleChatbotClick(wasPaused, channelId) {
        // Esta función no necesita cambios
        const container = this.el.querySelector('#chatbot_toggle_container');
        if (container) {
            container.innerHTML = '<i class="fa fa-spinner fa-spin"/>';
        }

        const methodToCall = wasPaused ? 'action_resume_chatbot' : 'action_pause_chatbot';

        this.env.services.rpc({
            model: 'discuss.channel',
            method: methodToCall,
            args: [channelId],
        }).then(() => {
            this._renderChatbotButton();
        });
    },
});