import boto.route53

from bootstrap_cfn import utils


class R53(object):

    # ELB zone ids, these are default for AWS
    # (and may need updating if AWS changes them)
    AWS_ELB_ZONE_ID = {
        "ap-northeast-1": "Z2YN17T5R711GT",
        "ap-southeast-1": "Z1WI8VXHPB1R38",
        "ap-southeast-2": "Z2999QAZ9SRTIC",
        "eu-west-1": "Z3NF1Z3NOM5OY2",
        "eu-central-1": "Z215JYRZR1TBD5",
        "sa-east-1": "Z2ES78Y61JGQKS",
        "us-east-1": "Z3DZXE0Q79N41H",
        "us-west-1": "Z1M58G0W56PQJA",
        "us-west-2": "Z33MTJ483KN6FU"
    }

    conn_cfn = None
    aws_region_name = None
    aws_profile_name = None

    def __init__(self, aws_profile_name, aws_region_name='eu-west-1'):
        self.aws_profile_name = aws_profile_name
        self.aws_region_name = aws_region_name

        self.conn_r53 = utils.connect_to_aws(boto.route53, self)

    def get_hosted_zone_id(self, zone_name):
        """
        Args:
            zone_name
        Returns:
             a zone id or None if no zone found
        """
        zone = self.conn_r53.get_hosted_zone_by_name(zone_name)
        if zone:
            zone = zone['GetHostedZoneResponse']['HostedZone']['Id']
            return zone.replace('/hostedzone/', '')

    def update_dns_record(self, zone, record, record_type, record_value, is_alias=False, dry_run=False):
        """
        Updates a dns record in route53
        Args:
            zone: a string specifying the zone id
            record: a string for the record to update
            record_value: a string if it is not an alias
                            a list, if it is an alias, of parameters to pass to
                            boto record.set_alias() function
            is_alias: a boolean to show if record_value is an alias
            record_type: a string to specify the record, eg "A"
            dry_run:
        Returns True if update successful or raises an exception if not
        """
        changes = boto.route53.record.ResourceRecordSets(self.conn_r53, zone)
        change = changes.add_change("UPSERT", record, record_type, ttl=60)
        if is_alias:
            # provide list of params as needed by function set_alias
            # http://boto.readthedocs.org/en/latest/ref/route53.html#boto.route53.record.Record.set_alias
            change.set_alias(*record_value)
        else:
            change.add_value(record_value)
        if dry_run:
            print(changes)
        else:
            changes.commit()
        return True

    def delete_dns_record(self, zone_id, record_name, record_type, record_value, is_alias=False, dry_run=False):
        """
        Delete a dns record in route53
        Args:
            zone_id: a string specifying the zone id
            record_name: a string for the record to update
            record_value: a string if it is not an alias
                            a list, if it is an alias, of parameters to pass to
                            boto record.set_alias() function
            record_type: a string to specify the record, eg "A"
            is_alias:
            dry_run:
        Returns:
             True if update successful or raises an exception if not
        """
        changes = boto.route53.record.ResourceRecordSets(self.conn_r53, zone_id)
        change = changes.add_change("DELETE", record_name, record_type, ttl=60)
        if is_alias:
            # provide list of params as needed by function set_alias
            # http://boto.readthedocs.org/en/latest/ref/route53.html#boto.route53.record.Record.set_alias
            change.set_alias(*record_value)
        else:
            change.add_value(record_value)
        if dry_run:
            print(changes)
        else:
            changes.commit()
        return True

    def delete_record(self, zone_name, zone_id, elb_name, stack_id, stack_tag, txt_tag_record):
        active_elb_name = "{}-{}".format(elb_name, stack_id)
        active_alias_record_object = self.get_full_record(zone_name, zone_id, active_elb_name, 'A')
        # delete Alias record
        if active_alias_record_object:
            if stack_tag == 'active':
                # if deleting "active"
                # check if this alias record matches active record
                main_alias_record_name = "{}.{}".format(elb_name, zone_name)
                main__alias_record_object = self.get_full_record(zone_name, zone_id, elb_name, 'A')
                main_alias_record_value = [main__alias_record_object.alias_hosted_zone_id,
                                           main__alias_record_object.alias_dns_name,
                                           main__alias_record_object.alias_evaluate_target_health]
                if main__alias_record_object.to_print() == active_alias_record_object.to_print():
                    self.delete_dns_record(zone_id, main_alias_record_name, 'A', main_alias_record_value, is_alias=True)
            else:
                active_alias_record_value = [active_alias_record_object.alias_hosted_zone_id,
                                             active_alias_record_object.alias_dns_name,
                                             active_alias_record_object.alias_evaluate_target_health]
                active_alias_record_name = "{}.{}".format(active_elb_name, zone_name)
                self.delete_dns_record(zone_id, active_alias_record_name, 'A', active_alias_record_value, is_alias=True)

        # delete TXT record
        txt_record_name = "{}.{}".format(txt_tag_record, zone_name)
        txt_record_value = '"{}"'.format(self.get_record(
                zone_name, zone_id, txt_tag_record, 'TXT'))
        if txt_record_value:
            self.delete_dns_record(zone_id, txt_record_name, 'TXT', txt_record_value)
        return True

    def get_record(self, zone_name, zone_id, record_name, record_type):
        """

        Args:
            zone_name:
            zone_id:
            record_name(String):
            record_type:
        Returns:
            String or None, in the event of there being no A or TXT record
        """
        record_fqdn = "{0}.{1}.".format(record_name, zone_name)
        rrsets = self.conn_r53.get_all_rrsets(zone_id, type=record_type, name=record_fqdn)
        for rr in rrsets:
            if rr.type == record_type and rr.name == record_fqdn:
                if rr.type == 'TXT':
                    rr.resource_records[0] = rr.resource_records[0][1:-1]
                if rr.type == 'A':
                    if rr.alias_dns_name:
                        return rr.alias_dns_name
                return rr.resource_records[0]
        return None

    def get_full_record(self, zone_name, zone_id, record_name, record_type):
        """
        Args:
            zone_name:
            zone_id:
            record_name:
            record_type:

        Returns:
            RecordObject
        """
        record_fqdn = "{0}.{1}.".format(record_name, zone_name)
        rrsets = self.conn_r53.get_all_rrsets(zone_id, type=record_type, name=record_fqdn)
        for rr in rrsets:
            if rr.type == record_type and rr.name == record_fqdn:
                return rr
        return None

    def hastag(self, zone_name, zone_id, record_name):
        """
        Check if stack_tag is in use
        Args:
            zone_name:
            zone_id:
            record_name:
        Returns:
            String if stack exists
            None if not.
        """
        hasrecord = self.get_record(zone_name, zone_id, record_name, 'TXT')
        return hasrecord
