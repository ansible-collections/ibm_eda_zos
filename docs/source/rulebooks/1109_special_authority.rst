.. ...........................................................................
.. © Copyright IBM Corporation 2026                                          .
.. ...........................................................................

.. _1109_special_authority:

1109_special_authority - Monitor zSecure alerts from Kafka for SPECIAL authority used by a non-SPECIAL user
===========================================================================================================

.. contents::
   :local:
   :depth: 1


Synopsis
--------

This rulebook monitors zSecure alert C2P1109I that is delivered by Kafka. The alert means that a
user exercised SPECIAL authority that is no longer in their RACF profile.

When the alert is received, the rulebook starts the AAP workflow template
**EDA - Alert 1109 Response Workflow**. The workflow investigates the user, asks an administrator
to approve or deny containment, and reports the outcome by email:

1. :ref:`1109_investigate` reads the RACF profile and the recent command history of the user and
   emails an approval request.
2. An administrator chooses **Approve** or **Deny** in AAP.
3. On approval, :ref:`tso_cancel_user` ends the TSO session and :ref:`racf_revoke` revokes the
   user.
4. :ref:`1109_notify_investigate` emails the outcome. On **Deny** or an expired approval, only
   this job runs, and no action is taken against the user.


Rulebook
--------


.. code-block:: yaml

   - name: Rule to handle alert 1109 - SPECIAL Authority Used by Non-SPECIAL User
     hosts: all

     sources:
       - name: kafka
         ansible.eda.kafka:
           topic: "{{ kafka_topic }}"
           host: "{{ kafka_host }}"
           port: "{{ kafka_port }}"
           security_protocol: "{{ security_protocol }}"
           ssl_cafile: "{{ cafile }}"
           check_hostname: true

         filters:
           - ibm.ibm_eda_zos.security_alerts:
               event_source: "kafka"

     rules:
       - name: Handle SPECIAL Authority Used by Non-SPECIAL User - C2P1109I

         condition:
           all:
             - events.c2p1109i << event.body.alert_code == "C2P1109I"

         action:
           run_workflow_template:
             name: "EDA - Alert 1109 Response Workflow"
             organization: "Default"

Parameters
----------

Sources
~~~~~~~

**kafka**

Connects to a Kafka broker to consume the zSecure alert messages.

**topic**
   The Kafka topic name that carries the zSecure alerts.

   :required: True
   :type: str

**host**
   The Kafka broker hostname or IP address.

   :required: True
   :type: str

**port**
   The Kafka broker port number.

   :required: True
   :type: int

**security_protocol**
   The security protocol for the Kafka connection. Common values are ``SSL`` and ``PLAINTEXT``.

   :required: True
   :type: str

**ssl_cafile**
   Path to the CA certificate file used for SSL/TLS verification.

   :required: True (when using SSL)
   :type: str

**check_hostname**
   Enable SSL hostname verification. Set to ``true`` to verify that the broker hostname matches
   the certificate.

   :required: False
   :default: true
   :type: bool


Filters
~~~~~~~

**ibm.ibm_eda_zos.security_alerts**

Filter plugin that parses the zSecure alert message from Kafka and adds structured fields, such as
``alert_code``, ``hostname`` and ``target_user``, to ``event.body``. Without this filter, the rule
condition does not match because the fields it references do not exist in the raw Kafka payload.

**event_source**
   Specifies the source type of the event stream.

   :required: True
   :type: str
   :choices: kafka


Rules
~~~~~

**Handle SPECIAL Authority Used by Non-SPECIAL User - C2P1109I**

Alert code monitored:

* **C2P1109I**: zSecure alert indicating that SPECIAL authority was used by a user whose RACF
  profile does not carry the SPECIAL attribute.

Condition
^^^^^^^^^

.. code-block:: yaml

   all:
     - events.c2p1109i << event.body.alert_code == "C2P1109I"

The event is stored under the name ``c2p1109i``.

Action
^^^^^^

Launches the AAP workflow template **EDA - Alert 1109 Response Workflow** in the Default
organization. The matched event is available to all jobs of the workflow through
``ansible_eda.events.c2p1109i``. The jobs of the workflow are documented on the playbook pages
listed in `See also`_.


Event structure
---------------

Event c2p1109i (zSecure alert C2P1109I)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The Kafka message carries the alert text in ``body.message`` and the system details in
``body.metadata``. The ``ibm.ibm_eda_zos.security_alerts`` filter adds the fields that the rule
and the workflow use. The following example shows the fields that the filter adds for a C2P1109I
alert. The values are examples only. Fields that the filter does not set for this alert, such as
``dataset``, ``resource`` and ``smf``, are not shown.

.. code-block:: json

   {
     "body": {
       "alert_code": "C2P1109I",
       "alert_message": "C2P1109I non-SPECIAL user USER01 issued SPECIAL command DELDSD 'USER01.TEST.DATA' GENERIC",
       "hostname": "zsys01.example.com",
       "target_user": "USER01",
       "authority_type": "SPECIAL",
       "user_category": "non-SPECIAL"
     }
   }

Event c2p1109i body fields
~~~~~~~~~~~~~~~~~~~~~~~~~~~

* **alert_code**: the zSecure alert code (``C2P1109I``).
* **alert_message**: the alert message text. It includes the SPECIAL command that the user issued.
  The workflow shows it as the triggering command.
* **hostname**: the z/OS system on which the alert was raised, as the first value of the
  ``metadata`` field of the Kafka message.
* **target_user**: the RACF user ID that issued the command.
* **authority_type**: the authority that was used (``SPECIAL``).
* **user_category**: the category of the user (``non-SPECIAL``).

The workflow reads ``alert_code``, ``alert_message``, ``hostname`` and ``target_user``. It does not
use ``authority_type`` and ``user_category``.


Variables
---------

When you activate the rulebook in Ansible Automation Platform, the following variables must be
defined:

.. code-block:: yaml

   kafka_topic: "zsecure-alerts"
   kafka_host: "kafka.example.com"
   kafka_port: 9093
   security_protocol: "SSL"
   cafile: "/path/to/ca-cert.pem"


Examples
--------

Example 1: Verifying the activation
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

After a C2P1109I alert is published to the Kafka topic:

1. In the activation history, confirm that the rule
   **Handle SPECIAL Authority Used by Non-SPECIAL User - C2P1109I** fired.
2. In AAP, open the **EDA - Alert 1109 Response Workflow** run that was started.
3. Check that the approval request email arrived. The workflow waits at the approval step until an
   administrator approves or denies.


Notes
-----

* The rulebook runs continuously, monitoring the Kafka topic for new events.
* Before you activate the rulebook, ensure that the workflow template
  **EDA - Alert 1109 Response Workflow** exists in the Default organization and is accessible in
  AAP.
* The workflow must be created in AAP. It consists of the Investigate job, an approval node, the
  End Session job, the Revoke Access job, and the Notify job, which runs in three nodes. The
  playbooks do not create it.
* The job templates of the workflow run ``C U=userid`` and ``ALTUSER userid REVOKE`` on the hosts
  that the inventory and the job template limit select. Make sure that they select only the z/OS
  system that you intend to change.


Workflow setup
--------------

The rulebook starts the workflow template **EDA - Alert 1109 Response Workflow** in the Default
organization. Create the workflow in AAP with the following nodes. The Notify job template is used
by three nodes, one for each outcome. Define its variables once.

.. list-table::
   :header-rows: 1
   :widths: 5 25 40 30

   * - #
     - Node
     - Job template playbook
     - Runs
   * - 1
     - Investigate
     - :ref:`1109_investigate`
     - First, after the start node.
   * - 2
     - Approval
     - Workflow approval node
     - After Investigate succeeds.
   * - 3
     - End Session
     - :ref:`tso_cancel_user`
     - After Approval succeeds.
   * - 4
     - Revoke
     - :ref:`racf_revoke`
     - After End Session.
   * - 5
     - Notify (success)
     - :ref:`1109_notify_investigate`
     - After Revoke.
   * - 6
     - Notify (denied)
     - :ref:`1109_notify_investigate`
     - After Approval fails.
   * - 7
     - Notify (investigation failed)
     - :ref:`1109_notify_investigate`
     - After Investigate fails.

The approval node timeout is set to 120 minutes and can be customised. If the timeout expires, the
denied path runs, the same as when an administrator denies the request.

Link the nodes as follows:

.. list-table::
   :header-rows: 1
   :widths: 25 30 20 25

   * - From
     - To
     - Link
     - Purpose
   * - Investigate
     - Approval
     - Run on success
     - Ask the administrator to decide.
   * - Investigate
     - Notify (investigation failed)
     - Run on fail
     - Report that the investigation did not finish.
   * - Approval
     - End Session
     - Run on success
     - The administrator approved.
   * - Approval
     - Notify (denied)
     - Run on fail
     - The administrator denied the request, or the approval expired.
   * - End Session
     - Revoke
     - Run always
     - Revoke the user even if the session could not be ended.
   * - Revoke
     - Notify (success)
     - Run always
     - Report the result of the approved path.


Troubleshooting
---------------

* Verify that the C2P1109I alert is published to the Kafka topic.
* Confirm that the ``ibm.ibm_eda_zos.security_alerts`` filter plugin is installed in the decision
  environment and parses the event, so that ``alert_code`` is exactly ``C2P1109I``.
* Review the activation logs for errors.


See also
--------

- Workflow jobs, see :ref:`1109_investigate`, :ref:`tso_cancel_user`, :ref:`racf_revoke`, and
  :ref:`1109_notify_investigate`.
- `Ansible Automation Platform - Getting started as an automation developer <https://docs.redhat.com/en/documentation/red_hat_ansible_automation_platform/2.6/get_started-assembly_gs_auto_dev>`_.
