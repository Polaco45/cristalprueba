///** @odoo-module **/
//
//import { _t } from '@web/core/l10n/translation';
//import paymentForm from '@payment/js/payment_form';
//
//paymentForm.include({
//async _submitForm(ev) {
//        ev.stopPropagation();
//        ev.preventDefault();
//        const isValid = await this.rpc("/shop/sale_price", {
//            });
//
//           if(isValid == false){
//                this._getSubmitButton().setAttribute('disabled', true);
//                }
//           else{
//            const checkedRadio = this.el.querySelector('input[name="o_payment_radio"]:checked');
//
//            // Block the entire UI to prevent fiddling with other widgets.
//            this._disableButton(true);
//
//            // Initiate the payment flow of the selected payment option.
//            const flow = this.paymentContext.flow = this._getPaymentFlow(checkedRadio);
//            const paymentOptionId = this.paymentContext.paymentOptionId = this._getPaymentOptionId(
//                checkedRadio
//            );
//            if (flow === 'token' && this.paymentContext['assignTokenRoute']) { // Assign token flow.
//                await this._assignToken(paymentOptionId);
//            } else { // Both tokens and payment methods must process a payment operation.
//                const providerCode = this.paymentContext.providerCode = this._getProviderCode(
//                    checkedRadio
//                );
//                const pmCode = this.paymentContext.paymentMethodCode = this._getPaymentMethodCode(
//                    checkedRadio
//                );
//                this.paymentContext.providerId = this._getProviderId(checkedRadio);
//                if (this._getPaymentOptionType(checkedRadio) === 'token') {
//                    this.paymentContext.tokenId = paymentOptionId;
//                } else { // 'payment_method'
//                    this.paymentContext.paymentMethodId = paymentOptionId;
//                }
//                const inlineForm = this._getInlineForm(checkedRadio);
//                this.paymentContext.tokenizationRequested = inlineForm?.querySelector(
//                    '[name="o_payment_tokenize_checkbox"]'
//                )?.checked ?? this.paymentContext['mode'] === 'validation';
//                await this._initiatePaymentFlow(providerCode, paymentOptionId, pmCode, flow);
//            }
//            }
//        }
//});


/** @odoo-module **/

import { _t } from '@web/core/l10n/translation';
import paymentForm from '@payment/js/payment_form';
import { rpc } from '@web/core/network/rpc';

paymentForm.include({
    async _submitForm(ev) {
        ev.stopPropagation();
        ev.preventDefault();

        const isValid = await rpc("/shop/sale_price", {});

        if (isValid === false) {
            this._getSubmitButton().setAttribute('disabled', true);
        } else {
            const checkedRadio = this.el.querySelector('input[name="o_payment_radio"]:checked');

            this._disableButton(true);

            const flow = this.paymentContext.flow = this._getPaymentFlow(checkedRadio);
            const paymentOptionId = this.paymentContext.paymentOptionId = this._getPaymentOptionId(
                checkedRadio
            );

            if (flow === 'token' && this.paymentContext['assignTokenRoute']) {
                await this._assignToken(paymentOptionId);
            } else {
                const providerCode = this.paymentContext.providerCode = this._getProviderCode(checkedRadio);
                const pmCode = this.paymentContext.paymentMethodCode = this._getPaymentMethodCode(checkedRadio);
                this.paymentContext.providerId = this._getProviderId(checkedRadio);

                if (this._getPaymentOptionType(checkedRadio) === 'token') {
                    this.paymentContext.tokenId = paymentOptionId;
                } else {
                    this.paymentContext.paymentMethodId = paymentOptionId;
                }

                const inlineForm = this._getInlineForm(checkedRadio);
                this.paymentContext.tokenizationRequested = inlineForm?.querySelector(
                    '[name="o_payment_tokenize_checkbox"]'
                )?.checked ?? this.paymentContext['mode'] === 'validation';

                await this._initiatePaymentFlow(providerCode, paymentOptionId, pmCode, flow);
            }
        }
    }
});
