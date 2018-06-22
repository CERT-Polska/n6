# -*- coding: utf-8 -*-

# Copyright (c) 2013-2018 NASK. All rights reserved.

import datetime
import cStringIO
import csv
import urlparse

from pyramid.httpexceptions import HTTPForbidden

from n6lib.common_helpers import SimpleNamespace
from n6lib.const import SURICATA_SNORT_CATEGORIES as _SURICATA_SNORT_CATEGORIES
from n6sdk.exceptions import TooMuchDataError
from n6sdk.pyramid_commons import register_stream_renderer
from n6sdk.pyramid_commons.renderers import BaseStreamRenderer
try:
    from n6lib.utils import iodeflib
except ImportError:
    iodeflib = None


class _BlRuleTemplate(object):

    def __init__(self, line_template):
        self.line_template = line_template  # line template must accept 'ip' keyword for str.format()

    def format(self, **data):
        result = []
        for ip in data['ip_list']:
            data['ip'] = ip
            result.append(self.line_template.format(**data))
        return "".join(result)


class _BaseSnortSuricataRenderer(BaseStreamRenderer):

    content_type = "text/plain"

    RULE_TEMPLATE = None

    # sid = (n6id & SID_MASK) | SID_OFFSET
    SID_MASK = 0x7FFFFFFF
    SID_OFFSET = 0x80000000

    CONFIDENCE_TO_INT = {'low': 1, 'medium': 2, 'high': 3}
    SURICATA_SNORT_CATEGORIES = {
        category: details
        for category, details in _SURICATA_SNORT_CATEGORIES.iteritems()
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
        result['name'] = data['name'] if data.get('name') is not None else ""
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
            return ""
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
            return ""
        parsed = urlparse.urlparse(url)
        output = [parsed.path]
        if parsed.query:
            output.extend(['?', parsed.query])
        if parsed.fragment:
            output.extend(['#', parsed.fragment])
        return "".join(output)

    def _address_to_ip(self, address):
        ips = [a.get('ip').strip() for a in address if a.get('ip') is not None]
        if not ips:
            return ""
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
            raise NotImplemented
        if self.filter_renderer_specific(data) or self.filter_common(data):
            return ""
        parsed_content = self.parse_data(data, **kwargs)
        return self.RULE_TEMPLATE.format(**parsed_content)

    def after_content(self, **kwargs):
        return "\n"


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
        ### XXX: the line below is strange; probably, it could be replated with:
        ###      `if not any(a.get('ip') is not None for a in data['address']):`
        ### and maybe even that check would be redundant -- because 'ip' is obligatory in 'address'
        if not [a.get('ip').strip() for a in data.get('address') if a.get('ip') is not None]:
            return True
        return False


class _BaseIPBlacklistRuleRenderer(_BaseSnortSuricataRenderer):

    def before_content(self, **kwargs):
        if 'category' in self.request.params:
            return '# ' + str(self.request.params.get('category')) + '\n'
        else:
            return ''

    def filter_renderer_specific(self, data, **kwargs):
        if data.get('address') is None:
            return True
        ### XXX: the line below is strange; probably, it could be replated with:
        ###      `if not any(a.get('ip') is not None for a in data['address']):`
        ### and maybe even that check would be redundant -- because 'ip' is obligatory in 'address'
        if not [a.get('ip').strip() for a in data.get('address') if a.get('ip') is not None]:
            return True
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
        output = cStringIO.StringIO()
        writer = csv.DictWriter(output, fieldnames=self.EVENT_FIELDS,
                                extrasaction='ignore', delimiter=',',
                                quotechar='"', quoting=csv.QUOTE_ALL)
        writer.writeheader()
        content = output.getvalue()
        output.close()
        return content

    def after_content(self, **kwargs):
        return "\n"

    def render_content(self, data, **kwargs):
        data = self._dict_to_csv_ready(data)
        # fields = sorted(data[0].keys())
        output = cStringIO.StringIO()
        writer = csv.DictWriter(output, fieldnames=self.EVENT_FIELDS,
                                extrasaction='ignore', delimiter=',',
                                quotechar='"', quoting=csv.QUOTE_ALL)
        writer.writerow(data)
        content = output.getvalue()
        output.close()
        return content

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
                str(value.get('asn')) if value.get('asn') is not None else "",
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
            if isinstance(target, unicode):
                target = target.encode('utf-8')
            details.append("target {}".format(target))
        serialized["details"] = " ".join(details)
        serialized = {
            k: (v.encode('utf-8') if isinstance(v, unicode)
                else v)
            for k, v in serialized.items()}
        return serialized


if iodeflib is None:
    StreamRenderer_iodef = None

else:

    @register_stream_renderer('iodef')
    class StreamRenderer_iodef(BaseStreamRenderer):

        content_type = "application/xml"

        conversion = {'high': 3, 'medium': 2, 'low': 1}
        iv_conversion = {v: k for k, v in conversion.items()}

        restriction = {'public': 3, 'need-to-know': 2, 'internal': 1, None: 0}
        iv_restriction = {3: 'public', 2: 'need-to-know', 1: 'private', 0: None}

        def iter_content(self, **kwargs):
            try:
                yield self.render_content(list(self.data_generator))
            except TooMuchDataError as exc:
                raise HTTPForbidden(exc.public_message)

        def _preprocess_query_string(self, request):
            if request.query_string:
                qs = request.query_string.split('&')
            else:
                qs = []
            qs = [q for q in qs if not (q.startswith('source=') or q.startswith('category='))]
            if qs:
                return "&".join(qs) + "&"
            else:
                return ""

        def _calculate_confidence(self, values, source, category):
            confidences = [self.conversion.get(c.confidence) for c in values
                           if c.source == source and c.category == category]
            if confidences:
                return self.iv_conversion.get(min(confidences))
            else:
                return None

        def _calculate_restriction(self, values, source, category):
            restrictions = [self.restriction.get(getattr(c, 'restriction', None)) for c in values
                            if c.source == source and c.category == category]
            if restrictions:
                return self.iv_restriction.get(min(restrictions))
            else:
                return None

        def dict_to_obj(self, value):
            obj = SimpleNamespace(**value)
            for k in ['source', 'confidence', 'category', 'time']:
                assert hasattr(obj, k)
            # NOTE: `restriction`, athough it is required to exist in the database, is being
            # discarded by N6DataSpec.clean_result_dict() for non-full-access clients
            for k in ['restriction',
                      'name', 'address', 'url', 'fqdn',
                      'proto', 'sport', 'dport', 'dip', 'adip']:
                if not hasattr(obj, k):
                    setattr(obj, k, None)
            return obj

        def render_content(self, data, **kwargs):
            # create a new IODEF document:
            iodef = iodeflib.IODEF_Document()

            incidents = {}
            # tz = str.format('{0:+06.2f}', float(time.timezone) / 3600)
            value = [self.dict_to_obj(d) for d in data]
            for event in value:
                incident_id = "{}source={}&category={}".format(
                                  self._preprocess_query_string(self.request),
                                  event.source, event.category
                               )
                if incident_id not in incidents:
                    restriction = self._calculate_restriction(value, event.source, event.category)
                    incident = iodeflib.Incident(
                                   id=incident_id,
                                   id_name='cert.pl',
                                   id_instance=event.source,
                                   # Changed call datetime.now () on DateTime.utcnow () task # 2683 in redmine
                                   report_time=datetime.datetime.utcnow().isoformat() + "Z",
                                   restriction=restriction,
                                   lang=None,
                                   purpose='reporting'
                                )
                    assessment = iodeflib.Assessment()
                    impact = iodeflib.Impact(type='ext-value', ext_type=event.category)
                    confidence = iodeflib.Confidence(
                                     rating=self._calculate_confidence(
                                         value,
                                         event.source,
                                         event.category
                                     )
                                  )
                    assessment.impacts.append(impact)
                    if confidence is not None:
                        assessment.confidence.append(confidence)
                    contact = iodeflib.Contact(
                                  contact_type='organization',
                                  role='irt',
                                  name="CERT Polska",
                                  descriptions=['generated by n6,'
                                                ' see http://n6.cert.pl/ for more information']
                              )
                    incident.assessments.append(assessment)
                    incident.contacts.append(contact)
                    incidents[incident_id] = incident
                incident = incidents[incident_id]

                event_data = iodeflib.EventData(
                                 descriptions=[event.name],
                                 detect_time=event.time.isoformat() + "Z"
                             )

                if event.address is not None:
                    ips = [i["ip"] for i in event.address]
                elif getattr(event, 'ip', None) is not None:
                    ## FIXME?: probably unnecessary, to be removed
                    ips = [event.ip]
                else:
                    ips = []
                flow = iodeflib.Flow()
                if not (ips or event.url is not None or event.fqdn is not None):
                    fqdn = 'unknown'
                else:
                    fqdn = event.fqdn
                if ips or event.url is not None or event.fqdn is not None:
                    system = iodeflib.System(category="source")
                    if event.url is not None:
                        address = iodeflib.Address(
                                      address=event.url,
                                      category='ext-value',
                                      ext_category='url'
                                  )
                        system.node_addresses.append(address)
                    if fqdn is not None:
                        system.node_names.append(event.fqdn)
                    for ip in ips:
                        address = iodeflib.Address(address=ip, category='ipv4-addr')
                        system.node_addresses.append(address)
                    if event.proto is not None and event.sport is not None:
                        service = iodeflib.Service(ip_protocol=event.proto, port=str(event.sport))
                        system.services.append(service)
                    flow.systems.append(system)
                if event.adip is not None or event.dport is not None or event.dip is not None:
                    system = iodeflib.System(category="target")
                    if event.adip is not None:
                        address = iodeflib.Address(
                                      address=event.adip,
                                      category='ext-value',
                                      ext_category='ipv4-addr-anonimized'
                                      ## FIXME???: s/anonimized/anonymized/ ???
                                      # (note: integration tests will need to be adjusted appropriately
                                      #        when it is fixed)
                                  )
                        system.node_addresses.append(address)
                    if event.dip is not None:
                        address = iodeflib.Address(address=event.dip, category='ipv4-addr')
                        system.node_addresses.append(address)
                    if event.proto is not None and event.dport is not None:
                        service = iodeflib.Service(ip_protocol=event.proto, port=str(event.dport))
                        system.services.append(service)
                    flow.systems.append(system)

                event_data.flows.append(flow)
                incident.event_data.append(event_data)

            for incident in incidents.values():
                iodef.incidents.append(incident)

            return str(iodef)
