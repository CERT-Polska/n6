# Amplifier
Kategoria `amplifier` to zdarzenia wskazujące na publiczne hosty, które posiadają błędną konfigurację usług i mogą być wykorzystywane do ataków DDoS ze wzmocnieniem. 


### ard
Host z publicznie dostępną usługą ARD (Apple Remote Desktop). Może być wykorzystany do ataków DDoS ze wzmocnieniem jak również udostępniać informacje o systemie.

### chargen
Host z publicznie dostępną sługą CharGen. Może być wykorzystany do ataków DDoS ze wzmocnieniem.

### coap
Host z publicznie dostępną usługą CoAP (Constrained Application Protocol). Może być wykorzystany do ataków DDoS ze wzmocnieniem jak również potencjalnie udostępniać wrażliwe informacje o systemie, w tym dane uwierzytelniające.

### dvr-dhcpdiscover
Host z publicznie dostępną usługą DVR DHCPDiscover. Może być wykorzystany do ataków DDoS ze wzmocnieniem.

### mdns
Host z publicznie dostępną usługą mDNS. Może być wykorzystany do ataków DDoS ze wzmocnieniem.

### mssql
Host z publicznie dostępną usługą MS-SQL Server Resolution Service. Może być wykorzystany do ataków DDoS ze wzmocnieniem jak również udostępniać informacje innych klientach w sieci.

### netbios
Host z publicznie dostępną usługą NetBIOS. Może być wykorzystany do ataków DDoS ze wzmocnieniem.

### ntp
Host z publicznie dostępną usługą NTP (Network Time Protocol). Host odpowiada na polecenie "monitor": `"ntpdc -n -c monlist [ip]"` albo na polecenie "version": `"ntpq -c rv [ip]"`.

### portmapper
Host z publicznie dostępną usługą Portmapper. Może być wykorzystany do ataków DDoS ze wzmocnieniem jak również udostępniać inne informacje o systemie. Host odpowiada na polecenie `"rpcinfo -T udp -p [IP]"`.

### qotd
Host z publicznie dostępną sługą Quote of the Day (QOTD). Może być wykorzystany do ataków DDoS ze wzmocnieniem.

### rdpeudp
Host z publicznie dostępną sługą Microsoft RDPEUDP (Rozszerzenie RDP poprzez UDP). Może być wykorzystany do ataków DDoS ze wzmocnieniem.

### resolver
Host z publicznie dostępną sługą DNS do rozwiązywania domen. Może być wykorzystany do ataków DDoS ze wzmocnieniem.

### snmp
Host z publicznie dostępną usługą SNMPv2. Może być wykorzystany do ataków DDoS ze wzmocnieniem. Host odpowiada na komendę `"snmpget -c public -v 2c [ip] 1.3.6.1.2.1.1.1.0"` albo `"snmpget -c public -v 2c [ip] 1.3.6.1.2.1.1.5.0"`.

### ubiquiti
Host z publicznie dostępną sługą Ubiquiti Discovery. Może być wykorzystany do ataków DDoS ze wzmocnieniem.

### xdmcp
Host z publicznie dostępną sługą  X Display Manager. Może być wykorzystany do ataków DDoS ze wzmocnieniem.
