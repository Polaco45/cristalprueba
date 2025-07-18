/** @odoo-module */
import { FormController } from "@web/views/form/form_controller";
import { patch } from "@web/core/utils/patch";
import { useService } from "@web/core/utils/hooks";

// 1) Conservamos los métodos originales
const _superSetup = FormController.prototype.setup;
const _superUpdate = FormController.prototype._update;

patch(FormController.prototype, "chatbot_whatsapp.ChatbotToggleButtonPatch", {
    /**
     * 2) Interceptamos setup para obtener el servicio RPC
     */
    setup(...args) {
        // Llamamos al setup original (si existe)
        _superSetup?.apply(this, args);
        // Inyectamos el servicio RPC
        this.rpc = useService("rpc");
    },

    /**
     * 3) Reemplazamos _update, llamando manualmente al original
     */
    async _update(...args) {
        await _superUpdate.apply(this, args);

        // Solo actuamos en canales WhatsApp
        const data = this.renderer.state?.data;
        if (this.modelName !== "discuss.channel"
            || !data
            || data.channel_type !== "whatsapp"
        ) {
            return;
        }

        const container = this.el.querySelector("#chatbot_toggle_container");
        if (!container) {
            return;
        }
        this.channelId = this.renderer.state.res_id;
        this._renderChatbotButton(container);
    },

    /**
     * 4) Renderizamos el botón llamando al RPC inyectado
     */
    _renderChatbotButton(container) {
        container.innerHTML = "";
        this.rpc
            .query({
                model: "discuss.channel",
                method: "get_chatbot_status",
                args: [this.channelId],
            })
            .then((result) => {
                const paused = result.status === "paused";
                const btn = document.createElement("button");
                btn.className = `btn btn-sm ${paused ? "btn-success" : "btn-warning"}`;
                btn.innerHTML = `<i class="fa ${paused ? "fa-play" : "fa-pause"}"></i> `
                              + (paused ? "Reanudar Chatbot" : "Pausar Chatbot");
                btn.addEventListener("click", () => {
                    this._onToggleClick(paused, container);
                });
                container.appendChild(btn);
            });
    },

    /**
     * 5) On‑click del toggle
     */
    _onToggleClick(wasPaused, container) {
        container.innerHTML = '<i class="fa fa-spinner fa-spin"></i>';
        this.rpc
            .query({
                model: "discuss.channel",
                method: wasPaused ? "action_resume_chatbot" : "action_pause_chatbot",
                args: [this.channelId],
            })
            .then(() => this._renderChatbotButton(container));
    },
});
