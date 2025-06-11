import datetime
import unittest
from decimal import Decimal

from proteus import Model, Wizard
from trytond.modules.account.tests.tools import (create_chart,
                                                 create_fiscalyear,
                                                 get_accounts)
from trytond.modules.account_invoice.tests.tools import \
    set_fiscalyear_invoice_sequences
from trytond.modules.company.tests.tools import create_company, get_company
from trytond.tests.test_tryton import drop_db
from trytond.tests.tools import activate_modules


class Test(unittest.TestCase):

    def setUp(self):
        drop_db()
        super().setUp()

    def tearDown(self):
        drop_db()
        super().tearDown()

    def test(self):

        # Imports
        today = datetime.date.today()

        # Install module
        config = activate_modules('production_subcontract')

        # Create company
        _ = create_company()
        company = get_company()

        # Reload the context
        User = Model.get('res.user')
        config._context = User.get_preferences(True, config.context)

        # Create fiscal year
        fiscalyear = set_fiscalyear_invoice_sequences(
            create_fiscalyear(company))
        fiscalyear.click('create_period')

        # Create chart of accounts
        _ = create_chart(company)
        accounts = get_accounts(company)
        revenue = accounts['revenue']
        expense = accounts['expense']

        # Create supplier warehouse
        Location = Model.get('stock.location')
        supplier_storage = Location(name='Supplier Storage', type='storage')
        supplier_storage.save()
        supplier_input = Location(name='Supplier Input', type='storage')
        supplier_input.save()
        supplier_output = Location(name='Supplier Output', type='storage')
        supplier_output.save()
        supplier_lost_found = Location(name='Supplier Lost Foud',
                                       type='lost_found')
        supplier_lost_found.save()
        supplier_production = Location(name='Supplier Production',
                                       type='production')
        supplier_production.save()

        supplier_warehouse = Location()
        supplier_warehouse.type = 'warehouse'
        supplier_warehouse.name = 'Supplier Warehouse'
        supplier_warehouse.storage_location = supplier_storage
        supplier_warehouse.input_location = supplier_input
        supplier_warehouse.output_location = supplier_output
        supplier_warehouse.lost_found_location = supplier_lost_found
        supplier_warehouse.production_location = supplier_production
        supplier_warehouse.save()

        # Create supplier
        Party = Model.get('party.party')
        party = Party(name='Supplier')
        party.production_warehouse = supplier_warehouse
        party.save()

        # Create account category
        ProductCategory = Model.get('product.category')
        account_category = ProductCategory(name="Account Category")
        account_category.accounting = True
        account_category.account_expense = expense
        account_category.account_revenue = revenue
        account_category.save()

        # Create product
        ProductUom = Model.get('product.uom')
        unit, = ProductUom.find([('name', '=', 'Unit')])
        ProductTemplate = Model.get('product.template')
        Product = Model.get('product.product')
        product = Product()
        template = ProductTemplate()
        template.name = 'product'
        template.default_uom = unit
        template.type = 'goods'
        template.producible = True
        template.list_price = Decimal(30)
        template.save()
        product.template = template
        product.cost_price = Decimal(20)
        product.save()

        # Create Components
        component1 = Product()
        template1 = ProductTemplate()
        template1.name = 'component 1'
        template1.default_uom = unit
        template1.type = 'goods'
        template1.list_price = Decimal(5)
        template1.save()
        component1.template = template1
        component1.cost_price = Decimal(1)
        component1.save()
        meter, = ProductUom.find([('symbol', '=', 'm')])
        centimeter, = ProductUom.find([('symbol', '=', 'cm')])
        component2 = Product()
        template2 = ProductTemplate()
        template2.name = 'component 2'
        template2.default_uom = meter
        template2.type = 'goods'
        template2.list_price = Decimal(7)
        template2.save()
        component2.template = template2
        component2.cost_price = Decimal(5)
        component2.save()

        # Create Subcontract Product
        subcontract = Product()
        stemplate = ProductTemplate()
        stemplate.name = 'Subcontract'
        stemplate.default_uom = unit
        stemplate.type = 'service'
        stemplate.purchasable = True
        stemplate.account_category = account_category
        stemplate.list_price = Decimal(0)
        stemplate.save()
        subcontract.template = stemplate
        subcontract.cost_price = Decimal(100)
        subcontract.save()

        # Create Bill of Material
        BOM = Model.get('production.bom')
        BOMInput = Model.get('production.bom.input')
        BOMOutput = Model.get('production.bom.output')
        bom = BOM(name='product', subcontract_product=subcontract)
        input1 = BOMInput()
        bom.inputs.append(input1)
        input1.product = component1
        input1.quantity = 5
        input2 = BOMInput()
        bom.inputs.append(input2)
        input2.product = component2
        input2.quantity = 150
        input2.unit = centimeter
        output = BOMOutput()
        bom.outputs.append(output)
        output.product = product
        output.quantity = 1
        bom.save()
        ProductBom = Model.get('product.product-production.bom')
        product.boms.append(ProductBom(bom=bom))
        product.save()

        # Create an Inventory
        warehouse, = Location.find(['code', '=', 'WH'])
        Inventory = Model.get('stock.inventory')
        InventoryLine = Model.get('stock.inventory.line')
        Location = Model.get('stock.location')
        storage = warehouse.storage_location
        inventory = Inventory()
        inventory.location = storage
        inventory_line1 = InventoryLine()
        inventory.lines.append(inventory_line1)
        inventory_line1.product = component1
        inventory_line1.quantity = 20
        inventory_line2 = InventoryLine()
        inventory.lines.append(inventory_line2)
        inventory_line2.product = component2
        inventory_line2.quantity = 6
        inventory.save()
        Inventory.confirm([inventory.id], config.context)
        self.assertEqual(inventory.state, 'done')

        # Create a Supplier Inventory
        storage = supplier_warehouse.storage_location
        inventory = Inventory()
        inventory.location = storage
        inventory_line1 = InventoryLine()
        inventory.lines.append(inventory_line1)
        inventory_line1.product = component1
        inventory_line1.quantity = 20
        inventory_line2 = InventoryLine()
        inventory.lines.append(inventory_line2)
        inventory_line2.product = component2
        inventory_line2.quantity = 6
        inventory_line3 = InventoryLine()
        inventory.lines.append(inventory_line3)
        inventory_line3.product = product
        inventory_line3.quantity = 2
        inventory.save()
        Inventory.confirm([inventory.id], config.context)
        self.assertEqual(inventory.state, 'done')

        # Make a production
        Production = Model.get('production')
        production = Production()
        production.warehouse = warehouse
        production.product = product
        production.bom = bom
        production.quantity = 2
        self.assertEqual(
            sorted([i.quantity for i in production.inputs]), [10, 300])
        output, = production.outputs
        self.assertEqual(output.quantity, 2)
        production.save()
        self.assertEqual(production.cost, Decimal('25.0000'))
        Production.wait([production.id], config.context)
        self.assertEqual(production.state, 'waiting')
        Production.assign_try([production.id], config.context)
        production.reload()
        self.assertEqual(all(i.state == 'assigned' for i in production.inputs),
                         True)
        Production.run([production.id], config.context)
        production.reload()
        self.assertEqual(all(i.state == 'done' for i in production.inputs),
                         True)
        self.assertEqual(
            len(set(i.effective_date == today for i in production.inputs)), 1)
        Production.do([production.id], config.context)
        production.reload()
        output, = production.outputs
        self.assertEqual(output.state, 'done')
        self.assertEqual(output.effective_date, production.effective_date)
        config._context['locations'] = [warehouse.id]
        product.reload()

        # Make a subcontract production
        Purchase = Model.get('purchase.purchase')
        Internal = Model.get('stock.shipment.internal')
        production = Production()
        production.warehouse = warehouse
        production.product = product
        production.bom = bom
        production.quantity = 2
        self.assertEqual(
            sorted([i.quantity for i in production.inputs]), [10, 300])
        output, = production.outputs
        self.assertEqual(output.quantity, 2)
        production.subcontract_product = subcontract
        production.save()
        # production warehouse is our warehouse
        self.assertEqual(production.warehouse, warehouse)
        self.assertEqual(production.cost, Decimal('25.0000'))
        Production.wait([production.id], config.context)
        production.reload()
        self.assertEqual(production.state, 'waiting')
        Production.create_purchase_request([production.id], config.context)
        production.reload()
        purchase_request = production.purchase_request

        create_purchase = Wizard('purchase.request.create_purchase',
                                 [purchase_request])
        create_purchase.form.party = party
        create_purchase.execute('start')
        purchase_request.reload()
        purchase = purchase_request.purchase
        line = purchase.lines[0]
        line.unit_price = line.product.cost_price
        line.save()
        purchase.save()
        Purchase.quote([purchase.id], config.context)
        purchase.reload()
        self.assertEqual(production.cost, Decimal('225.0000'))
        self.assertEqual(purchase.state, 'quotation')
        Purchase.confirm([purchase.id], config.context)
        purchase.reload()
        self.assertEqual(purchase.state, 'processing')

        production.reload()
        # confirm purchase, replace production warehouse to supplier warehouse
        self.assertEqual(production.warehouse, supplier_warehouse)
        self.assertEqual(production.destination_warehouse, warehouse)
        self.assertEqual(production.incoming_shipment.id, 1)

        internal = production.incoming_shipment
        Internal.wait([internal.id], config.context)
        internal.reload()
        self.assertEqual(internal.state, 'waiting')
        Internal.assign_try([internal.id], config.context)
        Internal.do([internal.id], config.context)
        internal.reload()
        self.assertEqual(internal.state, 'done')
        Production.assign_try([production.id], config.context)
        Production.run([production.id], config.context)
        production.reload()
        self.assertEqual(production.state, 'running')
        Production.do([production.id], config.context)
        production.reload()
        self.assertEqual(production.state, 'done')
        output, = production.outputs
        self.assertEqual(output.unit_price, Decimal('112.5000'))
