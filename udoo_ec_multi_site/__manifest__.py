 {
     'name': 'Udoo Multi-Company Product',
     'category': 'Website/Website',
     'summary': 'Manage multichannel listing eCommerce product ...',
     'version': '1.0.2',
     'license': 'OPL-1',
     'author': 'Sveltware Solutions',
     'website': 'https://www.linkedin.com/in/sveltware',
     'live_test_url': 'https://omux.sveltware.com/web/login',
     'images': ['static/description/banner.png'],
-    'depends': [
-        'website_sale',
-    ],
+    'depends': [
+        'website_sale',
+        'product',           # necesario para product.pricelist
+        'website',           # para heredar multi.website.mixin
+    ],
     'data': [
         'security/ir.model.access.csv',
         'views/product_views.xml',
         'views/multi_website_product.xml',
         'wizard/multi_website_setter.xml',
+        'views/product_pricelist_views.xml',  # vista para website_ids en precios
     ],
     'assets': {
         'web.assets_backend': [
             'udoo_ec_multi_site/static/src/**/*',
         ],
     },
 }
