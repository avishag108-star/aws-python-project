# AWS Final Project - Platform Engineering

This is my final project for the course.
It is a CLI tool written in Python (using boto3) that helps manage AWS resources.

## What it does
The tool has a menu to manage these resources:
* **EC2:** Create instances (I added a hard limit of 2 servers), Stop instances, and List them.
* **S3:** Create buckets, Upload files, and List buckets.
* **Route53:** Create DNS zones and records.

## Safety & Tagging
To avoid messing with other resources, the script only works on resources with the tag:
`CreatedBy: avishag-cli`

## Setup & Installation
1. Make sure you have AWS CLI configured.
2. Install the required package:
   ```bash
   pip install -r requirements.txt

How to run the main script:
python main.py