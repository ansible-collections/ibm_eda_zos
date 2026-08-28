##############################################################################
# Copyright (c) IBM Corporation 2026

# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#     http://www.apache.org/licenses/LICENSE-2.0
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
##############################################################################


"""Event filter plugin for processing zSecure user related security alerts.

This module provides an event filter that extracts and structures security
attributes from zSecure events received through Kafka. It parses alert messages
to extract key information such as alert codes, hostnames, data set names, user
information, and other security-relevant data.
"""

from __future__ import annotations
import logging
import re
from typing import Any

# Configure logger for this module
logger = logging.getLogger(__name__)

# Closed list of IBM-shipped base z/OS RACF class names used by resource
# extraction helpers.  Both _get_resource_name and _get_resource_class
# use this constant.
_RACF_CLASSES = (
    "ACCTNUM|APPL|CONSOLE|DATASET|DASDVOL|DIRACC|DIRSRCH|FACILITY|"
    "IPCOBJ|JESINPUT|JESSPOOL|LDAP|LOGSTRM|MSGCLASS|NETVIEW|NODES|"
    "OMVS|OMVSAPPL|OPERCMDS|PIMS|PKISERV|PROPCNTL|PROGRAM|"
    "PTKTDATA|RACFVARS|RDATALIB|RRSFDATA|SERVER|SERVAUTH|STARTED|"
    "SURROGAT|TAPEVOL|TAPEDSN|TERMINAL|TSOPROC|UNIXPRIV|XFACILIT"
)

DOCUMENTATION = r"""
---
short_description: Extract zSecure alert attributes from events.
description:
  - An event filter that extracts zSecure alert attributes from incoming
    events.
  - Extracts alert code, message, hostname, IP address, job name, group name,
    target user, action user and other attributes from alert messages.
  - If errors occur during processing, the original event is returned unchanged
    and errors are logged for debugging.
  - The filter uses defensive programming to ensure the event processing
    pipeline never crashes due to malformed or missing data.
options:
  event_source:
    description:
      - The source of the events coming in.
      - Currently supports 'kafka' as the event source.
      - Events from unsupported sources are passed through unchanged.
    type: str
    default: None
notes:
  - All extracted fields are optional except for the alert message itself.
  - If the alert message cannot be extracted, the event is returned unchanged.
  - Missing optional fields (IP address, job name, etc.) will be set to None.
  - Errors are logged at ERROR level for critical failures and WARNING level
    for missing optional data.
"""

EXAMPLES = r"""
- ansible.eda.kafka:
    host: localhost
    port: 9092
    topic: zsecure-alerts
  filters:
    - ibm.ibm_eda_zos.security_alerts:
        event_source: kafka
"""

# Helper functions


def _is_valid_userid(userid: str) -> bool:
    """Validate if a string is a valid mainframe user ID.

    Validates that the user ID follows mainframe naming conventions after
    stripping trailing punctuation:
    - Length between 2 and 8 characters
    - Must start with a letter
    - Can contain letters, numbers, and special characters (#, @, $)

    Parameters
    ----------
    userid : str
        The user ID string to validate

    Returns
    -------
    bool
        True if the user ID is valid, False otherwise

    """
    max_userid_length = 8  # IBM z/OS TSO/RACF user ID max length
    min_userid_length = 2

    userid = re.sub(r"[^\w\s]+$", "", userid)
    if (not userid or len(userid) > max_userid_length
            or len(userid) < min_userid_length):
        return False

    # Must start with letter
    if not userid[0].isalpha():
        return False

    # Can contain letters, numbers, and special chars (#, @, $)
    valid_chars = set("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789#@$")
    return all(c in valid_chars for c in userid.upper())


# Kafka related events
def _get_full_alert_message_kafka(string: str) -> str | None:
    """Extract the alert message content from within quotation marks.

    Uses regex pattern matching to find and extract text enclosed in
    double quotation marks from a Kafka event message string.

    Parameters
    ----------
    string : str
        The raw message string containing quoted alert text

    Returns
    -------
    str or None
        The extracted alert message with leading/trailing whitespace
        removed, or None if no quoted text is found

    """
    pattern = r"\"(.*?)\""
    pattern_search = re.search(pattern, string, re.DOTALL)
    alert_message = None
    if pattern_search is not None:
        alert_message = re.sub(
            r"\s*\n\s*", " ", pattern_search.group(1).strip()
        )
    return alert_message


def _get_alert_code_kafka(string: str) -> str:
    """Extract the alert code from an alert message.

    Assumes the alert code is always the first space-separated token
    in the alert message string.

    Parameters
    ----------
    string : str
        The alert message string

    Returns
    -------
    str
        The alert code (first word of the message)

    """
    string_split = string.split(" ")
    return string_split[0]


def _get_hostname_kafka(string: str) -> str | None:
    """Extract hostname from metadata string.

    Extracts the hostname from a comma-separated metadata string,
    assuming the hostname is always the first value from CDP.

    Parameters
    ----------
    string : str
        Comma-separated metadata string containing hostname

    Returns
    -------
    str or None
        The hostname (first comma-separated value), or None if the
        string is empty or None

    """
    if not string:
        logger.warning("Metadata string not found")
        return None

    string_split = string.split(",")
    return string_split[0]


def _get_ip_address(string: str) -> str | None:
    """Extract IPv4 address from a string using regex pattern matching.

    Searches for an IPv4 address pattern (e.g., 192.168.1.1) within
    the provided string.

    Parameters
    ----------
    string : str
        The string to search for an IP address

    Returns
    -------
    str or None
        The extracted IPv4 address with whitespace removed, or None if
        no IP address pattern is found

    """
    ip_pattern = r"\b(?:\d{1,3}\.){3}\d{1,3}\b"
    pattern_search = re.search(ip_pattern, string)
    return (
        pattern_search.group(0).strip() if pattern_search is not None else None
    )


def _get_job_name(string: str) -> str | None:
    """Extract job name from an alert message.

    Uses two strategies in order:

    1. Keyword match — searches for the word ``job`` (case-insensitive)
       and returns the immediately following token as the job name.
    2. STC fallback (SMF record type 1301) — if strategy 1 yields nothing,
       searches for the token ``STC`` and returns the token two positions
       ahead if it begins with a leading dot
       (e.g. ``STC <stcname> .<jobname>``), stripping that dot before
       returning.

    Parameters
    ----------
    string : str
        The alert message string to search.

    Returns
    -------
    str or None
        The extracted job name, or ``None`` if neither pattern matches.

    """
    substring = "job"
    string_split = string.split(" ")
    job_name = None
    for idx, strings in enumerate(string_split):
        if strings.lower() == substring and idx < len(string_split) - 1:
            job_name = string_split[idx + 1]
    if job_name is None:
        # Pattern: "...for STC <stcname> .<jobname>" (e.g. 1301)
        for idx, token in enumerate(string_split):
            if token == "STC" and idx < len(string_split) - 2:
                candidate = string_split[idx + 2]
                if candidate.startswith("."):
                    job_name = candidate[1:]
    return job_name


def _get_group_name(string: str) -> str | None:
    """Extract a RACF group name from an alert message.

    Scans the tokens in ``string`` looking for two patterns:

    * ``group <name>`` — preferred (unambiguous; e.g. event 1701)
    * ``in <name>`` — fallback (e.g. events 1107, 1108, 1114)

    Parameters
    ----------
    string : str
        The alert message string to search.

    Returns
    -------
    str or None
        The matched group name, or ``None`` if no valid group name
        is found.

    """
    # RACF group name: 1–8 uppercase alphanumeric or national (#, @, $)
    # characters, must start with a letter.
    racf_group_re = re.compile(r"^[A-Z][A-Z0-9#@$]{0,7}$")
    string_split = string.split(" ")
    group_name = None
    for idx, token in enumerate(string_split):
        if idx >= len(string_split) - 1:
            continue
        candidate = string_split[idx + 1]
        # Prefer the unambiguous "group <name>" pattern (e.g. 1701)
        if token == "group" and racf_group_re.match(candidate):
            return candidate
        # Fall back to "in <name>" pattern (e.g. 1107, 1108, 1114)
        if token == "in" and racf_group_re.match(candidate):
            group_name = candidate
    return group_name


def _get_target_user_name(string: str) -> str | None:
    """Extract target user name from an alert message.

    Searches for various keywords ('from', 'user', 'User', 'superuser',
    'Superuser', 'to', 'for') and extracts the following word as the
    target user name. Validates that the extracted value is a valid
    mainframe user ID.

    Special handling for 'User' keyword: looks for target user after
    subsequent 'from' or 'for' keywords.

    RACF user IDs are always uppercase, so any lowercase token is
    rejected before the userid validator runs. A small blocklist of
    well-known non-userid tokens that share the same uppercase character
    set (e.g. access levels, structural keywords) is also applied.

    Parameters
    ----------
    string : str
        The alert message string to search

    Returns
    -------
    str or None
        The target user name (valid user ID following a keyword), or
        None if no valid user ID is found

    """
    # Tokens that pass _is_valid_userid but are never a user ID in this
    # context.
    non_userid_tokens = frozenset({
        "APF", "UPDATE", "ALTER", "READ", "NONE", "CREATE", "STC",
    })

    substrings = ["from", "user", "User", "superuser", "Superuser",
                  "to", "for"]
    string_split = string.split(" ")
    target_user_name = None
    for idx, strings in enumerate(string_split):
        if strings not in substrings:
            continue

        if strings == "User":
            # Look for target user after "from" or "for" — apply the same
            # guards (no lowercase, not in blocklist) as the main branch.
            for j in range(idx + 2, len(string_split) - 1):
                if string_split[j] in ["from", "for"]:
                    cand = string_split[j + 1]
                    if (not any(c.islower() for c in cand) and
                            cand not in non_userid_tokens and
                            _is_valid_userid(cand)):
                        return cand
            continue

        # 'by user <ID>' belongs to action_user, not target_user —
        # except in C2P1407 ('obtained by user X').
        if (strings == "user" and idx > 0 and
                string_split[idx - 1] == "by" and
                "C2P1407" not in string):
            continue

        if idx >= len(string_split) - 1:
            continue
        candidate = string_split[idx + 1]
        if any(c.islower() for c in candidate):
            continue
        if candidate in non_userid_tokens:
            continue
        if candidate.endswith(":"):
            continue
        if (_is_valid_userid(candidate) and candidate != "user"):
            return candidate
    return target_user_name


def _get_dataset_name(string: str) -> str | None:
    """Extract dataset name from an alert message.

    Handles four distinct patterns found in zSecure alert messages:

    - ``data set <name>`` — most data alerts (1201, 1204, 1209–1214) and
      general_resource alert 1302
    - ``<name> on volume``— APF WTO-based alerts (1205, 1206, 1217, 1218)
      where the dataset name precedes ``on volume`` with no ``data set``
      keyword
    - ``detected: <name>``— APF detected alerts (1207, 1208) where the name
      follows a colon after ``detected``
    - ``set: <name>``— admin profile alerts (1202, 1203, 1215, 1216)
      where the dataset profile name follows ``set:``; dot required to
      exclude RACF class names (e.g. ``FACILITY``) that appear in the same
      position in general resource alerts (1304, 1305, 1307)

    Parameters
    ----------
    string : str
        The alert message string to search

    Returns
    -------
    str or None
        The extracted dataset name, or None if no pattern matches

    """
    pattern = re.search(
        r"data set (\S+\.\S+)"
        r"|(\S+\.\S+) on volume"
        r"|detected:\s*(\S+)"
        r"|\bset:\s*(\S+\.\S+)",
        string,
    )
    if pattern is None:
        return None
    return (
        pattern.group(1) or pattern.group(2)
        or pattern.group(3) or pattern.group(4)
    )


def _get_pds_member(string: str) -> str | None:
    """Extract PDS member name from an alert message.

    Searches for the keyword ``member`` and extracts the following token
    if it matches the MVS member name character set: 1–8 uppercase
    alphanumeric or national characters (``#``, ``@``, ``$``), with no
    dots.

    Parameters
    ----------
    string : str
        The alert message string to search

    Returns
    -------
    str or None
        The PDS member name, or None if no valid member name follows the
        ``member`` keyword

    """
    pattern = re.search(r"\bmember\s+([A-Z0-9#@$]{1,8})\b", string)
    return pattern.group(1) if pattern is not None else None


def _get_volume_serial(string: str) -> str | None:
    """Extract volume serial from an alert message.

    Searches for the phrase ``on volume`` and extracts the token that
    follows. Two formats are handled:

    - A real VOLSER: 1–6 uppercase alphanumeric characters (e.g. ``USER01``)
    - An SMS-managed indicator: angle-bracket phrase (e.g. ``<SMS MANAGED>``)

    Parameters
    ----------
    string : str
        The alert message string to search

    Returns
    -------
    str or None
        The volume serial or SMS indicator, or None if the pattern is
        not found

    """
    pattern = re.search(r"(?i:on volume)\s+([A-Z0-9]{1,6}|<[^>]+>)", string)
    return pattern.group(1) if pattern is not None else None


def _get_program_name(string: str) -> str | None:
    """Extract program name from an alert message.

    Handles two structural patterns found in zSecure alert messages:

    - ``program executed by <user>: <name>`` — UNIX audited program alerts
      (1405, 1406) where the program name follows a colon after the username.
      The name may be a UNIX path (e.g. ``/usr/bin/chprot``) or a bare name
      (e.g. ``rdefcha``).
    - ``program <name>`` — all other alerts (1302, 1408, 1123) where the
      program name is the token directly after the keyword ``program``,
      provided it is not the word ``executed`` (which introduces pattern A).

    Pattern A is tried first so that ``program executed`` messages are
    claimed by the colon-path branch and never fall through to pattern B.

    Parameters
    ----------
    string : str
        The alert message string to search

    Returns
    -------
    str or None
        The program name or path, or None if no pattern matches

    """
    pattern = re.search(
        r"\bprogram\s+executed\s+by\s+\S+:\s*(\S+)"
        r"|\bprogram\s+(?!executed\b)(\S+)",
        string,
    )
    if pattern is None:
        return None
    return pattern.group(1) or pattern.group(2)


def _get_smf_record_type(string: str) -> str | None:
    """Extract the SMF record type number from an alert message.

    Handles three structural patterns found in system alerts:

    - ``SMF record type: <n>``  — alert 1616: direct keyword label
    - ``FOR TYPE <n>``          — alerts 1607, 1608: buried inside the WTO
      message body after the ``msgid`` token
    - ``SMF <n>``               — alert 1611: record type follows ``SMF``
      directly at the start of the message payload

    Parameters
    ----------
    string : str
        The alert message string to search

    Returns
    -------
    str or None
        The SMF record type number as a string, or None if not found

    """
    pattern = re.search(
        r"\bSMF record type:\s*(\S+)"
        r"|\bFOR TYPE\s+(\d+)\b"
        r"|\bSMF\s+(\d+)\b",
        string,
    )
    if pattern is None:
        return None
    return next(g for g in pattern.groups() if g is not None)


def _get_smf_subsystem(string: str) -> str | None:
    """Extract the SMF subsystem identifier from an alert message.

    Searches for the keyword ``SUBSYS:`` and returns the token that
    immediately follows.

    Parameters
    ----------
    string : str
        The alert message string to search

    Returns
    -------
    str or None
        The subsystem identifier, or None if ``SUBSYS:`` is not present

    """
    pattern = re.search(r"\bSUBSYS:\s*(\S+)", string)
    return pattern.group(1) if pattern is not None else None


def _get_smf_records_lost(string: str) -> str | None:
    """Extract the number of SMF records lost from an alert message.

    Searches for a digit sequence immediately before the phrase
    ``records lost``.

    Parameters
    ----------
    string : str
        The alert message string to search

    Returns
    -------
    str or None
        The record-loss count as a string, or None if not found

    """
    pattern = re.search(r"\b(\d+)\s+records lost\b", string)
    return pattern.group(1) if pattern is not None else None


def _get_wto_msgid(string: str) -> str | None:
    """Extract the WTO message ID from an alert message.

    Uses ``WTO msgid:\\s*(\\S+)`` to handle inconsistent spacing after the
    ``WTO msgid:`` keyword

    Parameters
    ----------
    string : str
        The alert message string to search

    Returns
    -------
    str or None
        The WTO message ID token, or None if ``WTO msgid:`` is not present

    """
    pattern = re.search(r"\bWTO msgid:\s*(\S+)", string, re.IGNORECASE)
    return pattern.group(1) if pattern is not None else None


def _get_user_category(string: str) -> str | None:
    """Extract the user category from an alert message.

    Searches for the pattern ``non-<TYPE> user`` and returns the full
    ``non-<TYPE>`` token as the user category (e.g. ``non-SPECIAL``,
    ``non-OPERATIONS``).

    Parameters
    ----------
    string : str
        The alert message string to search

    Returns
    -------
    str or None
        The user category string (e.g. ``non-SPECIAL``), or None if the
        pattern is not found

    """
    pattern = re.search(r"\b(non-\S+)\s+user", string)
    return pattern.group(1) if pattern is not None else None


def _get_authority_type(string: str) -> str | None:
    """Extract the authority type from an alert message.

    Handles two structural patterns found in user alert messages:

    - ``authority <TYPE>``   — alerts 1105, 1106, 1114: authority type is
      the token immediately after ``authority``
    - ``non-<TYPE> user``    — alert 1109 only: authority type is embedded
      in the ``non-SPECIAL`` prefix

    Parameters
    ----------
    string : str
        The alert message string to search

    Returns
    -------
    str or None
        The authority type string, or None if no pattern matches

    """
    pattern = re.search(r"\bauthority\s+([A-Z]+)\b", string)
    if pattern is not None:
        return pattern.group(1)
    if "C2P1109" in string:
        match = re.search(r"\bnon-(\S+)\s+user", string)
        if match:
            return match.group(1)
    return None


def _get_access_level(string: str) -> str | None:
    """Extract the access level from an alert message.

    Handles the following structural patterns found across alert categories:

    - ``WARNING mode <LEVEL> by``           — alerts 1201, 1303: level follows
      ``WARNING mode`` and precedes ``by``
    - ``<LEVEL> access by``                 — alerts 1209–1213: level is the
      token immediately before ``access``
    - ``UACC/access set to <LEVEL>``        — alert 1304 (``UACC``) and alerts
      1202, 1203 (``access``)
    - ``Intent <LEVEL>``                    — alert 1110: level follows the
      keyword ``Intent``
    - ``Global <level> specified``          — alerts 1402, 1403: level is
      between ``Global`` and ``specified``

    Patterns are tried in order; the first match is returned.

    Parameters
    ----------
    string : str
        The alert message string to search

    Returns
    -------
    str or None
        The access level string, or None if no pattern matches

    """
    pattern = re.search(
        r"\bWARNING\s+mode\s+(\S+)\s+by"
        r"|\b(\S+)\s+access\s+by"
        r"|\b(?:UACC|access)\s+set\s+to\s+(\S+)"
        r"|\bIntent\s+(\S+)"
        r"|\bon\s+(\S+)\s+sensitive"
        r"|\bGlobal\s+(\S+)\s+specified",
        string,
    )
    if pattern is not None:
        return next(g for g in pattern.groups() if g is not None)
    return None


def _get_unix_path(string: str) -> str | None:
    """Extract UNIX file or directory path from an alert message.

    Handles three structural patterns found in UNIX alert messages:

    - ``on <path>``          — alerts 1401–1403: path contains a slash
    - ``directory <name>``   — alert 1404: bare name after ``directory``
    - ``for <name>``         — alert 1409 only: bare name after ``for``;

    Parameters
    ----------
    string : str
        The alert message string to search

    Returns
    -------
    str or None
        The UNIX path or name, or None if no pattern matches

    """
    pattern = re.search(
        r"\bon\s+(\.?\S*\/\S+)"
        r"|\bdirectory\s+(\S+)",
        string,
    )
    if pattern is not None:
        return pattern.group(1) or pattern.group(2)
    if "C2P1409" in string:  # edge case: bare name after 'for' (1409)
        match = re.search(r"\bfor\s+(\S+)", string)
        if match:
            return match.group(1)
    return None


def _get_resource_name(string: str) -> str | None:
    """Extract RACF resource name from an alert message.

    Handles three structural patterns found across alert categories:

    - ``Resource <name>``              — user_events (1110): explicit
      ``Resource`` label precedes the resource name token
    - ``on <known-class> <name>`` /    — general_resource (1303–1307):
      resource name is the token immediately after the class name
    - ``permit on <name>``             — unix_event (1411): resource name
      follows ``permit on`` directly with no class keyword present

    Parameters
    ----------
    string : str
        The alert message string to search

    Returns
    -------
    str or None
        The resource name, or None if no pattern matches

    """
    pattern = re.search(
        r"\bResource\s+(\S+)"
        r"|(?:on|:)\s+(?:" + _RACF_CLASSES + r")\s+(\S+)"
        r"|\bpermit\s+on\s+(\S+)",
        string,
    )
    if pattern is None:
        return None
    return next(g for g in pattern.groups() if g is not None)


def _get_resource_class(string: str) -> str | None:
    """Extract RACF resource class from an alert message.

    Handles the following structural patterns across alert categories:

    - ``activated/deactivated: <CLASS>`` — racf_control (1504, 1505): class
      activation/deactivation.
    - ``[Cc]lass <UPPER-TOKEN>``         — user_events (1110) uses ``Class``;
      racf_control (1506, 1507) uses lowercase ``class``.
    - ``:<whitespace><known-class>``     — general_resource (1304, 1305, 1307):
      class name follows a colon. Uses _RACF_CLASSES to avoid arbitrary tokens.
    - ``on <known-class>``               — general_resource (1303): class name
      follows ``on``.
    - ``C2P…I <known-class>/``           — general_resource (1301): class name
      precedes the ``/`` of a profile pattern.

    Parameters
    ----------
    string : str
        The alert message string to search

    Returns
    -------
    str or None
        The RACF resource class name, or None if no pattern matches

    """
    pattern = re.search(
        r"(?:activated|deactivated):\s*(\S+)"
        r"|\b[Cc]lass\s+([A-Z][A-Z0-9#@$]*)"
        r"|:\s*(" + _RACF_CLASSES + r")\b"
        r"|\bon\s+(" + _RACF_CLASSES + r")\b"
        r"|\bC2P\w+I\s+(" + _RACF_CLASSES + r")/",
        string,
    )
    if pattern is None:
        return None
    return next(g for g in pattern.groups() if g is not None)


def _get_action_user_name(string: str) -> str | None:
    """Extract the action user (the user who performed the action)
    from an alert message.

    Three extraction strategies are tried in order:

    1. **``User <ID>``** — uppercase ``User`` followed immediately by a valid
       user ID (edge-case pattern; returned immediately on first match).
    2. **``by <ID>``** — user ID following the keyword ``by``.  The literal
       token ``user`` is treated as an English keyword and skipped so that
       ``by user C##ASCH`` correctly yields ``C##ASCH``.
    3. **Alert-code fallback** — for alerts that carry no ``by`` keyword
       (C2P1410, C2P1701), the first token after the alert code is used.

    Parameters
    ----------
    string : str
        The alert message string to search.

    Returns
    -------
    str or None
        The action user ID, or ``None`` if no valid user ID is found.

    """
    substring = "by"
    string_split = string.split(" ")
    action_user_name = None

    # Check for "User X" pattern (action user at start edge case)
    for idx, strings in enumerate(string_split):
        if (strings == "User" and
                idx < len(string_split) - 1 and
                _is_valid_userid(string_split[idx + 1])):
            return string_split[idx + 1]

    # C2P1407I: 'Superuser privileged shell obtained by user X' — the subject
    # is the target user, not an action user; skip 'by' extraction entirely.
    if "C2P1407" not in string:
        for idx, strings in enumerate(string_split):
            if (strings == substring and
                    idx < len(string_split) - 1 and
                    string_split[idx + 1] != "unknown" and
                    _is_valid_userid(string_split[idx + 1])):
                candidate = string_split[idx + 1]

                if candidate == "user" and idx < len(string_split) - 2:
                    candidate = string_split[idx + 2]
                    if not _is_valid_userid(candidate):
                        continue

                if any(c.islower() for c in candidate):
                    continue
                action_user_name = candidate.rstrip(":")
    # C2P1410/C2P1701 lead with '<USER> assigned …' / '<USER> issued connect …'
    # — no 'by' keyword, so grab the first token after the alert code.
    if action_user_name is None and (
            "C2P1410" in string or "C2P1701" in string):
        m = re.search(r"\bC2P\w+I\s+(\S+)", string)
        if m and _is_valid_userid(m.group(1)):
            action_user_name = m.group(1)
    return action_user_name


def main(event: dict[str, Any], event_source: str | None = None) -> (
        dict[str, Any]):
    """Extract zSecure alert attributes and add them to the event.

    Processes Kafka events and extracts security-related attributes from
    the alert message.  On any error the original event is returned
    unchanged and the error is logged.

    Parameters
    ----------
    event : dict[str, Any]
        The event dictionary to process, expected to contain ``body`` with
        ``message`` and ``metadata`` fields for Kafka events.
    event_source : str or None, optional
        The source of the event (e.g. ``'kafka'``).  Events from
        unsupported sources are passed through unchanged.  Default is
        ``None``.

    Returns
    -------
    dict[str, Any]
        The event dictionary with extracted attributes added to ``body``,
        or the original event unchanged if processing fails or the source
        is not supported.

    Notes
    -----
    Fields added to ``event['body']``:

    - ``alert_message`` : str — full alert message text
    - ``alert_code`` : str — alert code identifier
    - ``hostname`` : str or None — source hostname
    - ``ip_address`` : str or None — IPv4 address
    - ``job_name`` : str or None — job name
    - ``group_name`` : str or None — RACF group name
    - ``target_user`` : str or None — user ID acted upon
    - ``action_user`` : str or None — user ID that performed the action
    - ``unix_path`` : str or None — UNIX file path
    - ``access_level`` : str or None — access level
    - ``authority_type`` : str or None — authority type
    - ``user_category`` : str or None — user category
    - ``dataset['dataset_name']`` : str or None — data set name
    - ``dataset['pds_member']`` : str or None — PDS member name
    - ``dataset['volume_serial']`` : str or None — volume serial
    - ``dataset['program_name']`` : str or None — program name
    - ``resource['resource_class']`` : str or None — RACF resource class
    - ``resource['resource_name']`` : str or None — resource name
    - ``smf['smf_record_type']`` : str or None — SMF record type
    - ``smf['smf_subsystem']`` : str or None — SMF subsystem identifier
    - ``smf['smf_records_lost']`` : str or None — number of SMF records lost
    - ``smf['wto_msgid']`` : str or None — WTO message identifier

    """
    if event_source == "kafka":
        try:
            # Safely access event body and message
            body = event.get("body")
            if not body:
                logger.error("Event missing 'body' field")
                return event

            given_alert_message = body.get("message")
            if not given_alert_message:
                logger.error("Event body missing 'message' field")
                return event

            # Extract alert message from quotes
            alert_msg = _get_full_alert_message_kafka(
                given_alert_message)
            if alert_msg:
                body["alert_message"] = alert_msg
            else:
                logger.warning("Could not extract alert message from event")
                return event

            # Extract alert code
            body["alert_code"] = _get_alert_code_kafka(alert_msg)

            # Extract hostname from metadata
            metadata_string = body.get("metadata", "")
            hostname = _get_hostname_kafka(metadata_string)
            if hostname:
                body["hostname"] = hostname
                logger.debug("Extracted hostname: %s", hostname)
            else:
                logger.warning("Could not extract hostname from metadata")

            # Initialise nested sub-dicts
            body["dataset"], body["resource"], body["smf"] = {}, {}, {}

            # Extract optional fields - failures are acceptable
            body["ip_address"] = _get_ip_address(alert_msg)
            body["job_name"] = _get_job_name(alert_msg)
            body["group_name"] = _get_group_name(alert_msg)
            body["target_user"] = _get_target_user_name(alert_msg)
            body["action_user"] = _get_action_user_name(alert_msg)
            body["dataset"]["dataset_name"] = _get_dataset_name(alert_msg)
            body["dataset"]["pds_member"] = _get_pds_member(alert_msg)
            body["dataset"]["volume_serial"] = _get_volume_serial(alert_msg)
            body["dataset"]["program_name"] = _get_program_name(alert_msg)
            body["resource"]["resource_class"] = _get_resource_class(alert_msg)
            body["resource"]["resource_name"] = _get_resource_name(alert_msg)
            body["smf"]["smf_record_type"] = _get_smf_record_type(alert_msg)
            body["smf"]["smf_subsystem"] = _get_smf_subsystem(alert_msg)
            body["smf"]["smf_records_lost"] = _get_smf_records_lost(alert_msg)
            body["smf"]["wto_msgid"] = _get_wto_msgid(alert_msg)
            body["unix_path"] = _get_unix_path(alert_msg)
            body["access_level"] = _get_access_level(alert_msg)
            body["authority_type"] = _get_authority_type(alert_msg)
            body["user_category"] = _get_user_category(alert_msg)

        except KeyError:
            logger.exception("Missing required field in event")
        except (ValueError, TypeError, AttributeError):
            logger.exception("Error processing event data")
        else:
            logger.debug("Successfully processed zSecure alert event")
        return event

    # Non-kafka events are passed through unchanged
    logger.debug("Event source '%s' not supported, returning event "
                 "unchanged", event_source)
    return event
