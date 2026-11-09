"""Glue between the database and the pure ML modules."""
from collections import defaultdict
from datetime import date

from inventory.models import SupplierPrice, Transaction
from inventory.stock import current_stock

from .ml.forecast import forecast_next_month
from .ml.recommend import recommend


def _month_start(d):
    return d.replace(day=1)


def _next_month(d):
    return date(d.year + (d.month == 12), d.month % 12 + 1, 1)


def monthly_consumption(item, today=None):
    """Monthly consumption totals for an item, oldest -> newest.

    The current (incomplete) month is left out so it does not drag the forecast
    down. Months with no consumption between the first and last month count as 0.
    Returns a list of (month_start_date, quantity).
    """
    today = today or date.today()
    this_month = _month_start(today)
    totals = defaultdict(int)
    for t in item.transactions.filter(kind=Transaction.CONSUMPTION, date__lt=this_month):
        totals[_month_start(t.date)] += t.quantity
    if not totals:
        return []
    months, cursor, last = [], min(totals), max(totals)
    while cursor <= last:
        months.append((cursor, totals.get(cursor, 0)))
        cursor = _next_month(cursor)
    return months


def forecast_for_item(item, today=None):
    """Returns (history, ForecastResult) or (history=[], None) when there is no data."""
    history = monthly_consumption(item, today)
    if not history:
        return history, None
    return history, forecast_next_month([q for _, q in history])


def supplier_options(item):
    """Latest price per supplier for an item, with that supplier's price history."""
    by_supplier = defaultdict(list)
    for p in SupplierPrice.objects.filter(item=item).select_related("supplier"):
        by_supplier[p.supplier].append(float(p.unit_price))   # queryset is ordered by date
    return [
        {"name": s.name, "price": prices[-1], "delivery_days": s.delivery_days, "history": prices}
        for s, prices in by_supplier.items()
    ]


def _add_months(d, n):
    total = d.year * 12 + (d.month - 1) + n
    return date(total // 12, total % 12 + 1, 1)


def dashboard_summary(org, today=None):
    """Numbers for the dashboard page, all computed from the organization's own records."""
    from inventory.models import Item, Supplier   # local import keeps the top of the file light

    today = today or date.today()
    this_month = _month_start(today)
    start, prev_start = _add_months(this_month, -6), _add_months(this_month, -12)

    def spend(qs):
        return float(sum(t.quantity * t.unit_price for t in qs if t.unit_price))

    purchases = Transaction.objects.filter(organization=org, kind=Transaction.PURCHASE)
    spend_now = spend(purchases.filter(date__gte=start))
    spend_prev = spend(purchases.filter(date__gte=prev_start, date__lt=start))
    change = round((spend_now - spend_prev) / spend_prev * 100, 1) if spend_prev else None

    items = list(Item.objects.filter(organization=org).prefetch_related("transactions"))
    monthly, next_total, alerts = {}, 0.0, []
    shortage = overstock = 0
    for item in items:
        for month, qty in monthly_consumption(item, today):
            if month >= start:
                monthly[month] = monthly.get(month, 0) + qty
        rec = recommendation_for_item(item, today)
        if rec is None:
            continue
        next_total += rec["forecast"]["forecast"]
        if rec["risk"] == "shortage":
            shortage += 1
            alerts.append({"severity": "high", "title": "Inventory shortage predicted",
                           "detail": f"{item.name}: stock {rec['current_stock']:g}, about "
                                     f"{rec['cover_days']:.0f} days of cover. Recommended buy: "
                                     f"{rec['recommended_quantity']}."})
        elif rec["risk"] == "overstock":
            overstock += 1
            alerts.append({"severity": "medium", "title": "Overstock risk",
                           "detail": f"{item.name}: stock {rec['current_stock']:g} is well above "
                                     f"the forecast of {rec['forecast']['forecast']:g}."})
        if rec["forecast"]["confidence"] == "low":
            alerts.append({"severity": "low", "title": "Low-confidence forecast",
                           "detail": f"{item.name}: only {rec['forecast']['history_months']} month(s) of history."})
    order = {"high": 0, "medium": 1, "low": 2}
    alerts.sort(key=lambda a: order[a["severity"]])

    recent = purchases.select_related("item", "supplier").order_by("-date", "-id")[:5]
    return {
        "kpis": {
            "total_spend": round(spend_now, 2),
            "spend_change_pct": change,
            "purchase_records": purchases.filter(date__gte=start).count(),
            "active_suppliers": Supplier.objects.filter(organization=org).count(),
            "items_tracked": len(items),
            "items_at_risk": shortage + overstock,
            "shortage_items": shortage,
        },
        "demand": {
            "actual": [{"month": m.strftime("%Y-%m"), "quantity": q} for m, q in sorted(monthly.items())],
            "next_month": {"month": _add_months(this_month, 0).strftime("%Y-%m"), "forecast": round(next_total, 1)},
        },
        "alerts": alerts[:6],
        "recent_purchases": [{
            "id": t.id, "date": t.date.isoformat(), "item": t.item.name,
            "supplier": t.supplier.name if t.supplier else None, "quantity": t.quantity,
            "total": float(t.quantity * t.unit_price) if t.unit_price else None,
        } for t in recent],
    }


def recommendation_for_item(item, today=None):
    history, forecast = forecast_for_item(item, today)
    if forecast is None:
        return None
    return recommend(
        item_name=item.name,
        forecast=forecast.as_dict(),
        current_stock=current_stock(item),
        suppliers=supplier_options(item),
        today=today,
    )
