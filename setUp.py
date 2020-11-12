import boto3
from dotenv import load_dotenv
import os
import time

# https://stackoverflow.com/questions/287871/how-to-print-colored-text-in-python
class bcolors:
    HEADER = "\033[95m"
    OKBLUE = "\033[94m"
    OKCYAN = "\033[96m"
    OKGREEN = "\033[92m"
    WARNING = "\033[93m"
    FAIL = "\033[91m"
    ENDC = "\033[0m"
    BOLD = "\033[1m"
    UNDERLINE = "\033[4m"


def create_security_group(client, securityGroupName, permissions, description):
    response = client.create_security_group(
        GroupName=securityGroupName, Description=description
    )

    security_group_id = response["GroupId"]

    client.authorize_security_group_ingress(
        GroupId=security_group_id,
        IpPermissions=permissions,
    )

    return security_group_id


def create_instances(instance_params, amount, session, script):
    if script is not None:
        instance_params["UserData"] = script
    instances = session.create_instances(**instance_params, MinCount=1, MaxCount=amount)

    print(f"\t{bcolors.OKGREEN}Created {amount} instace(s){bcolors.ENDC}")

    for i in instances:
        print(
            f"\t\t{bcolors.OKCYAN}Waiting instance {i.id} until running...{bcolors.ENDC}"
        )
        session.Instance(i.id).wait_until_running()

    return instances


def terminate_instances(keyName, session):
    instances = session.instances.filter(
        Filters=[{"Name": "instance-state-name", "Values": ["running"]}]
    )

    to_terminate = []
    for i in instances:
        if i.key_name == keyName:
            to_terminate.append(i.id)

    # request to terminate instances
    for j in to_terminate:
        session.Instance(j).terminate()

    print(f"\t{bcolors.OKGREEN}Instances are being terminated...{bcolors.ENDC}")

    # wait for them to be terminated
    for m in to_terminate:
        print(f"\t\t{bcolors.OKCYAN}Waiting instance {m} to terminate...{bcolors.ENDC}")
        session.Instance(m).wait_until_terminated()


if __name__ == "__main__":
    """
    Multicloud project using AWS EC2 service
    """

    load_dotenv(verbose=True)

    # common for both regions
    InstanceType = "t2.micro"

    """ 
        Part of the project developed in Ohio,
        amazon's us-east-2 region
    """

    keyNameRegion2 = "pellizzonOhio"
    region2 = "us-east-2"
    ImageIdRegion2 = "ami-07efac79022b86107"
    databaseSecurityGroupName = "pellizzonDatabaseSecurityGroup"

    session_region2 = boto3.Session(
        aws_access_key_id=os.getenv("ACCESS_KEY"),
        aws_secret_access_key=os.getenv("SECRET_KEY"),
    )

    ec2Region2 = session_region2.resource("ec2", region_name=region2)

    ec2ClientRegion2 = boto3.client(
        "ec2",
        aws_access_key_id=os.getenv("ACCESS_KEY"),
        aws_secret_access_key=os.getenv("SECRET_KEY"),
        region_name=region2,
    )

    print(
        f"{bcolors.UNDERLINE}{bcolors.HEADER}Initiating Ohio setup{bcolors.ENDC}{bcolors.ENDC}"
    )

    # delete keypair
    try:
        ec2ClientRegion2.delete_key_pair(KeyName=keyNameRegion2)
        print(f"\t{bcolors.OKBLUE}Key Pair deleted{bcolors.ENDC}")
    except:
        print(f"\t{bcolors.FAIL}Key already exists{bcolors.ENDC}")

    # create keypair
    try:
        key_pair = ec2Region2.create_key_pair(KeyName=keyNameRegion2)
        with open(f"{keyNameRegion2}.pem", "w") as pk_file:
            pk_file.write(key_pair.key_material)
        print(
            f"\t{bcolors.OKBLUE}Key Pair created and written in {keyNameRegion2}.pem file{bcolors.ENDC}"
        )
    except:
        print(f"\t{bcolors.FAIL}Key doesn't exist{bcolors.ENDC}")

    # delete existing instances
    try:
        terminate_instances(keyNameRegion2, ec2Region2)
    except:
        print(f"\t{bcolors.FAIL}Error deleting instances{bcolors.ENDC}")

    # then delete security group (can only be done once all instances associated with it are terminated)
    try:
        ec2ClientRegion2.delete_security_group(GroupName=databaseSecurityGroupName)
    except:
        print(f"\t{bcolors.FAIL}Security Group deletion error{bcolors.ENDC}")

    # create security group to add to instances
    try:
        db_permissions = [
            {
                "IpProtocol": "tcp",
                "FromPort": 22,
                "ToPort": 22,
                "IpRanges": [{"CidrIp": "0.0.0.0/0"}],
            },
            {
                "IpProtocol": "tcp",
                "FromPort": 5432,
                "ToPort": 5432,
                "IpRanges": [{"CidrIp": "0.0.0.0/0"}],
            },
        ]
        create_security_group(
            ec2ClientRegion2,
            databaseSecurityGroupName,
            db_permissions,
            "databseSG Pellizzon",
        )
    except:
        print(
            f"\t{bcolors.FAIL}Security Group already exists or another error might have happened{bcolors.ENDC}"
        )

    scriptDb = """#!/bin/bash
    sudo apt update
    sudo apt install postgresql postgresql-contrib -y
    sudo -u postgres createuser -s -i -d -r -l -w cloud
    sudo -u postgres psql -c "ALTER ROLE cloud WITH PASSWORD 'cloud';"
    sudo -u postgres psql -c "CREATE DATABASE tasks OWNER cloud;"
    sudo -u postgres sed -i "59 c listen_addresses='*'" /etc/postgresql/12/main/postgresql.conf
    sudo -u postgres bash -c 'echo "host all all 0.0.0.0/0 trust" >> /etc/postgresql/12/main/pg_hba.conf'
    sudo ufw allow 5432/tcp
    sudo systemctl restart postgresql
    """

    dbParams = {
        "ImageId": ImageIdRegion2,
        "InstanceType": InstanceType,
        "KeyName": keyNameRegion2,
        "SecurityGroups": [databaseSecurityGroupName],
        "TagSpecifications": [
            {
                "ResourceType": "instance",
                "Tags": [{"Key": "Name", "Value": "PellizzonDB"}],
            }
        ],
    }
    # create instances
    instancesRegion2 = create_instances(
        dbParams,
        1,
        ec2Region2,
        scriptDb,
    )

    instancesRegion2[0].reload()
    publicIpDatabase = instancesRegion2[0].public_ip_address
    # print(publicIpDatabase)

    """ 
        Part of the project developed in North Virginia,
        amazon's us-east-1 region
    """

    appSecurityGroupName = "pellizzonAppSecurityGroup"
    region1 = "us-east-1"
    keyNameRegion1 = "pellizzonNVirginia"
    ImageIdRegion1 = "ami-0dba2cb6798deb6d8"

    sessionRegion1 = boto3.Session(
        aws_access_key_id=os.getenv("ACCESS_KEY"),
        aws_secret_access_key=os.getenv("SECRET_KEY"),
    )

    ec2Region1 = sessionRegion1.resource("ec2", region_name=region1)

    ec2ClientRegion1 = boto3.client(
        "ec2",
        aws_access_key_id=os.getenv("ACCESS_KEY"),
        aws_secret_access_key=os.getenv("SECRET_KEY"),
        region_name=region1,
    )

    lbClient = boto3.client(
        "elbv2",
        aws_access_key_id=os.getenv("ACCESS_KEY"),
        aws_secret_access_key=os.getenv("SECRET_KEY"),
        region_name=region1,
    )

    ASGClient = boto3.client(
        "autoscaling",
        aws_access_key_id=os.getenv("ACCESS_KEY"),
        aws_secret_access_key=os.getenv("SECRET_KEY"),
        region_name=region1,
    )

    print(
        f"{bcolors.UNDERLINE}{bcolors.HEADER}Initiating N. Virginia setup{bcolors.ENDC}{bcolors.ENDC}"
    )

    # delete keypair
    try:
        ec2ClientRegion1.delete_key_pair(KeyName=keyNameRegion1)
        print(f"\t{bcolors.OKBLUE}Key Pair deleted{bcolors.ENDC}")
    except:
        print(f"\t{bcolors.FAIL}Key already exists{bcolors.ENDC}")

    # create keypair
    try:
        key_pair = ec2Region1.create_key_pair(KeyName=keyNameRegion1)
        with open(f"{keyNameRegion1}.pem", "w") as pk_file:
            pk_file.write(key_pair.key_material)
        print(
            f"\t{bcolors.OKBLUE}Key Pair created and written in {keyNameRegion1}.pem file{bcolors.ENDC}"
        )
    except:
        print(f"\t{bcolors.FAIL}Key doesn't exist{bcolors.ENDC}")

    # delete load balancer and wait
    lb_name = "pellizzonLb"
    try:
        active_lbs = lbClient.describe_load_balancers()["LoadBalancers"]
        for i in range(len(active_lbs)):
            if active_lbs[i]["LoadBalancerName"] == lb_name:
                my_lb_arn = active_lbs[i]["LoadBalancerArn"]
                lbClient.delete_load_balancer(LoadBalancerArn=my_lb_arn)
                print(f"\t{bcolors.OKGREEN}Delete Load Balancer{bcolors.ENDC}")
                lbWaiter = lbClient.get_waiter("load_balancers_deleted")
                print(
                    f"\t\t{bcolors.OKCYAN}Waiting Load Balancer to terminate...{bcolors.ENDC}"
                )
                lbWaiter.wait(Names=[lb_name])
    except:
        print(f"{bcolors.FAIL}Couldn't find load balancer{bcolors.ENDC}")

    try:
        active_targetGroups = lbClient.describe_target_groups(Names=[lb_name])[
            "TargetGroups"
        ]
        tgArn_toDelete = active_targetGroups[0]["TargetGroupArn"]
        lbClient.delete_target_group(TargetGroupArn=tgArn_toDelete)
        print(f"\t{bcolors.OKGREEN}Old TargetGroup removed{bcolors.ENDC}")
    except:
        print(f"\t{bcolors.FAIL}Old TargetGroup deletion error{bcolors.ENDC}")

    # delete existing instances
    try:
        terminate_instances(keyNameRegion1, ec2Region1)
    except:
        print(f"\t{bcolors.FAIL}Error deleting instances{bcolors.ENDC}")

    ASGName = "PellizzonAutoScalingORM"
    try:
        ASGClient.delete_auto_scaling_group(
            AutoScalingGroupName=ASGName, ForceDelete=True
        )
        print(f"\t{bcolors.OKGREEN}AutoScaling Group is being deleted{bcolors.ENDC}")
        print(f"\t\t{bcolors.OKCYAN}Waiting...{bcolors.ENDC}")
        # there are no currently available ASG waiters. So in order to create an ASG with the same name,
        # it is necessary to wait the deletion of the older one. Testing for a while, this should work for now.
        time.sleep(80)
    except:
        print(f"\t{bcolors.FAIL}AutoScaling Group deletion failed{bcolors.ENDC}")

    try:
        ASGClient.delete_launch_configuration(LaunchConfigurationName=ASGName)
        time.sleep(5)
        print(f"\t{bcolors.OKGREEN}Previous Launch Configuration removed{bcolors.ENDC}")
    except:
        print(f"\t{bcolors.FAIL}Launch Configuration deletion failed{bcolors.ENDC}")

    # then delete security group (can only be done once all instances associated with it are terminated)
    try:
        ec2ClientRegion1.delete_security_group(GroupName=appSecurityGroupName)
    except:
        print(f"\t{bcolors.FAIL}Security Group deletion error{bcolors.ENDC}")

    # create security group to add to instances
    try:
        appPermissions = [
            {
                "IpProtocol": "tcp",
                "FromPort": 22,
                "ToPort": 22,
                "IpRanges": [{"CidrIp": "0.0.0.0/0"}],
            },
            {
                "IpProtocol": "tcp",
                "FromPort": 8080,
                "ToPort": 8080,
                "IpRanges": [{"CidrIp": "0.0.0.0/0"}],
            },
        ]
        appSG_Id = create_security_group(
            ec2ClientRegion1,
            appSecurityGroupName,
            appPermissions,
            "SG App Pellizzon",
        )
    except:
        print(f"\t{bcolors.FAIL}Security Group already exists{bcolors.ENDC}")

    appParams = {
        "ImageId": ImageIdRegion1,
        "InstanceType": InstanceType,
        "KeyName": keyNameRegion1,
        "SecurityGroups": [appSecurityGroupName],
        "TagSpecifications": [
            {
                "ResourceType": "instance",
                "Tags": [{"Key": "Name", "Value": "PellizzonAMIExample"}],
            }
        ],
    }

    scriptAppSetup = f"""#!/bin/bash
    sudo apt update
    sudo apt install python3-dev libpq-dev python3-pip -y
    cd /home/ubuntu
    git clone https://github.com/Pellizzon/tasks.git
    sed -i "83 c 'HOST' : '{publicIpDatabase}'," tasks/portfolio/settings.py
    sh ./tasks/install.sh"""

    # create instance
    instancesRegion1 = create_instances(
        appParams,
        1,
        ec2Region1,
        scriptAppSetup,
    )

    print(
        f"{bcolors.UNDERLINE}{bcolors.HEADER}Finished initial setup. Starting AutoScaling Group and LoadBalancer{bcolors.ENDC}{bcolors.ENDC}"
    )

    subnets = ec2ClientRegion1.describe_subnets()["Subnets"]
    default_subnets_IDs = []

    vpcId = subnets[0]["VpcId"]
    for i in range(len(subnets)):
        default_subnets_IDs.append(subnets[i]["SubnetId"])

    loadBalancer = lbClient.create_load_balancer(
        Name=lb_name,
        Subnets=default_subnets_IDs,
        Scheme="internet-facing",
        Type="application",
        SecurityGroups=[appSG_Id],
        Tags=[{"Key": "name", "Value": f"{lb_name}"}],
    )

    print(f"\t{bcolors.OKGREEN}LoadBalancer created{bcolors.ENDC}")

    lbArn = loadBalancer.get("LoadBalancers", [{}])[0].get("LoadBalancerArn", None)

    targetGroup = lbClient.create_target_group(
        Name=lb_name, Protocol="HTTP", Port=8080, VpcId=vpcId
    )

    print(f"\t{bcolors.OKGREEN}TargetGroup created{bcolors.ENDC}")

    targetGroupArn = targetGroup.get("TargetGroups", [{}])[0].get(
        "TargetGroupArn", None
    )

    listener = lbClient.create_listener(
        DefaultActions=[{"TargetGroupArn": targetGroupArn, "Type": "forward"}],
        LoadBalancerArn=lbArn,
        Port=8080,
        Protocol="HTTP",
    )

    print(f"\t{bcolors.OKGREEN}LoadBalancer listener created{bcolors.ENDC}")

    ASGClient.create_auto_scaling_group(
        AutoScalingGroupName=ASGName,
        MinSize=1,
        MaxSize=5,
        DesiredCapacity=1,
        InstanceId=instancesRegion1[0].id,
        TargetGroupARNs=[targetGroupArn],
    )

    p = targetGroupArn.find("targetgroup")
    m = lbArn.find("app")

    print(f"\t{bcolors.OKGREEN}AutoScaling Group created{bcolors.ENDC}")

    ASGClient.put_scaling_policy(
        AutoScalingGroupName=ASGName,
        PolicyName="PellizzonAutomaticScaling",
        PolicyType="TargetTrackingScaling",
        TargetTrackingConfiguration={
            "PredefinedMetricSpecification": {
                "PredefinedMetricType": "ALBRequestCountPerTarget",
                "ResourceLabel": lbArn[m:] + "/" + targetGroupArn[p:],
            },
            "TargetValue": 1000,
        },
    )

    print(
        f"\t{bcolors.OKGREEN}Terminating instance {instancesRegion1[0].id}{bcolors.ENDC}"
    )
    ec2Region1.Instance(instancesRegion1[0].id).terminate()
    print(
        f"\t\t{bcolors.OKCYAN}Waiting instance {instancesRegion1[0].id} to terminate...{bcolors.ENDC}"
    )
    ec2Region1.Instance(instancesRegion1[0].id).wait_until_terminated()

    lbDNS = loadBalancer.get("LoadBalancers", [{}])[0].get("DNSName", None)
    print(
        f"{bcolors.WARNING}LoadBalancer can be accessed on: http://{lbDNS}:8080/{bcolors.ENDC}"
    )

    with open("pellizzon", "r") as file:
        code = file.readlines()

    code[7] = f'BASE_URL = "http://{lbDNS}:8080/tasks"\n'

    with open("pellizzon", "w") as file:
        file.writelines(code)
