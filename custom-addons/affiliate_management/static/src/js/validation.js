/** @odoo-module **/

import publicWidget from "@web/legacy/js/public/public_widget";
import { rpc } from "@web/core/network/rpc";

publicWidget.registry.AffiliateWebsite = publicWidget.Widget.extend({
            selector: '.container, .affiliate_banner, .oe_signup_form, #aff_link_gen_div',

            events: {
              'click #cpy_cde': '_copyReferralCode',
              'click #cpy_url': '_copyReferralUrl',
              'click #url_anchor': '_showReferralLink',
              'click #code_anchor': '_showReferralCode',
              'click #link_copy_button': '_copyProductLink',
              'click [id^=copy-btn_]': '_copyProductPageAffiliateLink',
              'click #banner_copy_button': '_copyProductBanner',
              'click #join-btn': '_joinNewAffiliate',
              'click [id^=yes_btn_uid_]': '_joinExistingUserAffiliate',
              'click .o_form_radio': '_displayBannerImage',
              'click .o_form_radio_product': '_displayProductBannerImage',
              'click .signup-btn': '_displayTandCError',  
            },

            init: function () {
                this._super.apply(this, arguments);
                this.input = {};
                this.clicked = false;
                this.orm = this.bindService("orm");
                
                $( ".button_image_generate_url" ).hide();

                document.onclick = function(e){
                  var aff_link_gen_div = document.getElementById('aff_link_gen_div');
                  if(aff_link_gen_div != undefined){
                    if(! aff_link_gen_div.contains(e.target)) {
                      $('#link-card-wrapper').fadeOut(100);
                    }
                    else{
                      if($(e.target)[0] === $('span#check_label2')[0] || $(e.target)[0] === $('i.fa-caret-up')[0]){
                          if($('#link-card-wrapper').css('display') != 'none') {
                            $('#link-card-wrapper').fadeOut(100);
                          }
                          else{
                              $('#link-card-wrapper').fadeIn(100);
                              var page_url = new URL(window.location);
                              page_url.searchParams.set('aff_key', `${$('span#aff_key').text()}`);
                              page_url.searchParams.set('db', `${$('span#db_name').text()}`);
                              var aff_url = page_url.toString();
                              $('input#usr_aff_url').val(aff_url);
                          }
                      }
                      else{
                        $('#link-card-wrapper').fadeIn(100);
                      }
                    }
                  }
                }
            },

            isValidEmailAddress: function(emailAddress) {
                // var pattern = /^([a-z\d!#$%&'*+\-\/=?^_`{|}~\u00A0-\uD7FF\uF900-\uFDCF\uFDF0-\uFFEF]+(\.[a-z\d!#$%&'*+\-\/=?^_`{|}~\u00A0-\uD7FF\uF900-\uFDCF\uFDF0-\uFFEF]+)*|"((([ \t]*\r\n)?[ \t]+)?([\x01-\x08\x0b\x0c\x0e-\x1f\x7f\x21\x23-\x5b\x5d-\x7e\u00A0-\uD7FF\uF900-\uFDCF\uFDF0-\uFFEF]|\\[\x01-\x09\x0b\x0c\x0d-\x7f\u00A0-\uD7FF\uF900-\uFDCF\uFDF0-\uFFEF]))*(([ \t]*\r\n)?[ \t]+)?")@(([a-z\d\u00A0-\uD7FF\uF900-\uFDCF\uFDF0-\uFFEF]|[a-z\d\u00A0-\uD7FF\uF900-\uFDCF\uFDF0-\uFFEF][a-z\d\-._~\u00A0-\uD7FF\uF900-\uFDCF\uFDF0-\uFFEF]*[a-z\d\u00A0-\uD7FF\uF900-\uFDCF\uFDF0-\uFFEF])\.)+([a-z\u00A0-\uD7FF\uF900-\uFDCF\uFDF0-\uFFEF]|[a-z\u00A0-\uD7FF\uF900-\uFDCF\uFDF0-\uFFEF][a-z\d\-._~\u00A0-\uD7FF\uF900-\uFDCF\uFDF0-\uFFEF]*[a-z\u00A0-\uD7FF\uF900-\uFDCF\uFDF0-\uFFEF])\.?$/i;
                var pattern = /^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,63}$/i;
                return pattern.test(emailAddress);
            },

            _joinNewAffiliate: function(e) {
                e.preventDefault();
                let email = $('#register_login').val();
                if (this.isValidEmailAddress(email)){
                    $('.affiliate_loader').show();
                    rpc("/affiliate/join", {'email': email}).then(function (result){
                      if (result){
                          console.log(result);
                          $(".aff_box").replaceWith(
                            "<div class='alert_msg_banner_signup' style='margin-top:10px;'>\
                            <center>\
                              <span style='color:white'>\
                                <img src='/affiliate_management/static/src/img/Icon_tick.png' />&nbsp;<span>"+result+"</span>\
                              </span>\
                              </center>\
                            </div>\
                            <br/>\
                            <div id='aff_req_btn'>\
                              <center>\
                                <a href='/shop' class='btn btn-success' style='width:180px;height:37px;' >Continue Shopping</a>\
                              </center>\
                            </div>");
                      }
                    });
                    $('.affiliate_loader').hide();
                }else{
                  console.log("wrong email");
                  alert("Invalid Email type");
                }
            },

            _joinExistingUserAffiliate: function (e) {
                e.preventDefault();
                let self = e.currentTarget;
                var uid = self.id.split("_")[3];
                rpc("/affiliate/request", {'user_id': uid}).then(function (result){
                  console.log(result);
                  if(result) {
                      $("#aff_req_btn").hide();
                      $(".alert_msg_banner").show();
                  }
                  else {

                  }
                });
            },

            _displayTandCError: function(e) {
                let c = $('#tc-signup-checkbox').is(':checked');
                console.log(c);
                if(c == false) {
                    e.preventDefault();
                    $('#term_condition_error').show();
                }
            },

            _copyReferralCode: function(e) {
                e.preventDefault();
                let self = $(e.currentTarget);
                // console.log("start");
                $("#usr_aff_code").select();
                self.text('Copied');
                setTimeout(function() {
                    $("#cpy_cde").html("<i class='fa fa-copy' />&nbsp;Copy");
                    window.getSelection().removeAllRanges();
                    $("#usr_aff_code").blur();              
                }, 2000);
                document.execCommand('copy');
            },

            _copyReferralUrl: function(e) {
                e.preventDefault();
                let self = $(e.currentTarget);
                $("#usr_aff_url").select();
                self.text('Copied');
                setTimeout(function() {
                    $("#cpy_url").html("<i class='fa fa-copy' />&nbsp;Copy");
                    window.getSelection().removeAllRanges();
                    $("#usr_aff_url").blur();              
                }, 2000);
                document.execCommand('copy');
            },

            _showReferralLink: function(e) {
                e.preventDefault();
                $("#affiliate_url_inp").show();
                $("#affiliate_code_inp").hide();
            },

            _showReferralCode: function(e) {
                e.preventDefault();
                $("#affiliate_url_inp").hide();
                $("#affiliate_code_inp").show();
            },

            _copyProductLink: function(e) {
                e.preventDefault();
                let self = $(e.currentTarget);
                self.text('Copied');
                setTimeout(function() {
                    self.text('Copy');
                }, 2000);
                $("#copy_link").show();
                $("#copy_link").select();
                document.execCommand('copy');
                $("#copy_link").hide();
            },

            _copyProductPageAffiliateLink: function(e) {
                e.preventDefault();
                let self = e.currentTarget;
                this.input = $("#copy-me_"+self.id.split("_")[1]);
                console.log("input",this.input)
                this._copyToClipboard();
                $('[id^=copy-btn_]').text('Copy to Clipboard')
                $(self).text('Copied');
                setTimeout(function() {
                    $(self).text('Copy to Clipboard');
                }, 2000);
            },


            _copyToClipboard: function() {
                var success   = true,
                      range     = document.createRange(),
                      selection;
              
                // For IE.
                if (window.clipboardData) {
                  console.log("clipboard")
                  window.clipboardData.setData("Text", this.input.val());
                } else {
                  // Create a temporary element off screen.
                  var tmpElem = $('<div>');
                  tmpElem.css({
                    position: "absolute",
                    left:     "-1000px",
                    top:      "-1000px",
                  });
                  // Add the input value to the temp element.
                  tmpElem.text(this.input.val());
                  console.log("tmpElem",tmpElem)
                  $("body").append(tmpElem);
                  // Select temp element.
                  range.selectNodeContents(tmpElem.get(0));
                  console.log("range",range)
                  selection = window.getSelection ();
                  selection.removeAllRanges ();
                  console.log("remove range")
                  selection.addRange (range);
                  // Lets copy.
                  try {
                    success = document.execCommand ("copy", false, null);
                  }
                  catch (e) {
                    copyToClipboardFF(this.input.val());
                  }
                  if (success) {
                    // alert ("The text is on the clipboard, try to paste it!");
                    // remove temp element.
                    tmpElem.remove();
                  }
                }
              },

              _copyProductBanner: function(e) {
                  e.preventDefault();
                  let self = $(e.currentTarget);
                  $("#banner_html_code").select();
                  document.execCommand('copy');
                  self.text('Copied');
                  setTimeout(function() {
                      self.text('Copy');
                      $("#banner_html_code").blur();
                  }, 2000);
                  if (this.clicked == false) {
                        $('#step3').replaceWith("<span class='step1'>&#10003;</span>");
                        this.clicked = true;
                  }
              },

              _displayBannerImage: function(e) {
                  let self = e.currentTarget;
                  $('[id^=product-text_]').hide();
                  console.log(self.getAttribute('id').split("_")[1])
                  let radio_id = self.getAttribute('id').split("_")[1];
                  $( ".button_image_generate_url" ).hide();
                  $('#image_'+radio_id).show();
              },


              _displayProductBannerImage: function(e) {
                  let self = e.currentTarget;
                  $(".button_image_generate_url").hide();
                  let product_text_id =$("#product-text_"+self.id.split("_")[1]);
                  $(product_text_id).show();
                  $( ".product_image" ).show();
              },
              
              

});

export default {
    AffiliateWebsite: publicWidget.registry.AffiliateWebsite,
};
