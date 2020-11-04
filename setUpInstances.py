import boto3
from dotenv import load_dotenv
import os


def create_security_group(client, securityGroupName):
    response = client.create_security_group(
        GroupName=securityGroupName, Description="Teste"
    )
    security_group_id = response["GroupId"]
    client.authorize_security_group_ingress(
        GroupId=security_group_id,
        IpPermissions=[
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
        ],
    )


def create_instances(
    imageId, instanceType, keyName, securityGroupName, amount, session
):
    instance_params = {
        "ImageId": imageId,
        "InstanceType": instanceType,
        "KeyName": keyName,
        "SecurityGroups": [securityGroupName],
    }
    instances = session.create_instances(**instance_params, MinCount=1, MaxCount=amount)
    instancesIds = []
    for i in instances:
        instancesIds.append(i.id)

    return instancesIds


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

    # wait for them to be terminated
    for m in to_terminate:
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

    # delete keypair
    try:
        ec2_client_region2.delete_key_pair(KeyName=keyName_region2)
    except:
        print("Key already exists")

    # create keypair
    try:
        key_pair = ec2_region2.create_key_pair(KeyName=keyName_region2)
        with open(f"{keyName_region2}.pem", "w") as pk_file:
            pk_file.write(key_pair.key_material)
    except:
        print("Key doesn't exist")

    # delete existing instances
    try:
        terminate_instances(keyName_region2, ec2_region2)
    except:
        print("Error deleting instances")

    # then delete security group (can only be done once all instances associated with it are terminated)
    try:
        ec2_client_region2.delete_security_group(GroupName=securityGroupName)
    except:
        print("Security Group deletion error exist")

    try:
        create_security_group(ec2_client_region2, securityGroupName)
    except:
        print("Security Group already exists")

    # create security group to add to instances
    try:
        instancesIds = create_instances(
            ImageId_region2,
            InstanceType,
            keyName_region2,
            securityGroupName,
            1,
            ec2_region2,
        )
    except:
        print("Error creating instances Ohio")


def main_region1(securityGroupName, InstanceType):
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

    # delete keypair
    try:
        ec2_client_region1.delete_key_pair(KeyName=keyName_region1)
    except:
        print("Key already exists")

    # create keypair
    try:
        key_pair = ec2_region1.create_key_pair(KeyName=keyName_region1)
        with open(f"{keyName_region1}.pem", "w") as pk_file:
            pk_file.write(key_pair.key_material)
    except:
        print("Key doesn't exist")

    # delete existing instances
    try:
        terminate_instances(keyName_region1, ec2_region1)
    except:
        print("Error deleting instances")

    # then delete security group (can only be done once all instances associated with it are terminated)
    try:
        ec2_client_region1.delete_security_group(GroupName=securityGroupName)
    except:
        print("Security Group deletion error exist")

    # create security group to add to instances
    try:
        create_security_group(ec2_client_region1, securityGroupName)
    except:
        print("Security Group already exists")

    # create instances
    try:
        instancesIds = create_instances(
            ImageId_region1,
            InstanceType,
            keyName_region1,
            securityGroupName,
            2,
            ec2_region1,
        )
    except:
        print("Error creating instances N Virginia")

    subnets = ec2_client_region1.describe_subnets()["Subnets"]
    default_subnets_IDs = []
    # caso precise desse id... Todas as subnets possuem o vpc default
    vpc_id = subnets[0]["VpcId"]
    for i in range(len(subnets)):
        default_subnets_IDs.append(subnets[i]["SubnetId"])

    lb_name = "pell-lb"
    active_lbs = lb_client.describe_load_balancers()["LoadBalancers"]
    for i in range(len(active_lbs)):
        if active_lbs[i]["LoadBalancerName"] == lb_name:
            my_lb_arn = active_lbs[i]["LoadBalancerArn"]

    try:
        lb_client.delete_load_balancer(LoadBalancerArn=my_lb_arn)
    except:
        print("Erro ao deletar loadBalancer")

    lb_client.create_load_balancer(
        Name=lb_name,
        Subnets=default_subnets_IDs,
        Tags=[{"Key": "name", "Value": "pell-lb"}],
    )


if __name__ == "__main__":

    load_dotenv(verbose=True)

    # comuns para os dois
    securityGroupName = "grupoTeste"
    InstanceType = "t2.micro"

    """ 
        Parte do projeto desenvolvida na região
        us-east-2 (Ohio)  
    """

    main_region2(securityGroupName, InstanceType)

    """ 
        Parte do projeto desenvolvida na região
        us-east-1 (North Virginia)    
    """

    main_region1(securityGroupName, InstanceType)
