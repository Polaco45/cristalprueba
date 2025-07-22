/** @odoo-module **/

// CHIVATO 1: ¿Se está cargando este archivo?
console.log("✅ [Chatbot] Archivo discuss_extend.js CARGADO.");

import { ThreadView } from "@mail/views/thread_view/thread_view";
import { patch } from "@web/core/utils/patch";

// CHIVATO 2: ¿Llega el código hasta aquí?
console.log("⏳ [Chatbot] Intentando aplicar parche a ThreadView...");

// La palabra 'debugger' pausará la ejecución del navegador aquí.
// Si las herramientas de desarrollador están abiertas, el código se detendrá
// y podrás ver si hay algún problema. Si no se detiene, el archivo ni siquiera se ejecuta.
debugger;

patch(ThreadView.prototype, 'chatbot_whatsapp.ThreadView', {

    /**
     * Nuestra nueva función que será llamada por el botón.
     */
    onClickCustomButton() {
        // CHIVATO 3: ¿Se ejecuta la función al hacer clic?
        alert("¡CLIC DETECTADO!");
        console.log("🔥 [Chatbot] ¡El botón funciona! La función onClickCustomButton se ha ejecutado.");
        console.log("Datos del hilo actual:", this.thread);
    },

});

// CHIVATO 4: ¿Se completó la definición del parche sin errores?
console.log("👍 [Chatbot] Parche para ThreadView definido con éxito.");