{
    'name': "POS Payment Reference Details",
    'version': '18.0.0.1',
    'depends': ['base', 'web', 'point_of_sale'],
    'author': "Yatrik Chauhan",
    'category': "Tools",
    'summary': 'The POS Payment Reference Validator module allows cashiers to enter and store payment reference details for card, UPI, and digital transactions in Odoo POS. It ensures secure payment validation, reduces fraud risks, and improves transaction tracking with an easy-to-toggle setting.',
    'description': """
       POS: Payment Reference Details module enhances the Odoo Point of Sale (POS) system by enabling cashiers and users to enter a payment reference when processing payments through card, UPI, or other digital payment providers. Odoo's default POS system lacks a built-in functionality to capture payment reference details, which is crucial for validating transactions. 
    """,
    'data': [
        'views/pos_payment_view.xml',
        'views/res_config_settings_view.xml',
    ],
    'price': 10,
    'currency': 'USD',
    "license": "LGPL-3",
    'live_test_url': 'https://youtu.be/D5CH3s4R6lY',
    'assets': {
        'point_of_sale._assets_pos': [
            'yc_pos_payment_ref/static/src/app/models/*.js',
            'yc_pos_payment_ref/static/src/app/screens/**/*.js',
            'yc_pos_payment_ref/static/src/app/screens/**/*.xml',
            'yc_pos_payment_ref/static/src/app/utils/**/*.js',
            'yc_pos_payment_ref/static/src/app/utils/**/*.xml',
            'yc_pos_payment_ref/static/src/css/*.css',
        ],
    },
    'images': ['static/description/banner.gif'],
    'installable': True,
    'application': True,
    'auto_install': False,
}
