SET SESSION time_zone = '+00:00';
SET SESSION sql_mode = 'STRICT_TRANS_TABLES,ERROR_FOR_DIVISION_BY_ZERO,NO_AUTO_CREATE_USER,NO_AUTO_VALUE_ON_ZERO,NO_ENGINE_SUBSTITUTION,NO_ZERO_DATE,NO_ZERO_IN_DATE';

CREATE INDEX idx_event_time ON n6.event (time);
CREATE INDEX idx_event_fqdn ON n6.event (fqdn);
CREATE INDEX idx_event_ip ON n6.event (ip);
CREATE INDEX idx_event_asn ON n6.event (asn);
CREATE INDEX idx_event_cc ON n6.event (cc);
CREATE INDEX idx_event_category ON n6.event (category);
CREATE INDEX idx_event_name ON n6.event (name);
CREATE INDEX idx_event_id ON n6.event (id);
CREATE INDEX idx_event_target ON n6.event (target);
CREATE INDEX idx_event_expires ON n6.event (expires);

CREATE INDEX idx_event_id_time ON n6.event (id,time);
CREATE INDEX idx_event_time_id ON n6.event (time,id);
CREATE INDEX idx_event_time_source ON n6.event (time,source);
CREATE INDEX idx_event_source_time ON n6.event (source,time);
CREATE INDEX idx_event_time_source_cc ON n6.event (time,source,cc);
CREATE INDEX idx_event_source_cc_modified ON n6.event (source,cc,modified);
CREATE INDEX idx_event_asn_time ON n6.event (asn,time);

CREATE INDEX idx_client_to_event_client ON n6.client_to_event (client);
CREATE INDEX idx_client_to_event_id ON n6.client_to_event (id);
CREATE INDEX idx_client_to_event_time ON n6.client_to_event (time);
