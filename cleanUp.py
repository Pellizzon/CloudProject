import boto3
from dotenv import load_dotenv
import os
import time
from botocore.exceptions import ClientError


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
    load_dotenv(verbose=True)

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
        f"{bcolors.UNDERLINE}{bcolors.HEADER}Initiating Ohio cleanup{bcolors.ENDC}{bcolors.ENDC}"
    )

    # delete keypair
    try:
        ec2ClientRegion2.delete_key_pair(KeyName=keyNameRegion2)
        print(f"\t{bcolors.OKBLUE}Key Pair deleted{bcolors.ENDC}")
    except ClientError as e:
        print(f"\t{bcolors.FAIL}{e}{bcolors.ENDC}")

    # delete existing instances
    try:
        terminate_instances(keyNameRegion2, ec2Region2)
    except ClientError as e:
        print(f"\t{bcolors.FAIL}{e}{bcolors.ENDC}")

    # then delete security group (can only be done once all instances associated with it are terminated)
    try:
        ec2ClientRegion2.delete_security_group(GroupName=databaseSecurityGroupName)
    except ClientError as e:
        print(f"\t{bcolors.FAIL}{e}{bcolors.ENDC}")

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
        f"{bcolors.UNDERLINE}{bcolors.HEADER}Initiating N. Virginia cleanup{bcolors.ENDC}{bcolors.ENDC}"
    )

    # delete keypair
    try:
        ec2ClientRegion1.delete_key_pair(KeyName=keyNameRegion1)
        print(f"\t{bcolors.OKBLUE}Key Pair deleted{bcolors.ENDC}")
    except ClientError as e:
        print(f"\t{bcolors.FAIL}{e}{bcolors.ENDC}")

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
        time.sleep(15)
    except ClientError as e:
        print(f"{bcolors.FAIL}{e}{bcolors.ENDC}")

    try:
        active_targetGroups = lbClient.describe_target_groups(Names=[lb_name])[
            "TargetGroups"
        ]
        tgArn_toDelete = active_targetGroups[0]["TargetGroupArn"]
        lbClient.delete_target_group(TargetGroupArn=tgArn_toDelete)
        print(f"\t{bcolors.OKGREEN}Old TargetGroup removed{bcolors.ENDC}")
    except ClientError as e:
        print(f"\t{bcolors.FAIL}{e}{bcolors.ENDC}")

    # delete existing instances
    try:
        terminate_instances(keyNameRegion1, ec2Region1)
    except ClientError as e:
        print(f"\t{bcolors.FAIL}{e}{bcolors.ENDC}")

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
    except ClientError as e:
        print(f"\t{bcolors.FAIL}{e}{bcolors.ENDC}")

    try:
        ASGClient.delete_launch_configuration(LaunchConfigurationName=ASGName)
        time.sleep(5)
        print(f"\t{bcolors.OKGREEN}Previous Launch Configuration removed{bcolors.ENDC}")
    except ClientError as e:
        print(f"\t{bcolors.FAIL}{e}{bcolors.ENDC}")

    # then delete security group (can only be done once all instances associated with it are terminated)
    try:
        ec2ClientRegion1.delete_security_group(GroupName=appSecurityGroupName)
    except ClientError as e:
        print(f"\t{bcolors.FAIL}{e}{bcolors.ENDC}")