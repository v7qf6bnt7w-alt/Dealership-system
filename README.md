# Car Dealership Management System

This project is a Python web application for a vehicle dealership with two profiles:

- Administrator
- Public customer area

## Features

- Admin login with username and password
- Create, edit and manage vehicle inventory
- Add stock, decrease stock, and mark vehicles as unavailable when stock reaches zero
- Upload multiple vehicle images and videos
- Searchable brand, model, and version suggestions backed by the SQLite catalog
- Add new brands, models, and versions for reuse; models and versions stay linked to their parent
- View customer purchase or information requests and update their status
- Public catalog with filtering, search, brand browsing, model and version selection
- Rotating hero carousel with featured vehicles
- Contact, social media, payment methods, and location section
- Request information or schedule a visit modal for each vehicle

## Default admin credentials

- Username: admin
- Password: admin123

## Run the app locally

1. Create and activate a virtual environment
2. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

3. Start the app:

   ```bash
   python app.py
   ```

4. Open the browser at:

   ```text
   http://127.0.0.1:5000/
   ```

## Project structure

- `app.py` - main Flask application
- `dealership.db` - SQLite database; the app adds its inventory and catalog tables while preserving the supplied car catalogue
- `templates/` - Jinja HTML templates
- `static/css/` - styling
- `static/js/` - frontend interaction
- `static/uploads/` - uploaded vehicle images and videos

Vehicle pictures and videos are uploaded together from the admin create/edit form. The existing catalogue in `dealership.db` is loaded into the autocomplete options at startup, and admin-added values are stored in the same database.
