import boto3
import sys
import os
import time

# --- הגדרות קבועות ---
AMI_ID = "ami-04b4f1a9cf54c11d0"
INSTANCE_TYPE = "t3.micro"
TAG_KEY = "CreatedBy"
TAG_VALUE = "avishag-cli"  # השם הייחודי שלך

# חיבורים לאמזון
ec2 = boto3.client('ec2', region_name='us-east-1')
s3 = boto3.client('s3', region_name='us-east-1')
route53 = boto3.client('route53', region_name='us-east-1')

# =======================
# חלק 1: שרתים (EC2)
# =======================
def create_instance():
    print("🚀 Checking limits...")
    try:
        response = ec2.describe_instances(
            Filters=[{'Name': f'tag:{TAG_KEY}', 'Values': [TAG_VALUE]},
                     {'Name': 'instance-state-name', 'Values': ['running', 'pending']}]
        )
        count = sum(len(r['Instances']) for r in response['Reservations'])
        
        if count >= 2:
            print(f"⛔ STOP! You already have {count}/2 servers. Cannot create more.")
            return

        print("✅ Creating new server...")
        res = ec2.run_instances(
            ImageId=AMI_ID, InstanceType=INSTANCE_TYPE, MinCount=1, MaxCount=1,
            TagSpecifications=[{'ResourceType': 'instance', 
                                'Tags': [{'Key': TAG_KEY, 'Value': TAG_VALUE}, 
                                         {'Key': 'Name', 'Value': 'My-Auto-Server'}]}]
        )
        print(f"🎉 Success! ID: {res['Instances'][0]['InstanceId']}")
    except Exception as e:
        print(f"❌ Error: {e}")

def list_instances():
    print("\n📋 Your Servers:")
    try:
        response = ec2.describe_instances(Filters=[{'Name': f'tag:{TAG_KEY}', 'Values': [TAG_VALUE]}])
        found = False
        for r in response['Reservations']:
            for i in r['Instances']:
                state = i['State']['Name']
                public_ip = i.get('PublicIpAddress', 'N/A')
                print(f"- ID: {i['InstanceId']} | Status: {state} | IP: {public_ip}")
                found = True
        if not found: print("No servers found.")
    except Exception as e:
        print(f"❌ Error: {e}")

def stop_instance():
    list_instances()
    instance_id = input("Enter Instance ID to STOP: ").strip()
    try:
        check = ec2.describe_instances(InstanceIds=[instance_id], Filters=[{'Name': f'tag:{TAG_KEY}', 'Values': [TAG_VALUE]}])
        if not check['Reservations']:
            print("⛔ Access Denied! This server is not yours.")
            return
        ec2.stop_instances(InstanceIds=[instance_id])
        print(f"✅ Stopping server {instance_id}...")
    except Exception as e:
        print(f"❌ Error: {e}")

# =======================
# חלק 2: אחסון (S3)
# =======================
def create_bucket():
    bucket_name = input("Enter unique bucket name: ").strip().lower()
    is_public = input("Should it be public? (yes/no): ").strip().lower()
    
    acl = 'private'
    if is_public == 'yes':
        confirm = input("⚠️ WARNING: Public bucket? (yes/no): ")
        if confirm == 'yes': acl = 'public-read'
        else: print("Cancelled. Defaulting to private.")
    
    try:
        print(f"Creating bucket '{bucket_name}'...")
        s3.create_bucket(Bucket=bucket_name)
        s3.put_bucket_tagging(
            Bucket=bucket_name,
            Tagging={'TagSet': [{'Key': TAG_KEY, 'Value': TAG_VALUE}]}
        )
        if acl == 'public-read':
            try:
                s3.put_bucket_acl(Bucket=bucket_name, ACL='public-read')
                print("🔓 Bucket set to PUBLIC.")
            except:
                print("⚠️ Could not set public access. Created as Private.")
        print(f"✅ Success! Bucket created.")
    except Exception as e:
        print(f"❌ Error: {e}")

def list_buckets():
    print("\n📦 Your S3 Buckets:")
    try:
        response = s3.list_buckets()
        found = False
        for bucket in response['Buckets']:
            name = bucket['Name']
            try:
                tags = s3.get_bucket_tagging(Bucket=name)
                tag_set = tags.get('TagSet', [])
                if any(t['Key'] == TAG_KEY and t['Value'] == TAG_VALUE for t in tag_set):
                    print(f"- Bucket: {name}")
                    found = True
            except: continue
        if not found: print("No managed buckets found.")
    except Exception as e:
        print(f"❌ Error: {e}")

def upload_file():
    list_buckets()
    bucket_name = input("Enter Bucket Name: ").strip()
    file_path = input("Enter file path: ").strip().replace('"', '')
    file_name = os.path.basename(file_path)
    
    try:
        tags = s3.get_bucket_tagging(Bucket=bucket_name)
        tag_set = tags.get('TagSet', [])
        if not any(t['Key'] == TAG_KEY and t['Value'] == TAG_VALUE for t in tag_set):
             print("⛔ Access Denied! Bucket not yours.")
             return
        print(f"⬆️ Uploading {file_name}...")
        s3.upload_file(file_path, bucket_name, file_name)
        print("✅ Upload successful!")
    except Exception as e:
        print(f"❌ Error: {e}")

# =======================
# חלק 3: דומיינים (Route53) - חדש!
# =======================
def create_dns_zone():
    zone_name = input("Enter DNS Zone name (e.g., my-site.com): ").strip()
    try:
        print(f"Creating Hosted Zone: {zone_name}...")
        # יצירת האזור עם חותמת זמן כדי שיהיה ייחודי
        ref = str(time.time())
        res = route53.create_hosted_zone(Name=zone_name, CallerReference=ref)
        zone_id = res['HostedZone']['Id']
        
        # ניקוי ה-ID (הוא מגיע לפעמים עם הקדמה)
        clean_id = zone_id.split('/')[-1]

        # הוספת תגית כדי שנדע שזה שלנו
        route53.change_tags_for_resource(
            ResourceType='hostedzone',
            ResourceId=clean_id,
            AddTags=[{'Key': TAG_KEY, 'Value': TAG_VALUE}]
        )
        print(f"✅ Success! Zone ID: {clean_id}")
    except Exception as e:
        print(f"❌ Error: {e}")

def list_dns_zones():
    print("\n🌐 Your DNS Zones:")
    try:
        response = route53.list_hosted_zones()
        found = False
        for zone in response['HostedZones']:
            clean_id = zone['Id'].split('/')[-1]
            try:
                # בדיקה האם האזור הזה שלנו (לפי תגית)
                tags = route53.list_tags_for_resource(ResourceType='hostedzone', ResourceId=clean_id)
                tag_list = tags['ResourceTagSet']['Tags']
                
                if any(t['Key'] == TAG_KEY and t['Value'] == TAG_VALUE for t in tag_list):
                    print(f"- Zone: {zone['Name']} (ID: {clean_id})")
                    found = True
            except: continue
            
        if not found: print("No managed zones found.")
    except Exception as e:
        print(f"❌ Error: {e}")

def create_dns_record():
    list_dns_zones()
    zone_id = input("Enter Zone ID: ").strip()
    record_name = input("Enter Record Name (e.g., www.my-site.com): ").strip()
    record_value = input("Enter Value (e.g., 1.2.3.4): ").strip()
    
    try:
        # בדיקת בעלות לפני השינוי
        tags = route53.list_tags_for_resource(ResourceType='hostedzone', ResourceId=zone_id)
        tag_list = tags['ResourceTagSet']['Tags']
        if not any(t['Key'] == TAG_KEY and t['Value'] == TAG_VALUE for t in tag_list):
            print("⛔ Access Denied! This zone is not yours.")
            return

        print("Creating DNS Record...")
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
        print("✅ Success! Record created.")
    except Exception as e:
        print(f"❌ Error: {e}")

# =======================
# תפריט ראשי סופי
# =======================
if __name__ == "__main__":
    while True:
        print("\n--- AWS MANAGER CLI (FINAL) ---")
        print("1. [EC2] Create Server")
        print("2. [EC2] List Servers")
        print("3. [EC2] Stop Server")
        print("4. [S3]  Create Bucket")
        print("5. [S3]  List Buckets")
        print("6. [S3]  Upload File")
        print("7. [DNS] Create Zone")
        print("8. [DNS] List Zones")
        print("9. [DNS] Add Record")
        print("0. Exit")
        
        choice = input("Select option: ").strip()

        if choice == "1": create_instance()
        elif choice == "2": list_instances()
        elif choice == "3": stop_instance()
        elif choice == "4": create_bucket()
        elif choice == "5": list_buckets()
        elif choice == "6": upload_file()
        elif choice == "7": create_dns_zone()
        elif choice == "8": list_dns_zones()
        elif choice == "9": create_dns_record()
        elif choice == "0": 
            print("Bye Bye! 👋")
            break
        else:
            print("Invalid option.")