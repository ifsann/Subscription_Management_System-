\# Brightloop Subscription Management System



A Flask + SQLite app for a gym. It covers signup, roles, plans,

subscriptions, invoices, discounts, payments and a dashboard.



\## Run

pip install -r requirements.txt

python seed\_demo.py

python app.py

Open http://127.0.0.1:5000



\## Logins

Admin: admin@brightloop.com / Admin@12345

Customer: member1@example.com / Member#1234



\## Flow

Subscription: Draft > Quotation > Confirmed > Active > Closed.

Run billing now creates invoices: line subtotal, discount, then 18% tax.

A unique constraint stops double billing.

Staff confirm invoices and record payments. Customers see only their own at /account.



\## Team

Ifsan: plans, subscriptions, discounts, billing core, final merge
Rithin-7: auth, roles, invoices, payments, dashboard, customer portal

