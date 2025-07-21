/** @odoo-module **/

import { Component, onWillUpdateProps, onMounted, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { registry } from "@web/core/registry";

class ChatbotToggleButton extends Component {
    static template = "chatbot_whatsapp.ChatbotToggleButton";
    static props = {
        thread: { type: Object },
        class: { type: String, optional: true },
    };

    setup() {
        this.rpc = useService("rpc");
        this.state = useState({ status: "loading" }); // loading, active, paused, error, hidden

        onMounted(() => this.fetchStatus(this.props.thread));
        onWillUpdateProps(async (nextProps) => {
            if (this.props.thread.id !== nextProps.thread.id) {
                await this.fetchStatus(nextProps.thread);
            }
        });
    }

    async fetchStatus(thread) {
        // Solo mostramos el botón en canales de WhatsApp
        if (thread?.type !== 'channel' || !thread.id) {
            this.state.status = "hidden";
            return;
        }
        
        this.state.status = "loading";
        try {
            const result = await this.rpc({
                model: 'discuss.channel',
                method: 'get_chatbot_status',
                args: [thread.id],
            });
            this.state.status = result.status; // Espera 'active' o 'paused'
        } catch (e) {
            console.error("Error al obtener estado del chatbot:", e);
            this.state.status = "error";
        }
    }

    async onToggleClick() {
        const threadId = this.props.thread.id;
        const method = this.state.status === 'paused' ? 'action_resume_chatbot' : 'action_pause_chatbot';
        this.state.status = "loading";
        try {
            await this.rpc({
                model: 'discuss.channel',
                method: method,
                args: [threadId],
            });
            await this.fetchStatus(this.props.thread); // Refresca el estado
        } catch (e) {
             console.error("Error al cambiar estado del chatbot:", e);
             this.state.status = "error";
        }
    }
}

// Registramos el componente para que Odoo lo reconozca
registry.category("components").add("ChatbotToggleButton", ChatbotToggleButton);