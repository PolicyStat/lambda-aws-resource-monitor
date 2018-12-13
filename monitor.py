import boto3
import logging
import os

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


def monitor():
    logger.info('Scanning for unexpected EC2 and RDS instances')

    expected_ec2_instances = set(os.environ.get('EXPECTED_EC2_INSTANCES', '').split())
    expected_rds_instances = tuple(os.environ.get('EXPECTED_RDS_INSTANCES', '').split())
    logger.debug(f'expected ec2 instances: {expected_ec2_instances}')
    logger.debug(f'expected rds instances: {expected_rds_instances}')

    unknown_ec2_instances = []

    ec2_instances = list(get_all_ec2_instances())
    ec2_full_names = []
    for region, instance in ec2_instances:
        state = instance.state.get('Name', None)
        if state == 'terminated':
            continue
        full_name = get_proper_ec2_name(region, instance)
        if full_name not in expected_ec2_instances:
            ec2_full_names.append(full_name)
            unknown_ec2_instances.append((full_name, instance))

    if ec2_full_names:
        logger.debug(' '.join(ec2_full_names))

    unknown_rds_instances = []
    rds_instances = list(get_all_rds_instances())
    rds_full_names = []
    for region, instance in rds_instances:
        full_name = get_proper_rds_name(region, instance)
        if not full_name.startswith(expected_rds_instances):
            rds_full_names.append(full_name)
            unknown_rds_instances.append((full_name, instance))

    if rds_full_names:
        logger.debug('RDS Full Names: {}'.format(' '.join(rds_full_names)))

    if not unknown_ec2_instances:
        logger.info('Did not find any unexpected EC2 resources')

    if not unknown_rds_instances:
        logger.info('Did not find any unexpected RDS resources')

    if unknown_ec2_instances or unknown_rds_instances:
        handle_unexpected_instances(unknown_ec2_instances, unknown_rds_instances)


def handle_unexpected_instances(ec2_instances, rds_instances):
    subject = '[AWS Resource Monitor] Warning: Found unexpected resources'

    ec2_description = 'None'
    rds_description = 'None'

    if ec2_instances:
        ec2_descriptions = []
        for full_name, instance in sorted(ec2_instances):
            ec2_descriptions.append(' '.join((
                full_name,
                instance.id,
                instance.state['Name'],
            )))
        ec2_description = '\n'.join(ec2_descriptions)

    if rds_instances:
        rds_descriptions = []
        for full_name, instance in sorted(rds_instances):
            rds_descriptions.append(' '.join((
                full_name,
                instance['DBInstanceStatus'],
                instance['DBInstanceClass'],
            )))
        rds_description = '\n'.join(rds_descriptions)

    message = f'''
The following EC2 instances were unexpectedly found:

{ec2_description}

The following RDS instances were unexpectedly found:

{rds_description}
'''
    send_notice(subject, message)


def send_notice(subject, message):
    logger.info(subject)
    logger.info(message)
    sns_arn = os.environ.get('SNS_TOPIC_ARN', None)
    if sns_arn:
        sns = boto3.client('sns')
        sns.publish(TopicArn=sns_arn, Message=message, Subject=subject)


def get_proper_ec2_name(region, instance):
    deployment = get_ec2_instance_tag_value(instance, 'Deployment')
    node = get_ec2_instance_tag_value(instance, 'Node')
    name = instance.id
    if node and deployment:
        name = f'{deployment}.{node}'

    full_name = f'{region}.{name}'
    return full_name


def get_ec2_instance_tag_value(instance, tag_key):
    try:
        tags = instance.tags
    except Exception as e:
        logger.exception(e)
        return

    tags = tags or []
    values = [tag.get('Value') for tag in tags if tag.get('Key') == tag_key]
    value = values[0] if values else None
    return value


def get_all_ec2_instances():
    ec2_regions = get_ec2_regions()
    for region in ec2_regions:
        conn = boto3.resource('ec2', region_name=region)
        instances = conn.instances.filter()
        for instance in instances:
            yield region, instance


def get_ec2_regions():
    ec2 = boto3.client('ec2')
    ec2_regions = [
        region['RegionName']
        for region in ec2.describe_regions()['Regions']
    ]
    return ec2_regions


def get_rds_regions():
    return boto3.session.Session().get_available_regions('rds')


def get_all_rds_instances():
    rds_regions = get_rds_regions()
    for region in rds_regions:
        conn = boto3.client('rds', region_name=region)
        result = conn.describe_db_instances()
        instances = result.get('DBInstances', [])
        for instance in instances:
            yield region, instance


def get_proper_rds_name(region, instance):
    instance_id = instance['DBInstanceIdentifier']
    return f'{region}.{instance_id}'


if __name__ == '__main__':
    monitor()
