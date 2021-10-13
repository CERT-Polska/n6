-- MySQL dump 10.13  Distrib 5.7.31, for Linux (x86_64)
--
-- Host: 127.0.0.1    Database: auth_db
-- ------------------------------------------------------
-- Server version	5.5.5-10.3.23-MariaDB-1:10.3.23+maria~bionic-log

/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!40101 SET NAMES utf8mb4 */;
/*!40103 SET @OLD_TIME_ZONE=@@TIME_ZONE */;
/*!40103 SET TIME_ZONE='+00:00' */;
/*!40014 SET @OLD_UNIQUE_CHECKS=@@UNIQUE_CHECKS, UNIQUE_CHECKS=0 */;
/*!40014 SET @OLD_FOREIGN_KEY_CHECKS=@@FOREIGN_KEY_CHECKS, FOREIGN_KEY_CHECKS=0 */;
/*!40101 SET @OLD_SQL_MODE=@@SQL_MODE, SQL_MODE='NO_AUTO_VALUE_ON_ZERO' */;
/*!40111 SET @OLD_SQL_NOTES=@@SQL_NOTES, SQL_NOTES=0 */;

--
-- Dumping data for table `ca_cert`
--

LOCK TABLES `ca_cert` WRITE;
/*!40000 ALTER TABLE `ca_cert` DISABLE KEYS */;
INSERT INTO `ca_cert` VALUES ('n6-client-ca','root','client','-----BEGIN CERTIFICATE-----\r\nMIIFLTCCAxWgAwIBAgIBATANBgkqhkiG9w0BAQ0FADAQMQ4wDAYDVQQDEwVuNi1j\r\nYTAeFw0xODEyMDMxNDMxMTJaFw0yOTExMTUxNDMxMTJaMEUxFTATBgNVBAMMDG42\r\nLWNsaWVudC1jYTEUMBIGA1UECgwLZXhhbXBsZS5jb20xFjAUBgNVBAsMDUludGVy\r\nbmFsIFVuaXQwggIiMA0GCSqGSIb3DQEBAQUAA4ICDwAwggIKAoICAQCi9ynFQP8w\r\nHkqbz3eP08E4+uhMVn9UmnEIBxk4JiPIwEfF4K8cqS/adPxn593JN7ZSWp2gmUDN\r\nhVnIkTLieYUE4l5ml3UUPAzzL67qVVbzYrpAxBl2R9jGLMqsKBu4N81qFZSNNgae\r\ngABmcU27zlm886Y3NWViXhw+xmchT7pfnzC6IvO1ZWWjLWf5TB1rRWdcWpvUzoR0\r\nAP9kvAlYgn7Bpikhr8TAcJO2U0SZ3wIZfpfQlCJuAZFvC1ZWUN+6sASHofLXFJ9G\r\nMNSckRqeF9l2I5o4rSNXl8SzEnPfRIEOZeAEH4PqiZndIos+AG5sOxeDFGJl37bl\r\nVhWhVlWBC/IsVN7pe+LrdaB517PDVeEG13h03lwKQuFY6S71MFNSx4I1k79Mv/vk\r\nwPpTX+bQvIIQufqPs+DEAT6IzF0XHgXwNKYL2JGe1mNrDvtaJVWRdpd1QLtaiFyz\r\nwhSvvE2W8H5aAf8Q7YVML6ZQoQdyUxgHC0MCzKNrLbUw7d00kbeBQzaeAIIrY/ja\r\nR+Kxgbn8gQeH1g50Gfwv8/WxRpKQvA6jmus27U2IEaUvVocc6yO0e+0amznyfVtM\r\nJvhp/l0uX55AD1m8/0AHGqGgGY2upCHOVfDSHPG56cwkLZcu9/AZbuMGdlPMombJ\r\n+hni4LQk4Ilek/tfccRVzcBLcFv37vg7YwIDAQABo10wWzAMBgNVHRMEBTADAQH/\r\nMAsGA1UdDwQEAwIB7jAdBgNVHQ4EFgQUHovFB01wmo4MiDn1gECB8nBUqb8wHwYD\r\nVR0jBBgwFoAUebOs9j7Tgd6NUHESErVk3xJhpAMwDQYJKoZIhvcNAQENBQADggIB\r\nAHP//EaPbNd9woRCkPy47sxuiASnfeuoTpcfmpBLsVty8VoM+qOE6EGzLwybwMkT\r\npppCbFwANqWjW1pU9UmX42fjr8viNmENpiHX68OC4qdhljNYL/4oESUKRYzmWUmB\r\n9tGXo9BfG7/uXAL6uCDvHulDkre4SnyhpZUzE1x8L+wkLregxqvVVSv9JsZLDtCP\r\n2ERcMWkL/E+JY16lglfD8TIUh/ANckLiRwesV5pb2XVr29EX+/jrvIRupkYGfWAq\r\nycKYxYxuZAmzDIkZzNL3zkcuSqXR+0BpT0zjTHchsYa4/GPjp3DH8CelKCWmj+JF\r\nSUsRMfHs+GELa6pLSC/tpDOLsvyeLIzIt7RxFVdcPHX7e4/Pz8XDNKXmbk0kHQ25\r\n639ZT6DBnDrsGb0EbBVnCj3VnDY19DDm+WpCVAqlrVORZEY3zkU+4FNgmjc6oeg6\r\nIbiP6t/MgbubhxOvhHdhs9hAI04/XCf83JmzTUlkRjqlLNOP675ds6o+9XcdclLR\r\nCKbzZdIBSWiQ9oxFlpOGtjozU5Xank4oAlq3N5dMX8yKcjfOKVJIZpWoxijrBSI7\r\nZWeBC10ageoP9qg/8YaljCZLurwZYPNYqvWbbaOj5q0Lx9dEbifwXXd48NvtOuCz\r\nUhCju03MWeeSvL5mPIXVfkCVWZOTlEHhbrNt7t63KUln\r\n-----END CERTIFICATE-----\r\n','[ ca ]\r\ndefault_ca                      = clientCA\r\n\r\n[ clientCA ]\r\ndir                             = .\r\ncertificate                     = $dir/ca-cert-n6-client-ca.pem\r\ndatabase                        = $dir/index.txt\r\nnew_certs_dir                   = $dir/tmp-certs\r\nprivate_key                     = $dir/ca-key-n6-client-ca.pem\r\nserial                          = $dir/next-serial.txt\r\n\r\ndefault_crl_days                = 365\r\ndefault_days                    = 365\r\ndefault_md                      = sha256\r\n\r\nunique_subject                  = no\r\npolicy                          = clientCA_policy\r\nx509_extensions                 = certificate_extensions\r\n\r\n[ clientCA_policy ]\r\ncommonName                      = supplied\r\norganizationName                = supplied\r\n\r\n[ certificate_extensions ]\r\nbasicConstraints                = CA:false\r\nkeyUsage                        = digitalSignature\r\nsubjectKeyIdentifier            = hash\r\nauthorityKeyIdentifier          = keyid,issuer\r\nnsCertType                      = client\r\n'),('n6-service-ca','root','service','-----BEGIN CERTIFICATE-----\r\nMIIFLjCCAxagAwIBAgIBAjANBgkqhkiG9w0BAQ0FADAQMQ4wDAYDVQQDEwVuNi1j\r\nYTAeFw0xODEyMDMxNDMxMDNaFw0yOTExMTUxNDMxMDNaMEYxFjAUBgNVBAMMDW42\r\nLXNlcnZpY2UtY2ExFDASBgNVBAoMC2V4YW1wbGUuY29tMRYwFAYDVQQLDA1JbnRl\r\ncm5hbCBVbml0MIICIjANBgkqhkiG9w0BAQEFAAOCAg8AMIICCgKCAgEA3BL7KyLt\r\n2nfKPnHvIbyLDy8sE8RCOJKc5Go0iqC6UcqH3fDqY8CI1omSkkEjeyBV/qb+lB7X\r\np+fAUyHwmQSR88xSZjUHXt4t780a2YnwGLVIC+S+x9GDKn+VZbj18MibaYozdAOf\r\nMncXX9jdgQF71do6NB17kdS9FgHKqzKrkzCg7ZoRUY/fvfcs9TuvTAvhjYdeX8wX\r\nv9T8vmyC9zYzaTsB2+gOJ3vEL4FmKcC2ZzZSgMk6BJrDnUjLPcq+WH0gdde+5gyo\r\nKMjdnRJMEhRIzKynCUFKWTfuxjNAOVvtqH8ZL8lQFYajQL7RcQh1iCbv7PKn4Ekd\r\nm5/dgzudVdwV4Su/hgo00EokH/Ee2ENFsv4tL5r3jsN1uvq1fPeeCJUKMDZ7HDrH\r\njcmPQqfSUJuzdkoFlzEjUL/NDfFcsI4SM6IfwkDz8gPShxt5QmdtSgDmZPQBF3Zr\r\nRSp2RKAfyhllh4/iDGjQeDgEn975GySm2uPOY/q55pxpYJAN9xMfCyETTcMKs7cg\r\nOx608vlQvls+XIzAZofTdbXpfDtXALZy2yjA4WiZqIoTxvDdn7N0GUXVXeqABDww\r\n70dyGQzH4+HBlvMHXv9Ev60HtHD9p2Ee/iS1ixwyn1CUgpi1xeTlwOXlTet7C0DP\r\n6CTvGAEuZ7PReB028KQzmemkEs+AILgXfZUCAwEAAaNdMFswDAYDVR0TBAUwAwEB\r\n/zALBgNVHQ8EBAMCAe4wHQYDVR0OBBYEFNUb3kPvGFlv7Qmibj1yHjxTbtf2MB8G\r\nA1UdIwQYMBaAFHmzrPY+04HejVBxEhK1ZN8SYaQDMA0GCSqGSIb3DQEBDQUAA4IC\r\nAQCVnYsTwE7BR172OM7RHWjjleC+5tZMROhcNU3z/LwVzdi19qmwvz8ocR/wC7y9\r\ncRCSyB+NaI4hTd2k67hnU40uL602WXYNaXx1Axhk8DiyxDQ6dDwegyDrvnjV3Sg/\r\nhUWFNZ7AM+GNRNZRZgkQOyNXqOfcmSkuakh0cnkEeMDPNz9YZAWaz//WjLkjSt8k\r\nIpOeva6BcZtdtpBcYR3YJzaxfpC+brrtvHHJ3c3nwmz0l7QO6yVgZz/JDx0Jj+C0\r\nOq2GDgh/yp7Eq/yneHdpPKbn4qQbubCQ0YwAyiX4KMYGy2ZyqzVthOat7Z/DWJnh\r\nYKw6Ov4nS00isuR/UGXm9El5Dtw+IytHXx6DKc7okLIlujyO+JjEzKsaSnCV9Xdr\r\nID8XQZ5jQt5tROnqjRcdQqalMvEy4Xfw+6YN15S9RxnrdDdLobNDpiJmVXdd9LYo\r\nZ8Chv6vrsHZbLULnBEsSyhzqMS5BhADg9GunAH3UewNBGrv2SvQXoIpqAAN/2yqS\r\nQfiKaoa0Ys6hhiFvsxr8ZQ0eFvVxpIu7S9m1PEbwdgZua9yW0Rt6w1fPcuLraAK1\r\nkJbqK3nNrCX8Tg0aEUVvObApviGq3NtXS64F4IfNlkfv8KQPTikDA2N5pp+TmEa+\r\nuIy0zutUOhlIFtkAs/UU+EGdeKZn+Lh+sD5FfClXSHsMXQ==\r\n-----END CERTIFICATE-----\r\n','[ ca ]\r\ndefault_ca                      = serviceCA\r\n\r\n[ serviceCA ]\r\ndir                             = .\r\ncertificate                     = $dir/ca-cert-n6-service-ca.pem\r\ndatabase                        = $dir/index.txt\r\nnew_certs_dir                   = $dir/tmp-certs\r\nprivate_key                     = $dir/ca-key-n6-service-ca.pem\r\nserial                          = $dir/next-serial.txt\r\n\r\ndefault_crl_days                = 365\r\ndefault_days                    = 365\r\ndefault_md                      = sha256\r\n\r\nunique_subject                  = no\r\npolicy                          = inner_serviceCA_policy\r\nx509_extensions                 = certificate_extensions\r\n\r\n[ inner_serviceCA_policy ]\r\ncommonName                      = supplied\r\norganizationName                = supplied\r\norganizationalUnitName          = supplied\r\n\r\n[ server_component_serviceCA_policy ]\r\ncommonName                      = supplied\r\norganizationName                = match\r\norganizationalUnitName          = match\r\n\r\n[ certificate_extensions ]\r\nbasicConstraints                = CA:false\r\nkeyUsage                        = nonRepudiation, digitalSignature, keyEncipherment, keyAgreement\r\nsubjectKeyIdentifier            = hash\r\nauthorityKeyIdentifier          = keyid,issuer\r\n'),('root',NULL,NULL,'-----BEGIN CERTIFICATE-----\r\nMIIFADCCAuigAwIBAgIJAJq2DJ2Lr+sXMA0GCSqGSIb3DQEBCwUAMBAxDjAMBgNV\r\nBAMTBW42LWNhMB4XDTE4MTIwMzE0MzAzNloXDTQ2MDQyMDE0MzAzNlowEDEOMAwG\r\nA1UEAxMFbjYtY2EwggIiMA0GCSqGSIb3DQEBAQUAA4ICDwAwggIKAoICAQCdFljt\r\nhGCCHbtFRRvZCgfdw2Pz49fma3zdFl1/Sle/d8rRtFZotZj3cmayFYNblB1DAHao\r\n3of3hJWWFnT40PgT9xfPNBCrEd2P6TvcFspq/mNKdJkk9s/YpahOyrx7Sn2Av+gV\r\npswNFOf9hwkpTT7ZyK68xKm4bjzfybMMwDpBF9abBvXlqvQMYSUu3L8VYjvJ3jyC\r\nyEcUke8qCXvPqdFV5ZVCMRtlSVvTsZh5zXDC76LckNVpAWpAxReNLKsqqmRcCkZj\r\nWc/Ogy/5DCCmbyRSwUAHGhJ7qrZrkk1sCsWe+8SfY58mUDdXDxHh/yFM4HjCVkg3\r\nP+ELtfBsnqUnsf4sTX5olCzNwsN7iA7uoU2RZ15h6gT3sHfTj1QWJsyodoeFEn1l\r\nmVcCc2qBhwlsMTnaGMsYuLNjVvE/uyEMUm6B1Nx1HWmAO7xTiljB+2+NiymI36l6\r\n4KBZP/eM+YLd8dhOnWLZV64/bqZN29v9ZfPmSJ+NfiybeL3g9NrclFBgkRVsK51u\r\nankKcagVCfcoMnls635nz89vgsBNscuzGjO6OOqrg4+OaYL/qs23IZJH3qG9Vqw8\r\n4dD7+U7Io00vjSdpvLyEAI6JbWS98l+PDFzuP+muB+wkGV6U4XHWE4p2HTVLBIZx\r\ndQS9MQxxzACU4/Pxhca+77m7qgTrsqtz+fFSKwIDAQABo10wWzAMBgNVHRMEBTAD\r\nAQH/MAsGA1UdDwQEAwIB7jAdBgNVHQ4EFgQUebOs9j7Tgd6NUHESErVk3xJhpAMw\r\nHwYDVR0jBBgwFoAUebOs9j7Tgd6NUHESErVk3xJhpAMwDQYJKoZIhvcNAQELBQAD\r\nggIBAC6+rjHhXh3p4bJZeRp41hqwY7WYRMi/25bPdUEWUOq8EFPbB5LBrYRyk+nD\r\n2qu50ZsosDmDnsyHcvvJqaFwo9vLEgWWiWuDEEnXGp1gQMBVs9McnuY/XgTZUSrg\r\nIhXZeavkHv2xmLj/fL4EGvfJzG/2CNm6CizWfJ30IqqAkFesU7SR0kWTvVdX0X+f\r\nFZBNNn5TZVQtdP3XuK1XGOCbmmEKAO7xp5ff5sjqQJZJpo5ugyF58Yx4yArn7ypn\r\nGDhKJN4dJvDcXwBkHCJJ3c8QV1AATqWfJqgD0iAzBtqsp3j3RPt65fu4S8oqCbJB\r\nKwyDaw2nHBrICLBHuSwNdmMLiz10zEQf6RpXoXEuCutCBKaOG4kgCPqvOHKhchnV\r\nh9RV+rOaN/v9TFMUgDzHPUyeUdgHL8t6JFrXm9j8C1OmXiUPF0emxgx/+VF7MWF0\r\nQ1ELBJ0g4z6Upi9RTvelZVH5UNRgO1bWGkF1nlx605pmaviZwVCMjKFU3y2Jzome\r\nhgPjSxc5fYqwoG4vBUETZl8QhN69ZdOttvDQodk5+rhnepco0J45tN/SqIiFwjnB\r\n4dyAbH91Ot3pVXEkpOXcKXKMGiN+W4q2+dqrzaqn0IDgeaqeOIZp7e+MaR53gXKt\r\nVSvzohkC0nBnbZihdyma/7oSQ3dQn+fPElN6PmnbrE++NXOE\r\n-----END CERTIFICATE-----\r\n','none');
/*!40000 ALTER TABLE `ca_cert` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Dumping data for table `cert`
--

LOCK TABLES `cert` WRITE;
/*!40000 ALTER TABLE `cert` DISABLE KEYS */;
INSERT INTO `cert` VALUES ('n6-service-ca','00000000000000000018','ads-adm@example.com',NULL,'-----BEGIN CERTIFICATE-----\r\nMIIFYjCCA0qgAwIBAgIBGDANBgkqhkiG9w0BAQsFADBGMRYwFAYDVQQDDA1uNi1z\r\nZXJ2aWNlLWNhMRQwEgYDVQQKDAtleGFtcGxlLmNvbTEWMBQGA1UECwwNSW50ZXJu\r\nYWwgVW5pdDAeFw0yMDA4MjAwOTIxNDBaFw0yODExMDYwOTIxNDBaMEcxHDAaBgNV\r\nBAMME2Fkcy1hZG1AZXhhbXBsZS5jb20xFDASBgNVBAoMC2V4YW1wbGUuY29tMREw\r\nDwYDVQQLDAhuNmFkbWluczCCAiIwDQYJKoZIhvcNAQEBBQADggIPADCCAgoCggIB\r\nAPXamUc/Ng9nmFFPcgAD82PD8aRbZRQrS93oAU+13KCG6BDVxqQgwrlE/JPu7JBm\r\no2unBsEVEP+ir+IyG5IbrPI/5vIaFXvZjcy91cUNe2yAPoAXLr6rjMMXX4ntuRI0\r\ni5p16OVp+nbMUSi0O0CgJj/OSK+d7Jx6J2ReWGe6CNd0eCVizlJ3isfmxWPh9bbu\r\neyriwJ0R1FueTZCU36ahzc4iFX0APOhDaz+pIpXZW33t9YEhPle2VG7hT/eEbpri\r\nledVZoFQvuD36gK0opMnGvYLkzX9id1Jcf6/rKAjfBUenqC2U2iB11j0UrFEz1+I\r\nv4hvoDKk8WmpYg6LgHSPD725p/1Ho7f9rXfhHZEBHwAmDSygrnyqgFMBQ7xKskTI\r\nmNO3PXaQ28MCmiB1HObq2mLWgLiSweEBsWdX4PNw3eVp0V4pl5+0QEI0+53FJUC/\r\n9M9dbKZ+eb+1AabeK/bZrzSe2U6qPvcI9HWpqm/JBCwk8GJgQIpIkDYYCe/4ZkiM\r\nFeS+lw9aNKZaUKDZbUZ9fNCTHz03QFP9oq1JjFyIkxd25D4eesaX8bsKUpTe2thO\r\nAUp61qhEK4Q1lAnTcOPMP9Q8KieproHXBzl55+nUr4hkJsC5DgenTCevr9RzYr0V\r\n6CHdCAGdB74rxWhxdgMCC8u1mAegBoo+yh0xhLmVwq+ZAgMBAAGjWjBYMAkGA1Ud\r\nEwQCMAAwCwYDVR0PBAQDAgPoMB0GA1UdDgQWBBS3bdFSkKXVknY7HpeAa2ulYkyp\r\ngDAfBgNVHSMEGDAWgBTVG95D7xhZb+0Jom49ch48U27X9jANBgkqhkiG9w0BAQsF\r\nAAOCAgEAB9pzXgrR43Ms14XnCMSmHjye4iTmR2XCgBMUjcmNH7sIyxgdxCkM02WB\r\n5ePCz0LpDmv2VihvhxTxq7C6hxjj7CDCn0kOL56B+aP8awwy/hq9hVrDa+puXtqe\r\ngNu5OakAeDB28rQVVFCqCDauI7ZjgwnpYyV01tz5LUVWvciXOVxmRCBfvkZB34T7\r\nHpNcyK22iQiEY0ECPPNQAD9jAW99RsnWQDCQZmvvfd1FdGxcexmndooEuDF4E+1W\r\nKca+nrDTRu/D3HA7aPVhjy3K9DW9wqY2yqHjY+3LTMnAcXMhYNiAWcUeZCIqaoaE\r\nUmEtDODDEEQ7f7oINzHcn53f2uZYoUDiCfifJhfn32P0Nyv3VqEoBtqn75xfIaKn\r\nhv70t//iMAqMFpNJkhp2+sqf9U0e31QBH33/kMsjaaGNqL7Y4Gtk2fTPwB9QXrhA\r\nd5q7hSs89ZVS13cWVPf27QRAZnkfJkYW5c7YqKmlriCIYZn253Wx9lxExdUjws+g\r\np9AVKWCCn+Chvd6fihCJbfZwx/BJGs5JyeunVg5yC9z/qmVweuDZ2pyXXvAr6Y8U\r\n/Dy8zH/fVt0dptL9c4Q4kqd9rkd4dkqDI9HBVNOQLBKcf+MQgBG+MOQxTeGmQTbl\r\nKNygRECgT8V6DfWvrgIhZ2WgDev1aXw3s5iSeV+NRFl7lH1akas=\r\n-----END CERTIFICATE-----\r\n','-----BEGIN CERTIFICATE REQUEST-----\r\nMIIEjDCCAnQCAQAwRzEcMBoGA1UEAwwTYWRzLWFkbUBleGFtcGxlLmNvbTEUMBIG\r\nA1UECgwLZXhhbXBsZS5jb20xETAPBgNVBAsMCG42YWRtaW5zMIICIjANBgkqhkiG\r\n9w0BAQEFAAOCAg8AMIICCgKCAgEA9dqZRz82D2eYUU9yAAPzY8PxpFtlFCtL3egB\r\nT7XcoIboENXGpCDCuUT8k+7skGaja6cGwRUQ/6Kv4jIbkhus8j/m8hoVe9mNzL3V\r\nxQ17bIA+gBcuvquMwxdfie25EjSLmnXo5Wn6dsxRKLQ7QKAmP85Ir53snHonZF5Y\r\nZ7oI13R4JWLOUneKx+bFY+H1tu57KuLAnRHUW55NkJTfpqHNziIVfQA86ENrP6ki\r\nldlbfe31gSE+V7ZUbuFP94RumuKV51VmgVC+4PfqArSikyca9guTNf2J3Ulx/r+s\r\noCN8FR6eoLZTaIHXWPRSsUTPX4i/iG+gMqTxaaliDouAdI8Pvbmn/Uejt/2td+Ed\r\nkQEfACYNLKCufKqAUwFDvEqyRMiY07c9dpDbwwKaIHUc5uraYtaAuJLB4QGxZ1fg\r\n83Dd5WnRXimXn7RAQjT7ncUlQL/0z11spn55v7UBpt4r9tmvNJ7ZTqo+9wj0damq\r\nb8kELCTwYmBAikiQNhgJ7/hmSIwV5L6XD1o0plpQoNltRn180JMfPTdAU/2irUmM\r\nXIiTF3bkPh56xpfxuwpSlN7a2E4BSnrWqEQrhDWUCdNw48w/1DwqJ6mugdcHOXnn\r\n6dSviGQmwLkOB6dMJ6+v1HNivRXoId0IAZ0HvivFaHF2AwILy7WYB6AGij7KHTGE\r\nuZXCr5kCAwEAAaAAMA0GCSqGSIb3DQEBCwUAA4ICAQChrTBsrpNGWjMjwH1j+Y89\r\n2pIVF5hoihy8mC57lZjgFDyuO8SYY24H+YRa5c98f9sQfW+8m3KjggcsZG6+CXrT\r\nAIHzB0ZyWOUFmtBaZOWB4hMSWks1rL4RRfcHDN/BH+fM4swcPDgCLoOVGSbpgr9d\r\nwVME4ixtcT3P9vUBctqEvXk9ISOB4+X/em6cSubj1h7mU+g6zB7lC3iiVRsuE6LE\r\ndC9b9uSmxlfQaCsHKhYwfKTsYag1vyCpmeefJDgUf50LYupv/7ClM8170TI2wldE\r\n3i8bvayjaaIX5hueMW/ZoUQxQ8nhhHcKMjvGmYejFFzQwg9V0/VwbQNoIdxk4UKI\r\nZv/DDMczwWP9juspnOCBR8/zb9D0IKD0DNu0/CLIWlkqx7bERCPTnPQIaMVHTw/x\r\nwiq11EPG/Q6l1vOf2W95UghOem9zjxv8y4SRZ+zn/+XjcchYyl8YGHp6UJMX9lFi\r\nP+0Me/hdY9zz837lrbYagZlAeoXGjDvnbguI7EGh+c2V9Bypi1b5jmJDTus6ughT\r\nrPbAB3+8Ubcb2VicKh7Agerjt2UcBoYNhkXjH1+4tmMTDiGu4xpeCQmOrBVWEiax\r\nrN+wWInG9snQoUuvjMrlu7DN0EC60bf9NJvtwu91FIKFJ7EG4c+QrGqi5mTcd3Im\r\ndoyTan4cAYDnDRE3VAsgVw==\r\n-----END CERTIFICATE REQUEST-----\r\n','2020-08-20 08:48:00','2028-11-06 12:46:00',0,0,'2020-08-25 08:48:00',NULL,NULL,NULL,NULL,NULL,NULL,NULL);
/*!40000 ALTER TABLE `cert` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Dumping data for table `system_group`
--

LOCK TABLES `system_group` WRITE;
/*!40000 ALTER TABLE `system_group` DISABLE KEYS */;
INSERT INTO `system_group` VALUES ('admins'),('clients');
/*!40000 ALTER TABLE `system_group` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Dumping data for table `user`
--

LOCK TABLES `user` WRITE;
/*!40000 ALTER TABLE `user` DISABLE KEYS */;
INSERT INTO `user` (`id`, `login`, `password`, `org_id`) VALUES (2,'ads-adm@example.com',NULL,'example.com');
/*!40000 ALTER TABLE `user` ENABLE KEYS */;
UNLOCK TABLES;
/*!40103 SET TIME_ZONE=@OLD_TIME_ZONE */;

--
-- Dumping data for table `user_system_group_link`
--

LOCK TABLES `user_system_group_link` WRITE;
/*!40000 ALTER TABLE `user_system_group_link` DISABLE KEYS */;
INSERT INTO `user_system_group_link` VALUES (2,'admins');
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

-- Dump completed on 2020-08-25 10:45:57
