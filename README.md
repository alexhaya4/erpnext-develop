# erpnext-develop

A development fork of [ERPNext](https://erpnext.com), one of the leading open-source ERP solutions built primarily in Python and JavaScript. This repository is intended for customizations, feature development, and experimentation on top of the core ERPNext platform.

## Table of Contents

- [About ERPNext](#about-erpnext)
- [Features](#features)
- [Getting Started](#getting-started)
- [Development](#development)
- [Contributing](#contributing)
- [License](#license)

## About ERPNext

ERPNext is a comprehensive, web-based ERP system for Small and Medium-sized Businesses (SMBs). It covers a wide range of business processes including Accounting, Inventory, Sales, Purchase, HR, Projects, Support, and more.

This repository is a development branch for working on enhancements, custom modules, and other contributions for ERPNext.

## Features

- Modular architecture: easy to extend and customize
- Built on Python (Frappe Framework) and JavaScript
- Modern web UI with responsive design
- RESTful API support
- Multi-currency, multi-company, localization
- Integrated Accounting, CRM, HR, Projects, and more

## Getting Started

### Prerequisites

- Python 3.10+
- Node.js 16+
- Yarn
- MariaDB / MySQL
- Redis
- wkhtmltopdf (for PDF generation)
- Bench CLI

### Installation

1. **Clone this repository:**
   ```bash
   git clone https://github.com/alexhaya4/erpnext-develop.git
   cd erpnext-develop
   ```

2. **Set up [Frappe Bench](https://frappeframework.com/docs/v14/user/en/installation):**
   - Install Bench CLI:
     ```bash
     pip install frappe-bench
     ```
   - Create a new bench:
     ```bash
     bench init my-bench --python python3
     cd my-bench
     bench get-app erpnext ../erpnext-develop
     bench new-site my-site
     bench --site my-site install-app erpnext
     bench start
     ```
   - Access the site at [http://localhost:8000](http://localhost:8000)

### Development

- All app code is in `erpnext/` directory.
- JavaScript assets are in `erpnext/public/`.
- Python modules are organized by business domain (e.g., `accounts`, `hr`, `stock`, etc).
- For custom scripts or modules, add new folders or files as per Frappe's conventions.

### Running Tests

```bash
bench --site my-site run-tests
```

## Contributing

1. Fork this repository.
2. Create a new branch for your feature or fix.
3. Make your changes and commit them with clear messages.
4. Push your branch and open a Pull Request.

Please adhere to the [ERPNext Contribution Guidelines](https://github.com/frappe/erpnext/blob/develop/CONTRIBUTING.md).

## License

This project is licensed under the GNU General Public License v3.0. See [LICENSE](LICENSE) for more details.
