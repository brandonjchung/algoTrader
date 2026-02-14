"""
Monitoring package for AlgoTrader

Provides InfluxDB metrics writing and email alerts for trading events.
"""

from .metrics_writer import MetricsWriter
from .email_alerts import EmailAlerts

__all__ = ['MetricsWriter', 'EmailAlerts']
