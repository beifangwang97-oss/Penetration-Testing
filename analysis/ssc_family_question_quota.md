# SSC Family Question Quota

- Scope: 98 parent techniques that have sub-techniques
- Goal: reduce total SSC volume while keeping representative coverage
- Source: `demo/data/attack_data.json`

## Quota Rule

- 1-2 sub-techniques -> 1 question
- 3-5 sub-techniques -> 2 questions
- 6-9 sub-techniques -> 3 questions
- 10-14 sub-techniques -> 4 questions
- 15+ sub-techniques -> 5 questions

## Summary

- Parent technique families with sub-techniques: 98
- Questions allocated to these 98 families: 212
- Parent techniques without sub-techniques: 258
- Questions allocated to those 258 techniques: 258
- Estimated total SSC count after compression: 470

## Distribution

- 1 question(s): 26 families
- 2 question(s): 44 families
- 3 question(s): 17 families
- 4 question(s): 8 families
- 5 question(s): 3 families

## Family Quota Table

| Parent Technique ID | Parent Technique Name | Sub-technique Count | Recommended SSC Count |
| --- | --- | ---: | ---: |
| T1001 | Data Obfuscation | 3 | 2 |
| T1003 | OS Credential Dumping | 8 | 3 |
| T1011 | Exfiltration Over Other Network Medium | 1 | 1 |
| T1016 | System Network Configuration Discovery | 2 | 1 |
| T1020 | Automated Exfiltration | 1 | 1 |
| T1021 | Remote Services | 8 | 3 |
| T1027 | Obfuscated Files or Information | 17 | 5 |
| T1036 | Masquerading | 12 | 4 |
| T1037 | Boot or Logon Initialization Scripts | 5 | 2 |
| T1048 | Exfiltration Over Alternative Protocol | 3 | 2 |
| T1052 | Exfiltration Over Physical Medium | 1 | 1 |
| T1053 | Scheduled Task/Job | 7 | 3 |
| T1055 | Process Injection | 12 | 4 |
| T1056 | Input Capture | 4 | 2 |
| T1059 | Command and Scripting Interpreter | 13 | 4 |
| T1069 | Permission Groups Discovery | 3 | 2 |
| T1070 | Indicator Removal | 10 | 4 |
| T1071 | Application Layer Protocol | 5 | 2 |
| T1074 | Data Staged | 2 | 1 |
| T1078 | Valid Accounts | 4 | 2 |
| T1087 | Account Discovery | 4 | 2 |
| T1090 | Proxy | 4 | 2 |
| T1098 | Account Manipulation | 7 | 3 |
| T1102 | Web Service | 3 | 2 |
| T1110 | Brute Force | 4 | 2 |
| T1114 | Email Collection | 3 | 2 |
| T1127 | Trusted Developer Utilities Proxy Execution | 3 | 2 |
| T1132 | Data Encoding | 2 | 1 |
| T1134 | Access Token Manipulation | 5 | 2 |
| T1136 | Create Account | 3 | 2 |
| T1137 | Office Application Startup | 6 | 3 |
| T1176 | Software Extensions | 2 | 1 |
| T1195 | Supply Chain Compromise | 3 | 2 |
| T1204 | User Execution | 5 | 2 |
| T1205 | Traffic Signaling | 2 | 1 |
| T1213 | Data from Information Repositories | 6 | 3 |
| T1216 | System Script Proxy Execution | 2 | 1 |
| T1218 | System Binary Proxy Execution | 14 | 4 |
| T1219 | Remote Access Tools | 3 | 2 |
| T1222 | File and Directory Permissions Modification | 2 | 1 |
| T1480 | Execution Guardrails | 2 | 1 |
| T1484 | Domain or Tenant Policy Modification | 2 | 1 |
| T1485 | Data Destruction | 1 | 1 |
| T1491 | Defacement | 2 | 1 |
| T1496 | Resource Hijacking | 4 | 2 |
| T1497 | Virtualization/Sandbox Evasion | 3 | 2 |
| T1498 | Network Denial of Service | 2 | 1 |
| T1499 | Endpoint Denial of Service | 4 | 2 |
| T1505 | Server Software Component | 6 | 3 |
| T1518 | Software Discovery | 2 | 1 |
| T1542 | Pre-OS Boot | 5 | 2 |
| T1543 | Create or Modify System Process | 5 | 2 |
| T1546 | Event Triggered Execution | 18 | 5 |
| T1547 | Boot or Logon Autostart Execution | 15 | 5 |
| T1548 | Abuse Elevation Control Mechanism | 6 | 3 |
| T1550 | Use Alternate Authentication Material | 4 | 2 |
| T1552 | Unsecured Credentials | 8 | 3 |
| T1553 | Subvert Trust Controls | 6 | 3 |
| T1555 | Credentials from Password Stores | 6 | 3 |
| T1556 | Modify Authentication Process | 9 | 3 |
| T1557 | Adversary-in-the-Middle | 4 | 2 |
| T1558 | Steal or Forge Kerberos Tickets | 5 | 2 |
| T1559 | Inter-Process Communication | 3 | 2 |
| T1560 | Archive Collected Data | 3 | 2 |
| T1561 | Disk Wipe | 2 | 1 |
| T1562 | Impair Defenses | 12 | 4 |
| T1563 | Remote Service Session Hijacking | 2 | 1 |
| T1564 | Hide Artifacts | 14 | 4 |
| T1565 | Data Manipulation | 3 | 2 |
| T1566 | Phishing | 4 | 2 |
| T1567 | Exfiltration Over Web Service | 4 | 2 |
| T1568 | Dynamic Resolution | 3 | 2 |
| T1569 | System Services | 3 | 2 |
| T1573 | Encrypted Channel | 2 | 1 |
| T1574 | Hijack Execution Flow | 13 | 4 |
| T1578 | Modify Cloud Compute Infrastructure | 5 | 2 |
| T1583 | Acquire Infrastructure | 8 | 3 |
| T1584 | Compromise Infrastructure | 8 | 3 |
| T1585 | Establish Accounts | 3 | 2 |
| T1586 | Compromise Accounts | 3 | 2 |
| T1587 | Develop Capabilities | 4 | 2 |
| T1588 | Obtain Capabilities | 7 | 3 |
| T1589 | Gather Victim Identity Information | 3 | 2 |
| T1590 | Gather Victim Network Information | 6 | 3 |
| T1591 | Gather Victim Org Information | 4 | 2 |
| T1592 | Gather Victim Host Information | 4 | 2 |
| T1593 | Search Open Websites/Domains | 3 | 2 |
| T1595 | Active Scanning | 3 | 2 |
| T1596 | Search Open Technical Databases | 5 | 2 |
| T1597 | Search Closed Sources | 2 | 1 |
| T1598 | Phishing for Information | 4 | 2 |
| T1599 | Network Boundary Bridging | 1 | 1 |
| T1600 | Weaken Encryption | 2 | 1 |
| T1601 | Modify System Image | 2 | 1 |
| T1602 | Data from Configuration Repository | 2 | 1 |
| T1606 | Forge Web Credentials | 2 | 1 |
| T1608 | Stage Capabilities | 6 | 3 |
| T1614 | System Location Discovery | 1 | 1 |
