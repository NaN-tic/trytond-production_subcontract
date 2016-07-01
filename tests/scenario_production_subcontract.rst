===================
Production Scenario
===================

=============
General Setup
=============

Imports::

    >>> import datetime
    >>> from dateutil.relativedelta import relativedelta
    >>> from decimal import Decimal
    >>> from proteus import config, Model, Wizard
    >>> today = datetime.date.today()
    >>> yesterday = today - relativedelta(days=1)

Create database::

    >>> config = config.set_trytond()
    >>> config.pool.test = True

Install production Module::

    >>> Module = Model.get('ir.module.module')
    >>> modules = Module.find([('name', '=', 'production_subcontract')])
    >>> Module.install([x.id for x in modules], config.context)
    >>> Wizard('ir.module.module.install_upgrade').execute('upgrade')

Create company::

    >>> Currency = Model.get('currency.currency')
    >>> CurrencyRate = Model.get('currency.currency.rate')
    >>> Company = Model.get('company.company')
    >>> Party = Model.get('party.party')
    >>> company_config = Wizard('company.company.config')
    >>> company_config.execute('company')
    >>> company = company_config.form
    >>> party = Party(name='Dunder Mifflin')
    >>> party.save()
    >>> company.party = party
    >>> currencies = Currency.find([('code', '=', 'USD')])
    >>> if not currencies:
    ...     currency = Currency(name='Euro', symbol=u'$', code='USD',
    ...         rounding=Decimal('0.01'), mon_grouping='[3, 3, 0]',
    ...         mon_decimal_point=',')
    ...     currency.save()
    ...     CurrencyRate(date=today + relativedelta(month=1, day=1),
    ...         rate=Decimal('1.0'), currency=currency).save()
    ... else:
    ...     currency, = currencies
    >>> company.currency = currency
    >>> company_config.execute('add')
    >>> company, = Company.find()

Reload the context::

    >>> User = Model.get('res.user')
    >>> config._context = User.get_preferences(True, config.context)

Create chart of accounts::

    >>> AccountTemplate = Model.get('account.account.template')
    >>> Account = Model.get('account.account')
    >>> AccountJournal = Model.get('account.journal')
    >>> account_template, = AccountTemplate.find([('parent', '=', None)])
    >>> create_chart = Wizard('account.create_chart')
    >>> create_chart.execute('account')
    >>> create_chart.form.account_template = account_template
    >>> create_chart.form.company = company
    >>> create_chart.execute('create_account')
    >>> receivable, = Account.find([
    ...         ('kind', '=', 'receivable'),
    ...         ('company', '=', company.id),
    ...         ])
    >>> payable, = Account.find([
    ...         ('kind', '=', 'payable'),
    ...         ('company', '=', company.id),
    ...         ])
    >>> revenue, = Account.find([
    ...         ('kind', '=', 'revenue'),
    ...         ('company', '=', company.id),
    ...         ])
    >>> expense, = Account.find([
    ...         ('kind', '=', 'expense'),
    ...         ('company', '=', company.id),
    ...         ])
    >>> create_chart.form.account_receivable = receivable
    >>> create_chart.form.account_payable = payable
    >>> create_chart.execute('create_properties')


Create payment term::

    >>> PaymentTerm = Model.get('account.invoice.payment_term')
    >>> PaymentTermLine = Model.get('account.invoice.payment_term.line')
    >>> payment_term = PaymentTerm(name='Direct')
    >>> payment_term_line = PaymentTermLine(type='remainder', days=0)
    >>> payment_term.lines.append(payment_term_line)
    >>> payment_term.save()

Create supplier warehouse::

    >>> Location = Model.get('stock.location')
    >>> supplier_storage = Location(name='Supplier Storage', type='storage')
    >>> supplier_storage.save()
    >>> supplier_input = Location(name='Supplier Input', type='storage')
    >>> supplier_input.save()
    >>> supplier_output = Location(name='Supplier Output', type='storage')
    >>> supplier_output.save()
    >>> supplier_production = Location(name='Supplier Production',
    ...     type='production')
    >>> supplier_production.save()
    >>> supplier_warehouse = Location()
    >>> supplier_warehouse.type = 'warehouse'
    >>> supplier_warehouse.name = 'Supplier Warehouse'
    >>> supplier_warehouse.storage_location = supplier_storage
    >>> supplier_warehouse.input_location = supplier_input
    >>> supplier_warehouse.output_location = supplier_output
    >>> supplier_warehouse.production_location  = supplier_production
    >>> supplier_warehouse.save()

Create supplier::

    >>> Party = Model.get('party.party')
    >>> party = Party(name='Supplier')
    >>> party.production_warehouse = supplier_warehouse
    >>> party.save()

Create product::

    >>> ProductUom = Model.get('product.uom')
    >>> unit, = ProductUom.find([('name', '=', 'Unit')])
    >>> ProductTemplate = Model.get('product.template')
    >>> Product = Model.get('product.product')
    >>> product = Product()
    >>> template = ProductTemplate()
    >>> template.name = 'product'
    >>> template.default_uom = unit
    >>> template.type = 'goods'
    >>> template.list_price = Decimal(30)
    >>> template.cost_price = Decimal(20)
    >>> template.save()
    >>> product.template = template
    >>> product.save()

Create Components::

    >>> component1 = Product()
    >>> template1 = ProductTemplate()
    >>> template1.name = 'component 1'
    >>> template1.default_uom = unit
    >>> template1.type = 'goods'
    >>> template1.list_price = Decimal(5)
    >>> template1.cost_price = Decimal(1)
    >>> template1.save()
    >>> component1.template = template1
    >>> component1.save()

    >>> meter, = ProductUom.find([('name', '=', 'Meter')])
    >>> centimeter, = ProductUom.find([('name', '=', 'centimeter')])
    >>> component2 = Product()
    >>> template2 = ProductTemplate()
    >>> template2.name = 'component 2'
    >>> template2.default_uom = meter
    >>> template2.type = 'goods'
    >>> template2.list_price = Decimal(7)
    >>> template2.cost_price = Decimal(5)
    >>> template2.save()
    >>> component2.template = template2
    >>> component2.save()

Create Subcontract Product::

    >>> subcontract = Product()
    >>> stemplate = ProductTemplate()
    >>> stemplate.name = 'Subcontract'
    >>> stemplate.default_uom = unit
    >>> stemplate.type = 'service'
    >>> stemplate.purchasable = True
    >>> stemplate.account_expense = expense
    >>> stemplate.account_revenue = revenue
    >>> stemplate.list_price = Decimal(0)
    >>> stemplate.cost_price = Decimal(100)
    >>> stemplate.save()
    >>> subcontract.template = stemplate
    >>> subcontract.save()

Create Bill of Material::

    >>> BOM = Model.get('production.bom')
    >>> BOMInput = Model.get('production.bom.input')
    >>> BOMOutput = Model.get('production.bom.output')
    >>> bom = BOM(name='product', subcontract_product=subcontract)
    >>> input1 = BOMInput()
    >>> bom.inputs.append(input1)
    >>> input1.product = component1
    >>> input1.quantity = 5
    >>> input2 = BOMInput()
    >>> bom.inputs.append(input2)
    >>> input2.product = component2
    >>> input2.quantity = 150
    >>> input2.uom = centimeter
    >>> output = BOMOutput()
    >>> bom.outputs.append(output)
    >>> output.product = product
    >>> output.quantity = 1
    >>> bom.save()

    >>> ProductBom = Model.get('product.product-production.bom')
    >>> product.boms.append(ProductBom(bom=bom))
    >>> product.save()

Create an Inventory::

    >>> warehouse, = Location.find(['code', '=', 'WH'])
    >>> Inventory = Model.get('stock.inventory')
    >>> InventoryLine = Model.get('stock.inventory.line')
    >>> Location = Model.get('stock.location')
    >>> storage = warehouse.storage_location
    >>> inventory = Inventory()
    >>> inventory.location = storage
    >>> inventory_line1 = InventoryLine()
    >>> inventory.lines.append(inventory_line1)
    >>> inventory_line1.product = component1
    >>> inventory_line1.quantity = 20
    >>> inventory_line2 = InventoryLine()
    >>> inventory.lines.append(inventory_line2)
    >>> inventory_line2.product = component2
    >>> inventory_line2.quantity = 6
    >>> inventory.save()
    >>> Inventory.confirm([inventory.id], config.context)
    >>> inventory.state
    u'done'

Create a Supplier Inventory::

    >>> storage = supplier_warehouse.storage_location
    >>> inventory = Inventory()
    >>> inventory.location = storage
    >>> inventory_line1 = InventoryLine()
    >>> inventory.lines.append(inventory_line1)
    >>> inventory_line1.product = component1
    >>> inventory_line1.quantity = 20
    >>> inventory_line2 = InventoryLine()
    >>> inventory.lines.append(inventory_line2)
    >>> inventory_line2.product = component2
    >>> inventory_line2.quantity = 6
    >>> inventory_line3 = InventoryLine()
    >>> inventory.lines.append(inventory_line3)
    >>> inventory_line3.product = product
    >>> inventory_line3.quantity = 2
    >>> inventory.save()
    >>> Inventory.confirm([inventory.id], config.context)
    >>> inventory.state
    u'done'

Make a production::

    >>> Production = Model.get('production')
    >>> production = Production()
    >>> production.warehouse = warehouse
    >>> production.product = product
    >>> production.bom = bom
    >>> production.quantity = 2
    >>> sorted([i.quantity for i in production.inputs]) == [10, 300]
    True
    >>> output, = production.outputs
    >>> output.quantity == 2
    True
    >>> production.cost
    Decimal('25.0')
    >>> production.save()
    >>> Production.wait([production.id], config.context)
    >>> production.state
    u'waiting'
    >>> Production.assign_try([production.id], config.context)
    True
    >>> production.reload()
    >>> all(i.state == 'assigned' for i in production.inputs)
    True
    >>> Production.run([production.id], config.context)
    >>> production.reload()
    >>> all(i.state == 'done' for i in production.inputs)
    True
    >>> len(set(i.effective_date == today for i in production.inputs))
    1
    >>> Production.done([production.id], config.context)
    >>> production.reload()
    >>> output, = production.outputs
    >>> output.state
    u'done'
    >>> output.effective_date == production.effective_date
    True
    >>> config._context['locations'] = [warehouse.id]
    >>> product.reload()
    >>> product.quantity == 2
    True

Make a subcontract production::

    >>> Purchase = Model.get('purchase.purchase')
    >>> Internal = Model.get('stock.shipment.internal')
    >>> production = Production()
    >>> production.warehouse = warehouse
    >>> production.product = product
    >>> production.bom = bom
    >>> production.quantity = 2
    >>> sorted([i.quantity for i in production.inputs]) == [10, 300]
    True
    >>> output, = production.outputs
    >>> output.quantity == 2
    True
    >>> production.cost
    Decimal('25.0')
    >>> production.subcontract_product = subcontract
    >>> production.save()
    >>> Production.wait([production.id], config.context)
    >>> production.reload()
    >>> production.state
    u'waiting'
    >>> Production.create_purchase_request([production.id], config.context)
    >>> production.reload()
    >>> purchase_request = production.purchase_request
    >>> create_purchase = Wizard('purchase.request.create_purchase',
    ...     [purchase_request])
    >>> create_purchase.form.party = party
    >>> create_purchase.execute('start')
    >>> purchase_request.reload()
    >>> purchase = purchase_request.purchase
    >>> purchase.payment_term = payment_term
    >>> purchase.invoice_method = 'manual'
    >>> purchase.save()
    >>> Purchase.quote([purchase.id], config.context)
    >>> purchase.reload()
    >>> purchase.state
    u'quotation'
    >>> Purchase.confirm([purchase.id], config.context)
    >>> purchase.reload()
    >>> purchase.state
    u'confirmed'
    >>> Purchase.process([purchase.id], config.context)
    >>> purchase.reload()
    >>> purchase.state
    u'done'
    >>> production.reload()
    >>> production.incoming_shipment.id
    1
    >>> internal = production.incoming_shipment
    >>> Internal.wait([internal.id], config.context)
    >>> internal.reload()
    >>> internal.state
    u'waiting'
    >>> Internal.assign_try([internal.id], config.context)
    True
    >>> Internal.done([internal.id], config.context)
    >>> internal.reload()
    >>> internal.state
    u'done'
    >>> Production.assign_try([production.id], config.context)
    True
    >>> Production.run([production.id], config.context)
    >>> production.reload()
    >>> production.state
    u'running'
