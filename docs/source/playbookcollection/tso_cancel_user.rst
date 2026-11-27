.. ...........................................................................
.. © Copyright IBM Corporation 2026                                          .
.. ...........................................................................

.. _tso_cancel_user:


tso_cancel_user -- End the active TSO session of a user
========================================================

.. contents::
   :local:
   :depth: 1


Synopsis
--------

End the active TSO session of a user with the z/OS operator command ``C U=userid``.

This playbook runs in the **EDA - Alert 1109 Response Workflow** after an administrator approves
the request. ``ALTUSER REVOKE`` does not end an active session, so this playbook ends the TSO
session of the user with ``C U=userid``.

A command error does not fail the playbook. It publishes a status, and the Notify job decides what
a non-success status means.


Variables
---------

From the workflow
~~~~~~~~~~~~~~~~~~

target_user
  The TSO user ID whose session is ended. The :ref:`1109_investigate` playbook publishes it as a
  workflow artifact.

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

Play 2: End the session
~~~~~~~~~~~~~~~~~~~~~~~~

1. **Validate the user ID.** The playbook asserts that ``target_user`` is a valid RACF user ID
   (1 to 8 characters from ``A-Z``, ``0-9``, ``#``, ``$`` and ``@``) and is not ``NONE`` or
   ``UNKNOWN``, because the value goes into an operator command.
2. **Verify connectivity.** The playbook waits for the z/OS host. If the host cannot be reached,
   the command is not attempted and the status is ``Unreachable``.
3. **Issue the command.** The playbook runs ``C U=userid`` with
   ``ibm.ibm_zos_core.zos_operator``. ``ignore_errors`` and ``ignore_unreachable`` keep the host
   in the play, so that the result can be reported.
4. **Classify the result.** The status is derived from the console text, as described in
   `Output`_.
5. **Publish the result.** The status and the detail are published with ``set_stats`` and also set
   as facts on localhost.


Output
------

The playbook publishes the following workflow artifacts with ``set_stats``:

* **admin_decision**: ``approved``.
* **tso_cancel_status**: one of the following:

  * ``Success``: the console returned a response.
  * ``Success (unconfirmed)``: the module succeeded but returned no response text, so the end of
    the session is not confirmed. Check on z/OS.
  * ``No active session``: the console text shows that the user is not logged on.
  * ``Rejected``: the console rejected the command.
  * ``Failed``: the module failed.
  * ``Unreachable``: the z/OS host could not be reached.

* **tso_cancel_detail**: a short text from the module or the console.

The :ref:`1109_notify_investigate` playbook treats ``Success`` and ``No active session`` as OK.
For any other status it shows the manual command ``C U=userid`` in the email.


Prerequisites
-------------

* The AAP job template must include a Machine credential for z/OS SSH access.
* The z/OS user must be permitted to issue the ``C U=`` operator command.
* The ``ibm.ibm_zos_core`` collection version 2.1.0 or later must be installed in the execution
  environment.
* The playbook runs on every host in ``target_hosts``. Make sure that the job template selects only
  the z/OS system that you intend to change.


Notes
-----

* The playbook sets ``gather_facts: false`` because no Ansible facts are required.
* A user with no active session is not an error. It is reported as ``No active session``.
* The statuses are derived from the console text, so a different console message can change how a
  result is classified.
* All output is written to the AAP job log. Restrict access to job logs as required by your
  security policy.


See also
--------

* The :ref:`1109_investigate` playbook that runs before the approval.
* The :ref:`racf_revoke` playbook that runs next.
* The :ref:`1109_notify_investigate` playbook that reports the result.
* To issue the operator command, see the `ibm.ibm_zos_core.zos_operator <https://ibm.github.io/z_ansible_collections_doc/ibm_zos_core/docs/source/modules/zos_operator.html>`_ module.
