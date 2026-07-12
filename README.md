# SmartFinance – Intelligent Personal Finance Management and Financial Forecasting System

SmartFinance is a Flask-based personal finance management system designed to help users track expenses, manage budgets, monitor savings, automate recurring expenses, receive bill reminders, and estimate future financial performance.

## Key Features

- Secure user registration and login
- Email OTP based forgot-password recovery
- Monthly income management
- Monthly and category-wise budgeting
- Expense tracking, search, edit, and delete
- Custom expense categories
- Savings goals and contribution tracking
- Financial health score
- Smart financial insights and analytics
- Six-month financial trend analysis
- Recurring expense automation
- Bill reminders and overdue alerts
- Financial forecasting using recent income and expense history
- In-app notifications
- CSV and PDF export
- Dark mode and profile settings
- Admin dashboard and role management

## Financial Forecasting

SmartFinance analyses recent expense history and income records to estimate:

- Predicted monthly income
- Predicted monthly expenses
- Predicted monthly savings
- Financial forecast status

The current forecasting engine uses recent financial records to generate behavioural estimates. Forecast quality improves as more monthly data is recorded.

## Technology Stack

- Python
- Flask
- SQLite
- HTML5
- CSS3
- JavaScript
- Jinja2
- Werkzeug
- SMTP Email OTP

## Project Structure

```text
expense-tracker/
├── app.py
├── static/
│   ├── app.js
│   └── style.css
├── templates/
│   ├── dashboard.html
│   ├── login.html
│   ├── register.html
│   ├── forgot_password.html
│   ├── verify_otp.html
│   ├── reset_password.html
│   ├── recurring_expenses.html
│   ├── bill_reminders.html
│   ├── forecast.html
│   └── ...
├── .gitignore
└── README.md
```

## Installation and Setup

### 1. Clone the repository

```bash
git clone https://github.com/Vinit1817/smartfinance-intelligent-finance-system.git
cd smartfinance-intelligent-finance-system
```

### 2. Install dependencies

```bash
python -m pip install flask werkzeug python-dotenv reportlab
```

### 3. Configure email OTP

Set the SMTP sender email and Gmail App Password as environment variables.

PowerShell:

```powershell
$env:SMTP_EMAIL="your-email@gmail.com"
$env:SMTP_PASSWORD="your-gmail-app-password"
```

Do not commit email passwords or secrets to GitHub.

### 4. Run the application

```bash
python app.py
```

Open the local Flask address shown in the terminal.

## Main Modules

### Financial Command Centre
Displays balance, income, expenses, savings rate, financial health score, trends, insights, budget usage, savings goals, and recent transactions.

### Recurring Expenses
Allows users to configure repeated monthly payments. SmartFinance records eligible recurring expenses for the selected month.

### Bill Reminders
Tracks bill deadlines and creates due or overdue notifications. Marking a bill as paid records it as an expense.

### Financial Forecasting
Uses recent financial history to estimate the next financial position and provide a forecast signal.

## Security

- Password hashing with Werkzeug
- Session-based authentication
- Email OTP password recovery
- OTP expiration
- User-specific financial records
- Admin role checks
- Environment-based SMTP credentials
- Local database excluded from Git tracking

## Future Enhancements

- Machine learning based expense forecasting
- Interactive forecasting charts
- Cloud deployment
- Mobile responsive enhancements
- Bank transaction integration
- Multi-factor authentication

## Project Title

**SmartFinance: An Intelligent Personal Finance Management and Financial Forecasting System**

## Author

**Vinit**

Computer Science and Engineering

## Disclaimer

SmartFinance is an academic and portfolio project. Forecasts are estimates based on recorded data and should not be treated as professional financial advice.
