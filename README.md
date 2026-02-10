# AWS Python CLI – Final Project

This is my submission for the Platform Engineering course.  
I built a Python CLI tool (using boto3) that helps manage AWS resources safely and easily.

## What the tool does

### EC2
- Creates **t3.micro** instances  
- **Hard limit:** maximum of 2 running instances  
- **Auto‑AMI:** pulls the latest Amazon Linux 2 AMI from **SSM Parameter Store**  
- Lists and stops only instances created by this CLI  

### S3
- Creates buckets (Private or Public)  
- Public buckets require explicit confirmation (“Are you sure?”)  
- Uploads files only to buckets created by this CLI  
- Lists only tagged buckets  

### Route53
- Creates Hosted Zones  
- Creates DNS A‑records  
- Lists only zones created by this CLI  

## Safety & Tags

All resources created by the tool include the following tags:

```
CreatedBy = avishag-cli
Owner = Avishag
Project = AWS-Final-Project
Environment = Dev
```

This ensures the tool manages only its own resources.

## Prerequisites
- Python 3 installed  
- AWS CLI configured (`aws configure`)  
- IAM permissions for EC2, S3, Route53, SSM  

## Installation

Clone the repository and install dependencies:

```bash
pip install -r requirements.txt
```

## How to run

```bash
python main.py
```

Choose an option from the menu (for example, press **1** to create an EC2 instance).

## Cleanup

Please remember to manually clean up resources after testing.

### EC2
Terminate instances:
```bash
aws ec2 terminate-instances --instance-ids <ID>
```

### S3
Delete bucket:
```bash
aws s3 rb s3://<bucket-name> --force
```

### Route53
Delete hosted zone:
```bash
aws route53 delete-hosted-zone --id <ZONE_ID>
```
