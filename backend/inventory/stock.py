"""Stock calculation shared by the API and the intelligence app."""
from .models import Transaction


def replay(movements):
    """movements: iterable of (date, id, kind, quantity). Returns (final_stock, lowest_stock_seen).

    Movements are applied in (date, id) order. A new, unsaved movement can use id=float('inf')
    so that it sorts after existing ones on the same day.
    """
    stock = 0
    lowest = 0
    for _date, _id, kind, qty in sorted(movements, key=lambda m: (m[0], m[1])):
        if kind == Transaction.PURCHASE:
            stock += qty
        elif kind == Transaction.CONSUMPTION:
            stock -= qty
        elif kind == Transaction.INVENTORY_COUNT:
            stock = qty
        lowest = min(lowest, stock)
    return stock, lowest


def current_stock(item):
    movements = [(t.date, t.id, t.kind, t.quantity) for t in item.transactions.all()]
    return replay(movements)[0]
