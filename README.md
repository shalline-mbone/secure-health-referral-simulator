# Secure Health Referral Simulator

**A Web-Based Flask Simulation for Token-Based Patient Referrals in Kenya**

## 📖 About the Project
This project develops a web-based simulator to demonstrate secure, token-based patient referrals within Kenya's three-tier healthcare system (Level 1: Primary Care, Level 2: County Referral, Level 3: National Referral). 

Currently, approximately 65% of inter-facility referrals in Kenya rely on unsecured digital platforms (like WhatsApp or email), exposing sensitive patient data to privacy breaches. This simulation addresses that vulnerability by modeling a system where facilities exchange **access tokens** instead of sending actual patient records. 

By using Flask and realistic Kenyan hospital profiles, the system visually teaches secure coordination, intelligent routing based on resource constraints, and data protection principles.

## ✨ Key Features
*   **Token-Based Referrals:** Eliminates the direct sharing of patient records; facilities generate a secure token that grants temporary, controlled access to patient data within the system.
*   **Intelligent Hospital Routing:** Automatically routes patients to the appropriate facility based on the severity of their condition and the hospital's available capabilities (preventing "referral ping-pong").
*   **Role-Based Access Control (RBAC):** Ensures data isolation so that hospitals only see the referrals intended for them, and users only see what their role permits.
*   **Audit Logging:** Tracks system events, token validations, and user actions to ensure accountability.
*   **Admin Dashboard:** Provides visual analytics, system statistics, and user management tools.

## 🛠️ Technology Stack
*   **Backend:** Python, Flask
*   **Database:** SQLite (with SQLAlchemy ORM)
*   **Database Migrations:** Flask-Migrate (Alembic)
*   **Frontend:** HTML, CSS, JavaScript (Jinja2 Templating)

## 🚀 How to Run the Project Locally

Follow these steps to set up the simulator on your local machine:

**1. Clone the repository:**
```bash
git clone https://github.com/shalline-mbone/secure-health-referral-simulator.git
cd secure-health-referral-simulator
