/** @odoo-module **/
import { patch } from "@web/core/utils/patch";
import { ThreadContainer } from "@mail/core/common/thread_container";
import { onMounted, onPatched, onWillUpdateProps } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";

patch(ThreadContainer.prototype, {
    setup() {
        super.setup(...arguments);
        this.rpc = useService("rpc");
        this.notification = useService("notification");

        // Estos "hooks" se aseguran de que el botón se actualice
        // cuando el chat se carga, se actualiza o cambiamos de conversación.
        onMounted(() => this._renderChatbotButton());
        onPatched(() => this._renderChatbotButton());
        onWillUpdateProps(() => this._renderChatbotButton());
    },

    // Dibuja el botón dinámicamente
    async _renderChatbotButton() {
        const container = this.root.el?.querySelector('#chatbot_toggle_container');
        const thread = this.props.thread;

        // Si no hay contenedor o no estamos en un canal de whatsapp, no hacemos nada.
        if (!container || thread?.type !== 'channel' || !thread.id) {
            if (container) container.innerHTML = ""; // Limpiamos por si quedó de otra vista
            return;
        }

        // Mostramos un spinner mientras cargamos el estado
        container.innerHTML = '<i class="fa fa-spinner fa-spin"/>';

        try {
            const result = await this.rpc({
                model: 'discuss.channel',
                method: 'get_chatbot_status',
                args: [thread.id],
            });

            const isPaused = result.status === 'paused';
            const button = document.createElement("button");
            
            button.className = `btn btn-sm ${isPaused ? "btn-success" : "btn-warning"}`;
            button.innerHTML = `<i class="fa ${isPaused ? "fa-play" : "fa-pause"} me-1"></i> ${isPaused ? _t("Reanudar") : _t("Pausar")}`;
            
            button.onclick = () => this._onToggleChatbotClick(isPaused, thread.id);
            
            // Reemplazamos el spinner con el botón
            container.innerHTML = "";
            container.appendChild(button);

        } catch (error) {
            console.error("Error al obtener estado del chatbot:", error);
            container.innerHTML = '<i class="fa fa-exclamation-triangle text-danger" title="Error"></i>';
        }
    },

    // Maneja el evento de clic
    async _onToggleChatbotClick(wasPaused, channelId) {
        const container = this.root.el?.querySelector('#chatbot_toggle_container');
        if (container) {
            container.innerHTML = '<i class="fa fa-spinner fa-spin"/>';
        }

        const methodToCall = wasPaused ? 'action_resume_chatbot' : 'action_pause_chatbot';

        try {
            await this.rpc({
                model: 'discuss.channel',
                method: methodToCall,
                // Los métodos de Odoo esperan una lista de IDs
                args: [[channelId]],
            });
            this.notification.add(_t("Estado del chatbot actualizado"), { type: 'success' });
            // Forzamos un re-dibujado para que se actualice el botón
            await this._renderChatbotButton();
        } catch (error) {
            this.notification.add(_t("Fallo al actualizar el estado"), { type: 'danger' });
            await this._renderChatbotButton(); // Re-dibujamos incluso si hay error
        }
    },
});