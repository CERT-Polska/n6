CREATE INDEX idx_event_time ON n6.event (time);
CREATE INDEX idx_event_fqdn ON n6.event (fqdn(100));
CREATE INDEX idx_event_url ON n6.event (url(2048));
CREATE INDEX idx_event_ip ON n6.event (ip);
CREATE INDEX idx_event_asn ON n6.event (asn);
CREATE INDEX idx_event_cc ON n6.event (cc(2));
CREATE INDEX idx_event_category ON n6.event (category);
CREATE INDEX idx_event_name ON n6.event (name(255));
CREATE INDEX idx_event_id ON n6.event (id);

CREATE INDEX idx_client_to_event_client ON n6.client_to_event (client(16));
CREATE INDEX idx_client_to_event_id ON n6.client_to_event (id);
CREATE INDEX idx_client_to_event_time ON n6.client_to_event (time);
