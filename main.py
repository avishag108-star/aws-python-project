import boto3
import os
import time

REGION = "us-east-1"
INSTANCE_TYPE = "t3.micro"

TAGS = [
    {'Key': 'CreatedBy', 'Value': 'avishag-cli'},
    {'Key': 'Owner', 'Value': 'Avishag'},
    {'Key': 'Project', 'Value': 'AWS-Final-Project'},
    {'Key': 'Environment', 'Value': 'Dev'}
]

ec2 = boto3.client('ec2', region_name=REGION)
s3 = boto3.client('s3', region_name=REGION)
route53 = boto3.client('route53', region_name=REGION)
ssm = boto3.client('ssm', region_name=REGION)


# ---------------- AMI via SSM ----------------

def get_latest_ami():
    try:
        response = ssm.get_parameter(
            Name="/aws/service/ami-amazon-linux-latest/amzn2-ami-hvm-x86_64-gp2"
        )
        return response["Parameter"]["Value"]
    except:
        # Fallback if permission issue
        return "ami-04b4f1a9cf54c11d0"


# ---------------- EC2 ----------------

def get_my_instances():
    response = ec2.describe_instances(
        Filters=[
            {'Name': 'tag:CreatedBy', 'Values': ['avishag-cli']},
            {'Name': 'instance-state-name', 'Values': ['running', 'pending']}
        ]
    )
    instances = []
    for r in response['Reservations']:
        for i in r['Instances']:
            instances.append(i)
    return instances


def create_instance():
    instances = get_my_instances()
    if len(instances) >= 2:
        print("Limit reached: 2 instances max.")
        return

    ami = get_latest_ami()
    print(f"Creating instance (AMI: {ami})...")

    try:
        res = ec2.run_instances(
            ImageId=ami,
            InstanceType=INSTANCE_TYPE,
            MinCount=1,
            MaxCount=1,
            TagSpecifications=[{
                'ResourceType': 'instance',
                'Tags': TAGS + [{'Key': 'Name', 'Value': 'CLI-Server'}]
            }]
        )
        print("Instance created:", res['Instances'][0]['InstanceId'])
    except Exception as e:
        print("Error:", e)


def list_instances():
    instances = get_my_instances()
    if not instances:
        print("No instances found.")
        return

    print("\nMy Instances:")
    for i in instances:
        print(f"ID: {i['InstanceId']} | State: {i['State']['Name']} | IP: {i.get('PublicIpAddress', 'N/A')}")


def stop_instance():
    list_instances()
    instance_id = input("Enter instance ID to stop: ").strip()

    my_ids = [i['InstanceId'] for i in get_my_instances()]
    if instance_id not in my_ids:
        print("Access denied: Not your instance.")
        return

    try:
        ec2.stop_instances(InstanceIds=[instance_id])
        print("Stopping:", instance_id)
    except Exception as e:
        print("Error:", e)


# ---------------- S3 ----------------

def create_bucket():
    bucket = input("Bucket name: ").strip().lower()
    public = input("Public? (yes/no): ").strip().lower()

    acl = "private"
    if public == "yes":
        confirm = input("Are you sure? (yes/no): ").strip().lower()
        if confirm == "yes":
            acl = "public-read"
        else:
            print("Cancelled public access.")
            return

    try:
        s3.create_bucket(Bucket=bucket)

        s3.put_bucket_tagging(
            Bucket=bucket,
            Tagging={'TagSet': TAGS}
        )

        if acl == "public-read":
            try:
                s3.delete_public_access_block(Bucket=bucket)
                s3.put_bucket_acl(Bucket=bucket, ACL="public-read")
                print("Bucket is Public.")
            except:
                print("Could not set public ACL (Check permissions). Created as private.")

        print("Bucket created.")
    except Exception as e:
        print("Error:", e)


def list_buckets():
    print("\nMy Buckets:")
    try:
        response = s3.list_buckets()
        found = False

        for b in response['Buckets']:
            try:
                tags = s3.get_bucket_tagging(Bucket=b['Name'])['TagSet']
                if any(t['Key'] == 'CreatedBy' and t['Value'] == 'avishag-cli' for t in tags):
                    print("-", b['Name'])
                    found = True
            except:
                continue

        if not found:
            print("No buckets found.")
    except Exception as e:
        print("Error:", e)


def upload_file():
    list_buckets()
    bucket = input("Bucket name: ").strip()
    path = input("File path: ").strip().replace('"', '')
    name = os.path.basename(path)

    try:
        tags = s3.get_bucket_tagging(Bucket=bucket)['TagSet']
        if not any(t['Key'] == 'CreatedBy' and t['Value'] == 'avishag-cli' for t in tags):
            print("Access denied.")
            return

        s3.upload_file(path, bucket, name)
        print("Upload complete.")
    except Exception as e:
        print("Error:", e)


# ---------------- Route53 ----------------

def create_dns_zone():
    domain = input("Domain name: ").strip()

    try:
        ref = str(time.time())
        res = route53.create_hosted_zone(Name=domain, CallerReference=ref)
        zone_id = res['HostedZone']['Id'].split('/')[-1]

        route53.change_tags_for_resource(
            ResourceType='hostedzone',
            ResourceId=zone_id,
            AddTags=TAGS
        )

        print("Zone created:", zone_id)
    except Exception as e:
        print("Error:", e)


def list_dns_zones():
    print("\nMy DNS Zones:")
    try:
        response = route53.list_hosted_zones()
        found = False

        for z in response['HostedZones']:
            zid = z['Id'].split('/')[-1]
            try:
                tags = route53.list_tags_for_resource(
                    ResourceType='hostedzone',
                    ResourceId=zid
                )['ResourceTagSet']['Tags']

                if any(t['Key'] == 'CreatedBy' and t['Value'] == 'avishag-cli' for t in tags):
                    print(f"{z['Name']} (ID: {zid})")
                    found = True
            except:
                continue

        if not found:
            print("No zones found.")
    except Exception as e:
        print("Error:", e)


def create_dns_record():
    list_dns_zones()
    zone_id = input("Zone ID: ").strip()
    name = input("Record name: ").strip()
    value = input("IP value: ").strip()

    try:
        tags = route53.list_tags_for_resource(
            ResourceType='hostedzone',
            ResourceId=zone_id
        )['ResourceTagSet']['Tags']

        if not any(t['Key'] == 'CreatedBy' and t['Value'] == 'avishag-cli' for t in tags):
            print("Access denied.")
            return

        route53.change_resource_record_sets(
            HostedZoneId=zone_id,
            ChangeBatch={
                'Changes': [{
                    'Action': 'UPSERT',
                    'ResourceRecordSet': {
                        'Name': name,
                        'Type': 'A',
                        'TTL': 300,
                        'ResourceRecords': [{'Value': value}]
                    }
                }]
            }
        )
        print("Record created.")
    except Exception as e:
        print("Error:", e)


# ---------------- Menu ----------------

def menu():
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
        print("9. Create DNS Record")
        print("0. Exit")

        c = input("Select: ").strip()

        if c == "1": create_instance()
        elif c == "2": list_instances()
        elif c == "3": stop_instance()
        elif c == "4": create_bucket()
        elif c == "5": list_buckets()
        elif c == "6": upload_file()
        elif c == "7": create_dns_zone()
        elif c == "8": list_dns_zones()
        elif c == "9": create_dns_record()
        elif c == "0": break
        else:
            print("Invalid option.")


if __name__ == "__main__":
    menu()