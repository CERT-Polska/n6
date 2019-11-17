DROP DATABASE if exists n6;
DROP DATABASE if exists auth_db;
CREATE DATABASE n6 CHARACTER SET utf8 COLLATE utf8_unicode_ci;
CREATE DATABASE auth_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

use n6;

SET GLOBAL max_allowed_packet=1073741824;

CREATE TABLE n6.event (
    id BINARY(16) NOT NULL,
    rid BINARY(16) NOT NULL,
    source VARCHAR(32) NOT NULL,
    origin ENUM('c2','dropzone','proxy','p2p-crawler','p2p-drone','sinkhole','sandbox','honeypot','darknet','av','ids','waf'),
    restriction ENUM('public','need-to-know','internal') NOT NULL,
    confidence ENUM('low','medium','high') NOT NULL,
    category ENUM('bots','cnc','dos-victim','malurl','phish','proxy','sandbox-url','scanning','server-exploit','spam','other','spam-url','amplifier','tor','dos-attacker','vulnerable','backdoor','dns-query','flow','flow-anomaly','fraud','leak','webinject','malware-action','deface', 'scam') NOT NULL,
    time DATETIME NOT NULL,
    name VARCHAR(255),
    md5 BINARY(16),
    sha1 BINARY(20),
    proto ENUM('tcp','udp','icmp'),
    address MEDIUMTEXT,
    ip INTEGER UNSIGNED NOT NULL,
    asn INTEGER UNSIGNED,
    cc VARCHAR(2),
    sport INTEGER,
    dip INTEGER UNSIGNED,
    dport INTEGER,
    url VARCHAR(2048),
    fqdn VARCHAR(255),
    target VARCHAR(100),
    custom MEDIUMTEXT,
    expires DATETIME,
    status ENUM('active','delisted','expired','replaced'),
    replaces BINARY(16),
    until DATETIME,
    count SMALLINT,
    modified DATETIME,
    PRIMARY KEY (id,time,ip)
) ENGINE=InnoDB DEFAULT CHARSET=utf8 COLLATE=utf8_unicode_ci;

CREATE TABLE n6.client_to_event (
    id Binary(16) NOT NULL,
    client VARCHAR(32),
    time datetime  NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8 COLLATE=utf8_unicode_ci;
