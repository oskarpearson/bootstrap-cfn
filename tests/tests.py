#!/usr/bin/env python

import unittest
from bootstrap_cfn.config import ProjectConfig, ConfigParser
import bootstrap_cfn.errors as errors
from testfixtures import compare
import json


class TestConfig(unittest.TestCase):

    def setUp(self):
        pass

    def test_project_config(self):
        '''
        Test the file is valid YAML and takes and environment
        '''
        config = ProjectConfig('tests/sample-project.yaml', 'dev')
        self.assertEquals(
            sorted(
                config.config.keys()), [
                'ec2', 'elb', 'rds', 's3', 'ssl'])

    def test_project_config_merge_password(self):
        '''
        Test the two config files merge properly by ensuring elements from both files are present
        '''
        config = ProjectConfig(
            'tests/sample-project.yaml',
            'dev',
            'tests/sample-project-passwords.yaml')
        self.assertEquals(
            config.config['rds']['instance-class'],
            'db.t2.micro')
        self.assertEquals(
            config.config['rds']['db-master-password'],
            'testpassword')


class TestConfigParser(unittest.TestCase):

    def setUp(self):
        self.maxDiff = 9000

    def test_iam(self):
        known = {'RolePolicies': {'Type': 'AWS::IAM::Policy',
                                  'Properties': {'PolicyName': 'BaseHost',
                                                 'PolicyDocument': {'Statement': [{'Action': ['autoscaling:Describe*'],
                                                                                   'Resource': '*',
                                                                                   'Effect': 'Allow'},
                                                                                  {'Action': ['ec2:Describe*'],
                                                                                   'Resource': '*',
                                                                                   'Effect': 'Allow'},
                                                                                  {'Action': ['rds:Describe*'],
                                                                                   'Resource': '*',
                                                                                   'Effect': 'Allow'},
                                                                                  {'Action': ['elasticloadbalancing:Describe*'],
                                                                                   'Resource': '*',
                                                                                   'Effect': 'Allow'},
                                                                                  {'Action': ['elasticache:Describe*'],
                                                                                   'Resource': '*',
                                                                                   'Effect': 'Allow'},
                                                                                  {'Action': ['cloudformation:Describe*'],
                                                                                   'Resource': '*',
                                                                                   'Effect': 'Allow'},
                                                                                  {'Action': ['s3:List*'],
                                                                                   'Resource': '*',
                                                                                   'Effect': 'Allow'}]},
                                                 'Roles': [{'Ref': 'BaseHostRole'}]}},
                 'InstanceProfile': {'Type': 'AWS::IAM::InstanceProfile',
                                     'Properties': {'Path': '/',
                                                    'Roles': [{'Ref': 'BaseHostRole'}]}},
                 'BaseHostRole': {'Type': 'AWS::IAM::Role',
                                  'Properties': {'Path': '/',
                                                 'AssumeRolePolicyDocument': {'Statement': [{'Action': ['sts:AssumeRole'],
                                                                                             'Effect': 'Allow',
                                                                                             'Principal': {'Service': ['ec2.amazonaws.com']}}]}}}}
        config = ConfigParser(None, 'my-stack-name')
        self.assertEquals(known, config.iam())

    def test_s3(self):
        known = {
            'StaticBucketPolicy': {
                'Type': 'AWS::S3::BucketPolicy',
                'Properties': {
                    'PolicyDocument': {
                        'Statement': [
                            {
                                'Action': [
                                    's3:Get*',
                                    's3:Put*',
                                    's3:List*'],
                                'Resource': 'arn:aws:s3:::moj-test-dev-static/*',
                                'Effect': 'Allow',
                                'Principal': {
                                    'AWS': '*'}}]},
                    'Bucket': {
                        'Ref': 'StaticBucket'}}},
            'StaticBucket': {
                'Type': 'AWS::S3::Bucket',
                'Properties': {
                    'AccessControl': 'BucketOwnerFullControl',
                    'BucketName': 'moj-test-dev-static'}}}
        config = ConfigParser(
            ProjectConfig(
                'tests/sample-project.yaml',
                'dev').config, 'my-stack-name')
        config = ConfigParser(
            ProjectConfig(
                'tests/sample-project.yaml',
                'dev').config,
            'my-stack-name')
        self.assertEquals(known, config.s3())

    def test_custom_s3_policy(self):
        expected_s3 = [
            {
                'Action': [
                    's3:Get*',
                    's3:Put*',
                    's3:List*',
                    's3:Delete*'],
                'Resource': 'arn:aws:s3:::moj-test-dev-static/*',
                            'Effect': 'Allow',
                            'Principal': {'AWS': '*'}
            }
        ]

        project_config = ProjectConfig('tests/sample-project.yaml', 'dev')

        project_config.config['s3'] = {
            'static-bucket-name': 'moj-test-dev-static',
            'policy': 'tests/sample-custom-s3-policy.json'}

        config = ConfigParser(project_config.config, 'my-stack-name')
        s3_cfg = config.s3()
        s3_custom_cfg = s3_cfg['StaticBucketPolicy'][
            'Properties']['PolicyDocument']['Statement']

        compare(expected_s3, s3_custom_cfg)

    def test_rds(self):
        known = {
            'DatabaseSG': {
                'Type': 'AWS::EC2::SecurityGroup',
                'Properties': {
                    'VpcId': {'Ref': 'VPC'},
                    'GroupDescription': 'SG for EC2 Access to RDS',
                    'SecurityGroupIngress': [
                        {
                            'CidrIp': {'Fn::FindInMap': ['SubnetConfig', 'VPC', 'CIDR']},
                            'IpProtocol': 'tcp',
                            'FromPort': 5432,
                            'ToPort': 5432
                        },
                        {
                            'CidrIp': {'Fn::FindInMap': ['SubnetConfig', 'VPC', 'CIDR']},
                            'IpProtocol': 'tcp',
                            'FromPort': 3306,
                            'ToPort': 3306
                        }
                    ]
                }
            },
            'RDSInstance': {
                'DependsOn': 'DatabaseSG',
                'Type': 'AWS::RDS::DBInstance',
                'Properties': {
                    'AllocatedStorage': 5,
                    'AllowMajorVersionUpgrade': False,
                    'AutoMinorVersionUpgrade': False,
                    'BackupRetentionPeriod': 1,
                    'DBInstanceClass': 'db.t2.micro',
                    'DBInstanceIdentifier': 'test-dev',
                    'DBName': 'test',
                    'VPCSecurityGroups': [{'Fn::GetAtt': ['DatabaseSG', 'GroupId']}],
                    'DBSubnetGroupName': {'Ref': 'RDSSubnetGroup'},
                    'Engine': 'postgres',
                    'EngineVersion': '9.3.5',
                    'MasterUserPassword': 'testpassword',
                    'MasterUsername': 'testuser',
                    'MultiAZ': False,
                    'PubliclyAccessible': False,
                    'StorageEncrypted': False,
                    'StorageType': 'gp2'
                }
            },
            'RDSSubnetGroup': {
                'Properties': {
                    'DBSubnetGroupDescription': 'VPC Subnets', 'SubnetIds': [
                        {
                            'Ref': 'SubnetA'
                        },
                        {
                            'Ref': 'SubnetB'
                        },
                        {
                            'Ref': 'SubnetC'
                        }
                    ]
                },
                'Type': 'AWS::RDS::DBSubnetGroup'
            }
        }

        config = ConfigParser(
            ProjectConfig(
                'tests/sample-project.yaml',
                'dev',
                'tests/sample-project-passwords.yaml').config, 'my-stack-name')
        self.assertEquals(known, config.rds())

    def test_elb(self):

        expected_resources = [
            {'ELBtestdevexternal': {
                u'Properties': {
                    u'Listeners': [
                        {'InstancePort': 80,
                         'LoadBalancerPort': 80,
                         'Protocol': 'TCP'},
                        {'InstancePort': 443,
                         'LoadBalancerPort': 443,
                         'Protocol': 'TCP'}
                    ],
                    u'LoadBalancerName': 'ELB-test-dev-external',
                    u'SecurityGroups': [{u'Ref': u'DefaultSGtestdevexternal'}],
                    u'Scheme': 'internet-facing',
                    u'ConnectionDrainingPolicy': {u'Enabled': True, u'Timeout': 120},
                    u'Subnets': [
                        {u'Ref': u'SubnetA'},
                        {u'Ref': u'SubnetB'},
                        {u'Ref': u'SubnetC'}
                    ],
                },
                u'Type': u'AWS::ElasticLoadBalancing::LoadBalancer'}},
            {'DNStestdevexternal': {
                u'Properties': {
                    u'Comment': u'Zone apex alias targeted to ElasticLoadBalancer.',
                    u'HostedZoneName': 'kyrtest.pf.dsd.io.',
                    u'RecordSets': [
                        {u'AliasTarget': {
                            u'DNSName': {u'Fn::GetAtt': ['ELBtestdevexternal', 'DNSName']},
                            u'HostedZoneId': {u'Fn::GetAtt': ['ELBtestdevexternal', 'CanonicalHostedZoneNameID']}},
                            u'Name': 'test-dev-external.kyrtest.pf.dsd.io.',
                            u'Type': u'A'}
                    ]
                },
                u'Type': u'AWS::Route53::RecordSetGroup'}},
            {'Policytestdevexternal': {
                u'Properties': {
                    u'PolicyDocument': {
                        u'Statement': [{
                            u'Action': [u'elasticloadbalancing:DeregisterInstancesFromLoadBalancer',
                                        u'elasticloadbalancing:RegisterInstancesWithLoadBalancer'],
                            u'Effect': u'Allow',
                            u'Resource': [{u'Fn::Join': [u'',
                                                         [u'arn:aws:elasticloadbalancing:',
                                                          {u'Ref': u'AWS::Region'},
                                                          u':',
                                                          {u'Ref': u'AWS::AccountId'},
                                                          ':loadbalancer/ELBtest-dev-external']]}]}]},
                    u'PolicyName': 'testdevexternalBaseHost',
                    u'Roles': [{u'Ref': u'BaseHostRole'}]},
                u'Type': u'AWS::IAM::Policy'}},
            {'ELBtestdevinternal': {
                u'Properties': {
                    u'Listeners': [
                        {'InstancePort': 80,
                         'LoadBalancerPort': 80,
                         'Protocol': 'TCP'}
                    ],
                    u'LoadBalancerName': 'ELB-test-dev-internal',
                    u'SecurityGroups': [{u'Ref': u'DefaultSGtestdevinternal'}],
                    u'ConnectionDrainingPolicy': {u'Enabled': True, u'Timeout': 120},
                    u'Scheme': 'internal',
                    u'Subnets': [
                        {u'Ref': u'SubnetA'},
                        {u'Ref': u'SubnetB'},
                        {u'Ref': u'SubnetC'}
                    ]
                },
                u'Type': u'AWS::ElasticLoadBalancing::LoadBalancer'}},
            {'DNStestdevinternal': {
                u'Properties': {
                    u'Comment': u'Zone apex alias targeted to ElasticLoadBalancer.',
                    u'HostedZoneName': 'kyrtest.pf.dsd.io.',
                    u'RecordSets': [
                        {u'AliasTarget': {
                            u'DNSName': {u'Fn::GetAtt': ['ELBtestdevinternal', 'DNSName']},
                            u'HostedZoneId': {u'Fn::GetAtt': ['ELBtestdevinternal', 'CanonicalHostedZoneNameID']}},
                            u'Name': 'test-dev-internal.kyrtest.pf.dsd.io.',
                            u'Type': u'A'}
                    ]
                },
                u'Type': u'AWS::Route53::RecordSetGroup'}},
            {'Policytestdevinternal': {u'Properties': {
                u'PolicyDocument': {
                    u'Statement': [{
                        u'Action': [u'elasticloadbalancing:DeregisterInstancesFromLoadBalancer',
                                    u'elasticloadbalancing:RegisterInstancesWithLoadBalancer'],
                        u'Effect': u'Allow',
                        u'Resource': [{u'Fn::Join': [u'',
                                                     [u'arn:aws:elasticloadbalancing:',
                                                      {u'Ref': u'AWS::Region'},
                                                      u':',
                                                      {u'Ref': u'AWS::AccountId'},
                                                      ':loadbalancer/ELBtest-dev-internal']]}]}]},
                        u'PolicyName': 'testdevinternalBaseHost',
                        u'Roles': [{u'Ref': u'BaseHostRole'}]},
                u'Type': u'AWS::IAM::Policy'}}
        ]

        expected_sgs = {
            'DefaultSGtestdevexternal': {
                'Properties': {
                    u'SecurityGroupIngress': [
                        {'ToPort': 443,
                         'IpProtocol': 'tcp',
                         'CidrIp': '0.0.0.0/0',
                         'FromPort': 443},
                        {'ToPort': 80,
                         'IpProtocol': 'tcp',
                         'CidrIp': '0.0.0.0/0',
                         'FromPort': 80}
                    ],
                    'VpcId': {'Ref': 'VPC'},
                    'GroupDescription': 'DefaultELBSecurityGroup'
                },
                'Type': u'AWS::EC2::SecurityGroup',
            },
            'DefaultSGtestdevinternal': {
                'Properties': {
                    u'SecurityGroupIngress': [
                        {'ToPort': 443,
                         'IpProtocol': 'tcp',
                         'CidrIp': '0.0.0.0/0',
                         'FromPort': 443},
                        {'ToPort': 80,
                         'IpProtocol': 'tcp',
                         'CidrIp': '0.0.0.0/0',
                         'FromPort': 80}
                    ],
                    'VpcId': {'Ref': 'VPC'},
                    'GroupDescription': 'DefaultELBSecurityGroup'
                },
                'Type': 'AWS::EC2::SecurityGroup',
            }
        }

        config = ConfigParser(
            ProjectConfig(
                'tests/sample-project.yaml',
                'dev').config, 'my-stack-name')
        elb_cfg, elb_sgs = config.elb()

        compare(expected_resources, elb_cfg)

        compare(expected_sgs, elb_sgs)

    def test_elb_custom_sg(self):

        expected_sgs = {
            'SGName': {
                'Properties': {
                    u'SecurityGroupIngress': [
                        {'ToPort': 443,
                         'IpProtocol': 'tcp',
                         'CidrIp': '1.2.3.4/32',
                         'FromPort': 443},
                    ],
                    'VpcId': {'Ref': 'VPC'},
                    'GroupDescription': 'DefaultELBSecurityGroup'
                },
                'Type': u'AWS::EC2::SecurityGroup',
            },
        }

        project_config = ProjectConfig('tests/sample-project.yaml', 'dev')

        # Remove the "test-dev-internal" ELB
        project_config.config['elb'] = [{
            'name': 'test-dev-external',
            'hosted_zone': 'kyrtest.pf.x',
            'scheme': 'internet-facing',
            'listeners': [
                {'LoadBalancerPort': 443,
                 'InstancePort': 443,
                 'Protocol': 'TCP'}
            ],
            'security_groups': {
                'SGName': [
                    {'IpProtocol': 'tcp',
                     'FromPort': 443,
                     'ToPort': 443,
                     'CidrIp': '1.2.3.4/32'},
                ]
            }
        }]

        config = ConfigParser(project_config.config, 'my-stack-name')
        elb_cfg, elb_sgs = config.elb()

        compare(expected_sgs, elb_sgs)

        [elb] = (e.values()[0] for e in elb_cfg if 'ELBtestdevexternal' in e)
        compare(elb['Properties']['SecurityGroups'],
                [{u'Ref': u'SGName'}])

    def test_cf_includes(self):
        project_config = ProjectConfig('tests/sample-project.yaml',
                                       'dev',
                                       'tests/sample-project-passwords.yaml')
        project_config.config['includes'] = ['tests/sample-include.json']
        known_outputs = {
            "dbhost": {
                "Description": "RDS Hostname",
                "Value": {"Fn::GetAtt": ["RDSInstance", "Endpoint.Address"]}
            },
            "dbport": {
                "Description": "RDS Port",
                "Value": {"Fn::GetAtt": ["RDSInstance", "Endpoint.Port"]}
            },
            "someoutput": {
                "Description": "For tests",
                "Value": "BLAHBLAH"
            }
        }
        config = ConfigParser(project_config.config, 'my-stack-name')
        cfg = json.loads(config.process())
        outputs = cfg['Outputs']
        compare(known_outputs, outputs)

    def test_process_no_elbs_no_rds(self):
        project_config = ProjectConfig('tests/sample-project.yaml', 'dev')
        # Assuming there's no ELB defined
        project_config.config.pop('elb')
        project_config.config.pop('rds')
        config = ConfigParser(project_config.config, 'my-stack-name')
        config.process()

    def test_elb_missing_cert(self):

        self.maxDiff = None
        project_config = ProjectConfig('tests/sample-project.yaml', 'dev')
        # Ugh. Fixtures please?
        project_config.config.pop('ssl')
        project_config.config['elb'] = [{
            'name': 'dev_docker-registry.service',
            'hosted_zone': 'kyrtest.foo.bar.',
            'certificate_name': 'my-cert',
            'scheme': 'internet-facing',
            'listeners': [
                {'LoadBalancerPort': 80,
                 'InstancePort': 80,
                 'Protocol': 'TCP'
                 },
                {'LoadBalancerPort': 443,
                 'InstancePort': 443,
                 'Protocol': 'HTTPS'
                 },
            ],
        }]
        config = ConfigParser(project_config.config, 'my-stack-name')
        with self.assertRaises(errors.CfnConfigError):
            config.elb()

    def test_elb_missing_cert_name(self):

        self.maxDiff = None
        project_config = ProjectConfig('tests/sample-project.yaml', 'dev')
        # Ugh. Fixtures please?
        project_config.config['elb'] = [{
            'name': 'dev_docker-registry.service',
            'hosted_zone': 'kyrtest.foo.bar.',
            'scheme': 'internet-facing',
            'listeners': [
                {'LoadBalancerPort': 80,
                 'InstancePort': 80,
                 'Protocol': 'TCP'
                 },
                {'LoadBalancerPort': 443,
                 'InstancePort': 443,
                 'Protocol': 'HTTPS'
                 },
            ],
        }]
        config = ConfigParser(project_config.config, 'my-stack-name')
        with self.assertRaises(errors.CfnConfigError):
            config.elb()

    def test_elb_with_ssl(self):

        self.maxDiff = None

        known = [
            {'ELBdev_dockerregistryservice': {'Properties': {'Listeners': [{'InstancePort': 80,
                                                                            'LoadBalancerPort': 80,
                                                                            'Protocol': 'TCP'},
                                                                           {'InstancePort': 443,
                                                                               'LoadBalancerPort': 443,
                                                                               'Protocol': 'HTTPS',
                                                                               'SSLCertificateId': {'Fn::Join': ['',
                                                                                                                 ['arn:aws:iam::',
                                                                                                                  {'Ref': 'AWS::AccountId'},
                                                                                                                  ':server-certificate/',
                                                                                                                  'my-cert-my-stack-name']]}}],
                                                             'LoadBalancerName': 'ELB-dev_docker-registryservice',
                                                             'SecurityGroups': [{'Ref': 'DefaultSGdev_dockerregistryservice'}],
                                                             u'ConnectionDrainingPolicy': {u'Enabled': True, u'Timeout': 120},
                                                             'Scheme': 'internet-facing',
                                                             'Subnets': [{'Ref': 'SubnetA'},
                                                                         {'Ref': 'SubnetB'},
                                                                         {'Ref': 'SubnetC'}]},
                                              'Type': 'AWS::ElasticLoadBalancing::LoadBalancer'}},
            {'DNSdev_dockerregistryservice': {'Properties': {'Comment': 'Zone apex alias targeted to ElasticLoadBalancer.',
                                                             'HostedZoneName': 'kyrtest.foo.bar.',
                                                             'RecordSets': [{'AliasTarget': {'DNSName': {'Fn::GetAtt': ['ELBdev_dockerregistryservice',
                                                                                                                        'DNSName']},
                                                                                             'HostedZoneId': {'Fn::GetAtt': ['ELBdev_dockerregistryservice',
                                                                                                                             'CanonicalHostedZoneNameID']}},
                                                                               'Name': 'dev_docker-registry.service.kyrtest.foo.bar.',
                                                                             'Type': 'A'}]},
                                              'Type': 'AWS::Route53::RecordSetGroup'}},
            {'Policydev_dockerregistryservice': {
                u'Properties': {u'PolicyDocument': {u'Statement': [{u'Action': [u'elasticloadbalancing:DeregisterInstancesFromLoadBalancer',
                                                                                u'elasticloadbalancing:RegisterInstancesWithLoadBalancer'],
                                                                    u'Effect': u'Allow',
                                                                    u'Resource': [{u'Fn::Join': [u'',
                                                                                                 [u'arn:aws:elasticloadbalancing:',
                                                                                                  {u'Ref': u'AWS::Region'},
                                                                                                  u':',
                                                                                                  {u'Ref': u'AWS::AccountId'},
                                                                                                  ':loadbalancer/ELBdev_docker-registryservice']]}]}]},
                                u'PolicyName': 'dev_dockerregistryserviceBaseHost',
                                u'Roles': [{u'Ref': u'BaseHostRole'}]},
                u'Type': u'AWS::IAM::Policy'}}
        ]

        project_config = ProjectConfig('tests/sample-project.yaml', 'dev')
        # Ugh. Fixtures please?
        project_config.config['elb'] = [{
            'name': 'dev_docker-registry.service',
            'hosted_zone': 'kyrtest.foo.bar.',
            'scheme': 'internet-facing',
            'certificate_name': 'my-cert',
            'listeners': [
                {'LoadBalancerPort': 80,
                 'InstancePort': 80,
                 'Protocol': 'TCP'
                 },
                {'LoadBalancerPort': 443,
                 'InstancePort': 443,
                 'Protocol': 'HTTPS'
                 },
            ],
        }]
        config = ConfigParser(project_config.config, 'my-stack-name')
        elb_cfg, elb_sgs = config.elb()
        self.assertEquals(known, elb_cfg)

    def test_elb_with_healthcheck(self):
        self.maxDiff = None
        known = [
            {'ELBdev_dockerregistryservice': {'Properties': {'Listeners': [{'InstancePort': 80,
                                                                            'LoadBalancerPort': 80,
                                                                            'Protocol': 'TCP'},
                                                                           {'InstancePort': 443,
                                                                               'LoadBalancerPort': 443,
                                                                               'Protocol': 'TCP'}],
                                                             'LoadBalancerName': 'ELB-dev_docker-registryservice',
                                                             'SecurityGroups': [{'Ref': 'DefaultSGdev_dockerregistryservice'}],
                                                             u'ConnectionDrainingPolicy': {u'Enabled': True, u'Timeout': 120},
                                                             'HealthCheck': {
                                                                 'HealthyThreshold': 10,
                                                                 'Interval': 2,
                                                                 'Target': 'HTTPS:80/blah',
                                                                 'Timeout': 5,
                                                                 'UnhealthyThreshold': 2},
                                                             'Scheme': 'internet-facing',
                                                             'Subnets': [{'Ref': 'SubnetA'},
                                                                         {'Ref': 'SubnetB'},
                                                                         {'Ref': 'SubnetC'}]},
                                              'Type': 'AWS::ElasticLoadBalancing::LoadBalancer'}},
            {'DNSdev_dockerregistryservice': {'Properties': {'Comment': 'Zone apex alias targeted to ElasticLoadBalancer.',
                                                             'HostedZoneName': 'kyrtest.foo.bar.',
                                                             'RecordSets': [{'AliasTarget': {'DNSName': {'Fn::GetAtt': ['ELBdev_dockerregistryservice',
                                                                                                                        'DNSName']},
                                                                                             'HostedZoneId': {'Fn::GetAtt': ['ELBdev_dockerregistryservice',
                                                                                                                             'CanonicalHostedZoneNameID']}},
                                                                               'Name': 'dev_docker-registry.service.kyrtest.foo.bar.',
                                                                             'Type': 'A'}]},
                                              'Type':
                                              'AWS::Route53::RecordSetGroup'}},
            {'Policydev_dockerregistryservice': {u'Properties': {u'PolicyDocument': {
                u'Statement': [{u'Action': [u'elasticloadbalancing:DeregisterInstancesFromLoadBalancer',
                                            u'elasticloadbalancing:RegisterInstancesWithLoadBalancer'],
                                u'Effect': u'Allow',
                                u'Resource': [{u'Fn::Join': [u'',
                                                             [u'arn:aws:elasticloadbalancing:',
                                                                 {u'Ref': u'AWS::Region'},
                                                                 u':',
                                                                 {u'Ref': u'AWS::AccountId'},
                                                                 ':loadbalancer/ELBdev_docker-registryservice']]}]}]},
                u'PolicyName': 'dev_dockerregistryserviceBaseHost',
                u'Roles': [{u'Ref': u'BaseHostRole'}]},
                u'Type': u'AWS::IAM::Policy'}}
        ]
        project_config = ProjectConfig('tests/sample-project.yaml', 'dev')
        project_config.config['elb'] = [{
            'name': 'dev_docker-registry.service',
            'hosted_zone': 'kyrtest.foo.bar.',
            'scheme': 'internet-facing',
            'listeners': [
                {'LoadBalancerPort': 80,
                 'InstancePort': 80,
                 'Protocol': 'TCP'
                 },
                {'LoadBalancerPort': 443,
                 'InstancePort': 443,
                 'Protocol': 'TCP'
                 },
            ],
            'health_check': {
                'HealthyThreshold': 10,
                'Interval': 2,
                'Target': 'HTTPS:80/blah',
                'Timeout': 5,
                'UnhealthyThreshold': 2
            }
        }]
        config = ConfigParser(project_config.config, 'my-stack-name')
        elb_cfg, elb_sgs = config.elb()
        compare(elb_cfg, known)

    def test_elb_with_reserved_chars(self):

        self.maxDiff = None
        known = [
            {'ELBdev_dockerregistryservice': {'Properties': {'Listeners': [{'InstancePort': 80,
                                                                            'LoadBalancerPort': 80,
                                                                            'Protocol': 'TCP'},
                                                                           {'InstancePort': 443,
                                                                               'LoadBalancerPort': 443,
                                                                               'Protocol': 'TCP'}],
                                                             'LoadBalancerName': 'ELB-dev_docker-registryservice',
                                                             'SecurityGroups': [{'Ref': 'DefaultSGdev_dockerregistryservice'}],
                                                             u'ConnectionDrainingPolicy': {u'Enabled': True, u'Timeout': 120},
                                                             'Scheme': 'internet-facing',
                                                             'Subnets': [{'Ref': 'SubnetA'},
                                                                         {'Ref': 'SubnetB'},
                                                                         {'Ref': 'SubnetC'}]},
                                              'Type': 'AWS::ElasticLoadBalancing::LoadBalancer'}},
            {'DNSdev_dockerregistryservice': {'Properties': {'Comment': 'Zone apex alias targeted to ElasticLoadBalancer.',
                                                             'HostedZoneName': 'kyrtest.foo.bar.',
                                                             'RecordSets': [{'AliasTarget': {'DNSName': {'Fn::GetAtt': ['ELBdev_dockerregistryservice',
                                                                                                                        'DNSName']},
                                                                                             'HostedZoneId': {'Fn::GetAtt': ['ELBdev_dockerregistryservice',
                                                                                                                             'CanonicalHostedZoneNameID']}},
                                                                               'Name': 'dev_docker-registry.service.kyrtest.foo.bar.',
                                                                             'Type': 'A'}]},
                                              'Type': 'AWS::Route53::RecordSetGroup'}},
            {'Policydev_dockerregistryservice': {
                u'Properties': {u'PolicyDocument': {u'Statement': [{u'Action': [u'elasticloadbalancing:DeregisterInstancesFromLoadBalancer',
                                                                                u'elasticloadbalancing:RegisterInstancesWithLoadBalancer'],
                                                                    u'Effect': u'Allow',
                                                                    u'Resource': [{u'Fn::Join': [u'',
                                                                                                 [u'arn:aws:elasticloadbalancing:',
                                                                                                  {u'Ref': u'AWS::Region'},
                                                                                                  u':',
                                                                                                  {u'Ref': u'AWS::AccountId'},
                                                                                                  ':loadbalancer/ELBdev_docker-registryservice']]}]}]},
                                u'PolicyName': 'dev_dockerregistryserviceBaseHost',
                                u'Roles': [{u'Ref': u'BaseHostRole'}]},
                u'Type': u'AWS::IAM::Policy'}}
        ]

        project_config = ProjectConfig('tests/sample-project.yaml', 'dev')
        # Ugh. Fixtures please?
        project_config.config['elb'] = [{
            'name': 'dev_docker-registry.service',
            'hosted_zone': 'kyrtest.foo.bar.',
            'scheme': 'internet-facing',
            'listeners': [
                {'LoadBalancerPort': 80,
                 'InstancePort': 80,
                 'Protocol': 'TCP'
                 },
                {'LoadBalancerPort': 443,
                 'InstancePort': 443,
                 'Protocol': 'TCP'
                 },
            ],
        }]
        config = ConfigParser(project_config.config, 'my-stack-name')
        elb_cfg, elb_sgs = config.elb()
        self.assertEquals(known, elb_cfg)

    def test_ec2(self):

        self.maxDiff = None

        known = {
            'BaseHostLaunchConfig': {'Properties': {'AssociatePublicIpAddress': 'true',
                                                    'BlockDeviceMappings': [{'DeviceName': '/dev/sda1',
                                                                             'Ebs': {'VolumeSize': 10}},
                                                                            {'DeviceName': '/dev/sdf',
                                                                             'Ebs': {'VolumeSize': 10}}],
                                                    'IamInstanceProfile': {'Ref': 'InstanceProfile'},
                                                    'ImageId': {'Fn::FindInMap': ['AWSRegion2AMI',
                                                                                  {'Ref': 'AWS::Region'},
                                                                                  'AMI']},
                                                    'InstanceType': 't2.micro',
                                                    'KeyName': 'default',
                                                    'SecurityGroups': [{'Ref': 'BaseHostSG'}, {'Ref': 'AnotherSG'}],
                                                    'UserData': {'Fn::Base64': {'Fn::Join': ['',
                                                                                             ['#!/bin/bash -xe\n',
                                                                                              '#do nothing for now']]}}},
                                     'Type': 'AWS::AutoScaling::LaunchConfiguration'},
            'BaseHostSG': {'Properties': {'GroupDescription': 'BaseHost Security Group',
                                          'SecurityGroupIngress': [{'CidrIp': '0.0.0.0/0',
                                                                    'FromPort': 22,
                                                                    'IpProtocol': 'tcp',
                                                                    'ToPort': 22},
                                                                   {'CidrIp': '0.0.0.0/0',
                                                                    'FromPort': 80,
                                                                    'IpProtocol': 'tcp',
                                                                    'ToPort': 80}],
                                          'VpcId': {'Ref': 'VPC'}},
                           'Type': 'AWS::EC2::SecurityGroup'},
            'AnotherSG': {'Properties': {'GroupDescription': 'BaseHost Security Group',
                                         'SecurityGroupIngress': [{'SourceSecurityGroupName': {'Ref': 'BaseHostSG'},
                                                                   'FromPort': 443,
                                                                   'IpProtocol': 'tcp',
                                                                   'ToPort': 443}],
                                         'VpcId': {'Ref': 'VPC'}},
                          'Type': 'AWS::EC2::SecurityGroup'},
            'ScalingGroup': {'Properties': {'AvailabilityZones': {'Fn::GetAZs': ''},
                                            'DesiredCapacity': 1,
                                            'LaunchConfigurationName': {'Ref': 'BaseHostLaunchConfig'},
                                            'MaxSize': 3,
                                            'MinSize': 0,
                                            'Tags': [{'Key': 'Role',
                                                      'PropagateAtLaunch': True,
                                                      'Value': 'docker'},
                                                     {'Key': 'Apps',
                                                      'PropagateAtLaunch': True,
                                                      'Value': 'test'},
                                                     {'Key': 'Env',
                                                      'PropagateAtLaunch': True,
                                                      'Value': 'dev'}],
                                            'VPCZoneIdentifier': [{'Ref': 'SubnetA'},
                                                                  {'Ref': 'SubnetB'},
                                                                  {'Ref': 'SubnetC'}]},
                             'Type': 'AWS::AutoScaling::AutoScalingGroup'}
        }

        config = ConfigParser(
            ProjectConfig(
                'tests/sample-project.yaml',
                'dev').config, 'my-stack-name')
        compare(known, config.ec2())

    def test_ec2_with_no_block_device_specified(self):
        project_config = ProjectConfig('tests/sample-project.yaml', 'dev')
        project_config.config['ec2'].pop('block_devices')
        config = ConfigParser(project_config.config, 'my-stack-name')
        config_output = config.ec2()['BaseHostLaunchConfig'][
            'Properties']['BlockDeviceMappings']
        known = [{'DeviceName': '/dev/sda1', 'Ebs': {'VolumeSize': 20}}]
        self.assertEquals(known, config_output)

if __name__ == '__main__':
    unittest.main()
