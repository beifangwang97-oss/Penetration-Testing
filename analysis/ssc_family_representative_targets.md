# SSC Family Representative Targets

- Scope: 98 parent techniques that have sub-techniques
- Purpose: provide a first-pass representative target list for compressed SSC generation
- Basis:
  - question quota from [ssc_family_question_quota.md](/c:/Users/王王鑫/Desktop/Penetration%20Testing/demo/analysis/ssc_family_question_quota.md)
  - selection logic from [ssc_family_selection_strategy.md](/c:/Users/王王鑫/Desktop/Penetration%20Testing/demo/analysis/ssc_family_selection_strategy.md)
- Notes:
  - this is a first-pass candidate list
  - larger, higher-impact families were manually adjusted
  - smaller families follow the same diversity-first selection rule

| Parent Technique ID | Parent Technique Name | Quota | Recommended Representative Targets |
| --- | --- | ---: | --- |
| T1001 | Data Obfuscation | 2 | T1001.003 Protocol or Service Impersonation<br>T1001.001 Junk Data |
| T1003 | OS Credential Dumping | 3 | T1003.002 Security Account Manager<br>T1003.005 Cached Domain Credentials<br>T1003.006 DCSync |
| T1011 | Exfiltration Over Other Network Medium | 1 | T1011.001 Exfiltration Over Bluetooth |
| T1016 | System Network Configuration Discovery | 1 | T1016.001 Internet Connection Discovery |
| T1020 | Automated Exfiltration | 1 | T1020.001 Traffic Duplication |
| T1021 | Remote Services | 3 | T1021.005 VNC<br>T1021.006 Windows Remote Management<br>T1021.001 Remote Desktop Protocol |
| T1027 | Obfuscated Files or Information | 5 | T1027.002 Software Packing<br>T1027.006 HTML Smuggling<br>T1027.010 Command Obfuscation<br>T1027.007 Dynamic API Resolution<br>T1027.013 Encrypted/Encoded File |
| T1036 | Masquerading | 4 | T1036.002 Right-to-Left Override<br>T1036.003 Rename Legitimate Utilities<br>T1036.004 Masquerade Task or Service<br>T1036.007 Double File Extension |
| T1037 | Boot or Logon Initialization Scripts | 2 | T1037.002 Login Hook<br>T1037.001 Logon Script (Windows) |
| T1048 | Exfiltration Over Alternative Protocol | 2 | T1048.001 Exfiltration Over Symmetric Encrypted Non-C2 Protocol<br>T1048.003 Exfiltration Over Unencrypted Non-C2 Protocol |
| T1052 | Exfiltration Over Physical Medium | 1 | T1052.001 Exfiltration over USB |
| T1053 | Scheduled Task/Job | 3 | T1053.005 Scheduled Task<br>T1053.003 Cron<br>T1053.004 Launchd |
| T1055 | Process Injection | 4 | T1055.001 Dynamic-link Library Injection<br>T1055.003 Thread Execution Hijacking<br>T1055.012 Process Hollowing<br>T1055.013 Process Doppelganging |
| T1056 | Input Capture | 2 | T1056.001 Keylogging<br>T1056.004 Credential API Hooking |
| T1059 | Command and Scripting Interpreter | 4 | T1059.001 PowerShell<br>T1059.003 Windows Command Shell<br>T1059.004 Unix Shell<br>T1059.009 Cloud API |
| T1069 | Permission Groups Discovery | 2 | T1069.003 Cloud Groups<br>T1069.001 Local Groups |
| T1070 | Indicator Removal | 4 | T1070.001 Clear Windows Event Logs<br>T1070.003 Clear Command History<br>T1070.004 File Deletion<br>T1070.006 Timestomp |
| T1071 | Application Layer Protocol | 2 | T1071.004 DNS<br>T1071.001 Web Protocols |
| T1074 | Data Staged | 1 | T1074.001 Local Data Staging |
| T1078 | Valid Accounts | 2 | T1078.001 Default Accounts<br>T1078.003 Local Accounts |
| T1087 | Account Discovery | 2 | T1087.002 Domain Account<br>T1087.004 Cloud Account |
| T1090 | Proxy | 2 | T1090.002 External Proxy<br>T1090.001 Internal Proxy |
| T1098 | Account Manipulation | 3 | T1098.001 Additional Cloud Credentials<br>T1098.002 Additional Email Delegate Permissions<br>T1098.004 SSH Authorized Keys |
| T1102 | Web Service | 2 | T1102.003 One-Way Communication<br>T1102.001 Dead Drop Resolver |
| T1110 | Brute Force | 2 | T1110.001 Password Guessing<br>T1110.004 Credential Stuffing |
| T1114 | Email Collection | 2 | T1114.001 Local Email Collection<br>T1114.002 Remote Email Collection |
| T1127 | Trusted Developer Utilities Proxy Execution | 2 | T1127.003 JamPlus<br>T1127.002 ClickOnce |
| T1132 | Data Encoding | 1 | T1132.001 Standard Encoding |
| T1134 | Access Token Manipulation | 2 | T1134.002 Create Process with Token<br>T1134.005 SID-History Injection |
| T1136 | Create Account | 2 | T1136.001 Local Account<br>T1136.003 Cloud Account |
| T1137 | Office Application Startup | 3 | T1137.001 Office Template Macros<br>T1137.003 Outlook Forms<br>T1137.005 Outlook Rules |
| T1176 | Software Extensions | 1 | T1176.001 Browser Extensions |
| T1195 | Supply Chain Compromise | 2 | T1195.001 Compromise Software Dependencies and Development Tools<br>T1195.002 Compromise Software Supply Chain |
| T1204 | User Execution | 2 | T1204.002 Malicious File<br>T1204.001 Malicious Link |
| T1205 | Traffic Signaling | 1 | T1205.002 Socket Filters |
| T1213 | Data from Information Repositories | 3 | T1213.003 Code Repositories<br>T1213.005 Messaging Applications<br>T1213.006 Databases |
| T1216 | System Script Proxy Execution | 1 | T1216.001 PubPrn |
| T1218 | System Binary Proxy Execution | 4 | T1218.004 InstallUtil<br>T1218.005 Mshta<br>T1218.010 Regsvr32<br>T1218.011 Rundll32 |
| T1219 | Remote Access Tools | 2 | T1219.001 IDE Tunneling<br>T1219.002 Remote Desktop Software |
| T1222 | File and Directory Permissions Modification | 1 | T1222.002 Linux and Mac File and Directory Permissions Modification |
| T1480 | Execution Guardrails | 1 | T1480.002 Mutual Exclusion |
| T1484 | Domain or Tenant Policy Modification | 1 | T1484.002 Trust Modification |
| T1485 | Data Destruction | 1 | T1485.001 Lifecycle-Triggered Deletion |
| T1491 | Defacement | 1 | T1491.002 External Defacement |
| T1496 | Resource Hijacking | 2 | T1496.003 SMS Pumping<br>T1496.001 Compute Hijacking |
| T1497 | Virtualization/Sandbox Evasion | 2 | T1497.001 System Checks<br>T1497.002 User Activity Based Checks |
| T1498 | Network Denial of Service | 1 | T1498.001 Direct Network Flood |
| T1499 | Endpoint Denial of Service | 2 | T1499.001 OS Exhaustion Flood<br>T1499.002 Service Exhaustion Flood |
| T1505 | Server Software Component | 3 | T1505.001 SQL Stored Procedures<br>T1505.003 Web Shell<br>T1505.004 IIS Components |
| T1518 | Software Discovery | 1 | T1518.002 Backup Software Discovery |
| T1542 | Pre-OS Boot | 2 | T1542.001 System Firmware<br>T1542.004 ROMMONkit |
| T1543 | Create or Modify System Process | 2 | T1543.003 Windows Service<br>T1543.002 Systemd Service |
| T1546 | Event Triggered Execution | 5 | T1546.003 Windows Management Instrumentation Event Subscription<br>T1546.004 Unix Shell Configuration Modification<br>T1546.012 Image File Execution Options Injection<br>T1546.013 PowerShell Profile<br>T1546.015 Component Object Model Hijacking |
| T1547 | Boot or Logon Autostart Execution | 5 | T1547.001 Registry Run Keys / Startup Folder<br>T1547.004 Winlogon Helper DLL<br>T1547.011 Plist Modification<br>T1547.013 XDG Autostart Entries<br>T1547.015 Login Items |
| T1548 | Abuse Elevation Control Mechanism | 3 | T1548.002 Bypass User Account Control<br>T1548.001 Setuid and Setgid<br>T1548.006 TCC Manipulation |
| T1550 | Use Alternate Authentication Material | 2 | T1550.003 Pass the Ticket<br>T1550.001 Application Access Token |
| T1552 | Unsecured Credentials | 3 | T1552.001 Credentials In Files<br>T1552.003 Shell History<br>T1552.004 Private Keys |
| T1553 | Subvert Trust Controls | 3 | T1553.001 Gatekeeper Bypass<br>T1553.003 SIP and Trust Provider Hijacking<br>T1553.004 Install Root Certificate |
| T1555 | Credentials from Password Stores | 3 | T1555.001 Keychain<br>T1555.003 Credentials from Web Browsers<br>T1555.004 Windows Credential Manager |
| T1556 | Modify Authentication Process | 3 | T1556.002 Password Filter DLL<br>T1556.003 Pluggable Authentication Modules<br>T1556.006 Multi-Factor Authentication |
| T1557 | Adversary-in-the-Middle | 2 | T1557.004 Evil Twin<br>T1557.002 ARP Cache Poisoning |
| T1558 | Steal or Forge Kerberos Tickets | 2 | T1558.001 Golden Ticket<br>T1558.003 Kerberoasting |
| T1559 | Inter-Process Communication | 2 | T1559.002 Dynamic Data Exchange<br>T1559.003 XPC Services |
| T1560 | Archive Collected Data | 2 | T1560.001 Archive via Utility<br>T1560.002 Archive via Library |
| T1561 | Disk Wipe | 1 | T1561.002 Disk Structure Wipe |
| T1562 | Impair Defenses | 4 | T1562.001 Disable or Modify Tools<br>T1562.002 Disable Windows Event Logging<br>T1562.004 Disable or Modify System Firewall<br>T1562.008 Disable or Modify Cloud Logs |
| T1563 | Remote Service Session Hijacking | 1 | T1563.001 SSH Hijacking |
| T1564 | Hide Artifacts | 4 | T1564.001 Hidden Files and Directories<br>T1564.003 Hidden Window<br>T1564.004 NTFS File Attributes<br>T1564.010 Process Argument Spoofing |
| T1565 | Data Manipulation | 2 | T1565.001 Stored Data Manipulation<br>T1565.002 Transmitted Data Manipulation |
| T1566 | Phishing | 2 | T1566.002 Spearphishing Link<br>T1566.003 Spearphishing via Service |
| T1567 | Exfiltration Over Web Service | 2 | T1567.004 Exfiltration Over Webhook<br>T1567.002 Exfiltration to Cloud Storage |
| T1568 | Dynamic Resolution | 2 | T1568.002 Domain Generation Algorithms<br>T1568.003 DNS Calculation |
| T1569 | System Services | 2 | T1569.003 Systemctl<br>T1569.002 Service Execution |
| T1573 | Encrypted Channel | 1 | T1573.001 Symmetric Cryptography |
| T1574 | Hijack Execution Flow | 4 | T1574.002 DLL Side-Loading<br>T1574.008 Path Interception by Search Order Hijacking<br>T1574.010 Services File Permissions Weakness<br>T1574.013 KernelCallbackTable |
| T1578 | Modify Cloud Compute Infrastructure | 2 | T1578.004 Revert Cloud Instance<br>T1578.001 Create Snapshot |
| T1583 | Acquire Infrastructure | 3 | T1583.001 Domains<br>T1583.004 Server<br>T1583.005 Botnet |
| T1584 | Compromise Infrastructure | 3 | T1584.001 Domains<br>T1584.004 Server<br>T1584.005 Botnet |
| T1585 | Establish Accounts | 2 | T1585.002 Email Accounts<br>T1585.001 Social Media Accounts |
| T1586 | Compromise Accounts | 2 | T1586.001 Social Media Accounts<br>T1586.002 Email Accounts |
| T1587 | Develop Capabilities | 2 | T1587.003 Digital Certificates<br>T1587.004 Exploits |
| T1588 | Obtain Capabilities | 3 | T1588.001 Malware<br>T1588.002 Tool<br>T1588.005 Exploits |
| T1589 | Gather Victim Identity Information | 2 | T1589.002 Email Addresses<br>T1589.001 Credentials |
| T1590 | Gather Victim Network Information | 3 | T1590.001 Domain Properties<br>T1590.002 DNS<br>T1590.005 IP Addresses |
| T1591 | Gather Victim Org Information | 2 | T1591.003 Identify Business Tempo<br>T1591.001 Determine Physical Locations |
| T1592 | Gather Victim Host Information | 2 | T1592.001 Hardware<br>T1592.002 Software |
| T1593 | Search Open Websites/Domains | 2 | T1593.002 Search Engines<br>T1593.001 Social Media |
| T1595 | Active Scanning | 2 | T1595.002 Vulnerability Scanning<br>T1595.001 Scanning IP Blocks |
| T1596 | Search Open Technical Databases | 2 | T1596.003 Digital Certificates<br>T1596.005 Scan Databases |
| T1597 | Search Closed Sources | 1 | T1597.002 Purchase Technical Data |
| T1598 | Phishing for Information | 2 | T1598.003 Spearphishing Link<br>T1598.001 Spearphishing Service |
| T1599 | Network Boundary Bridging | 1 | T1599.001 Network Address Translation Traversal |
| T1600 | Weaken Encryption | 1 | T1600.001 Reduce Key Space |
| T1601 | Modify System Image | 1 | T1601.001 Patch System Image |
| T1602 | Data from Configuration Repository | 1 | T1602.002 Network Device Configuration Dump |
| T1606 | Forge Web Credentials | 1 | T1606.002 SAML Tokens |
| T1608 | Stage Capabilities | 3 | T1608.001 Upload Malware<br>T1608.002 Upload Tool<br>T1608.005 Link Target |
| T1614 | System Location Discovery | 1 | T1614.001 System Language Discovery |
