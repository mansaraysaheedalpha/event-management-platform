#!/usr/bin/env python3
"""
Campaign Email Worker Entrypoint

Kafka consumer that processes sponsor email campaigns.
Consumes from topic: sponsor.campaigns.v1
Sends emails via Resend API.

Usage:
    python run_campaign_worker.py
"""
import sys
import os

# Add the app directory to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.workers.campaign_email_worker import main

if __name__ == "__main__":
    main()
