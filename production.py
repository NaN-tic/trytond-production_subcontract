# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.
from trytond.pool import Pool, PoolMeta
from trytond.model import ModelView, Workflow, fields
from trytond.pyson import Eval, Bool

__all__ = ['Party', 'PurchaseRequest', 'BOM', 'Production', 'Purchase']


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

    @classmethod
    def __setup__(cls):
        super(Production, cls).__setup__()
        # TODO: Do not allow starting a production if purchase_request has been
        # created but purchase order is not in processing state.
        cls._buttons.update({
                'create_purchase_request': {
                    'invisible': ~(Eval('state').in_(['draft', 'waiting']) &
                        Bool(Eval('subcontract_product')) &
                        ~Bool(Eval('purchase_request'))),
                    'icon': 'tryton-go-home',
                    }
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
    def process_purchase_request(cls, productions):
        pool = Pool()
        ShipmentInternal = pool.get('stock.shipment.internal')
        for production in productions:
            if not (production.purchase_request and
                    production.purchase_request.purchase and
                    production.purchase_request.purchase.state == 'processing'):
                continue
            if production.destination_warehouse:
                continue
            subcontract_warehouse = production._get_subcontract_warehouse()
            production.destination_warehouse = production.warehouse
            production.warehouse = subcontract_warehouse

            from_location = production.warehouse.storage_location
            to_location = production.destination_warehouse.storage_location
            shipment = ShipmentInternal()
            shipment.from_location = from_location
            shipment.to_location = to_location
            shipment.moves = []
            for output in production.outputs:
                move = production._get_incoming_shipment_move(output,
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

    def _get_incoming_shipment_move(self, output, from_location, to_location):
        Move = Pool().get('stock.move')
        return Move(
            from_location=from_location,
            to_location=to_location,
            product=output.product,
            # TODO: Support lots
            quantity=output.quantity,
            uom=output.uom,
            )

    def _get_subcontract_warehouse(self):
        return self.purchase_request.party.production_warehouse

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
    @ModelView.button
    @Workflow.transition('done')
    def done(cls, productions):
        InternalShipment = Pool().get('stock.shipment.internal')
        super(Production, cls).done(productions)
        shipments = [x.incoming_shipment for x in productions if
            x.incoming_shipment]
        if shipments:
            InternalShipment.assign_try(shipments)

# TODO: Internal shipment should be updated each time outputs are changed

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
