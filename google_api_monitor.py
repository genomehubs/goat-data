import os
import json
import logging
import smtplib
import requests
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from typing import Dict, List, Optional
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class GoogleAPIQuotaMonitor:
    def __init__(self):
        """Initialize the Google API Quota Monitor."""
        # Configure logging
        self._setup_logging()
        
        # Load configurations
        self.config = self._load_config()
        
        # Initialize credentials and service
        self.credentials = self._initialize_credentials()
        self.services = self._initialize_services()
        
        # Initialize quota tracking
        self.quota_usage = {
            'daily': 0,
            'minute': 0,
            'last_reset': datetime.now()
        }

    def _setup_logging(self):
        """Configure logging settings."""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('api_quota_monitor.log'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)

    def _load_config(self) -> Dict:
        """Load configuration settings from config.json."""
        try:
            with open('config.json', 'r') as f:
                config = json.load(f)
            return config
        except FileNotFoundError:
            self.logger.error("Configuration file not found. Using default settings.")
            return self._get_default_config()

    def _get_default_config(self) -> Dict:
        """Return default configuration settings."""
        return {
            'quota_thresholds': {
                'warning': 80,
                'critical': 90
            },
            'monitoring_interval': 300,  # 5 minutes
            'email_notifications': {
                'enabled': False,
                'smtp_server': os.getenv('SMTP_SERVER', ''),
                'smtp_port': 587,
                'sender_email': os.getenv('SENDER_EMAIL', ''),
                'receiver_email': os.getenv('RECEIVER_EMAIL', ''),
                'smtp_password': os.getenv('SMTP_PASSWORD', '')
            },
            'services_to_monitor': ['sheets', 'drive', 'docs']
        }

    def _initialize_credentials(self) -> service_account.Credentials:
        """Initialize Google API credentials."""
        try:
            credentials_path = os.getenv('GOOGLE_APPLICATION_CREDENTIALS')
            if not credentials_path:
                raise ValueError("GOOGLE_APPLICATION_CREDENTIALS environment variable not set")

            credentials = service_account.Credentials.from_service_account_file(
                credentials_path,
                scopes=['https://www.googleapis.com/auth/cloud-platform']
            )
            return credentials
        except Exception as e:
            self.logger.error(f"Failed to initialize credentials: {e}")
            raise

    def _initialize_services(self) -> Dict:
        """Initialize Google API services."""
        services = {}
        for service_name in self.config['services_to_monitor']:
            try:
                services[service_name] = build(
                    service_name, 
                    'v4' if service_name == 'sheets' else 'v3',
                    credentials=self.credentials
                )
            except Exception as e:
                self.logger.error(f"Failed to initialize {service_name} service: {e}")
        return services

    async def check_quota_usage(self) -> Dict:
        """Check current quota usage for all monitored services."""
        quota_data = {}
        
        for service_name, service in self.services.items():
            try:
                # Get project ID from credentials
                project_id = self.credentials.project_id
                
                # Get quota usage through Cloud Monitoring API
                monitoring_service = build('monitoring', 'v3', credentials=self.credentials)
                
                now = datetime.utcnow()
                start_time = (now - timedelta(hours=1)).isoformat() + 'Z'
                end_time = now.isoformat() + 'Z'
                
                request = monitoring_service.projects().timeSeries().list(
                    name=f'projects/{project_id}',
                    filter=f'metric.type="serviceruntime.googleapis.com/api/request_count"',
                    interval_startTime=start_time,
                    interval_endTime=end_time
                )
                
                response = request.execute()
                
                # Process the response
                quota_data[service_name] = self._process_quota_response(response)
                
            except Exception as e:
                self.logger.error(f"Error checking quota for {service_name}: {e}")
                quota_data[service_name] = {'error': str(e)}
        
        return quota_data

    def _process_quota_response(self, response: Dict) -> Dict:
        """Process the quota response data."""
        processed_data = {
            'daily_usage': 0,
            'daily_limit': 0,
            'minute_usage': 0,
            'minute_limit': 0
        }
        
        try:
            if 'timeSeries' in response:
                for series in response['timeSeries']:
                    metric_kind = series['metric']['type']
                    points = series.get('points', [])
                    
                    if points:
                        latest_point = points[0]
                        value = int(latest_point['value']['int64Value'])
                        
                        if 'daily' in metric_kind.lower():
                            processed_data['daily_usage'] = value
                        elif 'minute' in metric_kind.lower():
                            processed_data['minute_usage'] = value
                            
        except Exception as e:
            self.logger.error(f"Error processing quota response: {e}")
            
        return processed_data

    def check_quota_limits(self, quota_data: Dict):
        """Check if quota usage is approaching limits."""
        for service_name, data in quota_data.items():
            if 'error' in data:
                continue
                
            daily_percentage = (data['daily_usage'] / data['daily_limit'] * 100) if data['daily_limit'] else 0
            minute_percentage = (data['minute_usage'] / data['minute_limit'] * 100) if data['minute_limit'] else 0
            
            # Check against thresholds
            self._check_threshold(service_name, 'daily', daily_percentage)
            self._check_threshold(service_name, 'minute', minute_percentage)

    def _check_threshold(self, service_name: str, quota_type: str, usage_percentage: float):
        """Check usage against thresholds and trigger alerts if needed."""
        thresholds = self.config['quota_thresholds']
        
        if usage_percentage >= thresholds['critical']:
            self._send_alert(service_name, quota_type, usage_percentage, 'CRITICAL')
        elif usage_percentage >= thresholds['warning']:
            self._send_alert(service_name, quota_type, usage_percentage, 'WARNING')

    def _send_alert(self, service_name: str, quota_type: str, usage_percentage: float, level: str):
        """Send alerts for quota usage."""
        message = f"{level} Alert: {service_name} {quota_type} quota usage at {usage_percentage:.2f}%"
        self.logger.warning(message)
        
        if self.config['email_notifications']['enabled']:
            self._send_email_alert(message)

    def _send_email_alert(self, message: str):
        """Send email alert."""
        try:
            email_config = self.config['email_notifications']
            
            msg = MIMEText(message)
            msg['Subject'] = 'Google API Quota Alert'
            msg['From'] = email_config['sender_email']
            msg['To'] = email_config['receiver_email']
            
            with smtplib.SMTP(email_config['smtp_server'], email_config['smtp_port']) as server:
                server.starttls()
                server.login(email_config['sender_email'], email_config['smtp_password'])
                server.send_message(msg)
                
        except Exception as e:
            self.logger.error(f"Failed to send email alert: {e}")

    def generate_report(self, quota_data: Dict) -> str:
        """Generate a detailed report of quota usage."""
        report = ["Google API Quota Usage Report", "=" * 30, ""]
        
        for service_name, data in quota_data.items():
            report.append(f"\nService: {service_name}")
            report.append("-" * 20)
            
            if 'error' in data:
                report.append(f"Error: {data['error']}")
                continue
                
            report.append(f"Daily Usage: {data['daily_usage']} / {data['daily_limit']}")
            report.append(f"Minute Usage: {data['minute_usage']} / {data['minute_limit']}")
            
            # Calculate percentages
            daily_percentage = (data['daily_usage'] / data['daily_limit'] * 100) if data['daily_limit'] else 0
            minute_percentage = (data['minute_usage'] / data['minute_limit'] * 100) if data['minute_limit'] else 0
            
            report.append(f"Daily Usage Percentage: {daily_percentage:.2f}%")
            report.append(f"Minute Usage Percentage: {minute_percentage:.2f}%")
            
        return "\n".join(report)

    def save_report(self, report: str):
        """Save the report to a file."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"quota_report_{timestamp}.txt"
        
        try:
            with open(filename, 'w') as f:
                f.write(report)
            self.logger.info(f"Report saved to {filename}")
        except Exception as e:
            self.logger.error(f"Failed to save report: {e}")

def main():
    """Main function to run the quota monitor."""
    monitor = GoogleAPIQuotaMonitor()
    
    try:
        # Check quota usage
        quota_data = monitor.check_quota_usage()
        
        # Check against limits
        monitor.check_quota_limits(quota_data)
        
        # Generate and save report
        report = monitor.generate_report(quota_data)
        monitor.save_report(report)
        
    except Exception as e:
        monitor.logger.error(f"Error in main execution: {e}")

if __name__ == "__main__":
    main()