{
    'name': 'POS Invoice Journal Multiple Choice',
    'version': '18.0.1.0',
    'summary': 'multi-journal pos, allows the selection of multiple invoice journals in POS and the setting of a default journal.',
    'description': """
POS Invoice Journal Multiple Choice
========================
This module enables the selection of multiple journals for Point of Sale (POS) transactions and allows the configuration of a default journal in the POS. Users can choose between different accounting journals when processing transactions in the POS, providing flexibility for businesses that manage multiple journals for different purposes.

Key Features:
--------------
- Configure multiple journals in POS settings.
- Choose a default journal for transactions in the POS.
- Ensure that each sale transaction is assigned to the correct journal.
- Useful for businesses that need to manage different journals for sales, invoices, or other financial operations in their POS.

""",
    'author': 'KENDATEC',
    'website': 'https://kendatec.com',
    'category': 'Point of Sale',
    'license': 'AGPL-3',
    'price': 20,
    'currency': 'USD',
    'depends': ['base_setup','point_of_sale', 'account'],
    'data': [
        'views/res_config_settings_views.xml',
        'views/pos_order_view.xml',
    ],
    'images': [
        'static/description/images/banner_multi_journal.png'
    ],
    "assets": {
       'point_of_sale._assets_pos': [
            "pos_journal_multi_choice/static/src/js/core/PosOrder.js",
            "pos_journal_multi_choice/static/src/js/Screens/Payment/PaymentScreen.js",
            "pos_journal_multi_choice/static/src/xml/Screens/PaymentScreen.xml",  
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
    'support': 'soporte@kendatec.com',
    'maintainer': 'KENDATEC',
}
