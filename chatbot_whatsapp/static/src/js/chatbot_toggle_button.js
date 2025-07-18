/** @odoo-module */
import { FormController } from "@web/views/form/form_controller";
import { patch } from "@web/core/utils/patch";
import { rpc } from "web.rpc";

// 1) Guardamos el método original:
const originalUpdate = FormController.prototype._update;

patch(FormController.prototype, "chatbot_whatsapp.ChatbotToggleButtonPatch", {
    // 2) Reemplazamos sólo _update, invocando el original manualmente:
    async _update(...args) {
        // Llamamos al update original
        await originalUpdate.apply(this, args);

        // Tu lógica para mostrar el botón
        if (this.modelName !== 'discuss.channel'
            || this.renderer.state?.data?.channel_type !== 'whatsapp') {
            return;
        }
        const container = this.el.querySelector('#chatbot_toggle_container');
        if (!container) {
            return;
        }
        this.channelId = this.renderer.state.res_id;
        this._renderChatbotButton(container);
    },

    // 3) Movemos la lógica de render dentro del mismo patch
    _renderChatbotButton(container) {
        container.innerHTML = '';
        rpc.query({
            model: 'discuss.channel',
            method: 'get_chatbot_status',
            args: [this.channelId],
        }).then(result => {
            const paused = result.status === 'paused';
            const btn = document.createElement('button');
            btn.className = `btn btn-sm ${paused ? 'btn-success' : 'btn-warning'}`;
            btn.innerHTML = `<i class="fa ${paused ? 'fa-play' : 'fa-pause'}"></i> `
                          + (paused ? 'Reanudar Chatbot' : 'Pausar Chatbot');
            btn.addEventListener('click', () => this._onToggleClick(paused, container));
            container.appendChild(btn);
        });
    },

    _onToggleClick(wasPaused, container) {
        container.innerHTML = '<i class="fa fa-spinner fa-spin"></i>';
        rpc.query({
            model: 'discuss.channel',
            method: wasPaused ? 'action_resume_chatbot' : 'action_pause_chatbot',
            args: [this.channelId],
        }).then(() => this._renderChatbotButton(container));
    },
});
