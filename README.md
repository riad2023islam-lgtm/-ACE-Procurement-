# ACE Procurement Intelligence (SE331 Capstone, Team ACE)

AI-assisted procurement planning for educational institutions.
Stack (as in the SRS): **Django + Django REST Framework + SQLite**, **React (Vite)**, **scikit-learn / NumPy** for the ML.

## What the live demo covers

| Assessment item | Where it is |
|---|---|
| Authentication: registration, login, validation, secure passwords | `backend/accounts/`, `frontend/src/pages/AuthPage.jsx` |
| **FR3** Transaction and inventory entry (record and edit purchases, consumption, stock counts) | `backend/inventory/`, `frontend/src/pages/DataEntry.jsx` |
| **FR9** Demand forecasting with error range (+ **FR14** cold-start fallback) | `backend/intelligence/ml/forecast.py`, `services.py`, `views.py`, `frontend/src/pages/Forecast.jsx` |
| **FR11** Procurement recommendation (quantity, timing, supplier, reasoning) | `backend/intelligence/ml/recommend.py`, `views.py`, `frontend/src/pages/Recommendations.jsx` |

Also implemented from the SRS: FR1 (organization registration), FR2 (role-based accounts: admin / manager / store officer), NFR3 (each organization sees only its own data), NFR4 (role-based access), NFR6 (every recommendation shows its reasoning), NFR10 (fallback when history is short).

**Not implemented** (say so honestly if asked): FR4 CSV import, FR12/FR13 decision recording and Organizational Memory personalization, FR15/FR16, FR17-FR19, dashboard (FR8).

## Run it

You need Python 3.10+ and Node 18+.

```bash
# 1. Backend
cd backend
python -m venv .venv && source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python manage.py makemigrations accounts inventory        # creates the migration files: commit them
python manage.py migrate
python manage.py test                                     # runs all backend tests
python manage.py seed_demo --org "DIU Campus Supershop" \
    --username demo_admin --email demo@example.com --password '<pick a strong password>' \
    --store-username demo_store --store-password '<another strong password>'
python manage.py runserver                                # http://127.0.0.1:8000

# 2. Frontend (second terminal)
cd frontend
npm install
npm run dev                                               # http://localhost:5173
```

No password is stored in the code. `SECRET_KEY` is read from `DJANGO_SECRET_KEY`, or generated once into `backend/.secret_key` (git-ignored). Passwords are saved as PBKDF2 hashes.

**Important:** this project was written and checked in a sandbox where Django could not be installed. The ML code (`python -m unittest intelligence.tests.test_ml`) and the React bundle were run there; the Django code was only compile-checked. Run `python manage.py test` first on your machine and fix anything it reports before the demo day.

## Demo script (about 8 minutes)

1. **Registration**: open the app, click *Register organization*, submit empty (validation messages), enter a weak password (rejected), a duplicate username (rejected), then register properly. Mention: password hashed (show `User.password` starts with `pbkdf2_` in the Django admin or shell), org + admin profile created in one transaction.
2. **Login / logout** with the demo accounts; show a wrong password gives one generic error.
3. **Roles**: log in as `demo_store`: only the Data Entry tab is visible; calling `/api/recommendations/` returns 403. Log in as `demo_admin` for the rest.
4. **FR3 Data entry**: add an item, add a supplier, record a purchase, then a consumption larger than stock (rejected: negative stock). Edit a quantity and watch current stock recompute. Show the rows in SQLite (`python manage.py shell` or a DB viewer) as proof of database interaction.
5. **FR9 Forecast**: pick *A4 Paper Ream* (12 months history: ML model chosen by backtest, error range, chart). Then *Lab Gloves* (4 months: cold-start fallback, low confidence).
6. **FR11 Recommendations**: shortage / ok / overstock rows, click a row to show reasoning (forecast, stock, cover days, cheapest supplier, price trend). Change a stock count in Data Entry, reload, and show the recommendation changes.

## Who should own what (agree this in your team)

The SRS assigns auth/data entry to M1, ML to M2, frontend to M3. Suggested split of this code:

- **ML owner (M2):** `intelligence/` (`ml/forecast.py`, `ml/recommend.py`, `services.py`, `views.py`, `tests/`), `inventory/management/commands/seed_demo.py`
- **Backend/auth owner (M1):** `accounts/`, `inventory/` (models, serializers, views, stock.py)
- **Frontend owner (M3):** `frontend/`

Each person should **commit their own files from their own account**, in several small commits with real messages (for example "Add monthly aggregation of consumption", "Add rolling backtest to pick the model", "Add recommendation reasoning"). Do not copy the whole project in one commit: the examiners check commit history, and each of you must be able to explain your part line by line.

## Questions an examiner may ask about the ML part

- Why compare a moving average with a linear trend? *(Small, seasonal-ish monthly data; both are simple and explainable; the backtest chooses with evidence instead of assuming.)*
- What is a rolling-origin backtest? *(For each month from the middle onwards, predict it using only earlier months, compare to the actual, average the errors. No future data leaks into training.)*
- How is the error range computed? *(RMSE of the chosen model's backtest errors times 1.28, about an 80% interval if errors are roughly normal.)*
- Why is the current month excluded from history? *(It is incomplete and would pull the forecast down.)*
- What happens with little history? *(Fewer than 6 months: simple average of recent months, labelled low confidence: SRS FR14 / NFR10.)*
- How is the recommended quantity chosen? *(forecast minus current stock, never below 0, as in the SRS paper example 650 - 180 = 470; supplier = lowest current price, ties broken by delivery time; order date = today + stock cover days - delivery days.)*
- Limits? *(No seasonality model, only about 12 points of data, simulated demo data, no safety stock, personalization (FR13) not built yet.)*
