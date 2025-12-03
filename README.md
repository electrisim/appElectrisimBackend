# Electrisim Backend API

## About

This repository contains the backend API server for **[Electrisim](https://app.electrisim.com/)** - an open-source web-based application for comprehensive power system modeling, simulation, and analysis. The backend provides REST API endpoints for power system calculations and simulations using industry-standard libraries.

🌐 **Online Application**: [app.electrisim.com](https://app.electrisim.com/)  
📁 **Frontend Repository**: [Frontend Code](https://github.com/electrisim/appElectrisimFrontend)

## Features

The Electrisim backend provides computational engines for:

- **Power Flow Analysis** 
- **Optimal Power Flow (OPF)** 
- **Short-Circuit Analysis** 
- **Contingency Analysis** 
- **Controller Simulation** 
- **Time Series Simulation** 


## Technology Stack

- **Framework**: Flask (Python web framework)
- **Simulation Engines**: 
  - [pandapower](https://pandapower.readthedocs.io/) - Primary power system analysis library
  - [OpenDSS](https://www.epri.com/pages/sa/opendss) - Alternative simulation engine via py-dss-interface
- **Scientific Computing**: NumPy, SciPy, pandas
- **Web Server**: Gunicorn (production WSGI server)
- **Testing**: pytest
- **Deployment**: Heroku/Render ready with Procfile

## Architecture

```
├── app.py                          # Main Flask application and API routes
├── pandapower_electrisim.py        # pandapower simulation engine wrapper
├── opendss_electrisim.py          # OpenDSS simulation engine wrapper
├── requirements.txt               # Python dependencies
├── Procfile                      # Heroku/Render deployment configuration
├── runtime.txt                   # Python version specification
└── test_*.py                     # Test suites for various components
```

## Prerequisites

Before deploying the Electrisim backend, ensure you have:

- **Python 3.9.18** (specified in runtime.txt)
- **pip** (Python package manager)
- **Git** (version control)
- **Virtual Environment** tools (venv or virtualenv)

## Step-by-Step Deployment Guide

### 1. Clone the Repository

```bash
git clone <repository-url>
cd appElectrisimBackend
```

### 2. Create Virtual Environment

```bash
# Create virtual environment
python -m venv .venv

# Activate virtual environment
# On Windows:
.venv\Scripts\activate
# On macOS/Linux:
source .venv/bin/activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Local Development Setup

#### Run Development Server:
```bash
# Set Flask environment variables
export FLASK_APP=app.py
export FLASK_ENV=development

# Run the application
flask run

# Or run directly with Python
python app.py
```

The server will start on `http://localhost:5000` by default.

#### Test the API:
```bash
# Test basic connectivity
curl http://localhost:5000/

# Test API endpoint (requires JSON data)
curl -X POST http://localhost:5000/ \
  -H "Content-Type: application/json" \
  -d '{"test": "data"}'
```

### 5. Production Deployment

#### Option A: Heroku Deployment

1. **Install Heroku CLI** and login:
```bash
heroku login
```

2. **Create Heroku application**:
```bash
heroku create your-electrisim-backend
```

3. **Deploy to Heroku**:
```bash
git add .
git commit -m "Deploy to Heroku"
git push heroku main
```

4. **Configure environment variables**:
```bash
heroku config:set FLASK_ENV=production
heroku config:set FLASK_APP=app.py
```

#### Option B: Render Deployment

1. **Connect Repository**: Link your GitHub repository to Render
2. **Configure Build Settings**:
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `gunicorn app:app`
   - **Environment**: Python 3.9.18

3. **Deploy**: Render will automatically deploy from your repository

#### Option C: Self-Hosted Server

1. **Install system dependencies**:
```bash
# Ubuntu/Debian
sudo apt update
sudo apt install python3.9 python3-pip python3-venv nginx

# CentOS/RHEL
sudo yum install python39 python3-pip nginx
```

2. **Setup application**:
```bash
# Clone and setup
git clone <repository-url> /opt/electrisim-backend
cd /opt/electrisim-backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

3. **Create systemd service** (`/etc/systemd/system/electrisim-backend.service`):
```ini
[Unit]
Description=Electrisim Backend API
After=network.target

[Service]
User=www-data
Group=www-data
WorkingDirectory=/opt/electrisim-backend
Environment=PATH=/opt/electrisim-backend/.venv/bin
ExecStart=/opt/electrisim-backend/.venv/bin/gunicorn --workers 3 --bind 127.0.0.1:5000 app:app
Restart=always

[Install]
WantedBy=multi-user.target
```

4. **Configure Nginx reverse proxy**:
```nginx
server {
    listen 80;
    server_name your-backend-domain.com;
    
    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

5. **Start services**:
```bash
sudo systemctl enable electrisim-backend
sudo systemctl start electrisim-backend
sudo systemctl reload nginx
```

### 6. SSL/HTTPS Configuration

For production deployments, configure SSL:

```bash
# Using Certbot (Let's Encrypt)
sudo certbot --nginx -d your-backend-domain.com
```

### 7. Environment Configuration

#### CORS Settings
The backend is configured to accept requests from:
- Development: `localhost:5500`, `localhost:5501`, `127.0.0.1:5500`, `127.0.0.1:5501`
- Production: `app.electrisim.com`, `www.electrisim.com`, `electrisim.com`

Update CORS origins in `app.py` if deploying to different domains.

#### Environment Variables
```bash
# Production settings
export FLASK_ENV=production
export FLASK_APP=app.py

# Optional: Database configuration (if using database)
export DATABASE_URL=your_database_url

# Optional: API keys for external services
export API_KEY=your_api_key
```

## API Documentation

### Base URL
- **Development**: `http://localhost:5000`
- **Production**: `https://your-backend-domain.com`

### Endpoints

#### `GET /`
**Description**: Health check endpoint  
**Response**: `"Please send data to backend"`

#### `POST /`
**Description**: Main simulation endpoint  
**Content-Type**: `application/json`

**Request Body Structure**:
```json
{
  "simulationType": "powerflow|shortcircuit|contingency|timeseries",
  "elements": {
    "element_id": {
      "typ": "element_type",
      "name": "element_name",
      "parameters": {...}
    }
  },
  "settings": {
    "solver": "pandapower|opendss",
    "tolerance": 1e-6,
    "max_iteration": 100
  }
}
```

**Response Structure**:
```json
{
  "success": true,
  "results": {
    "busbars": [...],
    "lines": [...],
    "transformers": [...],
    "generators": [...],
    "loads": [...]
  },
  "convergence": true,
  "iterations": 5
}
```

### Simulation Types

1. **Power Flow Analysis**
   - Steady-state AC power flow
   - Voltage and power calculations
   - Loss analysis

2. **Short Circuit Analysis**
   - Three-phase fault calculations
   - Line-to-ground faults
   - Protection coordination

3. **Contingency Analysis**
   - N-1 security assessment
   - Critical element identification
   - System stability evaluation

4. **Time Series Simulation**
   - Load profile analysis
   - Renewable integration studies
   - Dynamic system behavior

## Testing

### Run Test Suite

```bash
# Run all tests
pytest

# Run specific test files
pytest test_pandapower.py
pytest test_opendss.py

# Run with coverage
pytest --cov=. --cov-report=html
```

### Test Files Overview

- `test_numeric_conversion_fix.py` - Data validation tests
- `test_transformer_parallel_fix.py` - Transformer modeling tests
- `test_busbar_count.py` - Bus system validation
- `test_voltage_and_generator_fixes.py` - Voltage calculation tests
- `test_comprehensive_fixes.py` - Integration tests

## Dependencies

### Core Dependencies
- **Flask 2.2.2** - Web framework
- **Flask-CORS 3.0.10** - Cross-origin resource sharing
- **pandapower 2.14.11** - Power system analysis
- **py-dss-interface 2.0.4** - OpenDSS integration
- **numpy 1.23** - Numerical computing
- **pandas 2.1.4** - Data manipulation
- **scipy 1.11.4** - Scientific computing

### Production Dependencies
- **gunicorn 20.1.0** - WSGI HTTP server

### Development Dependencies
- **pytest 7.4.3** - Testing framework

## Troubleshooting

### Common Issues

1. **Import Errors**:
   ```bash
   # Ensure all dependencies are installed
   pip install -r requirements.txt
   
   # Check Python version
   python --version  # Should be 3.9.18
   ```

2. **CORS Issues**:
   - Verify frontend URL is in CORS origins list in `app.py`
   - Check that requests include proper headers

3. **Simulation Errors**:
   - Validate input data format
   - Check pandapower/OpenDSS installation
   - Review error logs for specific issues

4. **Performance Issues**:
   - Consider increasing Gunicorn workers
   - Monitor memory usage for large networks
   - Implement caching for repetitive calculations

5. **Deployment Issues**:
   ```bash
   # Check logs
   heroku logs --tail  # For Heroku
   
   # Verify environment variables
   heroku config  # For Heroku
   
   # Test locally first
   gunicorn app:app --bind 0.0.0.0:5000
   ```

## Development

### Project Structure

```
appElectrisimBackend/
├── app.py                          # Flask application entry point
├── pandapower_electrisim.py        # pandapower simulation wrapper
├── opendss_electrisim.py          # OpenDSS simulation wrapper
├── requirements.txt               # Python dependencies
├── runtime.txt                   # Python version for deployment
├── Procfile                      # Process configuration for cloud deployment
├── test_*.py                     # Test suites
└── README.md                     # This file
```

### Adding New Features

1. **Create feature branch**:
```bash
git checkout -b feature/new-analysis-type
```

2. **Implement changes**:
   - Add new simulation functions to appropriate engine file
   - Update API routes in `app.py`
   - Add corresponding tests

3. **Test thoroughly**:
```bash
pytest test_new_feature.py
```

4. **Submit pull request** with comprehensive description

## Performance Considerations

- **Memory Usage**: Large power systems may require significant RAM
- **CPU Usage**: Complex simulations are computationally intensive
- **Scaling**: Consider horizontal scaling for high-traffic deployments
- **Caching**: Implement Redis/Memcached for repeated calculations

## Security

- **CORS Configuration**: Properly configured for known domains
- **Input Validation**: Implement comprehensive input sanitization
- **Rate Limiting**: Consider adding rate limiting for production
- **HTTPS**: Always use HTTPS in production environments

## Contributing

We welcome contributions! Please:

1. Fork the repository
2. Create a feature branch
3. Make changes with tests
4. Submit a pull request

### Development Guidelines
- Follow Python PEP 8 style guidelines
- Add unit tests for new features
- Update documentation for API changes
- Ensure backward compatibility

## License

This project is licensed under the Apache License 2.0 - see the [LICENSE](LICENSE) file for details.

## Support

- **Documentation**: [GitHub Wiki](../../wiki)
- **Issues**: [GitHub Issues](../../issues)
- **API Questions**: Use the `electrisim-api` tag on Stack Overflow

## Roadmap

🚧 **Upcoming Features**:
- integrating OpenDSS for further functionality- 
- Enhanced caching mechanisms
- Machine learning integration
- Distributed computing support
- Integrating AI

---

**Electrisim Backend** - Powering electrical engineering calculations with robust, scalable APIs.

For frontend repository and user interface, visit: [Frontend Repository](../appElectrisim/)
