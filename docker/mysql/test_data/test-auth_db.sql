use auth_db;

-- MySQL dump 10.13  Distrib 5.7.22, for Linux (x86_64)
--
-- Host: 127.0.0.1    Database: auth_db
-- ------------------------------------------------------
-- Server version	5.5.5-10.3.7-MariaDB-1:10.3.7+maria~jessie-log

/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!40101 SET NAMES utf8 */;
/*!40103 SET @OLD_TIME_ZONE=@@TIME_ZONE */;
/*!40103 SET TIME_ZONE='+00:00' */;
/*!40014 SET @OLD_UNIQUE_CHECKS=@@UNIQUE_CHECKS, UNIQUE_CHECKS=0 */;
/*!40014 SET @OLD_FOREIGN_KEY_CHECKS=@@FOREIGN_KEY_CHECKS, FOREIGN_KEY_CHECKS=0 */;
/*!40101 SET @OLD_SQL_MODE=@@SQL_MODE, SQL_MODE='NO_AUTO_VALUE_ON_ZERO' */;
/*!40111 SET @OLD_SQL_NOTES=@@SQL_NOTES, SQL_NOTES=0 */;

--
-- Table structure for table `ca_cert`
--

DROP TABLE IF EXISTS `ca_cert`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `ca_cert` (
  `ca_label` varchar(100) NOT NULL,
  `certificate` blob DEFAULT NULL,
  `parent_ca_label` varchar(100) DEFAULT NULL,
  PRIMARY KEY (`ca_label`),
  KEY `parent_ca_label` (`parent_ca_label`),
  CONSTRAINT `ca_cert_ibfk_1` FOREIGN KEY (`parent_ca_label`) REFERENCES `ca_cert` (`ca_label`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `ca_cert`
--

LOCK TABLES `ca_cert` WRITE;
/*!40000 ALTER TABLE `ca_cert` DISABLE KEYS */;
/*!40000 ALTER TABLE `ca_cert` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `cert`
--

DROP TABLE IF EXISTS `cert`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `cert` (
  `serial_hex` varchar(20) NOT NULL,
  `certificate` blob DEFAULT NULL,
  `created_by_login` varchar(255) DEFAULT NULL,
  `created_by_component_login` varchar(255) DEFAULT NULL,
  `is_client_cert` tinyint(1) DEFAULT NULL,
  `is_server_cert` tinyint(1) DEFAULT NULL,
  `created_on` datetime DEFAULT NULL,
  `valid_from` datetime DEFAULT NULL,
  `expires_on` datetime DEFAULT NULL,
  `ca_cert_label` varchar(100) DEFAULT NULL,
  `request_case_id` varchar(28) DEFAULT NULL,
  `owner_login` varchar(255) DEFAULT NULL,
  `owner_component_login` varchar(255) DEFAULT NULL,
  `revoked_on` datetime DEFAULT NULL,
  `revoked_by_login` varchar(255) DEFAULT NULL,
  `revoked_by_component_login` varchar(255) DEFAULT NULL,
  `revocation_comment` text DEFAULT NULL,
  PRIMARY KEY (`serial_hex`),
  KEY `created_by_login` (`created_by_login`),
  KEY `created_by_component_login` (`created_by_component_login`),
  KEY `ca_cert_label` (`ca_cert_label`),
  KEY `request_case_id` (`request_case_id`),
  KEY `owner_login` (`owner_login`),
  KEY `owner_component_login` (`owner_component_login`),
  KEY `revoked_by_login` (`revoked_by_login`),
  KEY `revoked_by_component_login` (`revoked_by_component_login`),
  CONSTRAINT `cert_ibfk_1` FOREIGN KEY (`created_by_login`) REFERENCES `user` (`login`),
  CONSTRAINT `cert_ibfk_2` FOREIGN KEY (`created_by_component_login`) REFERENCES `component` (`login`),
  CONSTRAINT `cert_ibfk_3` FOREIGN KEY (`ca_cert_label`) REFERENCES `ca_cert` (`ca_label`),
  CONSTRAINT `cert_ibfk_4` FOREIGN KEY (`request_case_id`) REFERENCES `request_case` (`request_case_id`),
  CONSTRAINT `cert_ibfk_5` FOREIGN KEY (`owner_login`) REFERENCES `user` (`login`),
  CONSTRAINT `cert_ibfk_6` FOREIGN KEY (`owner_component_login`) REFERENCES `component` (`login`),
  CONSTRAINT `cert_ibfk_7` FOREIGN KEY (`revoked_by_login`) REFERENCES `user` (`login`),
  CONSTRAINT `cert_ibfk_8` FOREIGN KEY (`revoked_by_component_login`) REFERENCES `component` (`login`),
  CONSTRAINT `CONSTRAINT_1` CHECK (`is_client_cert` in (0,1)),
  CONSTRAINT `CONSTRAINT_2` CHECK (`is_server_cert` in (0,1))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `cert`
--

LOCK TABLES `cert` WRITE;
/*!40000 ALTER TABLE `cert` DISABLE KEYS */;
/*!40000 ALTER TABLE `cert` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `component`
--

DROP TABLE IF EXISTS `component`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `component` (
  `login` varchar(255) NOT NULL,
  `password` varchar(60) DEFAULT NULL,
  PRIMARY KEY (`login`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `component`
--

LOCK TABLES `component` WRITE;
/*!40000 ALTER TABLE `component` DISABLE KEYS */;
/*!40000 ALTER TABLE `component` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `criteria_asn`
--

DROP TABLE IF EXISTS `criteria_asn`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `criteria_asn` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `asn` int(11) NOT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `criteria_asn`
--

LOCK TABLES `criteria_asn` WRITE;
/*!40000 ALTER TABLE `criteria_asn` DISABLE KEYS */;
/*!40000 ALTER TABLE `criteria_asn` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `criteria_asn_link`
--

DROP TABLE IF EXISTS `criteria_asn_link`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `criteria_asn_link` (
  `criteria_container_label` varchar(100) NOT NULL,
  `asn_id` int(11) NOT NULL,
  PRIMARY KEY (`criteria_container_label`,`asn_id`),
  KEY `asn_id` (`asn_id`),
  CONSTRAINT `criteria_asn_link_ibfk_1` FOREIGN KEY (`criteria_container_label`) REFERENCES `criteria_container` (`label`),
  CONSTRAINT `criteria_asn_link_ibfk_2` FOREIGN KEY (`asn_id`) REFERENCES `criteria_asn` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `criteria_asn_link`
--

LOCK TABLES `criteria_asn_link` WRITE;
/*!40000 ALTER TABLE `criteria_asn_link` DISABLE KEYS */;
/*!40000 ALTER TABLE `criteria_asn_link` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `criteria_category`
--

DROP TABLE IF EXISTS `criteria_category`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `criteria_category` (
  `category` varchar(255) NOT NULL,
  PRIMARY KEY (`category`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `criteria_category`
--

LOCK TABLES `criteria_category` WRITE;
/*!40000 ALTER TABLE `criteria_category` DISABLE KEYS */;
INSERT INTO `criteria_category` VALUES ('amplifier'),('backdoor'),('bots'),('cnc'),('deface'),('dns-query'),('dos-attacker'),('dos-victim'),('flow'),('flow-anomaly'),('fraud'),('leak'),('malurl'),('malware-action'),('other'),('phish'),('proxy'),('sandbox-url'),('scam'),('scanning'),('server-exploit'),('spam'),('spam-url'),('tor'),('vulnerable'),('webinject');
/*!40000 ALTER TABLE `criteria_category` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `criteria_category_link`
--

DROP TABLE IF EXISTS `criteria_category_link`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `criteria_category_link` (
  `criteria_container_label` varchar(100) NOT NULL,
  `criteria_category_name` varchar(255) NOT NULL,
  PRIMARY KEY (`criteria_container_label`,`criteria_category_name`),
  KEY `criteria_category_name` (`criteria_category_name`),
  CONSTRAINT `criteria_category_link_ibfk_1` FOREIGN KEY (`criteria_container_label`) REFERENCES `criteria_container` (`label`),
  CONSTRAINT `criteria_category_link_ibfk_2` FOREIGN KEY (`criteria_category_name`) REFERENCES `criteria_category` (`category`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `criteria_category_link`
--

LOCK TABLES `criteria_category_link` WRITE;
/*!40000 ALTER TABLE `criteria_category_link` DISABLE KEYS */;
/*!40000 ALTER TABLE `criteria_category_link` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `criteria_cc`
--

DROP TABLE IF EXISTS `criteria_cc`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `criteria_cc` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `cc` varchar(2) NOT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `criteria_cc`
--

LOCK TABLES `criteria_cc` WRITE;
/*!40000 ALTER TABLE `criteria_cc` DISABLE KEYS */;
/*!40000 ALTER TABLE `criteria_cc` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `criteria_cc_link`
--

DROP TABLE IF EXISTS `criteria_cc_link`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `criteria_cc_link` (
  `criteria_container_label` varchar(100) NOT NULL,
  `cc_id` int(11) NOT NULL,
  PRIMARY KEY (`criteria_container_label`,`cc_id`),
  KEY `cc_id` (`cc_id`),
  CONSTRAINT `criteria_cc_link_ibfk_1` FOREIGN KEY (`criteria_container_label`) REFERENCES `criteria_container` (`label`),
  CONSTRAINT `criteria_cc_link_ibfk_2` FOREIGN KEY (`cc_id`) REFERENCES `criteria_cc` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `criteria_cc_link`
--

LOCK TABLES `criteria_cc_link` WRITE;
/*!40000 ALTER TABLE `criteria_cc_link` DISABLE KEYS */;
/*!40000 ALTER TABLE `criteria_cc_link` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `criteria_container`
--

DROP TABLE IF EXISTS `criteria_container`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `criteria_container` (
  `label` varchar(100) NOT NULL,
  PRIMARY KEY (`label`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `criteria_container`
--

LOCK TABLES `criteria_container` WRITE;
/*!40000 ALTER TABLE `criteria_container` DISABLE KEYS */;
/*!40000 ALTER TABLE `criteria_container` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `criteria_criteria_container_link`
--

DROP TABLE IF EXISTS `criteria_criteria_container_link`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `criteria_criteria_container_link` (
  `criteria_container_label` varchar(100) NOT NULL,
  `criteria_name_id` int(11) NOT NULL,
  PRIMARY KEY (`criteria_container_label`,`criteria_name_id`),
  KEY `criteria_name_id` (`criteria_name_id`),
  CONSTRAINT `criteria_criteria_container_link_ibfk_1` FOREIGN KEY (`criteria_container_label`) REFERENCES `criteria_container` (`label`),
  CONSTRAINT `criteria_criteria_container_link_ibfk_2` FOREIGN KEY (`criteria_name_id`) REFERENCES `criteria_name` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `criteria_criteria_container_link`
--

LOCK TABLES `criteria_criteria_container_link` WRITE;
/*!40000 ALTER TABLE `criteria_criteria_container_link` DISABLE KEYS */;
/*!40000 ALTER TABLE `criteria_criteria_container_link` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `criteria_ip_network`
--

DROP TABLE IF EXISTS `criteria_ip_network`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `criteria_ip_network` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `ip_network` varchar(18) NOT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `criteria_ip_network`
--

LOCK TABLES `criteria_ip_network` WRITE;
/*!40000 ALTER TABLE `criteria_ip_network` DISABLE KEYS */;
/*!40000 ALTER TABLE `criteria_ip_network` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `criteria_ip_network_link`
--

DROP TABLE IF EXISTS `criteria_ip_network_link`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `criteria_ip_network_link` (
  `criteria_container_label` varchar(100) NOT NULL,
  `ip_network_id` int(11) NOT NULL,
  PRIMARY KEY (`criteria_container_label`,`ip_network_id`),
  KEY `ip_network_id` (`ip_network_id`),
  CONSTRAINT `criteria_ip_network_link_ibfk_1` FOREIGN KEY (`criteria_container_label`) REFERENCES `criteria_container` (`label`),
  CONSTRAINT `criteria_ip_network_link_ibfk_2` FOREIGN KEY (`ip_network_id`) REFERENCES `criteria_ip_network` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `criteria_ip_network_link`
--

LOCK TABLES `criteria_ip_network_link` WRITE;
/*!40000 ALTER TABLE `criteria_ip_network_link` DISABLE KEYS */;
/*!40000 ALTER TABLE `criteria_ip_network_link` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `criteria_name`
--

DROP TABLE IF EXISTS `criteria_name`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `criteria_name` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `name` varchar(255) NOT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `criteria_name`
--

LOCK TABLES `criteria_name` WRITE;
/*!40000 ALTER TABLE `criteria_name` DISABLE KEYS */;
/*!40000 ALTER TABLE `criteria_name` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `email_notification_address`
--

DROP TABLE IF EXISTS `email_notification_address`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `email_notification_address` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `email` varchar(255) NOT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `email_notification_address`
--

LOCK TABLES `email_notification_address` WRITE;
/*!40000 ALTER TABLE `email_notification_address` DISABLE KEYS */;
/*!40000 ALTER TABLE `email_notification_address` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `email_notification_time`
--

DROP TABLE IF EXISTS `email_notification_time`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `email_notification_time` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `notification_time` time DEFAULT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `email_notification_time`
--

LOCK TABLES `email_notification_time` WRITE;
/*!40000 ALTER TABLE `email_notification_time` DISABLE KEYS */;
/*!40000 ALTER TABLE `email_notification_time` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `inside_filter_asn`
--

DROP TABLE IF EXISTS `inside_filter_asn`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `inside_filter_asn` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `asn` int(11) NOT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `inside_filter_asn`
--

LOCK TABLES `inside_filter_asn` WRITE;
/*!40000 ALTER TABLE `inside_filter_asn` DISABLE KEYS */;
/*!40000 ALTER TABLE `inside_filter_asn` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `inside_filter_cc`
--

DROP TABLE IF EXISTS `inside_filter_cc`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `inside_filter_cc` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `cc` varchar(2) NOT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `inside_filter_cc`
--

LOCK TABLES `inside_filter_cc` WRITE;
/*!40000 ALTER TABLE `inside_filter_cc` DISABLE KEYS */;
/*!40000 ALTER TABLE `inside_filter_cc` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `inside_filter_fqdn`
--

DROP TABLE IF EXISTS `inside_filter_fqdn`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `inside_filter_fqdn` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `fqdn` varchar(255) NOT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `inside_filter_fqdn`
--

LOCK TABLES `inside_filter_fqdn` WRITE;
/*!40000 ALTER TABLE `inside_filter_fqdn` DISABLE KEYS */;
/*!40000 ALTER TABLE `inside_filter_fqdn` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `inside_filter_ip_network`
--

DROP TABLE IF EXISTS `inside_filter_ip_network`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `inside_filter_ip_network` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `ip_network` varchar(18) NOT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `inside_filter_ip_network`
--

LOCK TABLES `inside_filter_ip_network` WRITE;
/*!40000 ALTER TABLE `inside_filter_ip_network` DISABLE KEYS */;
/*!40000 ALTER TABLE `inside_filter_ip_network` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `inside_filter_url`
--

DROP TABLE IF EXISTS `inside_filter_url`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `inside_filter_url` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `url` varchar(2048) NOT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `inside_filter_url`
--

LOCK TABLES `inside_filter_url` WRITE;
/*!40000 ALTER TABLE `inside_filter_url` DISABLE KEYS */;
/*!40000 ALTER TABLE `inside_filter_url` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `org`
--

DROP TABLE IF EXISTS `org`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `org` (
  `org_id` varchar(32) NOT NULL,
  `actual_name` varchar(255) DEFAULT NULL,
  `full_access` tinyint(1) DEFAULT NULL,
  `access_to_inside` tinyint(1) DEFAULT NULL,
  `access_to_search` tinyint(1) DEFAULT NULL,
  `access_to_threats` tinyint(1) DEFAULT NULL,
  `stream_api_enabled` tinyint(1) DEFAULT NULL,
  `email_notifications_enabled` tinyint(1) DEFAULT NULL,
  `email_notifications_language` varchar(2) DEFAULT NULL,
  `email_notifications_business_days_only` tinyint(1) DEFAULT NULL,
  PRIMARY KEY (`org_id`),
  CONSTRAINT `CONSTRAINT_1` CHECK (`full_access` in (0,1)),
  CONSTRAINT `CONSTRAINT_2` CHECK (`access_to_inside` in (0,1)),
  CONSTRAINT `CONSTRAINT_3` CHECK (`access_to_search` in (0,1)),
  CONSTRAINT `CONSTRAINT_4` CHECK (`access_to_threats` in (0,1)),
  CONSTRAINT `CONSTRAINT_5` CHECK (`stream_api_enabled` in (0,1)),
  CONSTRAINT `CONSTRAINT_6` CHECK (`email_notifications_enabled` in (0,1)),
  CONSTRAINT `CONSTRAINT_7` CHECK (`email_notifications_business_days_only` in (0,1))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `org`
--

LOCK TABLES `org` WRITE;
/*!40000 ALTER TABLE `org` DISABLE KEYS */;
INSERT INTO `org` VALUES ('example.com',NULL,1,1,1,1,0,0,NULL,0);
/*!40000 ALTER TABLE `org` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `org_asn_link`
--

DROP TABLE IF EXISTS `org_asn_link`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `org_asn_link` (
  `org_id` varchar(32) NOT NULL,
  `asn_id` int(11) NOT NULL,
  PRIMARY KEY (`org_id`,`asn_id`),
  KEY `asn_id` (`asn_id`),
  CONSTRAINT `org_asn_link_ibfk_1` FOREIGN KEY (`org_id`) REFERENCES `org` (`org_id`),
  CONSTRAINT `org_asn_link_ibfk_2` FOREIGN KEY (`asn_id`) REFERENCES `inside_filter_asn` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `org_asn_link`
--

LOCK TABLES `org_asn_link` WRITE;
/*!40000 ALTER TABLE `org_asn_link` DISABLE KEYS */;
/*!40000 ALTER TABLE `org_asn_link` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `org_cc_link`
--

DROP TABLE IF EXISTS `org_cc_link`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `org_cc_link` (
  `org_id` varchar(32) NOT NULL,
  `cc_id` int(11) NOT NULL,
  PRIMARY KEY (`org_id`,`cc_id`),
  KEY `cc_id` (`cc_id`),
  CONSTRAINT `org_cc_link_ibfk_1` FOREIGN KEY (`org_id`) REFERENCES `org` (`org_id`),
  CONSTRAINT `org_cc_link_ibfk_2` FOREIGN KEY (`cc_id`) REFERENCES `inside_filter_cc` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `org_cc_link`
--

LOCK TABLES `org_cc_link` WRITE;
/*!40000 ALTER TABLE `org_cc_link` DISABLE KEYS */;
/*!40000 ALTER TABLE `org_cc_link` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `org_fqdn_link`
--

DROP TABLE IF EXISTS `org_fqdn_link`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `org_fqdn_link` (
  `org_id` varchar(32) NOT NULL,
  `fqdn_id` int(11) NOT NULL,
  PRIMARY KEY (`org_id`,`fqdn_id`),
  KEY `fqdn_id` (`fqdn_id`),
  CONSTRAINT `org_fqdn_link_ibfk_1` FOREIGN KEY (`org_id`) REFERENCES `org` (`org_id`),
  CONSTRAINT `org_fqdn_link_ibfk_2` FOREIGN KEY (`fqdn_id`) REFERENCES `inside_filter_fqdn` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `org_fqdn_link`
--

LOCK TABLES `org_fqdn_link` WRITE;
/*!40000 ALTER TABLE `org_fqdn_link` DISABLE KEYS */;
/*!40000 ALTER TABLE `org_fqdn_link` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `org_group`
--

DROP TABLE IF EXISTS `org_group`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `org_group` (
  `org_group_id` varchar(255) NOT NULL,
  `comment` text DEFAULT NULL,
  PRIMARY KEY (`org_group_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `org_group`
--

LOCK TABLES `org_group` WRITE;
/*!40000 ALTER TABLE `org_group` DISABLE KEYS */;
/*!40000 ALTER TABLE `org_group` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `org_group_inside_subsource_group_link`
--

DROP TABLE IF EXISTS `org_group_inside_subsource_group_link`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `org_group_inside_subsource_group_link` (
  `org_group_id` varchar(255) NOT NULL,
  `subsource_group_label` varchar(255) NOT NULL,
  PRIMARY KEY (`org_group_id`,`subsource_group_label`),
  KEY `subsource_group_label` (`subsource_group_label`),
  CONSTRAINT `org_group_inside_subsource_group_link_ibfk_1` FOREIGN KEY (`org_group_id`) REFERENCES `org_group` (`org_group_id`),
  CONSTRAINT `org_group_inside_subsource_group_link_ibfk_2` FOREIGN KEY (`subsource_group_label`) REFERENCES `subsource_group` (`label`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `org_group_inside_subsource_group_link`
--

LOCK TABLES `org_group_inside_subsource_group_link` WRITE;
/*!40000 ALTER TABLE `org_group_inside_subsource_group_link` DISABLE KEYS */;
/*!40000 ALTER TABLE `org_group_inside_subsource_group_link` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `org_group_inside_subsource_link`
--

DROP TABLE IF EXISTS `org_group_inside_subsource_link`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `org_group_inside_subsource_link` (
  `org_group_id` varchar(255) NOT NULL,
  `subsource_label` varchar(255) NOT NULL,
  PRIMARY KEY (`org_group_id`,`subsource_label`),
  KEY `subsource_label` (`subsource_label`),
  CONSTRAINT `org_group_inside_subsource_link_ibfk_1` FOREIGN KEY (`org_group_id`) REFERENCES `org_group` (`org_group_id`),
  CONSTRAINT `org_group_inside_subsource_link_ibfk_2` FOREIGN KEY (`subsource_label`) REFERENCES `subsource` (`label`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `org_group_inside_subsource_link`
--

LOCK TABLES `org_group_inside_subsource_link` WRITE;
/*!40000 ALTER TABLE `org_group_inside_subsource_link` DISABLE KEYS */;
/*!40000 ALTER TABLE `org_group_inside_subsource_link` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `org_group_search_subsource_group_link`
--

DROP TABLE IF EXISTS `org_group_search_subsource_group_link`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `org_group_search_subsource_group_link` (
  `org_group_id` varchar(255) NOT NULL,
  `subsource_group_label` varchar(255) NOT NULL,
  PRIMARY KEY (`org_group_id`,`subsource_group_label`),
  KEY `subsource_group_label` (`subsource_group_label`),
  CONSTRAINT `org_group_search_subsource_group_link_ibfk_1` FOREIGN KEY (`org_group_id`) REFERENCES `org_group` (`org_group_id`),
  CONSTRAINT `org_group_search_subsource_group_link_ibfk_2` FOREIGN KEY (`subsource_group_label`) REFERENCES `subsource_group` (`label`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `org_group_search_subsource_group_link`
--

LOCK TABLES `org_group_search_subsource_group_link` WRITE;
/*!40000 ALTER TABLE `org_group_search_subsource_group_link` DISABLE KEYS */;
/*!40000 ALTER TABLE `org_group_search_subsource_group_link` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `org_group_search_subsource_link`
--

DROP TABLE IF EXISTS `org_group_search_subsource_link`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `org_group_search_subsource_link` (
  `org_group_id` varchar(255) NOT NULL,
  `subsource_label` varchar(255) NOT NULL,
  PRIMARY KEY (`org_group_id`,`subsource_label`),
  KEY `subsource_label` (`subsource_label`),
  CONSTRAINT `org_group_search_subsource_link_ibfk_1` FOREIGN KEY (`org_group_id`) REFERENCES `org_group` (`org_group_id`),
  CONSTRAINT `org_group_search_subsource_link_ibfk_2` FOREIGN KEY (`subsource_label`) REFERENCES `subsource` (`label`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `org_group_search_subsource_link`
--

LOCK TABLES `org_group_search_subsource_link` WRITE;
/*!40000 ALTER TABLE `org_group_search_subsource_link` DISABLE KEYS */;
/*!40000 ALTER TABLE `org_group_search_subsource_link` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `org_group_threats_subsource_group_link`
--

DROP TABLE IF EXISTS `org_group_threats_subsource_group_link`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `org_group_threats_subsource_group_link` (
  `org_group_id` varchar(255) NOT NULL,
  `subsource_group_label` varchar(255) NOT NULL,
  PRIMARY KEY (`org_group_id`,`subsource_group_label`),
  KEY `subsource_group_label` (`subsource_group_label`),
  CONSTRAINT `org_group_threats_subsource_group_link_ibfk_1` FOREIGN KEY (`org_group_id`) REFERENCES `org_group` (`org_group_id`),
  CONSTRAINT `org_group_threats_subsource_group_link_ibfk_2` FOREIGN KEY (`subsource_group_label`) REFERENCES `subsource_group` (`label`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `org_group_threats_subsource_group_link`
--

LOCK TABLES `org_group_threats_subsource_group_link` WRITE;
/*!40000 ALTER TABLE `org_group_threats_subsource_group_link` DISABLE KEYS */;
/*!40000 ALTER TABLE `org_group_threats_subsource_group_link` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `org_group_threats_subsource_link`
--

DROP TABLE IF EXISTS `org_group_threats_subsource_link`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `org_group_threats_subsource_link` (
  `org_group_id` varchar(255) NOT NULL,
  `subsource_label` varchar(255) NOT NULL,
  PRIMARY KEY (`org_group_id`,`subsource_label`),
  KEY `subsource_label` (`subsource_label`),
  CONSTRAINT `org_group_threats_subsource_link_ibfk_1` FOREIGN KEY (`org_group_id`) REFERENCES `org_group` (`org_group_id`),
  CONSTRAINT `org_group_threats_subsource_link_ibfk_2` FOREIGN KEY (`subsource_label`) REFERENCES `subsource` (`label`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `org_group_threats_subsource_link`
--

LOCK TABLES `org_group_threats_subsource_link` WRITE;
/*!40000 ALTER TABLE `org_group_threats_subsource_link` DISABLE KEYS */;
/*!40000 ALTER TABLE `org_group_threats_subsource_link` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `org_inside_ex_subsource_group_link`
--

DROP TABLE IF EXISTS `org_inside_ex_subsource_group_link`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `org_inside_ex_subsource_group_link` (
  `org_id` varchar(32) NOT NULL,
  `subsource_group_label` varchar(255) NOT NULL,
  PRIMARY KEY (`org_id`,`subsource_group_label`),
  KEY `subsource_group_label` (`subsource_group_label`),
  CONSTRAINT `org_inside_ex_subsource_group_link_ibfk_1` FOREIGN KEY (`org_id`) REFERENCES `org` (`org_id`),
  CONSTRAINT `org_inside_ex_subsource_group_link_ibfk_2` FOREIGN KEY (`subsource_group_label`) REFERENCES `subsource_group` (`label`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `org_inside_ex_subsource_group_link`
--

LOCK TABLES `org_inside_ex_subsource_group_link` WRITE;
/*!40000 ALTER TABLE `org_inside_ex_subsource_group_link` DISABLE KEYS */;
/*!40000 ALTER TABLE `org_inside_ex_subsource_group_link` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `org_inside_ex_subsource_link`
--

DROP TABLE IF EXISTS `org_inside_ex_subsource_link`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `org_inside_ex_subsource_link` (
  `org_id` varchar(32) NOT NULL,
  `subsource_label` varchar(255) NOT NULL,
  PRIMARY KEY (`org_id`,`subsource_label`),
  KEY `subsource_label` (`subsource_label`),
  CONSTRAINT `org_inside_ex_subsource_link_ibfk_1` FOREIGN KEY (`org_id`) REFERENCES `org` (`org_id`),
  CONSTRAINT `org_inside_ex_subsource_link_ibfk_2` FOREIGN KEY (`subsource_label`) REFERENCES `subsource` (`label`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `org_inside_ex_subsource_link`
--

LOCK TABLES `org_inside_ex_subsource_link` WRITE;
/*!40000 ALTER TABLE `org_inside_ex_subsource_link` DISABLE KEYS */;
/*!40000 ALTER TABLE `org_inside_ex_subsource_link` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `org_inside_subsource_group_link`
--

DROP TABLE IF EXISTS `org_inside_subsource_group_link`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `org_inside_subsource_group_link` (
  `org_id` varchar(32) NOT NULL,
  `subsource_group_label` varchar(255) NOT NULL,
  PRIMARY KEY (`org_id`,`subsource_group_label`),
  KEY `subsource_group_label` (`subsource_group_label`),
  CONSTRAINT `org_inside_subsource_group_link_ibfk_1` FOREIGN KEY (`org_id`) REFERENCES `org` (`org_id`),
  CONSTRAINT `org_inside_subsource_group_link_ibfk_2` FOREIGN KEY (`subsource_group_label`) REFERENCES `subsource_group` (`label`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `org_inside_subsource_group_link`
--

LOCK TABLES `org_inside_subsource_group_link` WRITE;
/*!40000 ALTER TABLE `org_inside_subsource_group_link` DISABLE KEYS */;
/*!40000 ALTER TABLE `org_inside_subsource_group_link` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `org_inside_subsource_link`
--

DROP TABLE IF EXISTS `org_inside_subsource_link`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `org_inside_subsource_link` (
  `org_id` varchar(32) NOT NULL,
  `subsource_label` varchar(255) NOT NULL,
  PRIMARY KEY (`org_id`,`subsource_label`),
  KEY `subsource_label` (`subsource_label`),
  CONSTRAINT `org_inside_subsource_link_ibfk_1` FOREIGN KEY (`org_id`) REFERENCES `org` (`org_id`),
  CONSTRAINT `org_inside_subsource_link_ibfk_2` FOREIGN KEY (`subsource_label`) REFERENCES `subsource` (`label`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `org_inside_subsource_link`
--

LOCK TABLES `org_inside_subsource_link` WRITE;
/*!40000 ALTER TABLE `org_inside_subsource_link` DISABLE KEYS */;
INSERT INTO `org_inside_subsource_link` VALUES ('example.com','general access to abuse-ch.feodotracker'),('example.com','general access to abuse-ch.palevo-doms'),('example.com','general access to abuse-ch.palevo-ips'),('example.com','general access to abuse-ch.ransomware'),('example.com','general access to abuse-ch.spyeye-doms'),('example.com','general access to abuse-ch.spyeye-ips'),('example.com','general access to abuse-ch.ssl-blacklist'),('example.com','general access to abuse-ch.ssl-blacklist-dyre'),('example.com','general access to abuse-ch.zeus-doms'),('example.com','general access to abuse-ch.zeus-ips'),('example.com','general access to abuse-ch.zeustracker'),('example.com','general access to badips-com.server-exploit-list'),('example.com','general access to circl-lu.misp'),('example.com','general access to dns-bh.malwaredomainscom'),('example.com','general access to greensnow-co.list-txt'),('example.com','general access to packetmail-net.list'),('example.com','general access to packetmail-net.others-list'),('example.com','general access to packetmail-net.ratware-list'),('example.com','general access to spam404-com.scam-list'),('example.com','general access to zoneh.rss');
/*!40000 ALTER TABLE `org_inside_subsource_link` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `org_ip_network_link`
--

DROP TABLE IF EXISTS `org_ip_network_link`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `org_ip_network_link` (
  `org_id` varchar(32) NOT NULL,
  `ip_network_id` int(11) NOT NULL,
  PRIMARY KEY (`org_id`,`ip_network_id`),
  KEY `ip_network_id` (`ip_network_id`),
  CONSTRAINT `org_ip_network_link_ibfk_1` FOREIGN KEY (`org_id`) REFERENCES `org` (`org_id`),
  CONSTRAINT `org_ip_network_link_ibfk_2` FOREIGN KEY (`ip_network_id`) REFERENCES `inside_filter_ip_network` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `org_ip_network_link`
--

LOCK TABLES `org_ip_network_link` WRITE;
/*!40000 ALTER TABLE `org_ip_network_link` DISABLE KEYS */;
/*!40000 ALTER TABLE `org_ip_network_link` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `org_notification_email_link`
--

DROP TABLE IF EXISTS `org_notification_email_link`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `org_notification_email_link` (
  `org_id` varchar(32) NOT NULL,
  `email_notification_address_id` int(11) NOT NULL,
  PRIMARY KEY (`org_id`,`email_notification_address_id`),
  KEY `email_notification_address_id` (`email_notification_address_id`),
  CONSTRAINT `org_notification_email_link_ibfk_1` FOREIGN KEY (`org_id`) REFERENCES `org` (`org_id`),
  CONSTRAINT `org_notification_email_link_ibfk_2` FOREIGN KEY (`email_notification_address_id`) REFERENCES `email_notification_address` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `org_notification_email_link`
--

LOCK TABLES `org_notification_email_link` WRITE;
/*!40000 ALTER TABLE `org_notification_email_link` DISABLE KEYS */;
/*!40000 ALTER TABLE `org_notification_email_link` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `org_notification_time_link`
--

DROP TABLE IF EXISTS `org_notification_time_link`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `org_notification_time_link` (
  `org_id` varchar(32) NOT NULL,
  `notification_time_id` int(11) NOT NULL,
  PRIMARY KEY (`org_id`,`notification_time_id`),
  KEY `notification_time_id` (`notification_time_id`),
  CONSTRAINT `org_notification_time_link_ibfk_1` FOREIGN KEY (`org_id`) REFERENCES `org` (`org_id`),
  CONSTRAINT `org_notification_time_link_ibfk_2` FOREIGN KEY (`notification_time_id`) REFERENCES `email_notification_time` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `org_notification_time_link`
--

LOCK TABLES `org_notification_time_link` WRITE;
/*!40000 ALTER TABLE `org_notification_time_link` DISABLE KEYS */;
/*!40000 ALTER TABLE `org_notification_time_link` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `org_org_group_link`
--

DROP TABLE IF EXISTS `org_org_group_link`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `org_org_group_link` (
  `org_id` varchar(32) NOT NULL,
  `org_group_id` varchar(255) NOT NULL,
  PRIMARY KEY (`org_id`,`org_group_id`),
  KEY `org_group_id` (`org_group_id`),
  CONSTRAINT `org_org_group_link_ibfk_1` FOREIGN KEY (`org_id`) REFERENCES `org` (`org_id`),
  CONSTRAINT `org_org_group_link_ibfk_2` FOREIGN KEY (`org_group_id`) REFERENCES `org_group` (`org_group_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `org_org_group_link`
--

LOCK TABLES `org_org_group_link` WRITE;
/*!40000 ALTER TABLE `org_org_group_link` DISABLE KEYS */;
/*!40000 ALTER TABLE `org_org_group_link` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `org_search_ex_subsource_group_link`
--

DROP TABLE IF EXISTS `org_search_ex_subsource_group_link`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `org_search_ex_subsource_group_link` (
  `org_id` varchar(32) NOT NULL,
  `subsource_group_label` varchar(255) NOT NULL,
  PRIMARY KEY (`org_id`,`subsource_group_label`),
  KEY `subsource_group_label` (`subsource_group_label`),
  CONSTRAINT `org_search_ex_subsource_group_link_ibfk_1` FOREIGN KEY (`org_id`) REFERENCES `org` (`org_id`),
  CONSTRAINT `org_search_ex_subsource_group_link_ibfk_2` FOREIGN KEY (`subsource_group_label`) REFERENCES `subsource_group` (`label`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `org_search_ex_subsource_group_link`
--

LOCK TABLES `org_search_ex_subsource_group_link` WRITE;
/*!40000 ALTER TABLE `org_search_ex_subsource_group_link` DISABLE KEYS */;
/*!40000 ALTER TABLE `org_search_ex_subsource_group_link` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `org_search_ex_subsource_link`
--

DROP TABLE IF EXISTS `org_search_ex_subsource_link`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `org_search_ex_subsource_link` (
  `org_id` varchar(32) NOT NULL,
  `subsource_label` varchar(255) NOT NULL,
  PRIMARY KEY (`org_id`,`subsource_label`),
  KEY `subsource_label` (`subsource_label`),
  CONSTRAINT `org_search_ex_subsource_link_ibfk_1` FOREIGN KEY (`org_id`) REFERENCES `org` (`org_id`),
  CONSTRAINT `org_search_ex_subsource_link_ibfk_2` FOREIGN KEY (`subsource_label`) REFERENCES `subsource` (`label`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `org_search_ex_subsource_link`
--

LOCK TABLES `org_search_ex_subsource_link` WRITE;
/*!40000 ALTER TABLE `org_search_ex_subsource_link` DISABLE KEYS */;
/*!40000 ALTER TABLE `org_search_ex_subsource_link` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `org_search_subsource_group_link`
--

DROP TABLE IF EXISTS `org_search_subsource_group_link`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `org_search_subsource_group_link` (
  `org_id` varchar(32) NOT NULL,
  `subsource_group_label` varchar(255) NOT NULL,
  PRIMARY KEY (`org_id`,`subsource_group_label`),
  KEY `subsource_group_label` (`subsource_group_label`),
  CONSTRAINT `org_search_subsource_group_link_ibfk_1` FOREIGN KEY (`org_id`) REFERENCES `org` (`org_id`),
  CONSTRAINT `org_search_subsource_group_link_ibfk_2` FOREIGN KEY (`subsource_group_label`) REFERENCES `subsource_group` (`label`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `org_search_subsource_group_link`
--

LOCK TABLES `org_search_subsource_group_link` WRITE;
/*!40000 ALTER TABLE `org_search_subsource_group_link` DISABLE KEYS */;
/*!40000 ALTER TABLE `org_search_subsource_group_link` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `org_search_subsource_link`
--

DROP TABLE IF EXISTS `org_search_subsource_link`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `org_search_subsource_link` (
  `org_id` varchar(32) NOT NULL,
  `subsource_label` varchar(255) NOT NULL,
  PRIMARY KEY (`org_id`,`subsource_label`),
  KEY `subsource_label` (`subsource_label`),
  CONSTRAINT `org_search_subsource_link_ibfk_1` FOREIGN KEY (`org_id`) REFERENCES `org` (`org_id`),
  CONSTRAINT `org_search_subsource_link_ibfk_2` FOREIGN KEY (`subsource_label`) REFERENCES `subsource` (`label`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `org_search_subsource_link`
--

LOCK TABLES `org_search_subsource_link` WRITE;
/*!40000 ALTER TABLE `org_search_subsource_link` DISABLE KEYS */;
INSERT INTO `org_search_subsource_link` VALUES ('example.com','general access to abuse-ch.feodotracker'),('example.com','general access to abuse-ch.palevo-doms'),('example.com','general access to abuse-ch.palevo-ips'),('example.com','general access to abuse-ch.ransomware'),('example.com','general access to abuse-ch.spyeye-doms'),('example.com','general access to abuse-ch.spyeye-ips'),('example.com','general access to abuse-ch.ssl-blacklist'),('example.com','general access to abuse-ch.ssl-blacklist-dyre'),('example.com','general access to abuse-ch.zeus-doms'),('example.com','general access to abuse-ch.zeus-ips'),('example.com','general access to abuse-ch.zeustracker'),('example.com','general access to badips-com.server-exploit-list'),('example.com','general access to circl-lu.misp'),('example.com','general access to dns-bh.malwaredomainscom'),('example.com','general access to greensnow-co.list-txt'),('example.com','general access to packetmail-net.list'),('example.com','general access to packetmail-net.others-list'),('example.com','general access to packetmail-net.ratware-list'),('example.com','general access to spam404-com.scam-list'),('example.com','general access to zoneh.rss');
/*!40000 ALTER TABLE `org_search_subsource_link` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `org_threats_ex_subsource_group_link`
--

DROP TABLE IF EXISTS `org_threats_ex_subsource_group_link`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `org_threats_ex_subsource_group_link` (
  `org_id` varchar(32) NOT NULL,
  `subsource_group_label` varchar(255) NOT NULL,
  PRIMARY KEY (`org_id`,`subsource_group_label`),
  KEY `subsource_group_label` (`subsource_group_label`),
  CONSTRAINT `org_threats_ex_subsource_group_link_ibfk_1` FOREIGN KEY (`org_id`) REFERENCES `org` (`org_id`),
  CONSTRAINT `org_threats_ex_subsource_group_link_ibfk_2` FOREIGN KEY (`subsource_group_label`) REFERENCES `subsource_group` (`label`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `org_threats_ex_subsource_group_link`
--

LOCK TABLES `org_threats_ex_subsource_group_link` WRITE;
/*!40000 ALTER TABLE `org_threats_ex_subsource_group_link` DISABLE KEYS */;
/*!40000 ALTER TABLE `org_threats_ex_subsource_group_link` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `org_threats_ex_subsource_link`
--

DROP TABLE IF EXISTS `org_threats_ex_subsource_link`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `org_threats_ex_subsource_link` (
  `org_id` varchar(32) NOT NULL,
  `subsource_label` varchar(255) NOT NULL,
  PRIMARY KEY (`org_id`,`subsource_label`),
  KEY `subsource_label` (`subsource_label`),
  CONSTRAINT `org_threats_ex_subsource_link_ibfk_1` FOREIGN KEY (`org_id`) REFERENCES `org` (`org_id`),
  CONSTRAINT `org_threats_ex_subsource_link_ibfk_2` FOREIGN KEY (`subsource_label`) REFERENCES `subsource` (`label`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `org_threats_ex_subsource_link`
--

LOCK TABLES `org_threats_ex_subsource_link` WRITE;
/*!40000 ALTER TABLE `org_threats_ex_subsource_link` DISABLE KEYS */;
/*!40000 ALTER TABLE `org_threats_ex_subsource_link` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `org_threats_subsource_group_link`
--

DROP TABLE IF EXISTS `org_threats_subsource_group_link`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `org_threats_subsource_group_link` (
  `org_id` varchar(32) NOT NULL,
  `subsource_group_label` varchar(255) NOT NULL,
  PRIMARY KEY (`org_id`,`subsource_group_label`),
  KEY `subsource_group_label` (`subsource_group_label`),
  CONSTRAINT `org_threats_subsource_group_link_ibfk_1` FOREIGN KEY (`org_id`) REFERENCES `org` (`org_id`),
  CONSTRAINT `org_threats_subsource_group_link_ibfk_2` FOREIGN KEY (`subsource_group_label`) REFERENCES `subsource_group` (`label`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `org_threats_subsource_group_link`
--

LOCK TABLES `org_threats_subsource_group_link` WRITE;
/*!40000 ALTER TABLE `org_threats_subsource_group_link` DISABLE KEYS */;
/*!40000 ALTER TABLE `org_threats_subsource_group_link` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `org_threats_subsource_link`
--

DROP TABLE IF EXISTS `org_threats_subsource_link`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `org_threats_subsource_link` (
  `org_id` varchar(32) NOT NULL,
  `subsource_label` varchar(255) NOT NULL,
  PRIMARY KEY (`org_id`,`subsource_label`),
  KEY `subsource_label` (`subsource_label`),
  CONSTRAINT `org_threats_subsource_link_ibfk_1` FOREIGN KEY (`org_id`) REFERENCES `org` (`org_id`),
  CONSTRAINT `org_threats_subsource_link_ibfk_2` FOREIGN KEY (`subsource_label`) REFERENCES `subsource` (`label`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `org_threats_subsource_link`
--

LOCK TABLES `org_threats_subsource_link` WRITE;
/*!40000 ALTER TABLE `org_threats_subsource_link` DISABLE KEYS */;
INSERT INTO `org_threats_subsource_link` VALUES ('example.com','general access to abuse-ch.feodotracker'),('example.com','general access to abuse-ch.palevo-doms'),('example.com','general access to abuse-ch.palevo-ips'),('example.com','general access to abuse-ch.ransomware'),('example.com','general access to abuse-ch.spyeye-doms'),('example.com','general access to abuse-ch.spyeye-ips'),('example.com','general access to abuse-ch.ssl-blacklist'),('example.com','general access to abuse-ch.ssl-blacklist-dyre'),('example.com','general access to abuse-ch.zeus-doms'),('example.com','general access to abuse-ch.zeus-ips'),('example.com','general access to abuse-ch.zeustracker'),('example.com','general access to badips-com.server-exploit-list'),('example.com','general access to circl-lu.misp'),('example.com','general access to dns-bh.malwaredomainscom'),('example.com','general access to greensnow-co.list-txt'),('example.com','general access to packetmail-net.list'),('example.com','general access to packetmail-net.others-list'),('example.com','general access to packetmail-net.ratware-list'),('example.com','general access to spam404-com.scam-list'),('example.com','general access to zoneh.rss');
/*!40000 ALTER TABLE `org_threats_subsource_link` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `org_url_link`
--

DROP TABLE IF EXISTS `org_url_link`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `org_url_link` (
  `org_id` varchar(32) NOT NULL,
  `url_id` int(11) NOT NULL,
  PRIMARY KEY (`org_id`,`url_id`),
  KEY `url_id` (`url_id`),
  CONSTRAINT `org_url_link_ibfk_1` FOREIGN KEY (`org_id`) REFERENCES `org` (`org_id`),
  CONSTRAINT `org_url_link_ibfk_2` FOREIGN KEY (`url_id`) REFERENCES `inside_filter_url` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `org_url_link`
--

LOCK TABLES `org_url_link` WRITE;
/*!40000 ALTER TABLE `org_url_link` DISABLE KEYS */;
/*!40000 ALTER TABLE `org_url_link` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `request_case`
--

DROP TABLE IF EXISTS `request_case`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `request_case` (
  `request_case_id` varchar(28) NOT NULL,
  `csr` blob DEFAULT NULL,
  `sender_login` varchar(255) DEFAULT NULL,
  `status` varchar(16) DEFAULT NULL,
  `status_changed_on` datetime DEFAULT NULL,
  PRIMARY KEY (`request_case_id`),
  KEY `sender_login` (`sender_login`),
  CONSTRAINT `request_case_ibfk_1` FOREIGN KEY (`sender_login`) REFERENCES `user` (`login`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `request_case`
--

LOCK TABLES `request_case` WRITE;
/*!40000 ALTER TABLE `request_case` DISABLE KEYS */;
/*!40000 ALTER TABLE `request_case` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `source`
--

DROP TABLE IF EXISTS `source`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `source` (
  `source_id` varchar(32) NOT NULL,
  `anonymized_source_id` varchar(32) DEFAULT NULL,
  `dip_anonymization_enabled` tinyint(1) DEFAULT NULL,
  `comment` text DEFAULT NULL,
  PRIMARY KEY (`source_id`),
  CONSTRAINT `CONSTRAINT_1` CHECK (`dip_anonymization_enabled` in (0,1))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `source`
--

LOCK TABLES `source` WRITE;
/*!40000 ALTER TABLE `source` DISABLE KEYS */;
INSERT INTO `source` VALUES ('abuse-ch.feodotracker','hidden.aae31a45c4450de8',1,NULL),('abuse-ch.palevo-doms','hidden.a787624c785b1444',1,NULL),('abuse-ch.palevo-ips','hidden.5f94be44b3acaa53',1,NULL),('abuse-ch.ransomware','hidden.87a18e4bd66f3095',1,NULL),('abuse-ch.spyeye-doms','hidden.8d9cbf4103d14e58',1,NULL),('abuse-ch.spyeye-ips','hidden.f4b8a8fcd5251d3f',1,NULL),('abuse-ch.ssl-blacklist','hidden.b4c2645aa582b37e',1,NULL),('abuse-ch.ssl-blacklist-dyre','hidden.9b74496da16b6ede',1,NULL),('abuse-ch.zeus-doms','hidden.5e52b565cf90c261',1,NULL),('abuse-ch.zeus-ips','hidden.aab98c94b1b21834',1,NULL),('abuse-ch.zeustracker','hidden.3d1168e27eac2a5e',1,NULL),('badips-com.server-exploit-list','hidden.4fa228fefcfd412c',1,NULL),('circl-lu.misp','hidden.905239bd414dc5f7',1,NULL),('dns-bh.malwaredomainscom','hidden.cf5ecd69f7e7f740',1,NULL),('greensnow-co.list-txt','hidden.48b1c3a9f21972b1',1,NULL),('packetmail-net.list','hidden.0abbbb1e8efcd999',1,NULL),('packetmail-net.others-list','hidden.8b54e1fe148f728c',1,NULL),('packetmail-net.ratware-list','hidden.d01878f648571c30',1,NULL),('spam404-com.scam-list','hidden.3fd955150f7977c1',1,NULL),('zoneh.rss','hidden.63bc33bc23a94287',1,NULL);
/*!40000 ALTER TABLE `source` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `subsource`
--

DROP TABLE IF EXISTS `subsource`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `subsource` (
  `label` varchar(255) NOT NULL,
  `comment` text DEFAULT NULL,
  `source_id` varchar(255) DEFAULT NULL,
  PRIMARY KEY (`label`),
  KEY `source_id` (`source_id`),
  CONSTRAINT `subsource_ibfk_1` FOREIGN KEY (`source_id`) REFERENCES `source` (`source_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `subsource`
--

LOCK TABLES `subsource` WRITE;
/*!40000 ALTER TABLE `subsource` DISABLE KEYS */;
INSERT INTO `subsource` VALUES ('general access to abuse-ch.feodotracker',NULL,'abuse-ch.feodotracker'),('general access to abuse-ch.palevo-doms',NULL,'abuse-ch.palevo-doms'),('general access to abuse-ch.palevo-ips',NULL,'abuse-ch.palevo-ips'),('general access to abuse-ch.ransomware',NULL,'abuse-ch.ransomware'),('general access to abuse-ch.spyeye-doms',NULL,'abuse-ch.spyeye-doms'),('general access to abuse-ch.spyeye-ips',NULL,'abuse-ch.spyeye-ips'),('general access to abuse-ch.ssl-blacklist',NULL,'abuse-ch.ssl-blacklist'),('general access to abuse-ch.ssl-blacklist-dyre',NULL,'abuse-ch.ssl-blacklist-dyre'),('general access to abuse-ch.zeus-doms',NULL,'abuse-ch.zeus-doms'),('general access to abuse-ch.zeus-ips',NULL,'abuse-ch.zeus-ips'),('general access to abuse-ch.zeustracker',NULL,'abuse-ch.zeustracker'),('general access to badips-com.server-exploit-list',NULL,'badips-com.server-exploit-list'),('general access to circl-lu.misp',NULL,'circl-lu.misp'),('general access to dns-bh.malwaredomainscom',NULL,'dns-bh.malwaredomainscom'),('general access to greensnow-co.list-txt',NULL,'greensnow-co.list-txt'),('general access to packetmail-net.list',NULL,'packetmail-net.list'),('general access to packetmail-net.others-list',NULL,'packetmail-net.others-list'),('general access to packetmail-net.ratware-list',NULL,'packetmail-net.ratware-list'),('general access to spam404-com.scam-list',NULL,'spam404-com.scam-list'),('general access to zoneh.rss',NULL,'zoneh.rss');
/*!40000 ALTER TABLE `subsource` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `subsource_exclusion_criteria_link`
--

DROP TABLE IF EXISTS `subsource_exclusion_criteria_link`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `subsource_exclusion_criteria_link` (
  `subsource_label` varchar(255) NOT NULL,
  `criteria_container_label` varchar(100) NOT NULL,
  PRIMARY KEY (`subsource_label`,`criteria_container_label`),
  KEY `criteria_container_label` (`criteria_container_label`),
  CONSTRAINT `subsource_exclusion_criteria_link_ibfk_1` FOREIGN KEY (`subsource_label`) REFERENCES `subsource` (`label`),
  CONSTRAINT `subsource_exclusion_criteria_link_ibfk_2` FOREIGN KEY (`criteria_container_label`) REFERENCES `criteria_container` (`label`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `subsource_exclusion_criteria_link`
--

LOCK TABLES `subsource_exclusion_criteria_link` WRITE;
/*!40000 ALTER TABLE `subsource_exclusion_criteria_link` DISABLE KEYS */;
/*!40000 ALTER TABLE `subsource_exclusion_criteria_link` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `subsource_group`
--

DROP TABLE IF EXISTS `subsource_group`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `subsource_group` (
  `label` varchar(255) NOT NULL,
  `comment` text DEFAULT NULL,
  PRIMARY KEY (`label`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `subsource_group`
--

LOCK TABLES `subsource_group` WRITE;
/*!40000 ALTER TABLE `subsource_group` DISABLE KEYS */;
/*!40000 ALTER TABLE `subsource_group` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `subsource_group_link`
--

DROP TABLE IF EXISTS `subsource_group_link`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `subsource_group_link` (
  `subsource_label` varchar(255) NOT NULL,
  `subsource_group_label` varchar(255) NOT NULL,
  PRIMARY KEY (`subsource_label`,`subsource_group_label`),
  KEY `subsource_group_label` (`subsource_group_label`),
  CONSTRAINT `subsource_group_link_ibfk_1` FOREIGN KEY (`subsource_label`) REFERENCES `subsource` (`label`),
  CONSTRAINT `subsource_group_link_ibfk_2` FOREIGN KEY (`subsource_group_label`) REFERENCES `subsource_group` (`label`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `subsource_group_link`
--

LOCK TABLES `subsource_group_link` WRITE;
/*!40000 ALTER TABLE `subsource_group_link` DISABLE KEYS */;
/*!40000 ALTER TABLE `subsource_group_link` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `subsource_inclusion_criteria_link`
--

DROP TABLE IF EXISTS `subsource_inclusion_criteria_link`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `subsource_inclusion_criteria_link` (
  `subsource_label` varchar(255) NOT NULL,
  `criteria_container_label` varchar(100) NOT NULL,
  PRIMARY KEY (`subsource_label`,`criteria_container_label`),
  KEY `criteria_container_label` (`criteria_container_label`),
  CONSTRAINT `subsource_inclusion_criteria_link_ibfk_1` FOREIGN KEY (`subsource_label`) REFERENCES `subsource` (`label`),
  CONSTRAINT `subsource_inclusion_criteria_link_ibfk_2` FOREIGN KEY (`criteria_container_label`) REFERENCES `criteria_container` (`label`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `subsource_inclusion_criteria_link`
--

LOCK TABLES `subsource_inclusion_criteria_link` WRITE;
/*!40000 ALTER TABLE `subsource_inclusion_criteria_link` DISABLE KEYS */;
/*!40000 ALTER TABLE `subsource_inclusion_criteria_link` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `system_group`
--

DROP TABLE IF EXISTS `system_group`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `system_group` (
  `name` varchar(100) NOT NULL,
  PRIMARY KEY (`name`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `system_group`
--

LOCK TABLES `system_group` WRITE;
/*!40000 ALTER TABLE `system_group` DISABLE KEYS */;
/*!40000 ALTER TABLE `system_group` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `user`
--

DROP TABLE IF EXISTS `user`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `user` (
  `login` varchar(255) NOT NULL,
  `password` varchar(60) DEFAULT NULL,
  `org_id` varchar(100) DEFAULT NULL,
  PRIMARY KEY (`login`),
  KEY `org_id` (`org_id`),
  CONSTRAINT `user_ibfk_1` FOREIGN KEY (`org_id`) REFERENCES `org` (`org_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `user`
--

LOCK TABLES `user` WRITE;
/*!40000 ALTER TABLE `user` DISABLE KEYS */;
INSERT INTO `user` VALUES ('login@example.com','$2b$12$JZILBev5p6ja1PSWAoUcX.kvfbUpkXCegP1SEEyhPUklZ2q49yVAe','example.com');
/*!40000 ALTER TABLE `user` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `user_system_group_link`
--

DROP TABLE IF EXISTS `user_system_group_link`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `user_system_group_link` (
  `user_login` varchar(255) NOT NULL,
  `system_group_name` varchar(100) NOT NULL,
  PRIMARY KEY (`user_login`,`system_group_name`),
  KEY `system_group_name` (`system_group_name`),
  CONSTRAINT `user_system_group_link_ibfk_1` FOREIGN KEY (`user_login`) REFERENCES `user` (`login`),
  CONSTRAINT `user_system_group_link_ibfk_2` FOREIGN KEY (`system_group_name`) REFERENCES `system_group` (`name`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `user_system_group_link`
--

LOCK TABLES `user_system_group_link` WRITE;
/*!40000 ALTER TABLE `user_system_group_link` DISABLE KEYS */;
/*!40000 ALTER TABLE `user_system_group_link` ENABLE KEYS */;
UNLOCK TABLES;
/*!40103 SET TIME_ZONE=@OLD_TIME_ZONE */;

/*!40101 SET SQL_MODE=@OLD_SQL_MODE */;
/*!40014 SET FOREIGN_KEY_CHECKS=@OLD_FOREIGN_KEY_CHECKS */;
/*!40014 SET UNIQUE_CHECKS=@OLD_UNIQUE_CHECKS */;
/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
/*!40111 SET SQL_NOTES=@OLD_SQL_NOTES */;

-- Dump completed on 2018-06-27 11:29:41
