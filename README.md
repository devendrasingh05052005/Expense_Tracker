# ReceiptAI — Smart Expense Manager

A full-stack Django web app that uses EasyOCR to scan receipts and automatically extract expense data.

---

## Features

- **User Auth** — Register, login, logout with session authentication
- **Dashboard** — Spending stats + Chart.js monthly & category charts
- **Receipt Scanner** — Upload a photo → EasyOCR extracts total, date, merchant, suggests category
- **Expense CRUD** — Add, edit, delete expenses manually
- **Search & Filter** — Filter by date range, category, amount, keyword
- **Export** — Download expenses as CSV or PDF
- **Dark UI** — Clean responsive dark-mode interface

---

## Project Structure

```
expense_app/
├── config/
│   ├── settings.py       # Django settings
│   ├── urls.py           # Root URL config
│   └── wsgi.py
├── app/
│   ├── models.py         # Expense model
│   ├── views.py          # All views
│   ├── forms.py          # Django forms
│   ├── ocr.py            # EasyOCR + regex extractors
│   ├── urls.py           # App URL patterns
│   └── admin.py
├── templates/
│   ├── base.html         # Sidebar layout
│   ├── dashboard.html
│   ├── auth/
│   │   ├── login.html
│   │   └── register.html
│   └── expenses/
│       ├── list.html
│       ├── form.html
│       ├── upload.html
│       └── confirm_delete.html
├── static/
│   ├── css/style.css
│   └── js/app.js
├── manage.py
├── requirements.txt
├── render.yaml           # Render.com deployment config
└── build.sh
```

---

## Local Setup

```bash
# 1. Clone / download the project
cd expense_app

# 2. Create virtual environment
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Run migrations
python manage.py migrate

# 5. Create a superuser (optional)
python manage.py createsuperuser

# 6. Run the dev server
python manage.py runserver
```

Open http://127.0.0.1:8000 — register an account and start adding expenses.

> **Note on EasyOCR:** First run downloads ~200MB of model weights. This happens automatically but takes a moment. On the Render free tier, OCR may take 15–30 seconds per scan.

---

## Deploy to Render

1. Push this folder to a **GitHub repository**

2. Go to [render.com](https://render.com) → **New → Web Service**

3. Connect your GitHub repo

4. Fill in:
   | Field | Value |
   |---|---|
   | **Runtime** | Python 3 |
   | **Build Command** | `pip install -r requirements.txt && python manage.py collectstatic --noinput && python manage.py migrate` |
   | **Start Command** | `gunicorn config.wsgi:application` |

5. Add **Environment Variables**:
   | Key | Value |
   |---|---|
   | `SECRET_KEY` | Any long random string |
   | `DEBUG` | `False` |
   | `ALLOWED_HOSTS` | `yourapp.onrender.com` |

6. Click **Deploy** — it will be live in ~3 minutes.

> The `render.yaml` file in this project auto-configures everything if you use Render's Blueprint feature (New → Blueprint).

---

## Database

- Uses **SQLite** by default (works great on Render's free tier)
- To switch to PostgreSQL, update `DATABASES` in `config/settings.py` and add `psycopg2-binary` to `requirements.txt`

---

## Category Keywords

The OCR module auto-categorizes based on these keywords:

| Category | Keywords |
|---|---|
| 🍔 Food | restaurant, cafe, pizza, starbucks, zomato… |
| ✈️ Travel | uber, flight, hotel, petrol, metro… |
| 🛍️ Shopping | amazon, walmart, grocery, flipkart… |
| 💡 Bills | electricity, internet, phone, insurance… |
| 🏥 Health | pharmacy, hospital, doctor, gym… |
| 🎭 Entertainment | cinema, netflix, concert, ticket… |
