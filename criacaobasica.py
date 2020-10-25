import boto3
from dotenv import load_dotenv
import os

load_dotenv(verbose=True)

print(os.getenv('ACCESS_KEY'))

# client = boto3.client('ec2', 
#     aws_access_key_id=ACCESS_KEY,
#     aws_secret_access_key=SECRET_KEY,
#     region_name='us-east-1'
# )