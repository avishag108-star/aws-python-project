import boto3
import sys
import os
import time

# Configuration
AMI_ID = "ami-04b4f1a9cf54c11d0"
INSTANCE_TYPE = "t3.micro"
TAG_KEY = "CreatedBy"
TAG_VALUE = "avishag-cli" 

# Connect to AWS services
ec2 = boto3.client('ec2', region_name='us-east-1')
s3 = boto3.client('s3', region_name='us-east-1')
route53 = boto3.client('route53', region_name='us-east-1')

# --- EC2 Functions ---
def create_instance():
    print("Checking current instances...")
    try:
        # Filter for my specific instances
        response = ec2.describe_instances(
            Filters=[{'Name': f'tag:{TAG_KEY}', 'Values': [TAG_VALUE]},
                     {'Name': 'instance-state-name', 'Values': ['running', 'pending']}]
        )
        count = sum(len(r['Instances']) for r in response['Reservations'])
        
        # Hard limit check
        if count >= 2:
            print(f"Error: You have {count} servers running. Limit is 2.")
            return

        print("Creating new instance...")
        res = ec2.run_instances(
            ImageId=AMI_ID, InstanceType=INSTANCE_TYPE, MinCount=1, MaxCount=1,
            TagSpecifications=[{'ResourceType': 'instance', 
                                'Tags': [{'Key': TAG_KEY, 'Value': TAG_VALUE}, 
                                         {'Key': 'Name', 'Value': 'My-Auto-Server'}]}]
        )
        print(f"Instance created successfully: {res['Instances'][0]['InstanceId']}")
    except Exception as e:
        print(f"Error: {e}")

def list_instances():
    print("\nListing instances:")
    try:
        response = ec2.describe_instances(Filters=[{'Name': f'tag:{TAG_KEY}', 'Values': [TAG_VALUE]}])
        found = False
        for r in response['Reservations']:
            for i in r['Instances']:
                state = i['State']['Name']
                public_ip = i.get('PublicIpAddress', 'N/A')
                print(f"ID: {i['InstanceId']} | Status: {state} | IP: {public_ip}")
                found = True
        if not found: print("No instances found.")
    except Exception as e:
        print(f"Error: {e}")

def stop_instance():
    list_instances()
    instance_id = input("Enter Instance ID to stop: ").strip()
    try:
        # Verify ownership
        check = ec2.describe_instances(InstanceIds=[instance_id], Filters=[{'Name': f'tag:{TAG_KEY}', 'Values': [TAG_VALUE]}])
        if not check['Reservations']:
            print("Access Denied: This instance is not yours.")
            return
        ec2.stop_instances(InstanceIds=[instance_id])
        print(f"Stopping instance {instance_id}...")
    except Exception as e:
        print(f"Error: {e}")

# --- S3 Functions ---
def create_bucket():
    bucket_name = input("Enter bucket name: ").strip().lower()
    is_public = input("Public bucket? (yes/no): ").strip().lower()
    
    acl = 'private'
    if is_public == 'yes':
        confirm = input("Are you sure? (yes/no): ")
        if confirm == 'yes': acl = 'public-read'
    
    try:
        print(f"Creating bucket {bucket_name}...")
        s3.create_bucket(Bucket=bucket_name)
        
        # Add tag for identification
        s3.put_bucket_tagging(
            Bucket=bucket_name,
            Tagging={'TagSet': [{'Key': TAG_KEY, 'Value': TAG_VALUE}]}
        )
        
        if acl == 'public-read':
            try:
                s3.put_bucket_acl(Bucket=bucket_name, ACL='public-read')
                print("Bucket is now Public.")
            except:
                print("Warning: Could not set public access.")
        
        print("Bucket created successfully.")
    except Exception as e:
        print(f"Error: {e}")

def list_buckets():
    print("\nMy Buckets:")
    try:
        response = s3.list_buckets()
        found = False
        for bucket in response['Buckets']:
            name = bucket['Name']
            try:
                tags = s3.get_bucket_tagging(Bucket=name)
                tag_set = tags.get('TagSet', [])
                # Check if tag exists
                if any(t['Key'] == TAG_KEY and t['Value'] == TAG_VALUE for t in tag_set):
                    print(f"- {name}")
                    found = True
            except: continue
        if not found: print("No buckets found.")
    except Exception as e:
        print(f"Error: {e}")

def upload_file():
    list_buckets()
    bucket_name = input("Enter Bucket Name: ").strip()
    # Remove quotes if user added them
    file_path = input("Enter full file path: ").strip().replace('"', '')
    file_name = os.path.basename(file_path)
    
    try:
        # Check permissions
        tags = s3.get_bucket_tagging(Bucket=bucket_name)
        tag_set = tags.get('TagSet', [])
        if not any(t['Key'] == TAG_KEY and t['Value'] == TAG_VALUE for t in tag_set):
             print("Access Denied.")
             return
        
        print(f"Uploading {file_name}...")
        s3.upload_file(file_path, bucket_name, file_name)
        print("Upload complete.")
    except Exception as e:
        print(f"Error: {e}")

# --- Route53 Functions ---
def create_dns_zone():
    zone_name = input("Enter Domain name: ").strip()
    try:
        print(f"Creating Zone: {zone_name}...")
        ref = str(time.time())
        res = route53.create_hosted_zone(Name=zone_name, CallerReference=ref)
        zone_id = res['HostedZone']['Id'].split('/')[-1]

        # Tagging the zone
        route53.change_tags_for_resource(
            ResourceType='hostedzone',
            ResourceId=zone_id,
            AddTags=[{'Key': TAG_KEY, 'Value': TAG_VALUE}]
        )
        print(f"Zone created. ID: {zone_id}")
    except Exception as e:
        print(f"Error: {e}")

def list_dns_zones():
    print("\nMy DNS Zones:")
    try:
        response = route53.list_hosted_zones()
        found = False
        for zone in response['HostedZones']:
            clean_id = zone['Id'].split('/')[-1]
            try:
                tags = route53.list_tags_for_resource(ResourceType='hostedzone', ResourceId=clean_id)
                tag_list = tags['ResourceTagSet']['Tags']
                if any(t['Key'] == TAG_KEY and t['Value'] == TAG_VALUE for t in tag_list):
                    print(f"- {zone['Name']} (ID: {clean_id})")
                    found = True
            except: continue
            
        if not found: print("No zones found.")
    except Exception as e:
        print(f"Error: {e}")

def create_dns_record():
    list_dns_zones()
    zone_id = input("Enter Zone ID: ").strip()
    record_name = input("Enter Record Name: ").strip()
    record_value = input("Enter IP Value: ").strip()
    
    try:
        # Check ownership
        tags = route53.list_tags_for_resource(ResourceType='hostedzone', ResourceId=zone_id)
        tag_list = tags['ResourceTagSet']['Tags']
        if not any(t['Key'] == TAG_KEY and t['Value'] == TAG_VALUE for t in tag_list):
            print("Access Denied.")
            return

        route53.change_resource_record_sets(
            HostedZoneId=zone_id,
            ChangeBatch={
                'Changes': [{
                    'Action': 'UPSERT',
                    'ResourceRecordSet': {
                        'Name': record_name,
                        'Type': 'A',
                        'TTL': 300,
                        'ResourceRecords': [{'Value': record_value}]
                    }
                }]
            }
        )
        print("Record created successfully.")
    except Exception as e:
        print(f"Error: {e}")

# --- Main Menu ---
if __name__ == "__main__":
    while True:
        print("\n--- AWS CLI Tool ---")
        print("1. Create EC2 Instance")
        print("2. List EC2 Instances")
        print("3. Stop EC2 Instance")
        print("4. Create S3 Bucket")
        print("5. List S3 Buckets")
        print("6. Upload File to S3")
        print("7. Create DNS Zone")
        print("8. List DNS Zones")
        print("9. Add DNS Record")
        print("0. Exit")
        
        choice = input("Select: ").strip()

        if choice == "1": create_instance()
        elif choice == "2": list_instances()
        elif choice == "3": stop_instance()
        elif choice == "4": create_bucket()
        elif choice == "5": list_buckets()
        elif choice == "6": upload_file()
        elif choice == "7": create_dns_zone()
        elif choice == "8": list_dns_zones()
        elif choice == "9": create_dns_record()
        elif choice == "0": break
        else: print("Invalid option.")