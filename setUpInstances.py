import boto3
from dotenv import load_dotenv
import os


class KeyPair:
    def __init__(self, keyName):
        self.keyName = keyName

    def create(self):
        key_pair = ec2.create_key_pair(KeyName=self.keyName)
        with open(f"{self.keyName}.pem", "w") as pk_file:
            pk_file.write(key_pair.key_material)

    def delete(self):
        ec2_client.delete_key_pair(KeyName=self.keyName)


class InstanceManager:
    def __init__(self, imageId, instanceType, keyName, securityGroupName):
        self.imageId = imageId
        self.instanceType = instanceType
        self.keyName = keyName
        self.instanceId = []
        self.securityGroupName = securityGroupName

    def createInstances(self, amount):
        instance_params = {
            "ImageId": self.imageId,
            "InstanceType": self.instanceType,
            "KeyName": self.keyName,
            "SecurityGroups": [self.securityGroupName],
        }
        instances = ec2.create_instances(**instance_params, MinCount=1, MaxCount=amount)
        for i in instances:
            self.instanceId.append(i.id)

    def terminateInstances(self, keyName, wait=False):
        instances = ec2.instances.filter(
            Filters=[{"Name": "instance-state-name", "Values": ["running"]}]
        )

        to_delete = []
        for i in instances:
            if i.key_name == keyName:
                ec2.Instance(i.id).terminate()
                to_delete.append(i.id)

        if wait:
            for i in to_delete:
                ec2.Instance(i).wait_until_terminated()

    def waitUntilRunning(self):
        for i in self.instanceId:
            ec2.Instance(i).wait_until_running()

    def createSecurityGroup(self):
        response = ec2_client.create_security_group(
            GroupName=self.securityGroupName, Description="Teste"
        )
        security_group_id = response["GroupId"]
        ec2_client.authorize_security_group_ingress(
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

    def deleteSecurityGroup(self):
        print(ec2_client.delete_security_group(GroupName=self.securityGroupName))


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

    key = KeyPair("teste")

    try:
        key.delete()
    except:
        print("Key doesn't exist")

    try:
        key.create()
    except:
        print("Key already exists")

    instanceManager = InstanceManager(
        "ami-0dba2cb6798deb6d8", "t2.micro", key.keyName, "grupoTeste"
    )

    instanceManager.terminateInstances(key.keyName, wait=False)

    # try:
    #     instanceManager.deleteSecurityGroup()
    # except:
    #     print("Security Group doesn't exist")

    try:
        instanceManager.createSecurityGroup()
    except:
        print("Security Group already exists")

    instanceManager.createInstances(2)

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
