# Amplifier
Category `amplifier` refers to events with public hosts, have misconfigured services and can be used to perform DDoS Amplification Attacks. 


### ard
Host with publicly available ARD service (Apple Remote Desktop). Can be used to perform DDoS amplification attacks and share information about system.

### chargen
Host with publicly available Chargen service. Can be used to perform DDoS amplification attacks.

### coap
Host with publicly available CoAP service (Constrained Application Protocol). Can be used to perform DDoS amplification attacks and share information about system including authentication data.

### dvr-dhcpdiscover
Host with publicly available DVR DHCPDiscover service. Can be used to perform DDoS amplification attacks.

### mdns
Host with publicly available mDNS service. Can be used to perform DDoS amplification attacks.

### mssql
Host with publicly available MS-SQL Server Resolution Service. Can be used to perform DDoS amplification attacks and share information about other clients in the network.

### netbios
Host with publicly available NetBIOS service. Can be used to perform DDoS amplification attacks.

### ntp
Host with publicly available NTP service. (Network Time Protocol). Host answers to command "monitor": `"ntpdc -n -c monlist [ip]"` or answer for "version": `"ntpq -c rv [ip]"`.

### portmapper
Host with publicly available Portmapper service.Can be used to perform DDoS amplification attacks and share information about system. Host answers to command `"rpcinfo -T udp -p [IP]"`.

### qotd
Host with publicly available Quote of the Day (QOTD) service. Can be used to perform DDoS amplification attacks.

### rdpeudp
Host with publicly available Microsoft RDPEUDP (RDP extension via UDP). Can be used to perform DDoS amplification attacks.

### resolver
Host with publicly available Domain Name Resolution service. Can be used to perform DDoS amplification attacks.

### snmp
Host with publicly available SNMPv2 service. Can be used to perform DDoS amplification attacks. Host answers to command `"snmpget -c public -v 2c [ip] 1.3.6.1.2.1.1.1.0"` or `"snmpget -c public -v 2c [ip] 1.3.6.1.2.1.1.5.0"`.

### ubiquiti
Host with publicly available Ubiquiti service. Can be used to perform DDoS amplification attacks.

### xdmcp
Host with publicly available X Display Manager service. Can be used to perform DDoS amplification attacks.
