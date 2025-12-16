SET GLOBAL max_allowed_packet = 33554432;
-- Note: this max allowed packet size ^ is also set in `../conf.d/mariadb.cnf`.

SET SESSION time_zone = '+00:00';
SET SESSION sql_mode = 'STRICT_TRANS_TABLES,ERROR_FOR_DIVISION_BY_ZERO,NO_AUTO_CREATE_USER,NO_AUTO_VALUE_ON_ZERO,NO_ENGINE_SUBSTITUTION,NO_ZERO_DATE,NO_ZERO_IN_DATE';

DROP DATABASE if exists n6;
CREATE DATABASE n6 CHARACTER SET ascii COLLATE ascii_general_ci;

use n6;

CREATE TABLE n6.event (
    id BINARY(16) NOT NULL,
    rid BINARY(16) NOT NULL,
    source VARCHAR(32) NOT NULL,
    origin ENUM('c2','dropzone','proxy','p2p-crawler','p2p-drone','sinkhole','sandbox','honeypot','darknet','av','ids','waf'),
    restriction ENUM('public','need-to-know','internal') NOT NULL,
    confidence ENUM('low','medium','high') NOT NULL,
    category ENUM('bots','cnc','dos-victim','malurl','phish','proxy','sandbox-url','scanning','server-exploit','spam','other','spam-url','amplifier','tor','dos-attacker','vulnerable','backdoor','dns-query','flow','flow-anomaly','fraud','leak','webinject','malware-action','deface','scam','exposed') NOT NULL,
    time DATETIME NOT NULL,
    name VARCHAR(255),
    md5 BINARY(16),
    sha1 BINARY(20),
    proto ENUM('tcp','udp','icmp'),
    address MEDIUMTEXT,
    ip INTEGER UNSIGNED NOT NULL,
    asn INTEGER UNSIGNED,
    cc CHAR(2),
    sport SMALLINT UNSIGNED,
    dip INTEGER UNSIGNED NOT NULL,
    dport SMALLINT UNSIGNED,
    url VARCHAR(2048) CHARACTER SET utf8mb4 COLLATE utf8mb4_bin,
    fqdn VARCHAR(255),
    target VARCHAR(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_520_ci,
    custom MEDIUMTEXT,
    expires DATETIME,
    status ENUM('active','delisted','expired','replaced'),
    replaces BINARY(16),
    until DATETIME,
    count INTEGER UNSIGNED,
    modified DATETIME NOT NULL,
    sha256 BINARY(32),
    ignored BOOL,
    PRIMARY KEY (time,ip,id)
)   ENGINE = ROCKSDB
    DEFAULT CHARSET = ascii
    COLLATE = ascii_general_ci
    PARTITION BY RANGE COLUMNS(time) (
         PARTITION p_pre_2015 VALUES LESS THAN ('2015-01-01'),
         PARTITION p2015_2018 VALUES LESS THAN ('2018-01-01'),
         PARTITION p2018_2021 VALUES LESS THAN ('2021-01-01'),
         PARTITION p2021_2024 VALUES LESS THAN ('2024-01-01'),
         PARTITION p2024_2027 VALUES LESS THAN ('2027-01-01'),
         PARTITION p2027_2030 VALUES LESS THAN ('2030-01-01'),
         PARTITION p2030_2033 VALUES LESS THAN ('2033-01-01'),
         PARTITION p2033_2036 VALUES LESS THAN ('2036-01-01'),
         PARTITION p_max VALUES LESS THAN MAXVALUE
    );

CREATE TABLE n6.client_to_event (
    id Binary(16) NOT NULL,
    client VARCHAR(32),
    time DATETIME NOT NULL
)   ENGINE = ROCKSDB
    DEFAULT CHARSET = ascii
    COLLATE = ascii_general_ci
    PARTITION BY RANGE COLUMNS(time) (
         PARTITION p_pre_2015 VALUES LESS THAN ('2015-01-01'),
         PARTITION p2015_2018 VALUES LESS THAN ('2018-01-01'),
         PARTITION p2018_2021 VALUES LESS THAN ('2021-01-01'),
         PARTITION p2021_2024 VALUES LESS THAN ('2024-01-01'),
         PARTITION p2024_2027 VALUES LESS THAN ('2027-01-01'),
         PARTITION p2027_2030 VALUES LESS THAN ('2030-01-01'),
         PARTITION p2030_2033 VALUES LESS THAN ('2033-01-01'),
         PARTITION p2033_2036 VALUES LESS THAN ('2036-01-01'),
         PARTITION p_max VALUES LESS THAN MAXVALUE
    );
