import Boto3
import time

# AWS Region
region = 'N. Virginia'

# Web Application Deployment
s3_bucket_name = 'boto3'
ec2_instance_type = 't2.micro'
key_pair_name = 'your-key-pair-name'
security_group_id = 'your-security-group-id'
subnet_id = 'your-subnet-id'
web_app_script = 'your-web-app-deployment-script.sh'

# Load Balancing with ELB
elb_name = 'your-elb-name'

# Auto Scaling Group (ASG) Configuration
asg_name = 'your-asg-name'
min_size = 1
max_size = 3
desired_capacity = 1
scaling_policy_name = 'your-scaling-policy'
scaling_metric = 'AverageCPUUtilization'
scaling_threshold = 70  # Adjust as needed

# Lambda-based Health Checks & Management
health_check_lambda_name = 'health-check-lambda'
sns_topic_arn = 'your-sns-topic-arn'

# S3 Logging & Monitoring
log_analysis_lambda_name = 'log-analysis-lambda'
alb_arn = 'your-alb-arn'
s3_logs_bucket = 'your-s3-logs-bucket'

# SNS Notifications
sns_health_topic = 'arn:aws:sns:your-region:your-account-id:health-notifications'
sns_scaling_topic = 'arn:aws:sns:your-region:your-account-id:scaling-events'
sns_traffic_topic = 'arn:aws:sns:your-region:your-account-id:high-traffic-alerts'

# Infrastructure Automation
def deploy_infrastructure():
    # Create S3 bucket for static files
    s3_client = boto3.client('s3', region_name=region)
    s3_client.create_bucket(Bucket=s3_bucket_name)

    # Launch EC2 instance and deploy web application
    ec2_client = boto3.client('ec2', region_name=region)
    response = ec2_client.run_instances(
        ImageId='your-ami-id',
        InstanceType=ec2_instance_type,
        KeyName=key_pair_name,
        SecurityGroupIds=[security_group_id],
        SubnetId=subnet_id,
        UserData=web_app_script
    )

    instance_id = response['Instances'][0]['InstanceId']

    # Deploy ALB
    elbv2_client = boto3.client('elbv2', region_name=region)
    response = elbv2_client.create_load_balancer(
        Name=elb_name,
        Subnets=[subnet_id],
        SecurityGroups=[security_group_id],
        Scheme='internet-facing'
    )

    alb_arn = response['LoadBalancers'][0]['LoadBalancerArn']

    # Register EC2 instance with ALB
    target_group_response = elbv2_client.create_target_group(
        Name='target-group-for-' + asg_name,
        Protocol='HTTP',
        Port=80,
        VpcId='your-vpc-id'
    )

    elbv2_client.register_targets(
        TargetGroupArn=target_group_response['TargetGroups'][0]['TargetGroupArn'],
        Targets=[
            {
                'Id': instance_id,
            },
        ]
    )

    # Create ASG
    autoscaling_client = boto3.client('autoscaling', region_name=region)
    response = autoscaling_client.create_launch_configuration(
        LaunchConfigurationName='launch-config-for-' + asg_name,
        ImageId='your-ami-id',
        InstanceType=ec2_instance_type,
        KeyName=key_pair_name,
        SecurityGroups=[security_group_id]
    )

    autoscaling_client.create_auto_scaling_group(
        AutoScalingGroupName=asg_name,
        LaunchConfigurationName='launch-config-for-' + asg_name,
        MinSize=min_size,
        MaxSize=max_size,
        DesiredCapacity=desired_capacity,
        VPCZoneIdentifier=subnet_id,
        HealthCheckType='ELB',
        HealthCheckGracePeriod=300,
        Tags=[
            {
                'Key': 'Name',
                'Value': asg_name,
                'PropagateAtLaunch': True
            },
        ]
    )

    # Lambda for Health Checks
    lambda_client = boto3.client('lambda', region_name=region)
    health_check_lambda_code = """
        import boto3
        
        def lambda_handler(event, context):
            elbv2 = boto3.client('elbv2')
            asg = boto3.client('autoscaling')
            sns = boto3.client('sns')
            
            target_group_arn = 'your-target-group-arn'
            target_health = elbv2.describe_target_health(TargetGroupArn=target_group_arn)
            
            for target in target_health['TargetHealthDescriptions']:
                if target['TargetHealth']['State'] == 'unhealthy':
                    instance_id = target['Target']['Id']
                    
                    # Capture a snapshot of the failing instance
                    ec2 = boto3.client('ec2')
                    ec2.create_snapshot(VolumeId='your-volume-id', Description=f'Snapshot for instance {instance_id}')
                    
                    # Terminate the problematic instance
                    asg.terminate_instance_in_auto_scaling_group(InstanceId=instance_id, ShouldDecrementDesiredCapacity=True)
                    
                    # Send a notification through SNS to the administrators
                    sns.publish(TopicArn='your-sns-topic-arn', Message=f'Instance {instance_id} terminated due to health issues.')
    """

    lambda_client.create_function(
        FunctionName=health_check_lambda_name,
        Runtime='python3.8',
        Role='your-iam-role-arn',
        Handler='lambda_function.lambda_handler',
        Code={
            'ZipFile': health_check_lambda_code
        },
        Timeout=30
    )

    # Configure CloudWatch Alarms for ASG scaling policies
    cloudwatch_client = boto3.client('cloudwatch', region_name=region)
    cloudwatch_client.put_metric_alarm(
        AlarmName='scale-out-alarm',
        AlarmDescription='Scale Out Alarm',
        ActionsEnabled=True,
        AlarmActions=[sns_scaling_topic],
        MetricName=scaling_metric,
        Namespace='AWS/EC2',
        Statistic='Average',
        Period=300,
        EvaluationPeriods=1,
        Threshold=scaling_threshold,
        ComparisonOperator='GreaterThanOrEqualToThreshold',
        Dimensions=[
            {
                'Name': 'AutoScalingGroupName',
                'Value': asg_name
            },
        ]
    )

# Call the deploy_infrastructure function
deploy_infrastructure()
