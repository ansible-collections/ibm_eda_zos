.. ...........................................................................
.. © Copyright IBM Corporation 2026                                          .
.. ...........................................................................

.. _racf_revoke:


racf_revoke -- Revoke a RACF user and verify the result
========================================================

.. contents::
   :local:
   :depth: 1


Synopsis
--------

Revoke a RACF user with the ``ALTUSER userid REVOKE`` command and check the result by reading the
profile of the user.

This playbook runs in the **EDA - Alert 1109 Response Workflow** after an administrator approves
the request and after the :ref:`tso_cancel_user` job.

A command error does not fail the playbook. It publishes a status, and the Notify job decides what
a non-success status means.


Variables
---------

From the workflow
~~~~~~~~~~~~~~~~~~

target_user
  The RACF user ID to revoke. The :ref:`1109_investigate` playbook publishes it as a workflow
  artifact.

  | **type**: str

From the AAP job template
~~~~~~~~~~~~~~~~~~~~~~~~~~

target_hosts
  The inventory host or group where the playbook runs. Defaults to ``zos_target``.

  | **type**: str

system_environment
  Environment variables required for the z/OS tasks, such as the ZOAU and Python settings.

  | **type**: dict

zos_connect_timeout_s
  The number of seconds to wait for connectivity before the command is issued. Defaults to
  ``60``.

  | **type**: int


Process walkthrough
-------------------

The playbook has two plays.

Play 1: Record the approval
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The first play runs on localhost and publishes ``admin_decision: approved``, so that Notify reports
the approval even if the second play fails.

Play 2: Revoke and verify
~~~~~~~~~~~~~~~~~~~~~~~~~~

1. **Validate the user ID.** The playbook asserts that ``target_user`` is a valid RACF user ID
   (1 to 8 characters from ``A-Z``, ``0-9``, ``#``, ``$`` and ``@``) and is not ``NONE`` or
   ``UNKNOWN``, because the value goes into a RACF command.
2. **Verify connectivity.** The playbook waits for the z/OS host. If the host cannot be reached, no
   command is attempted and the step is reported as ``Unreachable``.
3. **Revoke the user.** The playbook runs ``ALTUSER userid REVOKE`` with
   ``ibm.ibm_zos_core.zos_tso_command``.
4. **Verify the change.** The playbook reads the profile with ``ibm.ibm_zos_core.zos_user_info``
   and looks for ``REVOKED`` in the ``ATTRIBUTES`` list. The verification is informational only
   and never changes the revoke status.
5. **Publish the result.** The statuses and the detail are published with ``set_stats`` and also
   set as facts on localhost.


Output
------

The playbook publishes the following workflow artifacts with ``set_stats``:

* **admin_decision**: ``approved``.
* **racf_revoke_status**: ``Success``, ``Failed`` or ``Unreachable``.
* **racf_revoke_detail**: a short text from the module.
* **racf_verify_status**: one of the following:

  * ``Verified``: ``REVOKED`` was found in the profile after the revoke.
  * ``Not verified``: ``REVOKED`` was not found in the profile. Check LISTUSER on z/OS.
  * ``Unavailable``: the profile could not be read.

The :ref:`1109_notify_investigate` playbook uses these values for the outcome email.


Prerequisites
-------------

* The AAP job template must include a Machine credential for z/OS SSH access.
* The z/OS user must have RACF authority to run ``ALTUSER`` with the ``REVOKE`` attribute.
* The ``ibm.ibm_zos_core`` collection version 2.1.0 or later must be installed in the execution
  environment. The ``zos_user_info`` module is not available in earlier versions.
* The playbook runs on every host in ``target_hosts``. Make sure that the job template selects only
  the z/OS system that you intend to change.


Notes
-----

* The playbook sets ``gather_facts: false`` because no Ansible facts are required.
* The overall status in the Notify email is based on the revoke status. A verification status of
  ``Not verified`` or ``Unavailable`` is shown in the email body, but it does not change the
  overall status.
* All output is written to the AAP job log. Restrict access to job logs as required by your
  security policy.


See also
--------

* The :ref:`tso_cancel_user` playbook that runs before this playbook.
* The :ref:`1109_notify_investigate` playbook that reports the result.
* To issue the RACF command, see the `ibm.ibm_zos_core.zos_tso_command <https://ibm.github.io/z_ansible_collections_doc/ibm_zos_core/docs/source/modules/zos_tso_command.html>`_ module.
* To read the RACF profile, see the `ibm.ibm_zos_core.zos_user_info <https://ibm.github.io/z_ansible_collections_doc/ibm_zos_core/docs/source/modules/zos_user_info.html>`_ module.
