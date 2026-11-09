"""Procurement recommendation (SRS FR11, NFR6).

Pure Python (no Django). Combines the demand forecast, current stock, supplier
prices and the price trend into: quantity, timing and supplier, plus the
reasoning shown to the user so they can accept or override it.

Rules (kept simple and explainable, see SRS section 2.3):
    quantity  = max(0, ceil(forecast - current_stock))      # SRS paper example: 650 - 180 = 470
    cover     = current_stock / (forecast / DAYS_PER_MONTH)  # days the stock will last
    order_by  = today + max(0, cover - supplier_delivery_days)
    supplier  = lowest current unit price (ties -> shorter delivery time)
    risk      = shortage | overstock | ok  (see assess_risk)
"""
import math
from datetime import date, timedelta
from typing import List, Optional

DAYS_PER_MONTH = 30
SHORTAGE_COVER_DAYS = 15      # less than this many days of stock left -> shortage risk
OVERSTOCK_RATIO = 1.5         # stock above 1.5x the monthly forecast -> overstock risk
TREND_THRESHOLD_PCT = 2.0     # |change| below this is reported as "stable"


def assess_risk(current_stock: float, forecast: float) -> str:
    if forecast <= 0:
        return "overstock" if current_stock > 0 else "ok"
    cover_days = current_stock / (forecast / DAYS_PER_MONTH)
    if cover_days < SHORTAGE_COVER_DAYS:
        return "shortage"
    if current_stock > OVERSTOCK_RATIO * forecast:
        return "overstock"
    return "ok"


def price_trend(price_history: List[float]) -> dict:
    """price_history is oldest -> newest unit prices for ONE supplier."""
    if len(price_history) < 2 or price_history[0] == 0:
        return {"direction": "unknown", "change_pct": None}
    change = (price_history[-1] - price_history[0]) / price_history[0] * 100
    if abs(change) < TREND_THRESHOLD_PCT:
        direction = "stable"
    else:
        direction = "up" if change > 0 else "down"
    return {"direction": direction, "change_pct": round(change, 1)}


def choose_supplier(suppliers: List[dict]) -> Optional[dict]:
    """suppliers: [{"name", "price", "delivery_days", "history": [prices...]}]"""
    priced = [s for s in suppliers if s.get("price") is not None]
    if not priced:
        return None
    return min(priced, key=lambda s: (s["price"], s["delivery_days"]))


def recommend(item_name: str, forecast: dict, current_stock: float,
              suppliers: List[dict], today: Optional[date] = None) -> dict:
    """forecast is ForecastResult.as_dict()."""
    today = today or date.today()
    predicted = forecast["forecast"]

    qty = max(0, math.ceil(predicted - current_stock))
    risk = assess_risk(current_stock, predicted)
    supplier = choose_supplier(suppliers)
    trend = price_trend(supplier["history"]) if supplier else {"direction": "unknown", "change_pct": None}

    if predicted > 0:
        cover_days = current_stock / (predicted / DAYS_PER_MONTH)
    else:
        cover_days = None

    order_by = None
    if qty > 0:
        delivery = supplier["delivery_days"] if supplier else 0
        wait = max(0, (cover_days if cover_days is not None else 0) - delivery)
        order_by = today + timedelta(days=int(wait))

    reasoning = [
        f"Forecast next month: {predicted:g} units "
        f"(range {forecast['lower']:g}-{forecast['upper']:g}, model: {forecast['model']}, "
        f"confidence: {forecast['confidence']}).",
        f"Current stock: {current_stock:g} units"
        + (f" (about {cover_days:.0f} days of cover)." if cover_days is not None else "."),
    ]
    if qty > 0:
        reasoning.append(f"Shortfall = forecast - stock = {qty} units to buy.")
    else:
        reasoning.append("Stock already covers the forecast: no purchase needed.")
    if supplier:
        reasoning.append(
            f"Cheapest supplier now: {supplier['name']} at {supplier['price']:g} per unit, "
            f"delivery {supplier['delivery_days']} day(s)."
        )
        if trend["direction"] != "unknown":
            reasoning.append(f"Price trend for this supplier: {trend['direction']} ({trend['change_pct']:+g}%).")
    else:
        reasoning.append("No supplier price recorded for this item yet.")
    if forecast["confidence"] == "low":
        reasoning.append("Low confidence: fewer than 6 months of history, so a simple average was used.")

    return {
        "item": item_name,
        "recommended_quantity": qty,
        "order_by": order_by.isoformat() if order_by else None,
        "risk": risk,
        "current_stock": current_stock,
        "cover_days": round(cover_days, 1) if cover_days is not None else None,
        "supplier": (
            {"name": supplier["name"], "unit_price": supplier["price"],
             "delivery_days": supplier["delivery_days"]} if supplier else None
        ),
        "price_trend": trend,
        "forecast": forecast,
        "reasoning": reasoning,
    }
