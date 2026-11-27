.. ...........................................................................
.. © Copyright IBM Corporation 2026                                          .
.. ...........................................................................

.. _1109_investigate:


1109_investigate -- Investigate a user and request approval for zSecure alert C2P1109I
=======================================================================================

.. contents::
   :local:
   :depth: 1


Synopsis
--------

Collect the RACF profile and the recent command history of a user, and email an approval request
to the security team when zSecure alert C2P1109I (SPECIAL authority used by a non-SPECIAL user) is
detected.

This playbook runs as the first job in the **EDA - Alert 1109 Response Workflow**, which the
:ref:`1109_special_authority` rulebook triggers. It makes no change to the user. It:

1. Reads the RACF profile of the user with the ``ibm.ibm_zos_core.zos_user_info`` module.
2. Submits a zSecure CARLa batch job (CKRCARLA) with ``ibm.ibm_zos_core.zos_job_submit``. The job
   lists the SMF type 80 records of the user from the active SMF data sets, and the playbook
   parses the SYSPRINT listing into a command history.
3. Publishes the findings as workflow artifacts with ``set_stats``.
4. Emails an approval request that contains the profile, the recent command history and a link to
   the workflow.

The profile and the history are read on a best-effort basis. If either cannot be read, the job
continues. The email then shows ``UNKNOWN`` for the profile fields and ``HISTORY UNAVAILABLE`` for
the history.


Variables
---------

From the EDA event context
~~~~~~~~~~~~~~~~~~~~~~~~~~~

These variables are available automatically to all jobs in an EDA-launched workflow through
``ansible_eda.events``. This playbook must run inside the **EDA - Alert 1109 Response Workflow**;
the workflow must be triggered by the EDA rulebook for these references to be populated.

ansible_eda.events.c2p1109i.body.alert_code
  The zSecure alert code. Defaults to ``C2P1109I``.

  | **type**: str

ansible_eda.events.c2p1109i.body.alert_message
  The alert message text. The playbook uses it as the triggering command. Defaults to an empty
  string.

  | **type**: str

ansible_eda.events.c2p1109i.body.target_user
  The RACF user ID that used the authority. Defaults to ``UNKNOWN``.

  | **type**: str

ansible_eda.events.c2p1109i.body.hostname
  The z/OS system on which the alert was raised. Defaults to ``UNKNOWN``.

  | **type**: str

From the AAP job template
~~~~~~~~~~~~~~~~~~~~~~~~~~

Define these variables in the extra variables of the AAP job template that launches the playbook.
System-specific values are not stored in the playbook.

target_hosts
  The inventory host or group where the playbook runs. Defaults to ``zos_target``.

  | **type**: str

system_environment
  Environment variables required for the z/OS tasks, such as the ZOAU and Python settings.

  | **type**: dict

zsecure_sckrload
  The library that holds the zSecure program CKRCARLA. This variable is required for the command
  history.

  | **type**: str

zsecure_racf_db
  The RACF database data set. When set, it is allocated to DD ``RACFDB`` in the CARLa job.
  Optional.

  | **type**: str

zsecure_ckfreeze
  The CKFREEZE data set for CARLa. When set, it is allocated in the CARLa input. Optional.

  | **type**: str

zlda_max_records
  The maximum number of the most recent history records to keep. Defaults to ``100``.

  | **type**: int

zsecure_carla_jobname
  The job name of the CARLa job. Defaults to ``CKRSMF80``.

  | **type**: str

zsecure_job_class
  The job class of the CARLa job. Defaults to ``A``.

  | **type**: str

zsecure_job_msgclass
  The message class of the CARLa job. Defaults to ``H``.

  | **type**: str

zsecure_carla_wait
  The number of seconds to wait for the CARLa job to finish. Defaults to ``60``.

  | **type**: int

aap_controller_host
  The host name of the AAP controller. It is used to build the link to the workflow run in the
  email. Without it, the email shows a message instead of a link.

  | **type**: str

security_alert_recipients
  The email recipients of the approval request. Set this variable in production. If it is empty, no
  email is sent and the approval waits in AAP without a message.

  | **type**: list

security_alert_sender
  The sender address of the email. Defaults to ``aap-security@example.com``.

  | **type**: str

smtp_server
  The host name of the SMTP server. Defaults to ``localhost``.

  | **type**: str

smtp_server_port
  The port of the SMTP server. Defaults to ``25``.

  | **type**: int


Process walkthrough
-------------------

The playbook runs in seven steps.

Step 1: Publish the alert context
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The playbook publishes ``target_user``, ``alert_code``, ``alert_command`` and ``hostname`` first,
with ``investigate_status: failed``. The last task of the playbook sets ``investigate_status`` to
``completed``. If a later task fails, Notify reports a failed investigation.

Step 2: Validate the user ID
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

``target_user`` comes from an event and is used in z/OS commands and in the CARLa input. The
playbook asserts that it is a valid RACF user ID (1 to 8 characters from ``A-Z``, ``0-9``, ``#``,
``$`` and ``@``) and that it is not ``NONE`` or ``UNKNOWN``. If the check fails, the job stops
before anything runs on z/OS.

Step 3: Read the RACF profile
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The playbook runs ``ibm.ibm_zos_core.zos_user_info`` for the user and reads the owner, default
group, attributes and last access from the base segment. If the profile cannot be read, for
example because the user is not found or the host is unreachable, the fields are set to
``UNKNOWN`` and the job continues.

Step 4: Read the command history from SMF type 80
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The playbook builds the CARLa input and checks it. ``zsecure_sckrload`` must be set, and each
input line must be at most 70 characters, because CKRCARLA reads only columns 1 to 72 and the JCL
template indents each line by 2 blanks. The input selects the SMF type 80 records of the user from
the active SMF data sets.

The playbook then renders ``templates/jcl/zlda_smf80_query.jcl.j2``, copies it to z/OS, and
submits it with ``ibm.ibm_zos_core.zos_job_submit``. A return code up to ``4`` is accepted. The
playbook reads SYSPRINT from the job output and parses it:

* The columns are located from the header line (Date, Time, User, Resource, Event description),
  not from fixed positions.
* Logon rows (``RACINIT``) are dropped, because the alert is about commands.
* The latest row whose command and resource both appear in the alert message is marked
  ``<< TRIGGER`` and is always kept.

Only records that are still in the active SMF data sets are returned.

If the CARLa settings are not valid, the host is unreachable, the job fails, or the listing cannot
be read, the history is reported as ``HISTORY UNAVAILABLE`` with the reason, and the job
continues.

Step 5: Build the history tables
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The playbook builds a full table and a short table. Both have the columns ``TIMESTAMP (z/OS
local)``, ``BY``, ``RESOURCE`` and ``EVENT DESCRIPTION``. The short table is used in the email. It
shows the last 10 records, and always keeps the trigger row.

Step 6: Publish the findings
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The playbook publishes the profile fields, the history tables and the CARLa job ID with
``set_stats``. All ``set_stats`` calls in this playbook use ``aggregate: false``, so that a later
value replaces an earlier one instead of being added to it.

Step 7: Email the approval request
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The playbook renders ``templates/racf_1109_approval_request.html.j2`` and sends it to the
recipients with ``community.general.mail``. The email contains the alert, the triggering command,
the recent command history, the RACF profile and a link to the workflow run, where the approver
chooses **Approve** or **Deny**. All values in the email are HTML-escaped.

If the template cannot be rendered, a short fallback body with the link is sent. If the email
fails or no recipients are set, the job continues, and the approval node keeps waiting in AAP. The
result is published as ``approval_email_status``.


Output
------

The playbook publishes the following workflow artifacts with ``set_stats``:

* **lu_user_id**, **lu_owner**, **lu_default_group**, **lu_last_access**, **lu_attributes**: the
  RACF profile fields, or ``UNKNOWN`` if the profile could not be read.
* **lu_joined**: the full LISTUSER text.
* **zlda_summary**: the full command history table.
* **zlda_summary_recent**: the command history table limited to the last 10 records.
* **zlda_record_count**: the number of history records.
* **zlda_status**: ``ok`` or ``unavailable``.
* **zlda_reason**: the reason when the history is unavailable.
* **carla_job_id**: the z/OS job ID of the CARLa job.
* **investigate_status**: ``failed`` until the last task sets it to ``completed``.
* **alert_command**, **alert_code**, **target_user**, **hostname**: the values from the alert.
* **approval_email_status**: ``Sent``, ``Skipped (no recipients)`` or ``Failed``.

The :ref:`1109_notify_investigate` playbook uses these values for the outcome email.


Prerequisites
-------------

* The Jinja2 template ``racf_1109_approval_request.html.j2`` and its base template
  ``racf_alert_base.html.j2``, the shared ``racf_listuser_section.html.j2`` template, and the JCL
  template ``jcl/zlda_smf80_query.jcl.j2`` must be present in the playbook's ``templates/``
  directory.
* The AAP job template must include a Machine credential for z/OS SSH access.
* The ``ibm.ibm_zos_core`` collection version 2.1.0 or later and the ``community.general``
  collection must be installed in the execution environment.
* The z/OS user must be able to submit jobs, and must have read access to the active SMF data
  sets and to the zSecure library.
* The SMTP server must be reachable from the AAP controller.
* The configured email recipients must be valid mailboxes.
* This playbook must run inside the **EDA - Alert 1109 Response Workflow** so that
  ``ansible_eda.events.c2p1109i`` is populated.


Notes
-----

* The timestamps in the history are the local time of the z/OS system, as shown in the listing.
* Email sending is delegated to ``localhost``, so the SMTP connection originates from the AAP
  controller regardless of the value of ``target_hosts``.
* All output is written to the AAP job log. Restrict access to job logs as required by your
  security policy.


Email template
--------------

The playbook renders ``templates/racf_1109_approval_request.html.j2``, which includes the shared
``racf_alert_base.html.j2`` base template. The base template provides the HTML document structure,
``<head>``, inline CSS, and the opening ``<body>`` tag. The template also includes the shared
``racf_listuser_section.html.j2`` template for the RACF profile table.

Template structure
~~~~~~~~~~~~~~~~~~

The template renders the following sections in order:

1. **Alert summary box** (``.alert-box``) — Displays the alert code, user ID, and hostname.
2. **What Happened box** (``.warning-box``) — Displays the triggering command and a short
   explanation of the alert.
3. **Decision Needed box** (``.info-box``) — Describes what **Approve** and **Deny** do, and links
   to the workflow run. If the link is not available, the box shows a message to set
   ``aap_controller_host``.
4. **Recent RACF Command Activity** — Displays ``zlda_summary_recent`` inside a ``<pre>`` block.
   If the history is empty, a ``.warning-box`` shows that no command history is available.
5. **RACF User Information** — Displays the user ID, owner, default group, and attributes.
6. **Footer** — A muted italic line identifying the message as an automated alert from
   Event-Driven Ansible.

Template notes
~~~~~~~~~~~~~~

* All values in the template are HTML-escaped.
* If the history could not be read, section 4 shows the ``HISTORY UNAVAILABLE`` text with the
  reason.
* The base template ``racf_alert_base.html.j2`` and ``racf_listuser_section.html.j2`` are shared
  across the zSecure alert email templates in this collection.

CARLa job template
~~~~~~~~~~~~~~~~~~

``templates/jcl/zlda_smf80_query.jcl.j2`` is rendered on the controller, copied to z/OS and
submitted. It defines the following:

* The job card, with the job name, class, and message class from ``zsecure_carla_jobname``,
  ``zsecure_job_class``, and ``zsecure_job_msgclass``.
* The step ``ZSECURE`` that runs ``CKRCARLA``, with ``STEPLIB`` set to ``zsecure_sckrload``.
* ``SYSPRINT``, which the playbook reads and parses.
* ``RACFDB``, set to ``zsecure_racf_db``, only when that variable is defined.
* ``SYSIN``, which holds the CARLa input that the playbook builds.


See also
--------

* The :ref:`1109_special_authority` rulebook that starts the workflow.
* The :ref:`tso_cancel_user` and :ref:`racf_revoke` playbooks that run after an administrator
  approves.
* The :ref:`1109_notify_investigate` playbook that reports the outcome.
* To read the RACF profile, see the `ibm.ibm_zos_core.zos_user_info <https://ibm.github.io/z_ansible_collections_doc/ibm_zos_core/docs/source/modules/zos_user_info.html>`_ module.
* To submit the CARLa job, see the `ibm.ibm_zos_core.zos_job_submit <https://ibm.github.io/z_ansible_collections_doc/ibm_zos_core/docs/source/modules/zos_job_submit.html>`_ module.
* Use the ``templates/racf_1109_approval_request.html.j2`` Jinja2 template for the email body.
