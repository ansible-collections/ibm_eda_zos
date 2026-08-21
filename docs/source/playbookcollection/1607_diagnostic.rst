.. ...........................................................................
.. © Copyright IBM Corporation 2026                                          .
.. ...........................................................................

.. _1607_diagnostic:


1607_diagnostic -- Capture SMF flood diagnostics for zSecure alert C2P1607I
============================================================================

.. contents::
   :local:
   :depth: 1


Synopsis
--------

Capture system diagnostics when zSecure alert C2P1607I (SMF Record Flood) is detected.

This playbook is launched as the first job in the **EDA - SMF 1607 Response Workflow**, which is
triggered by the :ref:`1607_SMF_Flood_Alert` rulebook. The playbook queries the current SMF
recording status on the target z/OS system, extracts the flooded SMF record type from the
correlated IFA780A WTO message, and publishes the derived values for use by downstream
notification jobs in the same workflow.


Variables
---------

From the EDA event context
~~~~~~~~~~~~~~~~~~~~~~~~~~~

These variables are available automatically to all jobs in an EDA-launched workflow through
``ansible_eda.events``. This playbook must run inside the **EDA - SMF 1607 Response Workflow**;
running it standalone will cause these references to be undefined.

ansible_eda.events.c2p1607i.body.alert_code
  The zSecure alert code, always ``C2P1607I`` for this workflow.

  | **type**: str

ansible_eda.events.c2p1607i.body.hostname
  The z/OS system name where the SMF record flood was detected.

  | **type**: str

ansible_eda.events.ifa780a.body.alert_message
  The IFA780A WTO message text. Read by the playbook ``vars:`` block as ``flood_wto_message``
  and used to extract the flooded SMF record type via regex.

  | **type**: str

From the AAP job template
~~~~~~~~~~~~~~~~~~~~~~~~~~

These variables must be defined on the AAP job template that launches the playbook:

target_hosts
  The inventory host or group where the ``D SMF`` operator command is issued.

  | **type**: str

system_environment
  Environment variables required for z/OS shell access, such as shared address space settings.

  | **type**: dict


Process walkthrough
-------------------

The playbook runs in four steps.

Step 1: Capture current SMF status
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Issues the ``D SMF`` operator command on the target z/OS system using the
``ibm.ibm_zos_core.zos_operator`` module. The raw console response is captured and formatted
into the ``d_smf_output`` variable, prefixed with a ``==== D SMF ====`` header for clarity in
the notification email.

Step 2: Extract the flooded SMF record type
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Parses the ``flood_wto_message`` variable — resolved from ``ansible_eda.events.ifa780a.body.alert_message``
in the ``vars:`` block — using a regex pattern (``TYPE\s+([0-9]+)``) to extract the numeric SMF
record type that triggered the flood filter. If the pattern does not match — for example, if the
message text is absent or malformed — the variable is set to ``UNKNOWN`` so the workflow can
continue without interruption.

Step 3: Display diagnostic summary
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Logs a formatted summary to the AAP job output, including the alert code, resolved SMF record
type, and hostname. This output is visible in the AAP job log for manual review.

Step 4: Publish derived results for downstream jobs
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Publishes ``smf_record_type`` and ``d_smf_output`` via ``ansible.builtin.set_stats`` so they
are available to subsequent jobs in the **EDA - SMF 1607 Response Workflow**, specifically the
notification job that renders and sends the alert email.


Output
------

The playbook produces two workflow-level outputs via ``set_stats``:

* **smf_record_type**: The numeric SMF record type extracted from the IFA780A message, or
  ``UNKNOWN`` if extraction failed.

* **d_smf_output**: The formatted output of the ``D SMF`` operator command, including the
  ``==== D SMF ====`` header.

Both values are consumed by the :ref:`send_alert_email_1607` playbook to populate the HTML
notification email.


Prerequisites
-------------

* The AAP job template must include a Machine credential for z/OS SSH access.
* The z/OS user running the playbook must be authorised to issue the ``D SMF`` operator command.
* The ``ibm.ibm_zos_core`` collection must be installed in the execution environment.
* This playbook must be run as a job inside the **EDA - SMF 1607 Response Workflow**, as it
  depends on ``ansible_eda.events`` being populated by the EDA rulebook.


Notes
-----

* The playbook sets ``gather_facts: false`` to reduce execution time, as no Ansible facts are
  required for the operator command or regex extraction.
* The ``D SMF`` command output is joined into a single multi-line string. On systems where the
  operator command produces a large response, the output is truncated to what the
  ``ibm.ibm_zos_core.zos_operator`` module returns.
* If ``flood_wto_message`` is empty or does not contain the expected pattern, ``smf_record_type``
  is set to ``UNKNOWN``. Downstream jobs handle this gracefully using the
  ``| default('UNKNOWN', true)`` filter.
* The debug task in Step 3 prints alert details to the AAP job log. Restrict access to job logs
  if your security policy requires it.
* ``set_stats`` publishes data at the AAP workflow level, making both variables available to
  all subsequent jobs in the workflow.


See also
--------

* The :ref:`1607_SMF_Flood_Alert` rulebook that triggers this playbook as part of the response workflow.
* The :ref:`send_alert_email_1607` playbook that consumes ``smf_record_type`` and ``d_smf_output`` to send the notification.
* To issue operator commands on z/OS, see the `ibm.ibm_zos_core.zos_operator <https://ibm.github.io/z_ansible_collections_doc/ibm_zos_core/docs/source/modules/zos_operator.html>`_ module.
