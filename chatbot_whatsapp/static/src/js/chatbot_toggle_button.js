/** @odoo-module **/
import { patch } from "@web/core/utils/patch";
// 🎯 Correct import:
import { Discuss } from "@mail/core/public_web/discuss";
import { onMounted, onPatched } from "@odoo/owl";

// Parcheamos el componente correcto
patch(Discuss.prototype, {
    setup() {
        // La sintaxis de setup es ligeramente diferente en componentes OWL puros
        super.setup(...arguments);
        onMounted(() => this._renderChatbotButton());
        onPatched(() => this._renderChatbotButton());
    },

    async _renderChatbotButton() {
        if (!this.el) return;

        const container = this.el.querySelector('#chatbot_toggle_container');
        
        // La forma de obtener el canal activo es a través de this.thread
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
        
        // El resto de la lógica es prácticamente idéntica
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