# -*- coding: utf-8 -*-

# Copyright (c) 2013-2019 NASK. All rights reserved.

import copy
import datetime
import json
import unittest
from urlparse import urlsplit

from mock import (
    MagicMock,
    Mock,
    patch,
    sentinel,
)
from unittest_expander import (
    expand,
    foreach,
    param,
    paramseq,
)

from n6.collectors.misp import MispCollector


raw_misp_events = (
    '{"response": [{"Event": {"orgc_id": "1", "ShadowAttribute": [], "id": '
    '"560", "threat_level_id": "1", "uuid": "5895ceec-1a20-4188-a1f3-1b40c0'
    'a83832", "Orgc": {"uuid": "56ef3277-1ad4-42f6-b90b-04e5c0a83832", "id"'
    ': "1", "name": "MISP"}, "Org": {"uuid": "56ef3277-1ad4-42f6-b90b-04e5c'
    '0a83832", "id": "1", "name": "MISP"}, "RelatedEvent": [], "sharing_gro'
    'up_id": "0", "timestamp": "1486219333", "date": "2017-02-10", "disable'
    '_correlation": false, "info": "Event drugi", "locked": false, "publish'
    '_timestamp": "1486219345", "Attribute": [{"category": "Artifacts dropp'
    'ed", "comment": "", "uuid": "5895ceff-db34-4efb-9435-1b3fc0a83832", "e'
    'vent_id": "560", "timestamp": "1486212863", "to_ids": true, "deleted":'
    ' false, "value": "syslog.png|14ed4644f44ac852ba5d4b3b3ac6126e317e9acc"'
    ', "sharing_group_id": "0", "ShadowAttribute": [], "disable_correlation'
    '": false, "SharingGroup": [], "distribution": "5", "type": "filename|s'
    'ha1", "id": "144657"}, {"category": "Artifacts dropped", "comment": ""'
    ', "uuid": "5895cf0f-cfec-4487-b2a9-4836c0a83832", "event_id": "560", "'
    'timestamp": "1486212879", "to_ids": true, "deleted": false, "value": "'
    'sample_n6_properties|9dbc8de342551aa62eac4c5b0ac42d0d39148939", "shari'
    'ng_group_id": "0", "ShadowAttribute": [], "disable_correlation": false'
    ', "SharingGroup": [], "distribution": "5", "type": "filename|sha1", "i'
    'd": "144660"}, {"category": "Artifacts dropped", "comment": "", "uuid"'
    ': "5895cf24-e7ac-4427-8602-2f89c0a83832", "event_id": "560", "timestam'
    'p": "1486212900", "to_ids": true, "deleted": false, "value": "kolska.o'
    'dt|2d50d4688e9d5e78bb8aecf448226ca1a525b96d", "sharing_group_id": "0",'
    ' "ShadowAttribute": [], "disable_correlation": false, "SharingGroup": '
    '[], "distribution": "5", "type": "filename|sha1", "id": "144663"}, {"c'
    'ategory": "Artifacts dropped", "comment": "", "uuid": "5895cf32-abb0-4'
    'e0d-aede-490fc0a83832", "event_id": "560", "timestamp": "1486212914", '
    '"to_ids": true, "deleted": false, "value": "misp_sample|fb145a0fef0ca3'
    '788349a4ba1f26db1c0b88cc31", "sharing_group_id": "0", "ShadowAttribute'
    '": [], "disable_correlation": false, "SharingGroup": [], "distribution'
    '": "5", "type": "filename|sha1", "id": "144666"}, {"category": "Artifa'
    'cts dropped", "comment": "", "uuid": "5895ceff-357c-4952-a6ba-1b3fc0a8'
    '3832", "event_id": "560", "timestamp": "1486212863", "to_ids": true, "'
    'deleted": false, "value": "syslog.png|b22bfabfc6896f526a19dcfadbae9d3a'
    '5636972bab7bbeeb7489182d957a3063", "sharing_group_id": "0", "ShadowAtt'
    'ribute": [], "disable_correlation": false, "SharingGroup": [], "distri'
    'bution": "5", "type": "filename|sha256", "id": "144658"}, {"category":'
    ' "Artifacts dropped", "comment": "", "uuid": "5895cf0f-a158-40c1-b9de-'
    '4836c0a83832", "event_id": "560", "timestamp": "1486212879", "to_ids":'
    ' true, "deleted": false, "value": "sample_n6_properties|5878690a8f63b5'
    '6d0e444b94a5f8dec5d321f7ba25afc57951abc42560888ed9", "sharing_group_id'
    '": "0", "ShadowAttribute": [], "disable_correlation": false, "SharingG'
    'roup": [], "distribution": "5", "type": "filename|sha256", "id": "1446'
    '61"}, {"category": "Artifacts dropped", "comment": "", "uuid": "5895cf'
    '24-091c-4244-babe-2f89c0a83832", "event_id": "560", "timestamp": "1486'
    '212900", "to_ids": true, "deleted": false, "value": "kolska.odt|298eac'
    'b2c9684d012267b6055e861e316134d920ea8d49a3ade5697c93335b27", "sharing_'
    'group_id": "0", "ShadowAttribute": [], "disable_correlation": false, "'
    'SharingGroup": [], "distribution": "5", "type": "filename|sha256", "id'
    '": "144664"}, {"category": "Artifacts dropped", "comment": "", "uuid":'
    ' "5895cf32-7290-494e-826d-490fc0a83832", "event_id": "560", "timestamp'
    '": "1486212914", "to_ids": true, "deleted": false, "value": "misp_samp'
    'le|512d47b0ee0cb463598eb8376840216ed2866848300d5952b2e5efee311ee6bc", '
    '"sharing_group_id": "0", "ShadowAttribute": [], "disable_correlation":'
    ' false, "SharingGroup": [], "distribution": "5", "type": "filename|sha'
    '256", "id": "144667"}, {"category": "Artifacts dropped", "comment": ""'
    ', "uuid": "5895ceff-32f0-4c03-946b-1b3fc0a83832", "event_id": "560", "'
    'timestamp": "1486212863", "to_ids": true, "deleted": false, "value": "'
    'syslog.png|e2f88b5d31b03b319c36cfb4979e7f8e", "sharing_group_id": "0",'
    ' "ShadowAttribute": [], "disable_correlation": false, "SharingGroup": '
    '[], "distribution": "5", "type": "malware-sample", "id": "144656"}, {"'
    'category": "Artifacts dropped", "comment": "", "uuid": "5895cf0f-ebf4-'
    '4662-b9c8-4836c0a83832", "event_id": "560", "timestamp": "1486212879",'
    ' "to_ids": true, "deleted": false, "value": "sample_n6_properties|8644'
    '071ccfff945ecd6127300a932fbd", "sharing_group_id": "0", "ShadowAttribu'
    'te": [], "disable_correlation": false, "SharingGroup": [], "distributi'
    'on": "5", "type": "malware-sample", "id": "144659"}, {"category": "Art'
    'ifacts dropped", "comment": "", "uuid": "5895cf24-51e4-4868-9412-2f89c'
    '0a83832", "event_id": "560", "timestamp": "1486212900", "to_ids": true'
    ', "deleted": false, "value": "kolska.odt|6e98c9e4b0b2232d331fb80ea5f19'
    '7bc", "sharing_group_id": "0", "ShadowAttribute": [], "disable_correla'
    'tion": false, "SharingGroup": [], "distribution": "5", "type": "malwar'
    'e-sample", "id": "144662"}, {"category": "Artifacts dropped", "comment'
    '": "", "uuid": "5895cf32-b3e8-4a7d-865c-490fc0a83832", "event_id": "56'
    '0", "timestamp": "1486212914", "to_ids": true, "deleted": false, "valu'
    'e": "misp_sample|d6d88f2e50080b9602da53dac1102762", "sharing_group_id"'
    ': "0", "ShadowAttribute": [], "disable_correlation": false, "SharingGr'
    'oup": [], "distribution": "5", "type": "malware-sample", "id": "144665'
    '"}], "attribute_count": "12", "org_id": "1", "analysis": "0", "publish'
    'ed": true, "distribution": "3", "proposal_email_lock": false, "Galaxy"'
    ': []}}, {"Event": {"orgc_id": "1", "ShadowAttribute": [], "id": "559",'
    ' "threat_level_id": "1", "uuid": "5895b819-37a0-4f2d-99fa-1abcc0a83832'
    '", "Orgc": {"uuid": "56ef3277-1ad4-42f6-b90b-04e5c0a83832", "id": "1",'
    ' "name": "MISP"}, "Org": {"uuid": "56ef3277-1ad4-42f6-b90b-04e5c0a8383'
    '2", "id": "1", "name": "MISP"}, "RelatedEvent": [], "sharing_group_id"'
    ': "0", "timestamp": "1486219299", "date": "2017-02-14", "disable_corre'
    'lation": false, "info": "Event numer jeden", "locked": false, "publish'
    '_timestamp": "1486219315", "Attribute": [{"category": "Artifacts dropp'
    'ed", "comment": "", "uuid": "5895b83d-29a4-4a3b-bc01-1b40c0a83832", "e'
    'vent_id": "559", "timestamp": "1486207037", "to_ids": true, "deleted":'
    ' false, "value": "wniosek.pdf|3d95be6f118dfabe73f4a1c7c77a7d0d2f9ef6a8'
    '59c61845d5e667bc10f1017f", "sharing_group_id": "0", "ShadowAttribute":'
    ' [], "disable_correlation": false, "SharingGroup": [], "distribution":'
    ' "5", "type": "filename|sha256", "id": "144648"}, {"category": "Artifa'
    'cts dropped", "comment": "", "uuid": "5895b855-a930-4b6c-b399-2f88c0a8'
    '3832", "event_id": "559", "timestamp": "1486207061", "to_ids": true, "'
    'deleted": false, "value": "zone_h_par.py|9ea826ef6f2761e11069ffa045c81'
    'a7235ebea9f59c27228594837fcc6ebdeb4", "sharing_group_id": "0", "Shadow'
    'Attribute": [], "disable_correlation": false, "SharingGroup": [], "dis'
    'tribution": "5", "type": "filename|sha256", "id": "144651"}, {"categor'
    'y": "Artifacts dropped", "comment": "", "uuid": "5895b87e-5ca0-4510-96'
    '1f-2f88c0a83832", "event_id": "559", "timestamp": "1486207102", "to_id'
    's": true, "deleted": false, "value": "wsdl|c61abf92233ee033474e8d91454'
    'fe10a3cce1325af42266a68df124d41dd44d0", "sharing_group_id": "0", "Shad'
    'owAttribute": [], "disable_correlation": false, "SharingGroup": [], "d'
    'istribution": "5", "type": "filename|sha256", "id": "144655"}, {"categ'
    'ory": "Artifacts dropped", "comment": "", "uuid": "5895b83d-cf34-4c9f-'
    'a921-1b40c0a83832", "event_id": "559", "timestamp": "1486207037", "to_'
    'ids": true, "deleted": false, "value": "wniosek.pdf|f0dc87b83bc6953c88'
    '44eafa55a256bf", "sharing_group_id": "0", "ShadowAttribute": [], "disa'
    'ble_correlation": false, "SharingGroup": [], "distribution": "5", "typ'
    'e": "malware-sample", "id": "144646"}, {"category": "Artifacts dropped'
    '", "comment": "", "uuid": "5895b855-eed0-4f1a-8184-2f88c0a83832", "eve'
    'nt_id": "559", "timestamp": "1486207061", "to_ids": true, "deleted": f'
    'alse, "value": "zone_h_par.py|cc5fc5eff65fb15f66d43f7d0dc90328", "shar'
    'ing_group_id": "0", "ShadowAttribute": [], "disable_correlation": fals'
    'e, "SharingGroup": [], "distribution": "5", "type": "malware-sample", '
    '"id": "144649"}, {"category": "Artifacts dropped", "comment": "", "uui'
    'd": "5895b87e-8f18-4d8c-956f-2f88c0a83832", "event_id": "559", "timest'
    'amp": "1486207102", "to_ids": true, "deleted": false, "value": "wsdl|7'
    '2fdafceec16ce8e75d3fb1b0174ba06", "sharing_group_id": "0", "ShadowAttr'
    'ibute": [], "disable_correlation": false, "SharingGroup": [], "distrib'
    'ution": "5", "type": "malware-sample", "id": "144653"}], "attribute_co'
    'unt": "6", "org_id": "1", "analysis": "0", "published": true, "distrib'
    'ution": "3", "proposal_email_lock": false, "Galaxy": []}}]}')

event_10_02 = (
    '{"Event": {"orgc_id": "1", "ShadowAttribute": [], "id": "560", "threat'
    '_level_id": "1", "uuid": "5895ceec-1a20-4188-a1f3-1b40c0a83832", "time'
    'stamp": "1486219333", "Org": {"uuid": "56ef3277-1ad4-42f6-b90b-04e5c0a'
    '83832", "name": "MISP", "id": "1"}, "RelatedEvent": [], "sharing_group'
    '_id": "0", "Orgc": {"uuid": "56ef3277-1ad4-42f6-b90b-04e5c0a83832", "n'
    'ame": "MISP", "id": "1"}, "date": "2017-02-10", "disable_correlation":'
    ' false, "info": "Event drugi", "locked": false, "publish_timestamp": "'
    '1486219345", "Attribute": [{"category": "Artifacts dropped", "comment"'
    ': "", "uuid": "5895ceff-db34-4efb-9435-1b3fc0a83832", "event_id": "560'
    '", "timestamp": "1486212863", "to_ids": true, "value": "syslog.png|14e'
    'd4644f44ac852ba5d4b3b3ac6126e317e9acc", "id": "144657", "deleted": fal'
    'se, "ShadowAttribute": [], "sharing_group_id": "0", "SharingGroup": []'
    ', "disable_correlation": false, "type": "filename|sha1", "distribution'
    '": "5"}, {"category": "Artifacts dropped", "comment": "", "uuid": "589'
    '5cf0f-cfec-4487-b2a9-4836c0a83832", "event_id": "560", "timestamp": "1'
    '486212879", "to_ids": true, "value": "sample_n6_properties|9dbc8de3425'
    '51aa62eac4c5b0ac42d0d39148939", "id": "144660", "deleted": false, "Sha'
    'dowAttribute": [], "sharing_group_id": "0", "SharingGroup": [], "disab'
    'le_correlation": false, "type": "filename|sha1", "distribution": "5"},'
    ' {"category": "Artifacts dropped", "comment": "", "uuid": "5895cf24-e7'
    'ac-4427-8602-2f89c0a83832", "event_id": "560", "timestamp": "148621290'
    '0", "to_ids": true, "value": "kolska.odt|2d50d4688e9d5e78bb8aecf448226'
    'ca1a525b96d", "id": "144663", "deleted": false, "ShadowAttribute": [],'
    ' "sharing_group_id": "0", "SharingGroup": [], "disable_correlation": f'
    'alse, "type": "filename|sha1", "distribution": "5"}, {"category": "Art'
    'ifacts dropped", "comment": "", "uuid": "5895cf32-abb0-4e0d-aede-490fc'
    '0a83832", "event_id": "560", "timestamp": "1486212914", "to_ids": true'
    ', "value": "misp_sample|fb145a0fef0ca3788349a4ba1f26db1c0b88cc31", "id'
    '": "144666", "deleted": false, "ShadowAttribute": [], "sharing_group_i'
    'd": "0", "SharingGroup": [], "disable_correlation": false, "type": "fi'
    'lename|sha1", "distribution": "5"}, {"category": "Artifacts dropped", '
    '"comment": "", "uuid": "5895ceff-357c-4952-a6ba-1b3fc0a83832", "event_'
    'id": "560", "timestamp": "1486212863", "to_ids": true, "value": "syslo'
    'g.png|b22bfabfc6896f526a19dcfadbae9d3a5636972bab7bbeeb7489182d957a3063'
    '", "id": "144658", "deleted": false, "ShadowAttribute": [], "sharing_g'
    'roup_id": "0", "SharingGroup": [], "disable_correlation": false, "type'
    '": "filename|sha256", "distribution": "5"}, {"category": "Artifacts dr'
    'opped", "comment": "", "uuid": "5895cf0f-a158-40c1-b9de-4836c0a83832",'
    ' "event_id": "560", "timestamp": "1486212879", "to_ids": true, "value"'
    ': "sample_n6_properties|5878690a8f63b56d0e444b94a5f8dec5d321f7ba25afc5'
    '7951abc42560888ed9", "id": "144661", "deleted": false, "ShadowAttribut'
    'e": [], "sharing_group_id": "0", "SharingGroup": [], "disable_correlat'
    'ion": false, "type": "filename|sha256", "distribution": "5"}, {"catego'
    'ry": "Artifacts dropped", "comment": "", "uuid": "5895cf24-091c-4244-b'
    'abe-2f89c0a83832", "event_id": "560", "timestamp": "1486212900", "to_i'
    'ds": true, "value": "kolska.odt|298eacb2c9684d012267b6055e861e316134d9'
    '20ea8d49a3ade5697c93335b27", "id": "144664", "deleted": false, "Shadow'
    'Attribute": [], "sharing_group_id": "0", "SharingGroup": [], "disable_'
    'correlation": false, "type": "filename|sha256", "distribution": "5"}, '
    '{"category": "Artifacts dropped", "comment": "", "uuid": "5895cf32-729'
    '0-494e-826d-490fc0a83832", "event_id": "560", "timestamp": "1486212914'
    '", "to_ids": true, "value": "misp_sample|512d47b0ee0cb463598eb83768402'
    '16ed2866848300d5952b2e5efee311ee6bc", "id": "144667", "deleted": false'
    ', "ShadowAttribute": [], "sharing_group_id": "0", "SharingGroup": [], '
    '"disable_correlation": false, "type": "filename|sha256", "distribution'
    '": "5"}, {"category": "Artifacts dropped", "comment": "", "uuid": "589'
    '5ceff-32f0-4c03-946b-1b3fc0a83832", "event_id": "560", "timestamp": "1'
    '486212863", "to_ids": true, "value": "syslog.png|e2f88b5d31b03b319c36c'
    'fb4979e7f8e", "id": "144656", "deleted": false, "ShadowAttribute": [],'
    ' "sharing_group_id": "0", "SharingGroup": [], "disable_correlation": f'
    'alse, "type": "malware-sample", "distribution": "5"}, {"category": "Ar'
    'tifacts dropped", "comment": "", "uuid": "5895cf0f-ebf4-4662-b9c8-4836'
    'c0a83832", "event_id": "560", "timestamp": "1486212879", "to_ids": tru'
    'e, "value": "sample_n6_properties|8644071ccfff945ecd6127300a932fbd", "'
    'id": "144659", "deleted": false, "ShadowAttribute": [], "sharing_group'
    '_id": "0", "SharingGroup": [], "disable_correlation": false, "type": "'
    'malware-sample", "distribution": "5"}, {"category": "Artifacts dropped'
    '", "comment": "", "uuid": "5895cf24-51e4-4868-9412-2f89c0a83832", "eve'
    'nt_id": "560", "timestamp": "1486212900", "to_ids": true, "value": "ko'
    'lska.odt|6e98c9e4b0b2232d331fb80ea5f197bc", "id": "144662", "deleted":'
    ' false, "ShadowAttribute": [], "sharing_group_id": "0", "SharingGroup"'
    ': [], "disable_correlation": false, "type": "malware-sample", "distrib'
    'ution": "5"}, {"category": "Artifacts dropped", "comment": "", "uuid":'
    ' "5895cf32-b3e8-4a7d-865c-490fc0a83832", "event_id": "560", "timestamp'
    '": "1486212914", "to_ids": true, "value": "misp_sample|d6d88f2e50080b9'
    '602da53dac1102762", "id": "144665", "deleted": false, "ShadowAttribute'
    '": [], "sharing_group_id": "0", "SharingGroup": [], "disable_correlati'
    'on": false, "type": "malware-sample", "distribution": "5"}], "attribut'
    'e_count": "12", "org_id": "1", "analysis": "0", "published": true, "di'
    'stribution": "3", "proposal_email_lock": false, "Galaxy": []}}'
)

event_14_02 = (
    '{"Event": {"orgc_id": "1", "ShadowAttribute": [], "id": "559", "threat'
    '_level_id": "1", "uuid": "5895b819-37a0-4f2d-99fa-1abcc0a83832", "time'
    'stamp": "1486219299", "Org": {"uuid": "56ef3277-1ad4-42f6-b90b-04e5c0a'
    '83832", "name": "MISP", "id": "1"}, "RelatedEvent": [], "sharing_group'
    '_id": "0", "Orgc": {"uuid": "56ef3277-1ad4-42f6-b90b-04e5c0a83832", "n'
    'ame": "MISP", "id": "1"}, "date": "2017-02-14", "disable_correlation":'
    ' false, "info": "Event numer jeden", "locked": false, "publish_timesta'
    'mp": "1486219315", "Attribute": [{"category": "Artifacts dropped", "co'
    'mment": "", "uuid": "5895b83d-29a4-4a3b-bc01-1b40c0a83832", "event_id"'
    ': "559", "timestamp": "1486207037", "to_ids": true, "value": "wniosek.'
    'pdf|3d95be6f118dfabe73f4a1c7c77a7d0d2f9ef6a859c61845d5e667bc10f1017f",'
    ' "id": "144648", "deleted": false, "ShadowAttribute": [], "sharing_gro'
    'up_id": "0", "SharingGroup": [], "disable_correlation": false, "type":'
    ' "filename|sha256", "distribution": "5"}, {"category": "Artifacts drop'
    'ped", "comment": "", "uuid": "5895b855-a930-4b6c-b399-2f88c0a83832", "'
    'event_id": "559", "timestamp": "1486207061", "to_ids": true, "value": '
    '"zone_h_par.py|9ea826ef6f2761e11069ffa045c81a7235ebea9f59c27228594837f'
    'cc6ebdeb4", "id": "144651", "deleted": false, "ShadowAttribute": [], "'
    'sharing_group_id": "0", "SharingGroup": [], "disable_correlation": fal'
    'se, "type": "filename|sha256", "distribution": "5"}, {"category": "Art'
    'ifacts dropped", "comment": "", "uuid": "5895b87e-5ca0-4510-961f-2f88c'
    '0a83832", "event_id": "559", "timestamp": "1486207102", "to_ids": true'
    ', "value": "wsdl|c61abf92233ee033474e8d91454fe10a3cce1325af42266a68df1'
    '24d41dd44d0", "id": "144655", "deleted": false, "ShadowAttribute": [],'
    ' "sharing_group_id": "0", "SharingGroup": [], "disable_correlation": f'
    'alse, "type": "filename|sha256", "distribution": "5"}, {"category": "A'
    'rtifacts dropped", "comment": "", "uuid": "5895b83d-cf34-4c9f-a921-1b4'
    '0c0a83832", "event_id": "559", "timestamp": "1486207037", "to_ids": tr'
    'ue, "value": "wniosek.pdf|f0dc87b83bc6953c8844eafa55a256bf", "id": "14'
    '4646", "deleted": false, "ShadowAttribute": [], "sharing_group_id": "0'
    '", "SharingGroup": [], "disable_correlation": false, "type": "malware-'
    'sample", "distribution": "5"}, {"category": "Artifacts dropped", "comm'
    'ent": "", "uuid": "5895b855-eed0-4f1a-8184-2f88c0a83832", "event_id": '
    '"559", "timestamp": "1486207061", "to_ids": true, "value": "zone_h_par'
    '.py|cc5fc5eff65fb15f66d43f7d0dc90328", "id": "144649", "deleted": fals'
    'e, "ShadowAttribute": [], "sharing_group_id": "0", "SharingGroup": [],'
    ' "disable_correlation": false, "type": "malware-sample", "distribution'
    '": "5"}, {"category": "Artifacts dropped", "comment": "", "uuid": "589'
    '5b87e-8f18-4d8c-956f-2f88c0a83832", "event_id": "559", "timestamp": "1'
    '486207102", "to_ids": true, "value": "wsdl|72fdafceec16ce8e75d3fb1b017'
    '4ba06", "id": "144653", "deleted": false, "ShadowAttribute": [], "shar'
    'ing_group_id": "0", "SharingGroup": [], "disable_correlation": false, '
    '"type": "malware-sample", "distribution": "5"}], "attribute_count": "6'
    '", "org_id": "1", "analysis": "0", "published": true, "distribution": '
    '"3", "proposal_email_lock": false, "Galaxy": []}}'
)

samples_10_02 = {
    144656: b'Event nr 144656 binary data.',
    144659: b'Event nr 144659 binay data.',
    144662: b'Event nr 144662 binary data.',
    144665: b'Event nr 144665 binary data.',
}

samples_14_02 = {
    144646: b'Event nr 144646 binary data.',
    144649: b'Event nr 144649 binary data.',
    144653: b'Event nr 144653 binary data.',
}

all_samples = copy.deepcopy(samples_10_02)
all_samples.update(samples_14_02)

all_samples_ids = set(all_samples.keys())
samples_14_02_ids = set(samples_14_02.keys())


def _str_to_datetime(datetime_str):
    datetime_format = '%Y-%m-%d %H:%M:%S'
    return datetime.datetime.strptime(datetime_str, datetime_format)


@paramseq
def _publishing_test_cases():
    newer_event = [json.loads(event_14_02)]
    all_events = [json.loads(event_10_02), json.loads(event_14_02)]
    yield param(state=None,
                expected_events=all_events,
                expected_samples=all_samples).label('All events and samples, no previous state.')
    yield param(state={'events_publishing_datetime': _str_to_datetime('2017-02-09 12:00:00'),
                       'samples_publishing_datetime': _str_to_datetime('2017-02-09 12:00:00'),
                       'last_published_samples': []},
                expected_events=all_events,
                expected_samples=all_samples).label('All events and samples with a state.')
    yield param(state={'events_publishing_datetime': _str_to_datetime('2017-02-12 12:00:00'),
                       'samples_publishing_datetime': _str_to_datetime('2017-02-09 12:00:00'),
                       'last_published_samples': []},
                expected_events=newer_event,
                expected_samples=all_samples).label('Events after 2017-02-12 and overdue samples.')
    yield param(state={'events_publishing_datetime': _str_to_datetime('2017-02-15 12:00:00'),
                       'samples_publishing_datetime': _str_to_datetime('2017-02-09 12:00:00'),
                       'last_published_samples': []},
                expected_events=None,
                expected_samples=all_samples).label('No new events, overdue samples after '
                                                    '2017-02-09.')
    yield param(state={'events_publishing_datetime': _str_to_datetime('2017-02-15 12:00:00'),
                       'samples_publishing_datetime': _str_to_datetime('2017-02-12 12:00:00'),
                       'last_published_samples': []},
                expected_events=None,
                expected_samples=samples_14_02).label('No new events, overdue samples after '
                                                      '2017-02-12.')
    yield param(state={'events_publishing_datetime': _str_to_datetime('2017-02-15 12:00:00'),
                       'samples_publishing_datetime': _str_to_datetime('2017-02-11 12:00:00'),
                       'last_published_samples': [144646, 144653]},
                expected_events=None,
                expected_samples={x: samples_14_02[x] for
                                  x in samples_14_02_ids - {144646, 144653}}).label(
        'No new events, overdue samples after 2017-02-11, partially downloaded.')
    yield param(state={'events_publishing_datetime': _str_to_datetime('2017-02-11 12:00:00'),
                       'samples_publishing_datetime': _str_to_datetime('2017-02-09 12:00:00'),
                       'last_published_samples': [144656, 144659]},
                expected_events=newer_event,
                expected_samples={x: all_samples[x] for
                                  x in all_samples_ids - {144656, 144659}}).label(
        'Events after 2017-02-11, overdue samples after 2017-02-09, partially downloaded.')


@expand
class TestMispCollector(unittest.TestCase):

    mocked_now_time = datetime.datetime(year=2017, month=2, day=20, hour=12)
    declared_exchanges = {'raw', 'sample'}
    mocked_config = {'misp_url': 'http://example.com',
                     'sample_path': '/',
                     'misp_key': sentinel,
                     'source': 'test',
                     'days_for_first_run': 20}
    state_with_invalid_datetimes = {
        'events_publishing_datetime': _str_to_datetime('2017-02-09 11:00:00'),
        'samples_publishing_datetime': _str_to_datetime('2017-02-12 11:00:00'),
        'last_published_samples': [],
    }
    mocked_output_components = ['test_rk', 'test_body', 'test_props']
    single_sample_test_url = 'http://example.com/download/123'

    def _add_timeout_mock(self, timeout, meth):
        meth()

    def _download_last_mock(self, initial_minutes):
        initial_delta = datetime.timedelta(minutes=int(initial_minutes.replace('m', '')))
        initial_datetime = self.mocked_now_time - initial_delta
        datetime_format = '%Y-%m-%d'
        raw_events = json.loads(raw_misp_events).get('response')
        events = [x['Event'] for x in raw_events
                  if (datetime.datetime.strptime(x['Event']['date'], datetime_format) >
                      initial_datetime)]
        result = {'response': [{'Event': x} for x in events]}
        return result

    def _publish_output_mock(self, rk, body, props, **kwargs):
        if kwargs.get('exchange') == 'sample':
            sample_id = int(props['headers']['meta']['misp']['id'])
            self._published_samples[sample_id] = body
        elif body:
            self._published_events = json.loads(body)

    def _download_sample_mock(self, url):
        split_url = urlsplit(url)
        sample_id = int(split_url.path.lstrip('/'))
        return all_samples[sample_id]

    def _save_state_mock(self, state):
        self._collector_state = state

    def __init__(self, *args, **kwargs):
        super(TestMispCollector, self).__init__(*args, **kwargs)
        self._published_events = None
        self._published_samples = {}
        self._collector_state = None

    @classmethod
    @patch('n6.base.queue.QueuedBase.preinit_hook')
    @patch('n6.base.queue.QueuedBase.parse_cmdline_args')
    def setUp(self, cmdargs_mock, preinit_mock):
        self._instance = MispCollector.__new__(MispCollector)
        self._instance.config = self.mocked_config

    def _init_class(self, mocked_state):
        with patch('n6.collectors.misp.datetime') as mocked_datetime_module, \
                patch('n6.collectors.generic.BaseCollector.__init__',
                      return_value=None, create=True), \
                patch('n6.collectors.generic.CollectorWithStateMixin.__init__',
                      return_value=None, create=True), \
                patch('n6.collectors.misp.PyMISP.__init__', return_value=None, create=True):
            # a partial mock of the `datetime` module; the value of
            # the `datetime.datetime.now` is mocked, but it is still
            # able to return a `datetime.datetime` instance
            mocked_datetime_module.now.return_value = self.mocked_now_time
            mocked_datetime_module.side_effect = lambda *args, **kw: datetime.datetime(*args, **kw)
            self._instance.load_state = Mock(return_value=mocked_state)
            self._instance._connection = Mock(create=True)
            self._instance.__init__()
        self._instance._connection.add_timeout.side_effect = self._add_timeout_mock
        self._instance._declared_output_exchanges = self.declared_exchanges
        self._instance._download_sample = Mock(side_effect=self._download_sample_mock)
        self._instance._closing = False
        self._instance.save_state = Mock(side_effect=self._save_state_mock)
        self._instance._now = self.mocked_now_time

    def _mocked_run(self):
        with patch('n6.base.queue.QueuedBase.run', side_effect=self._instance.start_publishing),\
                patch('n6.collectors.misp.PyMISP.download_last',
                      side_effect=self._download_last_mock),\
                patch('n6.base.queue.QueuedBase.publish_output',
                      side_effect=self._publish_output_mock),\
                patch('n6.base.queue.QueuedBase.inner_stop'):
            self._instance.run()

    @foreach(_publishing_test_cases)
    def test_publishing(self, state, expected_events, expected_samples):
        self._init_class(state)
        self._mocked_run()
        self.assertEqual(expected_events, self._published_events)
        self.assertEqual(expected_samples, self._published_samples)
        # check, whether all events and samples were published and if
        # the collector's state is saved with a new datetime
        # and an empty list of published samples
        self.assertEqual(self._collector_state['events_publishing_datetime'],
                         self.mocked_now_time)
        self.assertEqual(self._collector_state['samples_publishing_datetime'],
                         self.mocked_now_time)
        self.assertEqual(self._collector_state['last_published_samples'], [])
        # a teardown for the test
        self._published_events = None
        self._published_samples = {}
        self._collector_state = None

    def test_invalid_state_datetimes(self):
        with self.assertRaises(AssertionError):
            self._init_class(self.state_with_invalid_datetimes)

    def test_raw_publishing(self):
        self._init_class(None)
        self._instance._misp_events = self.mocked_output_components
        self._instance.publish_output = Mock()
        self._instance._output_components = Mock()
        self._instance._state = MagicMock()
        self._instance.save_state = Mock()
        self._instance._schedule = Mock()
        self._instance._do_publish_events()
        self._instance.publish_output.assert_called_with(*self.mocked_output_components)

    def test_sample_publishing(self):
        self._init_class(None)
        self._instance.publish_output = Mock()
        self._instance._output_components = self.mocked_output_components
        self._instance._current_sample = MagicMock()
        self._instance._state = MagicMock()
        self._instance.save_state = Mock()
        self._instance._schedule = Mock()
        self._instance._do_publish()
        self._instance.publish_output.assert_called_with(*self.mocked_output_components,
                                                         exchange='sample')

    @patch('n6.collectors.misp.urljoin', return_value=single_sample_test_url)
    def test_get_output_data_body(self, mocked_urljoin):
        mocked_events_datetime = 'some_datetime'
        self._init_class(None)
        self._instance._state = {'events_publishing_datetime': mocked_events_datetime}
        # self._instance._state
        self._instance._get_misp_events = Mock()
        self._instance._current_sample = MagicMock()
        self._instance._download_sample = Mock()
        # publishing events
        self._instance._publishing_samples = False
        self._instance.get_output_data_body('test_source')
        self._instance._get_misp_events.assert_called_once_with(mocked_events_datetime)
        # publishing samples
        self._instance._publishing_samples = True
        self._instance.get_output_data_body('test_source')
        self._instance._download_sample.assert_called_once_with(self.single_sample_test_url)

    def tearDown(self):
        self._instance = None
