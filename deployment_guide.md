# Travel Agent Deployment Guide

This guide provides step-by-step instructions for deploying the travel agent application in a production environment.

## Prerequisites

- Linux server (Ubuntu 20.04+ recommended)
- Python 3.10+
- Redis server
- Nginx (for SSL termination and as a reverse proxy)
- API keys for:
  - DeepSeek
  - Groq (optional)
  - Google Serper

## 1. Server Preparation

### Update the system
```bash
sudo apt update
sudo apt upgrade -y
```

### Install required packages
```bash
sudo apt install -y python3-pip python3-venv redis-server nginx supervisor
```

### Start and enable Redis
```bash
sudo systemctl start redis-server
sudo systemctl enable redis-server
```

## 2. Application Setup

### Clone the repository
```bash
git clone https://github.com/your-organization/travel-agent.git
cd travel-agent
```

### Create and activate a virtual environment
```bash
python3 -m venv venv
source venv/bin/activate
```

### Install dependencies
```bash
pip install -r requirements.txt
```

### Configure environment variables
Copy the example environment file and update it with your API keys:
```bash
cp .env.example .env
nano .env
```

Update the following variables in the .env file:
```
DEEPSEEK_API_KEY=your_deepseek_api_key
GROQ_API_KEY=your_groq_api_key
SERPER_API_KEY=your_serper_api_key
REDIS_URL=redis://localhost:6379/0
FLASK_SECRET_KEY=generate_a_secure_random_key
```

## 3. Run Optimizations

Run the optimization script to apply the recommended configurations:
```bash
python optimize_server.py --optimize
```

This will:
- Create a backup of your current configuration
- Generate optimized Gunicorn and Flask-Limiter configurations
- Provide a restore point in case of issues

## 4. Configure Supervisor

Create a supervisor configuration file to manage the Gunicorn process:
```bash
sudo nano /etc/supervisor/conf.d/travel-agent.conf
```

Add the following configuration:
```ini
[program:travel-agent]
directory=/path/to/travel-agent
command=/path/to/travel-agent/venv/bin/gunicorn -c gunicorn_config.py app:app
user=www-data
autostart=true
autorestart=true
startsecs=5
stopwaitsecs=60
stdout_logfile=/var/log/travel-agent/gunicorn.log
stderr_logfile=/var/log/travel-agent/gunicorn-error.log
environment=PYTHONUNBUFFERED=1

[group:travel-agent]
programs=travel-agent
```

Create log directories:
```bash
sudo mkdir -p /var/log/travel-agent
sudo chown www-data:www-data /var/log/travel-agent
```

Reload supervisor:
```bash
sudo supervisorctl reread
sudo supervisorctl update
```

## 5. Configure Nginx

Create an Nginx configuration file:
```bash
sudo nano /etc/nginx/sites-available/travel-agent
```

Add the following configuration:
```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://127.0.0.1:5001;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

Enable the site and restart Nginx:
```bash
sudo ln -s /etc/nginx/sites-available/travel-agent /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

## 6. SSL Configuration (Recommended)

Install certbot:
```bash
sudo apt install -y certbot python3-certbot-nginx
```

Obtain and configure SSL certificate:
```bash
sudo certbot --nginx -d your-domain.com
```

Follow the prompts to complete the SSL configuration.

## 7. Monitoring and Maintenance

### Check application status
```bash
sudo supervisorctl status travel-agent
```

### View logs
```bash
tail -f /var/log/travel-agent/gunicorn.log
tail -f /var/log/travel-agent/gunicorn-error.log
```

### Restart the application
```bash
sudo supervisorctl restart travel-agent
```

## 8. Load Testing

Before going live, it's recommended to perform load testing:
```bash
pip install locust
```

Create a locustfile.py with appropriate test scenarios and run:
```bash
locust -f locustfile.py --host=https://your-domain.com
```

## 9. Backup Strategy

Set up regular backups of:
- Redis data
- Application code
- Configuration files

Example Redis backup script:
```bash
#!/bin/bash
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR=/path/to/backups
redis-cli SAVE
cp /var/lib/redis/dump.rdb $BACKUP_DIR/redis_dump_$TIMESTAMP.rdb
```

## Troubleshooting

### Application doesn't start
- Check error logs: `tail -f /var/log/travel-agent/gunicorn-error.log`
- Verify environment variables: `cat .env`
- Check Python dependencies: `pip list`

### Connection issues
- Verify Redis is running: `sudo systemctl status redis-server`
- Check Nginx configuration: `sudo nginx -t`
- Verify port 5001 is only being used by Gunicorn: `lsof -i :5001`

### API-related issues
- Verify API keys in .env file
- Check API provider status pages
- Look for rate limit errors in the logs

## Restoring from Backup

If you need to restore the application to a previous state:
```bash
python optimize_server.py --restore pre_optimization_TIMESTAMP
```

Replace `TIMESTAMP` with the appropriate backup tag.
