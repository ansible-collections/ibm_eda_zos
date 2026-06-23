# Event-Driven Ansible for IBM Z

The **IBM EDA z/OS** collection provides rulebooks and playbooks for automating IBM Z operational scenarios through Event-Driven Ansible. This collection provides rulebooks that monitor zSecure alerts and trigger automated response playbooks for security events on z/OS.

## Description

The **IBM EDA z/OS** collection is part of the **Red Hat Ansible Validated Content for IBM Z®** offering that brings Event-Driven Ansible automation to IBM Z. This collection provides rulebooks and playbooks that users can customize for automating various IBM Z operational scenarios through event-driven workflows. The collection also includes a custom event filter that extracts key attributes from z/OS events (such as user IDs, alert codes, alert messages, and job names), eliminating the need for repetitive filtering in rulebooks and playbooks.

**The first release focuses on IBM Z Security**, enabling real-time monitoring of security events from zSecure and automating incident response workflows through rulebooks and response playbooks. The collection can be used to monitor RACF security alerts including group authority changes, password threshold breaches, unauthorized access attempts, and superuser logons.

Security teams can implement continuous compliance monitoring and automated response workflows, while system administrators can reduce mean time to response (MTTR) for security incidents. The collection integrates seamlessly with Kafka event streams, IBM z/OS systems, and email notification systems to provide end-to-end security automation.

## Requirements

Before you install the IBM EDA z/OS collection, ensure that you configure the Ansible Automation Platform controller, Event-Driven Ansible controller, and z/OS managed nodes with the following requirements found [here](https://ibm.github.io/z_ansible_collections_doc/index.html) under Event-Driven Ansible for IBM Z.

## Installation

Before using this collection, you need to install it with the Ansible Galaxy command-line tool:

```sh
ansible-galaxy collection install ibm.ibm_eda_zos
```

<br/>You can also include it in a requirements.yml file and install it with `ansible-galaxy collection install -r requirements.yml`, using the format:

```yaml
collections:
  - name: ibm.ibm_eda_zos
```

### Configuration Variables

The collection requires several configuration variables for Kafka connectivity, SMTP settings, and z/OS environment. These should be configured in your Rulebook Activation or Job Template extra variables:

```yaml
# Kafka Configuration for Rulebook Activation 
kafka_topic: "zsecure-alerts"
kafka_host: "kafka.example.com"
kafka_port: 9093
security_protocol: "SSL"
ssl_cafile: "/path/to/ca-cert.pem"

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

The collection includes a **security event filter** designed for Kafka event streams that automatically extracts valuable attributes from z/OS user related security events. This eliminates the need for custom regex filtering in every rulebook and playbook, significantly simplifying automation development and making event data readily accessible for conditions and variables.

This filter parses complex event messages and makes key information immediately available at the top level, including:

- User IDs
- Alert codes and messages
- Job names
- System information
- IP addresses

### Event-Driven Ansible Rulebooks

The collection includes rulebooks for monitoring IBM Z security events:

- **`1101_logon_by_unknown_user.yml`** - Monitors logon attempts by unknown users (C2P1101I).
- **`1103_superuser_logon.yml`** - Detects superuser logon events (C2P1103I).
- **`1107_1108_group_auth_status.yml`** - Monitors RACF group authority changes (C2P1107I, C2P1108I).
- **`1111_invalid_password_limit_exceeded.yml`** - Detects password threshold breaches with event correlation (C2P1111I, ICH408I).

### Response Playbooks

Response playbooks that can be triggered by rulebooks:

- **`gather_listuser_information.yml`** - Gathers RACF context and sends notifications for group authority changes.
- **`gather_password_policy_information.yml`** - Retrieves RACF policy, user details, and sends comprehensive alerts for password breaches.
- **`quarantine_user.yml`** - Quarantine a RACF user by applying CONTAIN attribute.
- **`remove_uid_access.yml`** - Remove OMVS UID(0) access from a RACF user.
- **`send_alert_email.yml`** - Send HTML email notification for security administrators.
- **`setr_jes_batchallracf.yml`** - Enable RACF authentication for all batch jobs.
- **`unquarantine_user.yml`** - Remove CONTAIN attribute and resume user access.

### Email Templates

HTML email templates for security notifications:

- **`racf_1101_alert.html.j2`** - RACF authentication for batch jobs alert template.
- **`racf_1103_alert.html.j2`** - Remove OMVS UID(0) access alert template.
- **`racf_1107_1108_alert.html.j2`** - Group authority change alert template.
- **`racf_1111_alert.html.j2`** - Password threshold breach alert template.
- **`racf_alert_base.html.j2`** - Base HTML structure with CSS styling.
- **`racf_email_alert.html.j2`** - Email alert template.
- **`racf_listuser_section.html.j2`** - Reusable RACF LISTUSER output display.

## Testing

All releases will meet the following test criteria.

* 100% success for Functional tests of rulebooks and playbooks.
* 100% success for [Sanity](https://docs.ansible.com/ansible/latest/dev_guide/testing/sanity/index.html#all-sanity-tests) tests as part of [ansible-test](https://docs.ansible.com/ansible/latest/dev_guide/testing.html#run-sanity-tests).
* 100% success for [ansible-lint](https://ansible.readthedocs.io/projects/lint/) allowing only false positives.

## Contributing

This community is not currently accepting contributions. However, we encourage you to open git issues for bugs, comments or feature requests.

Review the collection documentation to learn how you can create a development environment and test the collection's rulebooks and playbooks.

## Communication

If you would like to communicate with this community, you can do so through the following options.

* GitHub [issues](https://github.com/ansible-collections/ibm_eda_zos/issues).
* [Ansible Forum](https://forum.ansible.com/), please use the `zos` and `eda` tags to ensure proper awareness.
* Discord [System Z Enthusiasts](https://discord.gg/sze) room `ansible`.
* LinkedIn [Ansible for IBM Z](https://www.linkedin.com/groups/14515630/).
  
## Support

As **Ansible Validated Content**, this collection is supported by the community through GitHub and Ansible Galaxy. Community support is available at no charge and is limited to the collection content itself.

<br/>Community support does **not** include:
- Ansible Automation Platform components
- I[BM Z Open Automation Utilities (ZOAU)](https://www.ibm.com/docs/en/zoau)
- [IBM Open Enterprise SDK for Python](https://www.ibm.com/products/open-enterprise-python-zos)
- [ansible-core](https://github.com/ansible/ansible)

<br/>For issues with the collection:
1. Check existing [GitHub issues](https://github.com/ansible-collections/ibm_eda_zos/issues).

2. Open a new issue with detailed information about your environment and the problem.

<br/>For issues with dependencies (ZOAU, Python SDK, z/OS), please contact IBM support directly.


## Release Notes and Roadmap

The collection's cumulative release notes can be found in the [CHANGELOG.rst](CHANGELOG.rst) file.

<br/>**Current Release:** Version 1.0.0

The collection provides core security monitoring capabilities for IBM Z systems with Event-Driven Ansible.

## Related Information

### Documentation
- [IBM Z Ansible Collections](https://ibm.github.io/z_ansible_collections_doc/index.html) - Comprehensive documentation for all IBM Z Ansible collections

### Examples and Samples
- [IBM Z Ansible Samples](https://github.com/IBM/z_ansible_collections_samples) - Example playbooks and use cases
- [Event-Driven Ansible Documentation](https://access.redhat.com/documentation/en-us/red_hat_ansible_automation_platform/2.4/html/event-driven_ansible_controller_user_guide/index) - Official EDA documentation

### Additional Resources
- [Getting Started with Ansible for IBM Z](https://ibm.github.io/z_ansible_collections_doc/reference/helpful_links.html) - Helpful links and resources
- [IBM zSecure Documentation](https://www.ibm.com/docs/en/zsecure) - zSecure product documentation
- [RACF Documentation](https://www.ibm.com/docs/en/zos) - z/OS RACF security documentation

## License Information

This collection is licensed under [Apache License, Version 2.0](http://www.apache.org/licenses/LICENSE-2.0).

See individual files for applicable licenses.