# Event-Driven Ansible for IBM Z

The **IBM EDA z/OS** collection provides rulebooks and playbooks for automating IBM Z operational scenarios through Event-Driven Ansible. This collection provides rulebooks that monitor zSecure alerts and trigger automated response playbooks for security events on z/OS.

## Description

The **IBM EDA z/OS** collection is part of the **Red Hat Ansible Validated Content for IBM Z®** offering that brings Event-Driven Ansible automation to IBM Z. This collection provides rulebooks and playbooks that users can customize for automating various IBM Z operational scenarios through event-driven workflows. The collection also includes a custom event filter that extracts key attributes from z/OS events (such as user IDs, alert codes, alert messages, and job names), eliminating the need for repetitive filtering in rulebooks and playbooks.

**The first release focuses on IBM Z Security**, enabling real-time monitoring of security events from zSecure and automating incident response workflows through rulebooks and response playbooks. The collection can be used to monitor RACF security alerts including group authority changes, password threshold breaches, unauthorized access attempts, and superuser logons.

Security teams can implement continuous compliance monitoring and automated response workflows, while system administrators can reduce mean time to response (MTTR) for security incidents. The collection integrates seamlessly with Kafka event streams, IBM z/OS systems, and email notification systems to provide end-to-end security automation.

## Requirements

Before you install the IBM EDA z/OS collection, ensure that you configure the Ansible Automation Platform controller, Event-Driven Ansible controller, and z/OS managed nodes with the following requirements:

### Ansible Automation Platform
- **Ansible Automation Platform** 2.5 or later with Event-Driven Ansible Controller
- **Decision Environment** with required collections installed
- **Job Templates** configured for response playbooks

### IBM Z System Requirements
- **z/OS** *[insert version number]*
- **IBM zSecure** installed and configured to publish alerts *[insert version number]*
- **Common Data Provider for Z** installed and configured to stream SYSLOG data to Apache Kafka

### Event Streaming
- **Apache Kafka** broker configured with SSL/TLS

### Additional Requirements
- **IBM Z Open Automation Utilities (ZOAU)** *[insert version number]*
- **IBM Open Enterprise SDK for Python** *[insert version number]*
- **SMTP server** for email notifications


### Collection Dependencies
- `ibm.ibm_zos_core` >= *[insert version number]*
- `ansible.utils` >= *[insert version number]*
- `ansible.eda` (included with AAP)
- `community.general` (for email notifications)

## Installation

Before using this collection, you need to install it with the Ansible Galaxy command-line tool:

```sh
ansible-galaxy collection install ibm.ibm_eda_zos
```

<br/>You can also include it in a requirements.yml file and install it with `ansible-galaxy collection install -r requirements.yml`, using the format:

```yaml
collections:
  - name: ibm.ibm_eda_zos
  - name: ibm.ibm_zos_core
    version: ">=1.13.1"
  - name: ansible.utils
    version: ">=6.0.0"
  - name: community.general
```

### Configuration Variables

The collection requires several configuration variables for Kafka connectivity, SMTP settings, and z/OS environment. These should be configured in your Rulebook Activation or Job Template extra variables:

```yaml
# Kafka Configuration for Rulebook Activation 
kafka_topic: "zsecure-alerts"
kafka_host: "kafka.example.com"
kafka_port: 9093
security_protocol: "SSL"
cafile: "/path/to/ca-cert.pem"

# Email Configuration for Job Templates
security_alert_recipients:
  - security-team@example.com
  - zos-admins@example.com
security_alert_sender: "eda-alerts@example.com"
smtp_server: "smtp.example.com"
smtp_server_port: 587

# z/OS Environment Variables for Host information
system_environment:
  _BPXK_AUTOCVT: "ON"
  ZOAU_HOME: "/usr/lpp/IBM/zoautil"
  PYTHONPATH: "/usr/lpp/IBM/zoautil/lib"
  LIBPATH: "/usr/lpp/IBM/zoautil/lib:/lib:/usr/lib:."
  PATH: "/usr/lpp/IBM/zoautil/bin:/bin:/usr/bin:."
  _CEE_RUNOPTS: "FILETAG(AUTOCVT,AUTOTAG) POSIX(ON)"
  _TAG_REDIR_ERR: "txt"
  _TAG_REDIR_IN: "txt"
  _TAG_REDIR_OUT: "txt"
  LANG: "C"
  PYTHONSTDINENCODING: "cp1047"
```

## Key Features

### Custom Event Filter

The collection includes a **security event filter** designed for Kafka event streams that automatically extracts valuable attributes from z/OS security events. This eliminates the need for custom regex filtering in every rulebook and playbook, significantly simplifying automation development and making event data readily accessible for conditions and variables.

This filter parses complex event messages and makes key information immediately available at the top level, including:

- User IDs
- Alert codes and messages
- Job names
- System information
- IP addresses

### Event-Driven Ansible Rulebooks

The collection includes rulebooks for monitoring IBM Z security events:

- **`1107_1108_group_auth_status.yml`** - Monitors RACF group authority changes (C2P1107I, C2P1108I)
- **`1111_invalid_password_limit_exceeded.yml`** - Detects password threshold breaches with event correlation (C2P1111I, ICH408I)
- **`1101_logon_by_unknown_user.yml`** - Monitors logon attempts by unknown users (C2P1101I)
- **`1103_superuser_logon.yml`** - Detects superuser logon events (C2P1103I)

### Response Playbooks

Response playbooks that can be triggered by rulebooks:

- **`respond_to_1107_1108_group_authority.yml`** - Gathers RACF context and sends notifications for group authority changes
- **`respond_to_1111_password_threshold.yml`** - Retrieves RACF policy, user details, and sends comprehensive alerts for password breaches
- **`quarantine_user.yml`** - Automated user quarantine for security incidents
- **`send_alert_email.yml`** - Flexible email notification with HTML templates

### Email Templates

HTML email templates for security notifications:

- **`racf_alert_base.html.j2`** - Base HTML structure with CSS styling
- **`racf_1107_1108_alert.html.j2`** - Group authority change alert template
- **`racf_1111_alert.html.j2`** - Password threshold breach alert template
- **`racf_listuser_section.html.j2`** - Reusable RACF LISTUSER output display

## Testing

All releases will meet the following test criteria.

* 100% success for Functional tests of rulebooks and playbooks.
* 100% success for [Sanity](https://docs.ansible.com/ansible/latest/dev_guide/testing/sanity/index.html#all-sanity-tests) tests as part of [ansible-test](https://docs.ansible.com/ansible/latest/dev_guide/testing.html#run-sanity-tests).
* 100% success for [ansible-lint](https://ansible.readthedocs.io/projects/lint/) allowing only false positives.

<br/>This release of the collection was tested with following dependencies. *[versions to be added]*

* ansible-core 
* Python 
* Ansible Automation Platform 
* IBM Open Enterprise SDK for Python
* IBM Z Open Automation Utilities (ZOAU) 
* z/OS 
* Apache Kafka 

## Contributing

This community is not currently accepting contributions. However, we encourage you to open git issues for bugs, comments or feature requests.

<br/>Review the collection documentation to learn how you can create a development environment and test the collection's rulebooks and playbooks.

## Communication

If you would like to communicate with this community, you can do so through the following options.

* GitHub discussions.
* GitHub issues.
* Ansible Forum, please use the `zos` and `eda` tags to ensure proper awareness.
* Discord System Z Enthusiasts room `ansible`.
* LinkedIn Ansible for IBM Z.
  
## Support

As **Ansible Validated Content**, this collection is supported by the community through GitHub and Ansible Galaxy. Community support is available at no charge and is limited to the collection content itself.

<br/>Community support does **not** include:
- Ansible Automation Platform components
- IBM Z Open Automation Utilities (ZOAU)
- IBM Open Enterprise SDK for Python
- ansible-core
- Red Hat support services

<br/>For issues with the collection:
1. Check existing GitHub issues
2. Open a new issue with detailed information about your environment and the problem

<br/>For issues with dependencies (ZOAU, Python SDK, z/OS), please contact IBM support directly.

<br/>**Note:** This is a preview release (version 0.0.1) and is provided as-is for evaluation and testing purposes. Production use is not recommended until the collection reaches General Availability (GA) status.

## Release Notes and Roadmap

The collection's cumulative release notes can be found in the [CHANGELOG.rst](CHANGELOG.rst) file.

<br/>**Current Release:** Version 1.0.0

The collection provides core security monitoring capabilities for IBM Z systems with Event-Driven Ansible.

## Related Information

### Documentation
- [Event-Driven Ansible Rulebooks](extensions/eda/README.md) - Complete EDA rulebook documentation
- [Security Response Playbooks](playbooks/security/README.md) - Detailed playbook documentation
- [IBM Z Ansible Collections](https://ibm.github.io/z_ansible_collections_doc/index.html) - Comprehensive documentation for all IBM Z Ansible collections

### Examples and Samples
- [IBM Z Ansible Samples](https://github.com/IBM/z_ansible_collections_samples) - Example playbooks and use cases
- [Event-Driven Ansible Documentation](https://access.redhat.com/documentation/en-us/red_hat_ansible_automation_platform/2.4/html/event-driven_ansible_controller_user_guide/index) - Official EDA documentation

### Additional Resources
- [Getting Started with Ansible for IBM Z](https://ibm.github.io/z_ansible_collections_doc/reference/helpful_links.html) - Helpful links and resources
- [IBM zSecure Documentation](https://www.ibm.com/docs/en/zsecure) - zSecure product documentation
- [RACF Documentation](https://www.ibm.com/docs/en/zos) - z/OS RACF security documentation

## License Information

Some portions of this collection are licensed under [GNU General Public License, Version 3.0](https://opensource.org/licenses/GPL-3.0), and other portions of this collection are licensed under [Apache License, Version 2.0](http://www.apache.org/licenses/LICENSE-2.0).

See individual files for applicable licenses.