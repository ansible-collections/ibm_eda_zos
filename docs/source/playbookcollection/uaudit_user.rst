.. ...........................................................................
.. © Copyright IBM Corporation 2026                                          .
.. ...........................................................................

.. _uaudit_user:


uaudit_user -- Set UAUDIT status for a RACF user
================================================

.. contents::
   :local:
   :depth: 1


Synopsis
--------

Set the UAUDIT attribute for a RACF user when a security alert is detected.

This playbook is launched by an EDA rulebook when zSecure reports a security event requiring 
immediate user auditing on z/OS. The playbook issues the RACF ALTUSER command to apply the 
UAUDIT attribute to the affected user, retrieves the updated user profile information using 
the ``ibm.ibm_zos_core.zos_user_info`` module, displays the user's RACF attributes, and sets 
status information for downstream notification processes.


Variables
---------

From the rulebook event
~~~~~~~~~~~~~~~~~~~~~~~~

These variables are populated automatically from the matched event when the rulebook launches 
the job template:

tso_user
  The RACF user ID for which UAUDIT status will be set. Extracted from ``ansible_eda.event.body.action_user``.
  Defaults to 'UNKNOWN' if not provided.

  | **type**: str

alert_message
  The descriptive message about the security event that triggered the playbook. Extracted from ``ansible_eda.event.body.alert_message``.
  Defaults to 'No Message Text' if not provided.

  | **type**: str


From the AAP job template
~~~~~~~~~~~~~~~~~~~~~~~~~~

These variables must be defined on the AAP job template that launches the playbook:

target_hosts
  The inventory host or group where the playbook executes. Defaults to 'localhost' if not specified.

  | **type**: str

system_environment
  Environment variables required for z/OS shell access, such as shared address space settings.

  | **type**: dict


Process walkthrough
-------------------

The playbook runs in two phases based on whether a valid user ID is provided.

Phase 1: Validate the target user
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The playbook checks if the ``tso_user`` variable contains a valid RACF user ID. If the value 
is 'UNKNOWN', the playbook logs a message indicating it cannot proceed and sets a status message 
for notification purposes. The playbook then skips the UAUDIT actions.

Phase 2: Execute UAUDIT and verify (valid user only)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

When a valid user ID is provided, the playbook:

1. Issues the ALTUSER command to set the UAUDIT attribute on the user. The command is executed 
   with a maximum return code of 4 to allow for informational messages while still treating the 
   operation as successful.

2. Retrieves the user's profile information by using the ``ibm.ibm_zos_core.zos_user_info`` module 
   for the affected user.

3. Displays the user's RACF attributes (base segment attributes) after setting the UAUDIT attribute 
   to confirm the update.

4. Sets status information using ``set_stats`` to record whether the ALTUSER command succeeded or 
   failed. This status message is available to downstream processes, such as email notification playbooks.

5. Logs the result to the AAP job output, showing whether the ALTUSER command was successful.


Output
------

The playbook produces two outputs:

* A status message set through ``set_stats`` that indicates whether the ALTUSER command was executed 
  successfully or failed. This message is available to subsequent playbooks or notification workflows.

* A run summary in the AAP job output showing the alert message, target user, RACF command results, 
  and the user's attributes after setting the UAUDIT status.


Prerequisites
-------------

* The AAP job template must include a Machine credential for z/OS SSH access.
* The z/OS user running the playbook must be permitted to issue the TSO command.
* The z/OS user must have RACF authority to execute the ALTUSER command with the UAUDIT attribute and query user profile information.
* The ``ibm.ibm_zos_core`` collection must be installed and available on the control node.
* The ``tso_user`` must exist in RACF (if 'UNKNOWN', the playbook will skip UAUDIT actions).


Notes
-----

* The playbook executes on the host specified by the ``target_hosts`` variable, which should be 
  defined in the AAP inventory used by the job template.
* The ALTUSER command accepts return codes up to 4 as successful, allowing for informational messages 
  while still applying the UAUDIT attribute.
* The UAUDIT attribute directs RACF to log all security-relevant actions and resource access attempts 
  for the specified user in SMF records.
* The ``set_stats`` data is available to subsequent playbooks in the same workflow, enabling 
  notification playbooks to include the command status in alert emails.
* All output is written to the AAP job log. Restrict access to job logs if your security policy 
  requires it.


See also
--------

* To issue the RACF commands, see `ibm.ibm_zos_core.zos_tso_command <https://ibm.github.io/z_ansible_collections_doc/ibm_zos_core/docs/source/modules/zos_tso_command.html>`_ module.
* To retrieve user profile information, see `ibm.ibm_zos_core.zos_user_info <https://ibm.github.io/z_ansible_collections_doc/ibm_zos_core/docs/source/modules/zos_user_info.html>`_ module.
* Email notification playbooks that consume the ``set_stats`` data from this playbook.
