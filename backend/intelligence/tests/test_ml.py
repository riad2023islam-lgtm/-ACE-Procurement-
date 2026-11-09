"""Unit tests for the ML logic. These do not need Django or a database:
    python -m unittest intelligence.tests.test_ml -v
"""
import unittest
from datetime import date

from intelligence.ml.forecast import MIN_HISTORY, forecast_next_month
from intelligence.ml.recommend import assess_risk, choose_supplier, price_trend, recommend


class ForecastTests(unittest.TestCase):
    def test_cold_start_uses_simple_average_low_confidence(self):
        result = forecast_next_month([100, 120, 110])
        self.assertEqual(result.model, "simple_average_fallback")
        self.assertEqual(result.confidence, "low")
        self.assertAlmostEqual(result.forecast, 110.0)
        self.assertIsNone(result.mae)

    def test_enough_history_uses_ml_model_with_error_range(self):
        series = [420, 450, 470, 620, 680, 500, 480, 520]
        result = forecast_next_month(series)
        self.assertGreaterEqual(len(series), MIN_HISTORY)
        self.assertIn(result.model, ("moving_average", "linear_trend"))
        self.assertEqual(result.confidence, "normal")
        self.assertLessEqual(result.lower, result.forecast)
        self.assertGreaterEqual(result.upper, result.forecast)
        self.assertIsNotNone(result.mae)

    def test_trending_series_prefers_linear_trend(self):
        series = [100, 110, 120, 130, 140, 150, 160, 170]
        result = forecast_next_month(series)
        self.assertEqual(result.model, "linear_trend")
        self.assertAlmostEqual(result.forecast, 180.0, delta=1.0)

    def test_forecast_never_negative(self):
        result = forecast_next_month([50, 40, 30, 20, 10, 5, 1])
        self.assertGreaterEqual(result.forecast, 0)
        self.assertGreaterEqual(result.lower, 0)

    def test_empty_history_rejected(self):
        with self.assertRaises(ValueError):
            forecast_next_month([])


class RecommendationTests(unittest.TestCase):
    SUPPLIERS = [
        {"name": "Corporate Co", "price": 500.0, "delivery_days": 2, "history": [480, 490, 500]},
        {"name": "Dealer Ltd", "price": 520.0, "delivery_days": 4, "history": [520, 520]},
    ]

    def test_srs_paper_example(self):
        # SRS section 1.4: forecast ~650, stock 180 -> buy ~470 from the cheaper supplier.
        forecast = {"forecast": 650.0, "lower": 600.0, "upper": 700.0,
                    "model": "linear_trend", "confidence": "normal", "mae": 40.0, "history_months": 12}
        rec = recommend("A4 Paper", forecast, 180, self.SUPPLIERS, today=date(2026, 11, 1))
        self.assertEqual(rec["recommended_quantity"], 470)
        self.assertEqual(rec["supplier"]["name"], "Corporate Co")
        self.assertEqual(rec["risk"], "shortage")          # 180 / (650/30) = 8.3 days
        self.assertEqual(rec["order_by"], "2026-11-07")    # 8.3 - 2 delivery days -> 6 days from today
        self.assertTrue(rec["reasoning"])

    def test_no_purchase_when_stock_covers_forecast(self):
        forecast = {"forecast": 100.0, "lower": 90.0, "upper": 110.0,
                    "model": "moving_average", "confidence": "normal", "mae": 5.0, "history_months": 10}
        rec = recommend("Toner", forecast, 120, self.SUPPLIERS, today=date(2026, 11, 1))
        self.assertEqual(rec["recommended_quantity"], 0)
        self.assertIsNone(rec["order_by"])

    def test_risk_levels(self):
        self.assertEqual(assess_risk(10, 300), "shortage")
        self.assertEqual(assess_risk(300, 300), "ok")
        self.assertEqual(assess_risk(600, 300), "overstock")

    def test_supplier_tie_breaks_on_delivery_time(self):
        picked = choose_supplier([
            {"name": "Slow", "price": 10.0, "delivery_days": 5, "history": []},
            {"name": "Fast", "price": 10.0, "delivery_days": 1, "history": []},
        ])
        self.assertEqual(picked["name"], "Fast")

    def test_price_trend(self):
        self.assertEqual(price_trend([100, 110])["direction"], "up")
        self.assertEqual(price_trend([100, 90])["direction"], "down")
        self.assertEqual(price_trend([100, 101])["direction"], "stable")
        self.assertEqual(price_trend([100])["direction"], "unknown")

    def test_no_supplier_prices(self):
        forecast = {"forecast": 100.0, "lower": 90.0, "upper": 110.0,
                    "model": "moving_average", "confidence": "normal", "mae": 5.0, "history_months": 10}
        rec = recommend("Marker", forecast, 10, [], today=date(2026, 11, 1))
        self.assertIsNone(rec["supplier"])


if __name__ == "__main__":
    unittest.main()
