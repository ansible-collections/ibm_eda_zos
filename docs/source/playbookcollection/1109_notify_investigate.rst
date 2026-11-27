.. ...........................................................................
.. © Copyright IBM Corporation 2026                                          .
.. ...........................................................................

.. _1109_notify_investigate:


1109_notify_investigate -- Email the outcome of the zSecure alert C2P1109I response
===================================================================================

.. contents::
   :local:
   :depth: 1


Synopsis
--------

Send an HTML email that reports the outcome of the **EDA - Alert 1109 Response Workflow**.

The workflow runs this playbook from three nodes, one for each outcome:

* **Approved**: the email reports what was done (end session and revoke) and, if a step did not
  succeed, the manual commands to run on z/OS.
* **Denied**: the email states that the administrator denied the request and that no action was
  taken. An expired approval takes the same path and is reported as denied.
* **Investigation failed**: the email states that the Investigate job did not finish, that no
  administrator decision was made and that no action was taken.

The playbook runs on localhost, so it works when the z/OS host is unreachable.


Variables
---------

From the workflow
~~~~~~~~~~~~~~~~~~

These variables are published by the earlier jobs of the workflow. A missing value is reported as
``Not run`` or ``UNKNOWN``.

target_user, hostname, alert_code, alert_command
  The alert context from :ref:`1109_investigate`.

investigate_status
  ``failed`` until the Investigate job finishes, then ``completed``.

admin_decision
  ``approved``. It is published by :ref:`tso_cancel_user` and :ref:`racf_revoke`, and it is not set
  on the deny path.

tso_cancel_status, tso_cancel_detail
  The result from :ref:`tso_cancel_user`.

racf_revoke_status, racf_revoke_detail, racf_verify_status
  The results from :ref:`racf_revoke`.

From the AAP job template
~~~~~~~~~~~~~~~~~~~~~~~~~~

security_alert_recipients
  The email recipients. If empty, the email is skipped.

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

aap_controller_host
  The host name of the AAP controller. It is used to build the workflow link in the fallback email
  body.

  | **type**: str


Process walkthrough
-------------------

The playbook runs in four phases.

Phase 1: Decide the path
~~~~~~~~~~~~~~~~~~~~~~~~~

The path comes from ``admin_decision`` (``approved`` or ``denied``). If it is not set, which is the
case on the deny path, a published end-session or revoke status means ``approved``. Otherwise the
decision is ``denied``.

Phase 2: Compute the overall status
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The overall status is one of the following:

* ``SUCCESS``: approved, the end-session status is ``Success`` or ``No active session``, and the
  revoke status is ``Success``.
* ``PARTIAL``: approved, and one of the two steps did not succeed.
* ``FAILED``: approved, and neither step succeeded.
* ``DENIED``: not approved, and the Investigate job finished.
* ``INVESTIGATION_FAILED``: not approved, and the Investigate job did not finish.

An approval always wins, even when the Investigate job did not reach its last task.

Phase 3: Send the email
~~~~~~~~~~~~~~~~~~~~~~~~

The playbook renders ``templates/racf_1109_alert.html.j2`` and sends it with
``community.general.mail``. The subject depends on the status:

* ``[INFO]`` for ``SUCCESS``.
* ``[NOTIFICATION]`` for ``DENIED``.
* ``[ACTION REQUIRED]`` for ``PARTIAL``, ``FAILED`` and ``INVESTIGATION_FAILED``.

If the template cannot be rendered, a short fallback body is sent. If no recipients are set, the
email is reported as ``Skipped (no recipients)``. An SMTP error is reported as ``Failed``.

Phase 4: Publish the outcome and flag the run
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The playbook publishes the outcome with ``set_stats``. The job then fails when the overall status is
``PARTIAL``, ``FAILED`` or ``INVESTIGATION_FAILED``, or when the email failed. The workflow run then
shows red. Each Notify node ends its path, so nothing downstream is blocked.


Output
------

The playbook produces the following outputs:

* An HTML email to the configured recipients with the alert details, the result of each step, and
  the manual follow-up commands when a step did not succeed.
* The following workflow artifacts, published with ``set_stats``:

  * **quarantine_action**: the overall status.
  * **email_status**: ``Sent``, ``Skipped (no recipients)`` or ``Failed``.
  * **email_recipients**: the recipients, as text.
  * **target_user**, **alert_code**: the alert context.


Prerequisites
-------------

* The Jinja2 template ``racf_1109_alert.html.j2`` and its base template ``racf_alert_base.html.j2``
  must be present in the playbook's ``templates/`` directory.
* The SMTP server must be reachable from the AAP controller.
* The configured email recipients must be valid mailboxes.
* Use one job template for all three Notify nodes in the workflow, and link them as follows:

  * From Revoke, with **Run always**, so that the report is sent even if an earlier job failed.
    Missing results then show as ``Not run``.
  * From Approval, with **Run on fail**, to report a denied or expired request.
  * From Investigate, with **Run on fail**, to report that the investigation did not finish. This
    is reported as ``INVESTIGATION_FAILED``.
* The ``community.general`` collection must be installed in the execution environment.


Notes
-----

* The artifact name ``quarantine_action`` holds the overall status, although this playbook does
  not quarantine the user.
* An expired approval is reported as ``DENIED``.
* All output is written to the AAP job log. Restrict access to job logs as required by your
  security policy.


Email template
--------------

The playbook renders ``templates/racf_1109_alert.html.j2``, which includes the shared
``racf_alert_base.html.j2`` base template. The base template provides the HTML document structure,
``<head>``, inline CSS, and the opening ``<body>`` tag.

Template structure
~~~~~~~~~~~~~~~~~~

The template renders the following sections in order:

1. **Alert summary box** (``.alert-box``) — Displays the alert code, user ID, and hostname.
2. **What Happened box** (``.warning-box``) — Displays the triggering command and a short
   explanation of the alert.
3. **Decision section** — Depends on the path:

   * **Investigation failed**: an ``.alert-box`` that states that the Investigate job did not
     finish and that no action was taken.
   * **Denied**: an ``.info-box`` that states that the administrator denied the request and that
     no action was taken.
   * **Approved**: a box with the overall result, and a table with the end session, revoke, and
     verification results. The box is an ``.info-box`` for ``SUCCESS`` and an ``.alert-box``
     otherwise.

4. **Manual follow-up box** (``.warning-box``) — Lists the commands to run on z/OS for the steps
   that did not succeed. It is rendered only when the approved result is not ``SUCCESS``.
5. **Footer** — A muted italic line identifying the message as an automated alert from
   Event-Driven Ansible. The text depends on the path.

Template notes
~~~~~~~~~~~~~~

* All values in the template are HTML-escaped.
* The base template ``racf_alert_base.html.j2`` is shared across the zSecure alert email
  templates in this collection.


See also
--------

* The :ref:`1109_special_authority` rulebook that starts the workflow.
* The :ref:`1109_investigate`, :ref:`tso_cancel_user`, and :ref:`racf_revoke` playbooks that
  publish the values that this playbook reports.
* To send the email, see the `community.general.mail <https://docs.ansible.com/ansible/latest/collections/community/general/mail_module.html>`_ module.
* Use the ``templates/racf_1109_alert.html.j2`` Jinja2 template for the email body.
