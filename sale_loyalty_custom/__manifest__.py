# -*- coding: utf-8 -*-
{
    'name': "Discounts & Loyalty with Customer Filters",

    'summary': """
        Effortlessly manage discounts, loyalty programs, customer-specific filters, and country-based free shipping with this advanced module.
    """,

    'description': """
        This module enhances Odoo's Discount & Loyalty features with customer-specific filters for targeted discounts, country-based free shipping rules, and seamless workflow integration. It helps businesses efficiently manage promotions and shipping policies. 
        Perfect for boosting sales and customer satisfaction with tailored solutions.
    """,

    'author': "EWall Solutions Pvt. Ltd.",
    'website': "http://www.ewallsolutions.com",
    'company': "EWall Solutions Pvt. Ltd.",

    'category': 'Website',
    'version': '18.0',
    'license': 'OPL-1',
    'support':'support@ewallsolutions.com',
    'currency':'USD',
    'price':'59.00',

    # any module necessary for this one to work correctly
    'depends': ['sale_loyalty','sale','sale_loyalty_delivery','loyalty','website_sale'],

    # always loaded
    'data': [
        'security/ir.model.access.csv',
        'views/loyalty_program_views.xml',
        'views/loyalty_rewards_views.xml',
        'views/res_partner.xml',
        'views/loyalty_customer_tier_views.xml',
        'views/website_sale_loyalty_template.xml'
    ],
    'images': ['static/description/banner.png'],
    'installable': True
}

