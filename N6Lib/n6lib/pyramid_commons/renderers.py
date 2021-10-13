# Copyright (c) 2013-2021 NASK. All rights reserved.

from io import StringIO
import csv
import urllib.parse

from n6lib.const import SURICATA_SNORT_CATEGORIES as _SURICATA_SNORT_CATEGORIES
from n6lib.common_helpers import as_bytes
from n6sdk.pyramid_commons import register_stream_renderer
from n6sdk.pyramid_commons.renderers import BaseStreamRenderer


class _BlRuleTemplate(object):

    def __init__(self, line_template):
        self.line_template = line_template  # line template must accept 'ip' keyword for str.format()

    def format(self, **data):
        result = []
        for ip in data['ip_list']:
            data['ip'] = ip
            result.append(self.line_template.format(**data))
        return ''.join(result)


class _BaseSnortSuricataRenderer(BaseStreamRenderer):

    content_type = "text/plain"

    RULE_TEMPLATE = None

    # sid = (n6id & SID_MASK) | SID_OFFSET
    SID_MASK = 0x7FFFFFFF
    SID_OFFSET = 0x80000000

    CONFIDENCE_TO_INT = {'low': 1, 'medium': 2, 'high': 3}
    SURICATA_SNORT_CATEGORIES = {
        category: details
        for category, details in _SURICATA_SNORT_CATEGORIES.items()
        if details['include']
    }

    def filter_renderer_specific(self, data, **kwargs):
        raise NotImplemented

    def filter_common(self, data, **kwargs):
        if data.get('category') not in self.SURICATA_SNORT_CATEGORIES:
            return True
        return False

    def parse_data(self, data, **kwargs):
        result = {}
        result['id'] = data['id']
        result['sid'] = self._id_to_sid(data['id'])
        result['classtype'] = self._category_to_classtype(data['category'])
        result['category'] = data['category']
        result['name'] = data['name'] if data.get('name') is not None else ''
        result['qname'] = self._fqdn_to_qname(data.get('fqdn'))
        result['fqdn'] = data.get('fqdn')
        result['url'] = data.get('url')
        result['url_no_fqdn'] = self._url_to_url_no_fqdn(data.get('url'))
        result['dport_http'] = data['dport'] if data.get('dport') else '$HTTP_PORTS'
        result['dport_ip'] = data['dport'] if data.get('dport') else 'any'
        result['ip'] = self._address_to_ip(data.get('address'))
        result['ip_list'] = [a.get('ip').strip() for a in data.get('address') if a.get('ip') is not None]
        result['proto'] = self._proto_to_proto(data.get('proto'))
        result['reputation_category_id'] = self._category_to_reputation_category_id(data['category'])
        result['score'] = self._category_confidence_to_score(data['category'], data['confidence'])

        return result

    def _id_to_sid(self, n6id):
        return (int(n6id, 16) & self.SID_MASK) | self.SID_OFFSET

    def _fqdn_to_qname(self, fqdn):
        if not fqdn:
            return ''
        fqdn_parts = fqdn.split('.')
        qname_parts = []
        for part in fqdn_parts:
            qname_parts.append(str(len(part)).zfill(2))
            qname_parts.append(part)
        return "|%s|00|" % "|".join(qname_parts)

    def _category_to_classtype(self, category):
        return self.SURICATA_SNORT_CATEGORIES[category]['classtype']

    def _category_to_reputation_category_id(self, category):
        return self.SURICATA_SNORT_CATEGORIES[category]['rep_id']

    def _category_confidence_to_score(self, category, confidence):
        category_factor = self.SURICATA_SNORT_CATEGORIES[category]['score_factor']
        confidence_factor = self.CONFIDENCE_TO_INT[confidence]
        return category_factor * confidence_factor * 14

    def _url_to_url_no_fqdn(self, url):
        if not url:
            return ''
        parsed = urllib.parse.urlparse(url)
        output = [parsed.path]
        if parsed.query:
            output.extend(['?', parsed.query])
        if parsed.fragment:
            output.extend(['#', parsed.fragment])
        return ''.join(output)

    def _address_to_ip(self, address):
        ips = [a.get('ip').strip() for a in address if a.get('ip') is not None]
        if not ips:
            return ''
        if len(ips) == 1:
            return ips[0]
        else:
            return '[' + ','.join(ips) + ']'

    def _proto_to_proto(self, proto):
        if proto not in ('tcp', 'ip', 'udp'):
            return 'ip'
        return proto

    def render_content(self, data, **kwargs):
        if self.RULE_TEMPLATE is None:
            raise NotImplementedError
        if self.filter_renderer_specific(data) or self.filter_common(data):
            return b''
        parsed_content = self.parse_data(data, **kwargs)
        return as_bytes(self.RULE_TEMPLATE.format(**parsed_content))

    def after_content(self, **kwargs):
        return b"\n"


class _BaseDNSRuleRenderer(_BaseSnortSuricataRenderer):

    def filter_renderer_specific(self, data, **kwargs):
        if not data.get('fqdn'):
            return True
        return False


class _BaseHTTPRuleRenderer(_BaseSnortSuricataRenderer):

    def filter_renderer_specific(self, data, **kwargs):
        if not data.get('url'):
            return True
        return False


class _BaseIPRuleRenderer(_BaseSnortSuricataRenderer):

    def filter_renderer_specific(self, data, **kwargs):
        if data.get('address') is None:
            return True
        assert (data['address'] and all(a.get('ip') is not None
                                        for a in data['address'])), 'if not true we have a bug...'
        return False


class _BaseIPBlacklistRuleRenderer(_BaseSnortSuricataRenderer):

    def before_content(self, **kwargs):
        if 'category' in self.request.params:
            return b'# ' + as_bytes(str(self.request.params.get('category'))) + b'\n'
        else:
            return b''

    def filter_renderer_specific(self, data, **kwargs):
        if data.get('address') is None:
            return True
        assert (data['address'] and all(a.get('ip') is not None
                                        for a in data['address'])), 'if not true we have a bug...'
        return False


@register_stream_renderer('snort-dns')
class SnortDNSRenderer(_BaseDNSRuleRenderer):

    RULE_TEMPLATE = (
        'alert udp $HOME_NET any -> $DNS_SERVERS 53 '
        '(msg:"n6 {category} {name} {fqdn}"; content:"|01 00 00 01 00 00 00 00 00 00|"; '
        'offset:2; depth:10; content:"{qname}"; nocase; fast_pattern:only; '
        'classtype:{classtype}; sid:{sid}; gid:6000001; rev:1; metadata:n6id {id};)\n'
    )


@register_stream_renderer('suricata-dns')
class SuricataDNSRenderer(_BaseDNSRuleRenderer):

    RULE_TEMPLATE = (
        'alert dns $HOME_NET any -> $DNS_SERVERS 53 '
        '(msg:"n6 {category} {name} {fqdn}"; content:"{qname}"; '
        'nocase; fast_pattern:only; classtype:{classtype}; sid:{sid}; gid:6000001; '
        'rev:1; metadata:n6id {id};)\n'
    )



@register_stream_renderer('snort-http')
class SnortHTTPRenderer(_BaseHTTPRuleRenderer):

    RULE_TEMPLATE = (
        'alert tcp $HOME_NET any -> any {dport_http} '
        '(msg:"n6 {category} {name} {url}"; flow:to_server,established; '
        'content:"{url_no_fqdn}"; http_uri; nocase; content:"Host|3A| {fqdn}"; '
        'nocase; fast_pattern:only; http_header; classtype:{classtype}; '
        'sid:{sid}; gid:6000002; rev:1; metadata:n6id {id};)\n'
    )


@register_stream_renderer('suricata-http')
class SuricataHTTPRenderer(_BaseHTTPRuleRenderer):

    RULE_TEMPLATE = (
        'alert http $HOME_NET any -> any {dport_http} '
        '(msg:"n6 {category} {name} {url}"; flow:to_server,established; '
        'content:"{url_no_fqdn}"; http_uri; nocase; content:"Host|3A| {fqdn}"; '
        'nocase; fast_pattern:only; http_header; classtype:{classtype}; '
        'sid:{sid}; gid:6000002; rev:1; metadata:n6id {id};)\n'
    )


@register_stream_renderer('snort-ip')
class SnortIPRenderer(_BaseIPRuleRenderer):

    RULE_TEMPLATE = (
        'alert {proto} $HOME_NET any -> {ip} {dport_ip} '
        '(msg:"n6 {category} {name} {ip}"; classtype:{classtype}; '
        'sid:{sid}; gid:6000003; rev:1; metadata:n6id {id};)\n'
    )


@register_stream_renderer('suricata-ip')
class SuricataIPRenderer(_BaseIPRuleRenderer):

    RULE_TEMPLATE = (
        'alert ip $HOME_NET any -> {ip} {dport_ip} '
        '(msg:"n6 {category} {name} {ip}"; classtype:{classtype}; '
        'sid:{sid}; gid:6000003; rev:1; metadata:n6id {id};)\n'
    )


@register_stream_renderer('snort-ip-bl')
class SnortIPBlacklistRenderer(_BaseIPBlacklistRuleRenderer):

    RULE_TEMPLATE = _BlRuleTemplate('{ip}/32 #{id} {name}\n')


@register_stream_renderer('suricata-ip-bl')
class SuricatatIPBlacklistRenderer(_BaseIPBlacklistRuleRenderer):

    RULE_TEMPLATE = _BlRuleTemplate('{ip},{reputation_category_id},{score} #{id} {name}\n')


@register_stream_renderer('csv')
class StreamRenderer_csv(BaseStreamRenderer):

    content_type = "text/csv"

    EVENT_FIELDS = ["time", "id", "source",
                    "category", "name", "md5",
                    "ip", "url", "fqdn", "asn",
                    "cc", "details"]

    def before_content(self, **kwargs):
        output = StringIO(newline='')
        writer = csv.DictWriter(output, fieldnames=self.EVENT_FIELDS,
                                extrasaction='ignore', delimiter=',',
                                quotechar='"', quoting=csv.QUOTE_ALL)
        writer.writeheader()
        content = output.getvalue()
        output.close()
        return as_bytes(content)

    def after_content(self, **kwargs):
        return b'\n'

    def render_content(self, data, **kwargs):
        data = self._dict_to_csv_ready(data)
        # fields = sorted(data[0].keys())
        output = StringIO(newline='')
        writer = csv.DictWriter(output, fieldnames=self.EVENT_FIELDS,
                                extrasaction='ignore', delimiter=',',
                                quotechar='"', quoting=csv.QUOTE_ALL)
        writer.writerow(data)
        content = output.getvalue()
        output.close()
        return as_bytes(content)

    def _dict_to_csv_ready(self, value):
        serialized = {k: v for k, v in value.items()
                      if k not in ('ip', 'cc', 'asn', 'address', 'time')}
        serialized['time'] = value['time'].isoformat() + "Z"
        name = serialized.get('name')
        if name:
            serialized['name'] = name.replace('\n', '\\n').replace('\r', '\\r')
        address = value.get('address')
        if address is not None:
            serialized['ip'] = " ".join([a.get('ip') for a in address if a.get('ip') is not None]).strip()
            serialized['asn'] = " ".join(map(str, [a.get('asn') for a
                                    in address if a.get('asn') is not None])
                                ).strip()
            serialized['cc'] = " ".join([a.get('cc') for a in address if a.get('cc') is not None]).strip()
        else:
            serialized['ip'], serialized['asn'], serialized['cc'] = (
                value.get('ip'),
                str(value.get('asn')) if value.get('asn') is not None else '',
                value.get('cc')
            )

        details = []
        dest_ip = serialized.get('dip', serialized.get('adip'))
        if value.get('proto') is not None:
            details.append("{}".format(value.get('proto')))
        if value.get('sport') is not None:
            details.append("from port {}".format(value.get('sport')))
        if dest_ip is not None:
            if value.get('dport') is not None:
                details.append("to {}:{}".format(dest_ip, value.get('dport')))
            else:
                details.append("to {}".format(dest_ip))
        elif value.get('dport') is not None:
            details.append("to port {}".format(value.get('dport')))
        target = value.get('target')
        if target is not None:
            details.append("target {}".format(target))
        serialized["details"] = " ".join(details)
        return serialized
