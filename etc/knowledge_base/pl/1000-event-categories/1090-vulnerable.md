# Vulnerable
Kategoria `vulnerable` to zdarzenia wskazujące na hosty z podatnymi usługami, posiadające błędną konfigurację albo usługi wystawione publicznie do sieci Internet zwiększając powierzchnię ataku.


### 21nails;smtp
Podatny serwer Exim posiadający podatności 21nails.

### 403-bypass-using-headers
Potencjalne ominięcie "403 Forbidden" przy użyciu nagłówków (np. X-Forwarded-For, X-Original-URL)

### 403-bypass-using-nullbyte
Potencjalne ominięcie "403 Forbidden" przy użyciu nullbyte.

### adb
Wystawiony publicznie serwer Android ADB (Android Debug Bridge).

### afp
Wystawiany publicznie serwer Apple AFP (Apple Filing Protocol).

### amqp
Wystawione publicznie urządzenie z otwartą usługą AMQP (Advanced Message Queueing Protocol).

### bacnet
System przemysłowy ICS/OT z wystawioną publicznie usługą BACnet (Building Automation and Control Networks).

### bad_certificate_names
Serwer zwraca certyfikat dla innej domeny.

### badsecret;basic-auth
Publiczna strona internetowa wykorzystująca "basic-auth" i posiadająca słabe hasło.

### badwpad
Host z systemem Windows posiadający błędną konfigurację DNS który próbuje pobrać konfigurację proxy z serwera "wpad.pl". Więcej informacji na https://cert.pl/posts/2019/06/przejecie-domen-pl-zwiazanych-z-atakiem-badwpad.

### basic-auth;http
Publiczna strona internetowa wykorzystująca "basic-auth" dostępna przez HTTP (transport hasła jest bez szyfrowania).

### certificate_authority_invalid
Certyfikat podpisany przez niezaufane CA.

### cisco-smart-install
Host z publicznie dostępną usługą Cisco Smart Install. Poprzez tą usługę potencjalnie jest możliwa modyfikacja konfiguracji przełącznika Cisco.

### close_domain_expiration_date
Data nazwy domenowej bliska wygaśnięciu.

### closed_wordpress_plugin
Plugin w systemie WordPress, którego wsparcie zostało zakończone.

### codesys
Wystawiony publicznie system przemysłowy ICS/OT producenta Codesys.

### cwmp
Host z wystawioną publicznie usługą CWMP (CPE WAN Management Protocol). Tego typu usługi są często obiektem ataków przez botnety IoT.

### dangling_dns_record
Wykryto ustawienia DNS stwarzające ryzyko przejęcia domeny.

### directory_index
Wykryto konfigurację serwera pozwalającą na listowanie plików.

### dnp3
Wystawiony publicznie system przemysłowy ICS/OT wykorzystujący protokół DNP3 (Distributed Network Protocol version 3).

### ds-store-file
Wykryto plik .DS_Store, zawierający informację o nazwach plików w katalogu, w tym potencjalnie np. kopii zapasowych lub innych plików, które nie powinny być publicznie dostępne.

### elasticsearch
Wystawiony publicznie serwer ElasticSearch.

### eol;exchange
Serwer Microsoft Exchange, którego wsparcie uległo zakończeniu i przestał otrzymywać poprawki bezpieczeństwa.

### error-logs
Wykryto publicznie dostępny dziennik zdarzeń serwera HTTP.

### ethernet_ip
Wystawiony publicznie system przemysłowy ICS/OT wykorzystujący protokół Ethernet-over-IP.

### expired_ssl_certificate
Przeterminowany certyfikat serwera.

### exposed_archive
Pod adresem znajdują się archiwa plików, które mogą zawierać wrażliwe dane.

### exposed_configuration_file
Pod adresem znajdują się pliki konfiguracyjne lub ich kopie zapasowe.

### exposed_file_with_listing
Pod adresem mogą znajdować się informacje o nazwach niektórych plików lub folderów, które są obecne na serwerze.

### exposed_log_file
Pod adresem znajdują się pliki logów.

### exposed_phpinfo
Pod adresem znajdują się pliki udostępniające informacje o konfiguracji serwera.

### exposed_php_source
Pod adresem znajdują się pliki zawierające kod źródłowy PHP, który nie jest interpretowany przez serwer.

### exposed_php_var_dump
Pod adresem w kodzie strony znajduje się zrzut danych PHP, np. generowany przez funkcję var_dump.

### exposed_sql_dump
Pod adresem znajdują się zrzuty bazy danych.

### exposed_version_control_folder
Pod adresem znajdują się publicznie dostępne dane systemu kontroli wersji wraz z informacjami umożliwiającymi logowanie.

### fox
Wystawiony publicznie system przemysłowy ICS/OT wykorzystujący protokół Fox.

### freepbx-compromised;http
Host z wystawioną publicznie usługą freePBX, która została przejęta. Wykorzystywany protokół to HTTP.

### freepbx-compromised;ssl
Host z wystawioną publicznie usługą freePBX, która została przejęta. Wykorzystywany protokół to SSL.

### ftp, clear text pass
Serwer FTP, z którym nie udaje się wynegocjować połączenia z szyfrowaniem.

### ge-srtp
Wystawiony publicznie system przemysłowy ICS/OT wykorzystujący protokół SRTP (Service Request Transfer Protocol).

### git-config-file
Katalog repozytorium kodu .git publicznie dostępny do pobrania przez HTTP.

### github-takeover
Wykryto domenę kierującą do serwisu Github Pages, ale domena docelowa jest wolna. Atakujący może zarejestrować taką domenę w serwisie Github Pages, aby serwować tam swoje treści. Jeśli domena nie jest używana, rekomendujemy jej usunięcie.

### go-pprof-debug
Wykryto stronę z informacjami diagnostycznymi systemu go pprof.

### iccp
Wystawiony publicznie system przemysłowy ICS/OT wykorzystujący protokół ICCP (Inter-Control Center Communications Protocol).

### iec-60870-5-104
Wystawiony publicznie system przemysłowy ICS/OT wykorzystujący protokół IEC 60870-5-104.

### insecure_wordpress
Pod adresem znajdują się wersja systemu WordPress, która nie są już wspierana i jest oznaczona jako niebezpieczna na liście wersji.

### ipmi
Host z wystawioną publicznie usługą IPMI (Intelligent Platform Management Interface). Protokół ten wykorzystywany jest do zdalnego zarządzania w systemach typu "Lights Out management suites"

### ipp
Host z publicznie dostępną usługą IPP (Internet Printing Protocol).

### isakmp
Host z publicznie dostępną usługą wykorzystującą protokół ISAKMP, n.p. IPsec.

### joomla_outdated_extension
Pod adresem znajdują się strony z nieaktualnymi rozszerzeniami Joomla.

### ldap
Publicznie dostępny serwer LDAP.

### megarac
Publicznie dostępna usługa MegaRAC wykorzystywana do zdalnego dostępu typu "Lights Out management suite".

### melsecq
Wystawiony publicznie system przemysłowy ICS/OT MELSEC-Q.

### memcached
Wystawiona publicznie usługa Memcached z dostępem do bazy `"klucz":"wartość"`.

### misconfigured_email dmarc
Domena nie ma poprawnie skonfigurowanych mechanizmów weryfikacji nadawcy wiadomości e-mail. Wykryto problem z mechanizmem DMARC. Więcej informacji o tym jak skonfigurować poprawnie pocztę na https://cert.pl/posts/2021/10/mechanizmy-weryfikacji-nadawcy-wiadomosci.

### misconfigured_email spf
Domena nie ma poprawnie skonfigurowanych mechanizmów weryfikacji nadawcy wiadomości e-mail. Wykryto problem z mechanizmem SPF. Więcej informacji o tym jak skonfigurować poprawnie pocztę na https://cert.pl/posts/2021/10/mechanizmy-weryfikacji-nadawcy-wiadomosci

### mixed-active-content
Część zawartości strony internetowej jest ładowana poprzez HTTP zamiast HTTPS.

### modbus
Wystawiony publicznie system przemysłowy ICS/OT wykorzystujący protokół MODBUS.

### modbus-closed
Wystawiony publicznie system przemysłowy ICS/OT wykorzystujący protokół MODBUS. Dostęp ograniczony w warstwie aplikacji.

### mongodb
Publicznie dostępny serwer bazy danych MongoDB.

### mqtt
Host z wystawioną publicznie usługą MQTT głównie z otartym dostępem. Hosty wystawione na porcie 1883 nie mają włączonego szyfrowania.

### nat-pnp
Host z działającą publicznie usługą NAT-PMP (NAT Port Mapping Protocol).

### no_https_redirect
Brak przekierowania na szyfrowaną komunikację HTTPS.

### nuclei_exposed_panel
Wystawiony publicznie panel logowania.

### old_joomla
Pod następującym adresem znajdują się nieaktualne wersje systemu Joomla.

### old_wordpress
Pod następującymi adresem znajdują się nieaktualne wersje systemu WordPress.

### omron-fins
Wystawiony publicznie system przemysłowy ICS/OT producenta Omron wykorzystujący protokół FINS.

### opc-ua-binary
Wystawiony publicznie system przemysłowy ICS/OT wykorzystujący protokół OPC UA. 

### open_port_database
Pod adresem znajduje się publicznie dostępny serwer baz danych.

### open_port_remote_desktop
Pod adresem znajduje się publicznie dostępna usługa zdalnego dostępu np. RDP albo VNC. 

### open_port_smb
Pod adresem znajduje się publicznie dostępny serwer SMB.

### open-redirect
Wykryto podatność Open Redirect, umożliwiającą atakującemu spreparowanie linku w Państwa domenie, który przekierowuje do dowolnej innej strony, w tym np. zawierającej szkodliwe oprogramowanie.

### open-redirect-bypass
Wykryto podatność Open Redirect, umożliwiającą atakującemu spreparowanie linku w Państwa domenie, który przekierowuje do dowolnej innej strony, w tym np. zawierającej szkodliwe oprogramowanie.

### open-redirect-simplified
Wykryto podatność Open Redirect, umożliwiającą atakującemu spreparowanie linku w Państwa domenie, który przekierowuje do dowolnej innej strony, w tym np. zawierającej szkodliwe oprogramowanie.

### paloalto;ssl;threat-prevention-sigs-not-detected,vpn
Brama VPN producenta Paloalto wykazująca brak włączonej usługi Threat Prevention.

### pcworx
Wystawiony publicznie system przemysłowy ICS/OT wykorzystujący oprogramowanie PC WORX i protokół tego producenta do zdalnego programowania.

### phpinfo-files
Pod adresem znajdują się pliki udostępniające informacje o konfiguracji serwera.

### prometheus-metrics
Wykryto stronę "Prometheus metrics".

### radmin
Host z systemem Windows posiadający publicznie dostępną usługę do zdalnego zarządzania Radmin.

### rdp
Host z publicznie dostępną usługą RDP (Remote Desktop Protocol).

### redis
Wystawiony publicznie serwer usługi redis.

### reflected-xss
Wykryto podatność Reflected Cross-Site Scripting. Atakujący może spreparować link, który - gdy kliknięty przez administratora - wykona dowolną operację na stronie z jego uprawnieniami (np. modyfikację treści).

### removed_domain_existing_vhost:
Wykryto brak rekordu domeny, przy użyciu odpowiednich nagłówków HTTP strona nadal odpowiada zawartością.

### roundcube-log-disclosure
Wykryto dziennik zdarzeń systemu Roundcube. Może on zawierać takie dane jak np. informacje o nadawcach i odbiorcach e-maili czy informacje o konfiguracji systemu.

### rsync
Wystawiony publicznie serwer usługi rsync.

### rtsp-detect
Wykryto publicznie dostępny serwer RTSP.

### s7
Wystawiony publicznie system przemysłowy ICS/OT wykorzystujący protokół S7.

### script_unregistered_domain
Strona ładuje skrypty z domen, które nie są zarejestrowane.

### smb
Host z publicznie dostępną usługą SMB.

### snmpv1-community-detect-string
Wykryto konfigurację protokołu SNMPv1 umożliwiającą nieuwierzytelnionym użytkownikom pobranie informacji na temat systemu takich jak konfiguracja sieci, działające procesy czy informacje na temat urządzeń.

### sqli-error-based
Wykryto podatność SQL Injection na podstawie komunikatu o błędzie. Ta podatność może umożliwiać pobranie dowolnej informacji z bazy danych.

### sql_injection:core
Adres URL zawiera podatność typu SQL Injection.

### ssl-freak
Host z SSL/TLS obsługujący szyfrowanie podatne na atak typu MITM.

### ssl-poodle
Host pozwalający na obsługę metody szyfrowania SSL v3.0, która jest podatna na atak POODLE.

### telnet
Wystawiony publicznie serwer z niezapewniającą szyfrowania usługą Telnet.

### tftp
Wystawiony publicznie serwer z niezapewniającą szyfrowania usługą tftp.

### unitronics
Wystawiony publicznie system przemysłowy ICS/OT wykorzystujący protokół producenta Unitronics.

### vnc
Wystawiony publicznie serwer VNC.

### wordpress_outdated_plugin_theme
Pod adresem znajdują się strony z nieaktualnymi wtyczkami lub szablonami WordPress.

### zone_transfer_possible
Włączony mechanizm transferu strefy w domenie.
