/** @odoo-module */

import { patch } from "@web/core/utils/patch";
import { FormController } from "@web/views/form/form_controller";
import { onMounted, onPatched } from "@odoo/owl";

const originalSetup = FormController.prototype.setup;

patch(FormController.prototype, {
    setup() {
        originalSetup.apply(this, arguments);
        // ✅ Ya no necesitamos useRef. Los hooks se encargarán de llamar al render.
        onMounted(() => this._renderChatbotButton());
        onPatched(() => this._renderChatbotButton());
    },

    async _renderChatbotButton() {
        // ✅ Usamos this.el.querySelector para encontrar el div.
        const container = this.el.querySelector('#chatbot_toggle_container');

        if (!this.model.root || !this.model.root.data) {
             return;
        }

        if (!container || this.model.root.resModel !== 'discuss.channel' || this.model.root.data.channel_type !== 'whatsapp') {
            if (container) {
                container.innerHTML = "";
            }
            return;
        }
        
        const channelId = this.model.root.resId;
        if (!channelId) {
            container.innerHTML = "";
            return;
        }

        container.innerHTML = '<i class="fa fa-spinner fa-spin"/>';

        const result = await this.env.services.rpc({
            model: 'discuss.channel',
            method: 'get_chatbot_status',
            args: [channelId],
        });

        // Verificamos de nuevo el contenedor porque el DOM pudo haber cambiado.
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
        });
    },
});