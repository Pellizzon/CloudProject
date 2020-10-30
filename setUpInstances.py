import boto3
from dotenv import load_dotenv
import os


def create_instances(imageId, instanceType, keyName, securityGroupName, amount):
    instance_params = {
        "ImageId": imageId,
        "InstanceType": instanceType,
        "KeyName": keyName,
        "SecurityGroups": [securityGroupName],
    }
    instances = ec2.create_instances(**instance_params, MinCount=1, MaxCount=amount)
    instancesIds = []
    for i in instances:
        instancesIds.append(i.id)

    return instancesIds


def terminate_instances(keyName):
    instances = ec2.instances.filter(
        Filters=[{"Name": "instance-state-name", "Values": ["running"]}]
    )

    for i in instances:
        if i.key_name == keyName:
            ec2.Instance(i.id).terminate()


if __name__ == "__main__":

    load_dotenv(verbose=True)

    session = boto3.Session(
        aws_access_key_id=os.getenv("ACCESS_KEY"),
        aws_secret_access_key=os.getenv("SECRET_KEY"),
    )

    ec2 = session.resource("ec2", region_name="us-east-1")

    ec2_client = boto3.client(
        "ec2",
        aws_access_key_id=os.getenv("ACCESS_KEY"),
        aws_secret_access_key=os.getenv("SECRET_KEY"),
        region_name="us-east-1",
    )

    keyName = "teste"
    securityGroupName = "grupoTeste"
    ImageId = "ami-0dba2cb6798deb6d8"
    InstanceType = "t2.micro"

    # delete keypair
    try:
        ec2_client.delete_key_pair(KeyName=keyName)
    except:
        print("Key already exists")

    # create keypair
    try:
        key_pair = ec2.create_key_pair(KeyName=keyName)
        with open(f"{keyName}.pem", "w") as pk_file:
            pk_file.write(key_pair.key_material)
    except:
        print("Key doesn't exist")

    # delete existing instances
    try:
        terminate_instances(keyName)
    except:
        print("Error deleting instances")

    # then delete security group (can only be done once all instances associated with it are terminated)
    # try:
    #     ec2_client.delete_security_group(GroupName=securityGroupName)
    # except:
    #     print("Security Group deletion error exist")

    # create security group to add to instances
    try:
        instancesIds = create_instances(
            ImageId, InstanceType, keyName, securityGroupName, 2
        )
    except:
        print("Security Group already exists")

    subnets = ec2_client.describe_subnets()["Subnets"]
    default_subnets_IDs = []
    # caso precise desse id... Todas as subnets possuem o vpc default
    vpc_id = subnets[0]["VpcId"]
    for i in range(len(subnets)):
        default_subnets_IDs.append(subnets[i]["SubnetId"])

    lb_client = boto3.client(
        "elbv2",
        aws_access_key_id=os.getenv("ACCESS_KEY"),
        aws_secret_access_key=os.getenv("SECRET_KEY"),
        region_name="us-east-1",
    )

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
