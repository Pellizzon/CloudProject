import boto3
from dotenv import load_dotenv
import os


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


def create_security_group(client, securityGroupName):
    response = client.create_security_group(
        GroupName=securityGroupName, Description="Teste"
    )
    security_group_id = response["GroupId"]
    permissions = [
        {
            "IpProtocol": "tcp",
            "FromPort": 8080,
            "ToPort": 8080,
            "IpRanges": [{"CidrIp": "0.0.0.0/0"}],
        },
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

    client.authorize_security_group_ingress(
        GroupId=security_group_id,
        IpPermissions=permissions,
    )


def create_instances(
    imageId, instanceType, keyName, securityGroupName, amount, session, script
):
    instance_params = {
        "ImageId": imageId,
        "InstanceType": instanceType,
        "KeyName": keyName,
        "SecurityGroups": [securityGroupName],
    }
    if script is not None:
        instance_params["UserData"] = script
    instances = session.create_instances(**instance_params, MinCount=1, MaxCount=amount)

    print(f"{bcolors.OKGREEN}Created {amount} instace(s){bcolors.ENDC}")

    for i in instances:
        print(f"{bcolors.OKCYAN}Waiting instance {i.id} until running...{bcolors.ENDC}")
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

    print(f"{bcolors.OKCYAN}Instances are being terminated...{bcolors.ENDC}")

    # wait for them to be terminated
    for m in to_terminate:
        print(f"{bcolors.OKGREEN}Waiting instance {m} to terminate...{bcolors.ENDC}")
        session.Instance(m).wait_until_terminated()


def main_region2(securityGroupName, InstanceType):
    keyName_region2 = "teste2"
    region2 = "us-east-2"
    ImageId_region2 = "ami-07efac79022b86107"

    session_region2 = boto3.Session(
        aws_access_key_id=os.getenv("ACCESS_KEY"),
        aws_secret_access_key=os.getenv("SECRET_KEY"),
    )

    ec2_region2 = session_region2.resource("ec2", region_name=region2)

    ec2_client_region2 = boto3.client(
        "ec2",
        aws_access_key_id=os.getenv("ACCESS_KEY"),
        aws_secret_access_key=os.getenv("SECRET_KEY"),
        region_name=region2,
    )

    print(f"{bcolors.HEADER}Initiating Ohio setup{bcolors.ENDC}")

    # delete keypair
    try:
        ec2_client_region2.delete_key_pair(KeyName=keyName_region2)
        print(f"{bcolors.OKBLUE}Key Pair deleted{bcolors.ENDC}")
    except:
        print(f"{bcolors.FAIL}Key already exists{bcolors.ENDC}")

    # create keypair
    try:
        key_pair = ec2_region2.create_key_pair(KeyName=keyName_region2)
        with open(f"{keyName_region2}.pem", "w") as pk_file:
            pk_file.write(key_pair.key_material)
        print(
            f"{bcolors.OKCYAN}Key Pair created and writen in {keyName_region2}.pem file{bcolors.ENDC}"
        )
    except:
        print(f"{bcolors.FAIL}Key doesn't exist{bcolors.ENDC}")

    # delete existing instances
    try:
        terminate_instances(keyName_region2, ec2_region2)
    except:
        print(f"{bcolors.FAIL}Error deleting instances{bcolors.ENDC}")

    # then delete security group (can only be done once all instances associated with it are terminated)
    try:
        ec2_client_region2.delete_security_group(GroupName=securityGroupName)
    except:
        print(f"{bcolors.FAIL}Security Group deletion error{bcolors.ENDC}")

    # create security group to add to instances
    try:
        create_security_group(ec2_client_region2, securityGroupName)
    except:
        print(f"{bcolors.FAIL}Security Group already exists{bcolors.ENDC}")

    script_database = """#!/bin/bash
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
    # create instances
    instances_r2 = create_instances(
        ImageId_region2,
        InstanceType,
        keyName_region2,
        securityGroupName,
        1,
        ec2_region2,
        script_database,
    )

    instances_r2[0].reload()
    public_ip_database = instances_r2[0].public_ip_address

    return public_ip_database


def main_region1(securityGroupName, InstanceType, install_script):
    region1 = "us-east-1"
    keyName_region1 = "teste"
    ImageId_region1 = "ami-0dba2cb6798deb6d8"

    session_region1 = boto3.Session(
        aws_access_key_id=os.getenv("ACCESS_KEY"),
        aws_secret_access_key=os.getenv("SECRET_KEY"),
    )

    ec2_region1 = session_region1.resource("ec2", region_name=region1)

    ec2_client_region1 = boto3.client(
        "ec2",
        aws_access_key_id=os.getenv("ACCESS_KEY"),
        aws_secret_access_key=os.getenv("SECRET_KEY"),
        region_name=region1,
    )

    lb_client = boto3.client(
        "elbv2",
        aws_access_key_id=os.getenv("ACCESS_KEY"),
        aws_secret_access_key=os.getenv("SECRET_KEY"),
        region_name=region1,
    )

    print(f"{bcolors.HEADER}Initiating N. Virginia setup{bcolors.ENDC}")

    # delete keypair
    try:
        ec2_client_region1.delete_key_pair(KeyName=keyName_region1)
        print(f"{bcolors.OKBLUE}Key Pair deleted{bcolors.ENDC}")
    except:
        print(f"{bcolors.FAIL}Key already exists{bcolors.ENDC}")

    # create keypair
    try:
        key_pair = ec2_region1.create_key_pair(KeyName=keyName_region1)
        with open(f"{keyName_region1}.pem", "w") as pk_file:
            pk_file.write(key_pair.key_material)
        print(
            f"{bcolors.OKCYAN}Key Pair created and writen in {keyName_region1}.pem file{bcolors.ENDC}"
        )
    except:
        print(f"{bcolors.FAIL}Key doesn't exist{bcolors.ENDC}")

    # delete existing instances
    try:
        terminate_instances(keyName_region1, ec2_region1)
    except:
        print(f"{bcolors.FAIL}Error deleting instances{bcolors.ENDC}")

    # then delete security group (can only be done once all instances associated with it are terminated)
    try:
        ec2_client_region1.delete_security_group(GroupName=securityGroupName)
    except:
        print(f"{bcolors.FAIL}Security Group deletion error{bcolors.ENDC}")

    # create security group to add to instances
    try:
        create_security_group(ec2_client_region1, securityGroupName)
    except:
        print(f"{bcolors.FAIL}Security Group already exists{bcolors.ENDC}")

    # create instances
    try:
        instances_r1 = create_instances(
            ImageId_region1,
            InstanceType,
            keyName_region1,
            securityGroupName,
            1,
            ec2_region1,
            install_script,
        )
    except:
        print("Error creating instances N Virginia")

    # subnets = ec2_client_region1.describe_subnets()["Subnets"]
    # default_subnets_IDs = []
    # # caso precise desse id... Todas as subnets possuem o vpc default
    # vpc_id = subnets[0]["VpcId"]
    # for i in range(len(subnets)):
    #     default_subnets_IDs.append(subnets[i]["SubnetId"])

    # lb_name = "pell-lb"
    # active_lbs = lb_client.describe_load_balancers()["LoadBalancers"]
    # for i in range(len(active_lbs)):
    #     if active_lbs[i]["LoadBalancerName"] == lb_name:
    #         my_lb_arn = active_lbs[i]["LoadBalancerArn"]

    # try:
    #     lb_client.delete_load_balancer(LoadBalancerArn=my_lb_arn)
    # except:
    #     print("Erro ao deletar loadBalancer")

    # lb_client.create_load_balancer(
    #     Name=lb_name,
    #     Subnets=default_subnets_IDs,
    #     Tags=[{"Key": "name", "Value": "pell-lb"}],
    # )


if __name__ == "__main__":

    load_dotenv(verbose=True)

    # comuns para os dois
    securityGroupName = "grupoTeste"
    InstanceType = "t2.micro"

    """ 
        Parte do projeto desenvolvida na região
        us-east-2 (Ohio)  
    """

    public_ip_database = main_region2(securityGroupName, InstanceType)
    # print(public_ip_database)

    """ 
        Parte do projeto desenvolvida na região
        us-east-1 (North Virginia)    
    """

    install_region1 = f"""#!/bin/bash
    sudo apt update
    sudo apt install python3-dev libpq-dev python3-pip -y
    cd /home/ubuntu
    git clone https://github.com/Pellizzon/tasks.git
    sed -i "83 c 'HOST' : '{public_ip_database}'," tasks/portfolio/settings.py
    sh ./tasks/install.sh"""

    print(install_region1)

    main_region1(securityGroupName, InstanceType, install_region1)
