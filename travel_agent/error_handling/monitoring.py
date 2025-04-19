"""
Error monitoring system for the travel agent application.
Provides a monitoring dashboard and status tracking for errors.
"""

import logging
import json
import time
import os
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
import threading
from collections import defaultdict, Counter

# Configure logging
logger = logging.getLogger('travel_agent.monitoring')

class ErrorMonitor:
    """
    Error monitoring system that tracks error patterns, frequency, and status.
    Provides a dashboard for monitoring system health.
    """
    
    def __init__(self, log_dir: str = None):
        """
        Initialize error monitor.
        
        Args:
            log_dir: Directory containing log files
        """
        # Default log directory if not specified
        if not log_dir:
            log_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'logs')
        
        self.log_dir = log_dir
        self.error_stats = defaultdict(Counter)
        self.component_status = {}
        self.error_trends = defaultdict(list)
        self.system_status = "healthy"  # overall system status
        
        # Status update interval in seconds
        self.update_interval = 300  # 5 minutes
        
        # Last update timestamp
        self.last_update = 0
        
        # Thread lock for thread safety
        self.lock = threading.RLock()
    
    def register_error(self, error_id: str, component: str, severity: str, timestamp: float) -> None:
        """
        Register an error in the monitoring system.
        
        Args:
            error_id: Unique error ID
            component: Component name
            severity: Error severity
            timestamp: Error timestamp
        """
        with self.lock:
            # Update error statistics
            self.error_stats[component][severity] += 1
            
            # Update error trends (keep last 24 hours)
            current_hour = int(timestamp / 3600)
            self.error_trends[component].append((current_hour, severity))
            
            # Clean up old trend data
            cutoff = current_hour - 24
            self.error_trends[component] = [
                (hour, sev) for hour, sev in self.error_trends[component]
                if hour > cutoff
            ]
            
            # Update component status based on error severity
            if severity == "CRITICAL":
                self.component_status[component] = "critical"
                self.system_status = "degraded"
            elif severity == "ERROR" and self.component_status.get(component) not in ["critical"]:
                self.component_status[component] = "error"
                if self.system_status == "healthy":
                    self.system_status = "warning"
            elif severity == "WARNING" and not self.component_status.get(component):
                self.component_status[component] = "warning"
    
    def update_status(self, force: bool = False) -> Dict[str, Any]:
        """
        Update system status based on recent errors.
        
        Args:
            force: Force update regardless of interval
            
        Returns:
            Current system status
        """
        current_time = time.time()
        
        # Only update if interval has passed or force update is requested
        if not force and (current_time - self.last_update) < self.update_interval:
            return self._get_status_summary()
        
        with self.lock:
            self.last_update = current_time
            
            # Reset status for components with no recent errors
            for component in list(self.component_status.keys()):
                # Check if component has errors in the last hour
                current_hour = int(current_time / 3600)
                recent_errors = [
                    (hour, sev) for hour, sev in self.error_trends[component]
                    if hour > current_hour - 1
                ]
                
                # If no recent errors, improve status
                if not recent_errors:
                    if self.component_status[component] == "critical":
                        self.component_status[component] = "error"
                    elif self.component_status[component] == "error":
                        self.component_status[component] = "warning"
                    elif self.component_status[component] == "warning":
                        del self.component_status[component]
            
            # Update overall system status
            if any(status == "critical" for status in self.component_status.values()):
                self.system_status = "degraded"
            elif any(status == "error" for status in self.component_status.values()):
                self.system_status = "warning"
            else:
                self.system_status = "healthy"
            
            return self._get_status_summary()
    
    def _get_status_summary(self) -> Dict[str, Any]:
        """
        Get current system status summary.
        
        Returns:
            Status summary dictionary
        """
        return {
            "system_status": self.system_status,
            "component_status": dict(self.component_status),
            "error_counts": {
                component: dict(counts)
                for component, counts in self.error_stats.items()
            },
            "last_updated": self.last_update
        }
    
    def get_error_dashboard(self) -> Dict[str, Any]:
        """
        Generate a comprehensive error dashboard.
        
        Returns:
            Dashboard data
        """
        # Force status update
        status = self.update_status(force=True)
        
        # Calculate error trends
        current_hour = int(time.time() / 3600)
        hourly_trends = defaultdict(lambda: defaultdict(int))
        
        for component, errors in self.error_trends.items():
            for hour, severity in errors:
                hour_offset = current_hour - hour
                if hour_offset < 24:  # Last 24 hours
                    hourly_trends[component][hour_offset] += 1
        
        # Format for display
        trends_formatted = {}
        for component, hours in hourly_trends.items():
            trends_formatted[component] = [
                hours.get(hour_offset, 0)
                for hour_offset in range(24)
            ]
        
        # Parse error logs for recent detailed errors
        recent_errors = self._parse_recent_errors(10)
        
        return {
            "status": status,
            "trends": trends_formatted,
            "recent_errors": recent_errors,
            "timestamp": time.time()
        }
    
    def _parse_recent_errors(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Parse log files to extract recent errors.
        
        Args:
            limit: Maximum number of errors to return
            
        Returns:
            List of recent errors
        """
        errors = []
        error_log_path = os.path.join(self.log_dir, 'error.log')
        
        try:
            if os.path.exists(error_log_path):
                with open(error_log_path, 'r') as f:
                    # Read last 100 lines (errors are multi-line)
                    lines = []
                    for line in f:
                        lines.append(line)
                        if len(lines) > 100 * 4:  # Assuming each error takes ~4 lines
                            lines.pop(0)
                    
                    # Parse error entries
                    current_error = {}
                    for line in lines:
                        if ' - ERROR - ' in line or ' - CRITICAL - ' in line:
                            # Start of new error
                            if current_error and len(errors) < limit:
                                errors.append(current_error)
                            
                            # Parse error ID and message
                            parts = line.split(' - ')
                            if len(parts) >= 4:
                                timestamp = parts[0]
                                component = parts[1]
                                level = parts[2]
                                error_id_and_message = parts[3]
                                
                                # Extract error ID
                                error_id = None
                                if '[' in error_id_and_message and ']' in error_id_and_message:
                                    error_id = error_id_and_message.split('[')[1].split(']')[0]
                                    message = error_id_and_message.split(']', 1)[1].strip()
                                else:
                                    message = error_id_and_message
                                
                                current_error = {
                                    "timestamp": timestamp,
                                    "component": component,
                                    "level": level,
                                    "error_id": error_id,
                                    "message": message,
                                    "details": []
                                }
                        elif current_error and 'Context:' in line:
                            try:
                                # Extract context JSON
                                context_json = line.split('Context:', 1)[1].strip()
                                context = json.loads(context_json)
                                current_error["context"] = context
                            except:
                                current_error["details"].append(line.strip())
                        elif current_error:
                            current_error["details"].append(line.strip())
                    
                    # Add the last error if it exists
                    if current_error and len(errors) < limit:
                        errors.append(current_error)
        except Exception as e:
            logger.error(f"Error parsing log file: {str(e)}")
        
        return errors[:limit]

    def reset_component_status(self, component: str) -> None:
        """
        Manually reset a component's status.
        
        Args:
            component: Component name to reset
        """
        with self.lock:
            if component in self.component_status:
                del self.component_status[component]
            self.update_status(force=True)
    
    def get_health_check(self) -> Tuple[Dict[str, Any], int]:
        """
        Get system health check for monitoring and alerting.
        
        Returns:
            Health status and HTTP status code
        """
        status = self.update_status()
        
        health = {
            "status": status["system_status"],
            "components": status["component_status"],
            "timestamp": time.time()
        }
        
        # Determine HTTP status code based on system status
        if status["system_status"] == "healthy":
            http_status = 200
        elif status["system_status"] == "warning":
            http_status = 200  # Still operational
        else:  # degraded
            http_status = 503  # Service unavailable
        
        return health, http_status

# Global instance
error_monitor = ErrorMonitor()

# Flask route handlers for the monitoring dashboard
def register_monitoring_routes(app):
    """
    Register monitoring routes with Flask app.
    
    Args:
        app: Flask application
    """
    from flask import jsonify, render_template, Response
    
    @app.route("/api/health", methods=["GET"])
    def health_check():
        """Health check endpoint for monitoring."""
        health, status_code = error_monitor.get_health_check()
        return jsonify(health), status_code
    
    @app.route("/api/errors/dashboard", methods=["GET"])
    def error_dashboard():
        """Error dashboard data endpoint."""
        dashboard = error_monitor.get_error_dashboard()
        return jsonify(dashboard)
    
    @app.route("/api/errors/reset/<component>", methods=["POST"])
    def reset_component(component):
        """Reset component status."""
        error_monitor.reset_component_status(component)
        return jsonify({"status": "success", "message": f"Reset {component} status"})
