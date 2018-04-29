# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.
from trytond.pool import Pool
from . import production


def register():
    Pool.register(
        production.Party,
        production.PurchaseRequest,
        production.BOM,
        production.Production,
        production.Purchase,
        production.PartyProductionWarehouse,
        module='production_subcontract', type_='model')
