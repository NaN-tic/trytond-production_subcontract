# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.
from trytond.pool import Pool, PoolMeta
from trytond.model import Workflow, ModelView, fields
from trytond.wizard import Wizard, Button, StateAction, StateView
from trytond.pyson import Eval, Bool, PYSONEncoder
from trytond.transaction import Transaction

__all__ = ['Party', 'PurchaseRequest', 'BOM', 'Production',
    'ProductionSubcontractInternalStart', 'ProductionSubcontractInternal',
    'OpenShipmentInternal', 'Purchase']


class Party:
    __name__ = 'party.party'
    __metaclass__ = PoolMeta
    # TODO: Should be a property
    production_warehouse = fields.Property(fields.Many2One('stock.location',
            'Production Warehouse', domain=[
                ('type', '=', 'warehouse'),
                ]))


class PurchaseRequest:
    __name__ = 'purchase.request'
    __metaclass__ = PoolMeta

    @classmethod
    def get_origin(cls):
        Model = Pool().get('ir.model')
        res = super(PurchaseRequest, cls).get_origin()
        models = Model.search([
                ('model', '=', 'production'),
                ])
        for model in models:
            res.append([model.model, model.name])
        return res


class BOM:
    __name__ = 'production.bom'
    __metaclass__ = PoolMeta
    subcontract_product = fields.Many2One('product.product',
        'Subcontract Product',  domain=[
            ('purchasable', '=', True),
            ('type', '=', 'service'),
            ])

# TODO: Subcontract cost must be added to the cost of the production

class Production:
    __name__ = 'production'
    __metaclass__ = PoolMeta

    subcontract_product = fields.Many2One('product.product',
        'Subcontract Product',  domain=[
            ('purchasable', '=', True),
            ('type', '=', 'service'),
            ])
    purchase_request = fields.Many2One('purchase.request',
        'Purchase Request', readonly=True)
    incoming_shipment = fields.Many2One('stock.shipment.internal',
        'Incoming Shipment', readonly=True)
    destination_warehouse = fields.Many2One('stock.location',
        'Destination Warehouse', domain=[
            ('type', '=', 'warehouse'),
            ], readonly=True)
    supplier = fields.Function(fields.Many2One('party.party', 'Supplier'),
        'get_supplier', searcher='search_supplier')
    internal_moves = fields.Function(fields.One2Many('stock.move', None,
        'Internal Moves'), 'get_internal_moves')
    internal_shipments = fields.Function(fields.One2Many('stock.shipment.internal',
        None, 'Internal Shipments'), 'get_internal_shipments')

    @classmethod
    def __setup__(cls):
        super(Production, cls).__setup__()
        cls._buttons.update({
                'create_purchase_request': {
                    'invisible': ~(Eval('state').in_(['draft', 'waiting']) &
                        Bool(Eval('subcontract_product')) &
                        ~Bool(Eval('purchase_request'))),
                    'icon': 'tryton-go-home',
                    },
                'create_internal_shipment': {
                    'invisible': Eval('state').in_(['cancel', 'done']) |
                        ~(Bool(Eval('destination_warehouse'))),
                    'icon': 'tryton-go-home',
                    },
                })
        cls._error_messages.update({
                'no_subcontract_warehouse': ('The party "%s" has no production '
                    'location.'),
                'no_warehouse_production_location': ('The warehouse "%s" has '
                    'no production location.'),
                'no_incoming_shipment': ('The production "%s" has no incoming '
                    'shipment. You must process the purchase before the '
                    'production can be assigned.'),
                'internal_shipment_already_exists': (
                    'A Shipment Internal already exists for the production '
                    '\"%(production)s\".'),
                })

    def get_supplier(self, name):
        return (self.purchase_request.party.id if self.purchase_request and
            self.purchase_request.party else None)

    @classmethod
    def search_supplier(cls, name, clause):
        return [('purchase_request.party',) + tuple(clause[1:])]

    @classmethod
    def copy(cls, productions, default=None):
        if default is None:
            default = {}
        default['purchase_request'] = None
        default['incoming_shipment'] = None
        default['destination_warehouse'] = None
        return super(Production, cls).copy(productions, default)

    @classmethod
    @ModelView.button
    def create_purchase_request(cls, productions):
        for production in productions:
            if not production.subcontract_product:
                continue
            if not production.state in ('draft', 'waiting'):
                continue
            request = production._get_purchase_request()
            request.save()
            production.purchase_request = request
            production.save()

    @classmethod
    @ModelView.button
    def create_internal_shipment(cls, productions):
        cls.create_internal_shipments(productions)

    @classmethod
    @ModelView.button
    #@Workflow.transition('assigned')
    def assign_try(cls, productions):
        for p in productions:
            if p.purchase_request:
                if not p.incoming_shipment:
                    cls.raise_user_error('no_incoming_shipment', (
                        p.code,))
        return super(Production, cls).assign_try(productions)

    @classmethod
    @ModelView.button
    @Workflow.transition('done')
    def done(cls, productions):
        InternalShipment = Pool().get('stock.shipment.internal')
        super(Production, cls).done(productions)
        shipments = [x.incoming_shipment for x in productions if
            x.incoming_shipment]
        if shipments:
            InternalShipment.assign_try(shipments)

    def on_change_product(self):
        res = super(Production, self).on_change_product()
        if self.bom:
            res['subcontract_product'] = (self.bom.subcontract_product.id if
                self.bom.subcontract_product else None)
        return res

    def on_change_bom(self):
        res = super(Production, self).on_change_bom()
        if self.bom:
            res['subcontract_product'] = (self.bom.subcontract_product.id if
                self.bom.subcontract_product else None)
        return res

    def get_internal_moves(self, name):
        Move = Pool().get('stock.move')
        return [m.id for m in Move.search([('origin', 'in', [
            'stock.move,%s' % i.id for i in self.inputs])])]

    def get_internal_shipments(self, name):
        shipments = set()
        for move in self.internal_moves:
            shipments.add(move.shipment)
        return [s.id for s in shipments]

    def _get_purchase_request(self):
        PurchaseRequest = Pool().get('purchase.request')
        return PurchaseRequest(
            product=self.subcontract_product,
            company=self.company,
            uom=self.subcontract_product.default_uom,
            quantity=self.quantity,
            computed_quantity=self.quantity,
            warehouse=self.warehouse,
            origin=self,
            )

    @classmethod
    def _get_internal_shipment(cls, from_location, to_location, reference=None):
        ShipmentInternal = Pool().get('stock.shipment.internal')

        shipment = ShipmentInternal()
        shipment.reference = reference
        shipment.from_location = from_location
        shipment.to_location = to_location
        shipment.moves = []
        return shipment

    @classmethod
    def process_purchase_request(cls, productions):
        ShipmentInternal = Pool().get('stock.shipment.internal')

        for production in productions:
            if not (production.purchase_request and
                    production.purchase_request.purchase and
                    production.purchase_request.purchase.state in
                        ('processing', 'done')):
                continue
            if production.destination_warehouse:
                continue
            subcontract_warehouse = production._get_subcontract_warehouse()
            if not subcontract_warehouse:
                cls.raise_user_error('no_subcontract_warehouse', (
                    production.purchase_request.party.rec_name, ))
            production.destination_warehouse = production.warehouse
            production.warehouse = subcontract_warehouse
            if not production.warehouse.production_location:
                cls.raise_user_error('no_warehouse_production_location', (
                    production.warehouse.rec_name, ))
            production.location = production.warehouse.production_location

            from_location = production.warehouse.storage_location
            to_location = production.destination_warehouse.storage_location
            shipment = ShipmentInternal()
            shipment.from_location = from_location
            shipment.to_location = to_location
            shipment.moves = []
            for output in production.outputs:
                move = production._get_shipment_move(output,
                    from_location, to_location)
                shipment.moves.append(move)
            shipment.save()
            ShipmentInternal.wait([shipment])
            production.incoming_shipment = shipment

            storage_location = production.warehouse.storage_location
            production_location = production.warehouse.production_location
            for move in production.inputs:
                move.from_location = storage_location
                move.to_location = production_location
                move.save()
            for move in production.outputs:
                move.from_location = production_location
                move.to_location = storage_location
                move.save()
            production.save()

    def _get_shipment_move(self, move, from_location, to_location):
        Move = Pool().get('stock.move')
        return Move(
            from_location=from_location,
            to_location=to_location,
            product=move.product,
            # TODO: Support lots
            quantity=move.quantity,
            uom=move.uom,
            origin=move,
            )

    def _get_subcontract_warehouse(self):
        return self.purchase_request.party.production_warehouse

    @classmethod
    def compute_request(cls, product, warehouse, quantity, date, company):
        req = super(Production, cls).compute_request(product, warehouse, quantity, date, company)
        if req.bom:
            req.subcontract_product = req.bom.subcontract_product
        return req

    @classmethod
    def write(cls, *args):
        actions = iter(args)
        to_update = []
        for productions, values in zip(actions, actions):
            if 'outputs' in values:
                to_update.extend(productions)
        super(Production, cls).write(*args)
        if to_update:
            Production._sync_outputs_to_shipment(to_update)

    # TODO: Missing function to synchronize output production moves with
    # incoming internal shipment. Should emulate behaviour of ShipmentOut and
    # ShipmentIn where there is no direct linke between stock moves but are
    # calculated by product and quantities. See _sync_inventory_to_outgoing in
    # stock/shipment.py.
    @classmethod
    def _sync_outputs_to_shipment(cls, productions):
        pass

    @classmethod
    def create_internal_shipments(cls, productions):
        '''Create internal shipmets group by destination warehouse'''
        pool = Pool()
        ShipmentInternal = pool.get('stock.shipment.internal')
        Product = pool.get('product.product')
        Date = pool.get('ir.date')

        today = Date.today()

        internal_grouping = {}
        for production in productions:
            if not production.destination_warehouse:
                continue
            if production.state in ('cancel', 'done'):
                continue
            if production.internal_moves:
                cls.raise_user_warning(
                    'production_internal_shipment_%d' % production.id,
                    'internal_shipment_already_exists', {
                        'production': production.rec_name,
                        })

            key = (production.destination_warehouse.storage_location,
                production.warehouse.storage_location,)
            if key in internal_grouping:
                internal_grouping[key].append(production)
            else:
                internal_grouping[key] = [production]

        to_create = []
        for k, productions in internal_grouping.iteritems():
            from_location = k[0]
            to_location = k[1]

            reference = ', '.join([p.code for p in productions])
            planned_start_dates = [p.planned_start_date for p in productions \
                if p.planned_start_date]

            # get product qty in to location
            product_ids = set()
            for production in productions:
                for input in production.inputs:
                    product_ids.add(input.product.id)

            with Transaction().set_context(forecast=True,
                    stock_date_end=today):
                pbl = Product.products_by_location([to_location.id],
                    list(product_ids))

            shipment = cls._get_internal_shipment(
                from_location,
                to_location,
                reference)
            if planned_start_dates:
                shipment.planned_start_date = min(planned_start_dates)
            for production in productions:
                for input in production.inputs:
                    qty_move = input.quantity
                    key = (to_location.id, input.product.id)
                    # in case that exist stock in to warehouse, substract qty moves
                    if key in pbl:
                        qty = pbl[key]
                        if qty >= qty_move:
                            pbl[key] = qty - qty_move
                            continue
                        elif qty > 0:
                            qty_move = qty_move - qty
                            pbl[key] = 0
                    if qty_move == 0:
                        continue
                    move = production._get_shipment_move(input,
                        from_location, to_location)
                    move.quantity = qty_move
                    shipment.moves.append(move)
            to_create.append(shipment._save_values)

        if to_create:
            return ShipmentInternal.create(to_create)

# TODO: Internal shipment should be updated each time outputs are changed


class ProductionSubcontractInternalStart(ModelView):
    'Production Subcontract Internal Start'
    __name__ = 'production.subcontract.internal.start'


class ProductionSubcontractInternal(Wizard):
    'Production Subcontract Internal'
    __name__ = 'production.subcontract.internal'
    start = StateView('production.subcontract.internal.start',
        'production_subcontract.create_internal_start_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Create', 'create_internal', 'tryton-ok', default=True),
            ])
    create_internal = StateAction('stock.act_shipment_internal_form')

    def do_create_internal(self, action):
        Production = Pool().get('production')

        productions = Production.browse(Transaction().context['active_ids'])
        shipments = Production.create_internal_shipments(productions)

        if shipments:
            data = {'res_id': [s.id for s in shipments]}
            if len(shipments) == 1:
                action['views'].reverse()
            return action, data


class OpenShipmentInternal(Wizard):
    'Open Shipment Internal'
    __name__ = 'production.subcontract.open_internal'
    start_state = 'open_'
    open_ = StateAction('stock.act_shipment_internal_form')

    def do_open_(self, action):
        Production = Pool().get('production')

        shipments = set()
        for production in Production.browse(Transaction().context['active_ids']):
            for shipment in production.internal_shipments:
                shipments.add(shipment.id)

        encoder = PYSONEncoder()
        action['pyson_domain'] = encoder.encode([('id', 'in', list(shipments))])
        action['pyson_search_value'] = encoder.encode([])
        return action, {}


class Purchase:
    __name__ = 'purchase.purchase'
    __metaclass__ = PoolMeta

    @classmethod
    def process(cls, purchases):
        pool = Pool()
        PurchaseRequest = pool.get('purchase.request')
        Production = pool.get('production')

        super(Purchase, cls).process(purchases)

        lines = []
        for purchase in purchases:
            for line in purchase.lines:
                lines.append(line.id)

        requests = PurchaseRequest.search([
                ('purchase_line', 'in', lines),
                ])
        requests = [x.id for x in requests]
        productions = Production.search([
                ('purchase_request', 'in', requests),
                ])
        if productions:
            Production.process_purchase_request(productions)
