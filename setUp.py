import boto3
from dotenv import load_dotenv
import os

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


def create_security_group(client, securityGroupName, permissions):
    response = client.create_security_group(
        GroupName=securityGroupName, Description="Teste"
    )

    security_group_id = response["GroupId"]

    client.authorize_security_group_ingress(
        GroupId=security_group_id,
        IpPermissions=permissions,
    )


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

    keyNameRegion2 = "teste2"
    region2 = "us-east-2"
    ImageIdRegion2 = "ami-07efac79022b86107"
    databaseSecurityGroupName = "databaseGroup"

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
            ec2ClientRegion2, databaseSecurityGroupName, db_permissions
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

    appSecurityGroupName = "grupoTeste"
    region1 = "us-east-1"
    keyNameRegion1 = "teste"
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

    # delete existing instances
    try:
        terminate_instances(keyNameRegion1, ec2Region1)
    except:
        print(f"\t{bcolors.FAIL}Error deleting instances{bcolors.ENDC}")

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
        create_security_group(ec2ClientRegion1, appSecurityGroupName, appPermissions)
    except:
        print(f"\t{bcolors.FAIL}Security Group already exists{bcolors.ENDC}")

    appParams = {
        "ImageId": ImageIdRegion1,
        "InstanceType": InstanceType,
        "KeyName": keyNameRegion1,
        "SecurityGroups": [appSecurityGroupName],
    }

    scriptAppSetup = f"""#!/bin/bash
    sudo apt update
    sudo apt install python3-dev libpq-dev python3-pip -y
    cd /home/ubuntu
    git clone https://github.com/Pellizzon/tasks.git
    sed -i "83 c 'HOST' : '{publicIpDatabase}'," tasks/portfolio/settings.py
    sh ./tasks/install.sh"""

    # create instance
    instances_r1 = create_instances(
        appParams,
        1,
        ec2Region1,
        scriptAppSetup,
    )

    print(
        f"{bcolors.UNDERLINE}{bcolors.HEADER}Finished initial setup. Starting AutoScaling Group and LoadBalancer{bcolors.ENDC}{bcolors.ENDC}"
    )

    # asClient = boto3.client(
    #     "autoscaling",
    #     aws_access_key_id=os.getenv("ACCESS_KEY"),
    #     aws_secret_access_key=os.getenv("SECRET_KEY"),
    #     region_name=region1,
    # )

    # asGroupName = "AutoScalingORM"
    # asClient.create_auto_scaling_group(
    #     AutoScalingGroupName=asGroupName,
    #     MinSize=1,
    #     MaxSize=5,
    #     DesiredCapacity=1,
    # )

    # lbClient = boto3.client(
    #     "elbv2",
    #     aws_access_key_id=os.getenv("ACCESS_KEY"),
    #     aws_secret_access_key=os.getenv("SECRET_KEY"),
    #     region_name=region1,
    # )

    # subnets = ec2ClientRegion1.describe_subnets()["Subnets"]
    # default_subnets_IDs = []
    # # caso precise desse id... Todas as subnets possuem o vpc default
    # vpc_id = subnets[0]["VpcId"]
    # for i in range(len(subnets)):
    #     default_subnets_IDs.append(subnets[i]["SubnetId"])

    # lb_name = "pell-lb"
    # active_lbs = lbClient.describe_load_balancers()["LoadBalancers"]
    # for i in range(len(active_lbs)):
    #     if active_lbs[i]["LoadBalancerName"] == lb_name:
    #         my_lb_arn = active_lbs[i]["LoadBalancerArn"]

    # try:
    #     lbClient.delete_load_balancer(LoadBalancerArn=my_lb_arn)
    # except:
    #     print("Erro ao deletar loadBalancer")

    # lbClient.create_load_balancer(
    #     Name=lb_name,
    #     Subnets=default_subnets_IDs,
    #     Tags=[{"Key": "name", "Value": "pell-lb"}],
    # )
