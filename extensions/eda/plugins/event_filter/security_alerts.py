################################################################################
# Copyright (c) IBM Corporation 2026
################################################################################

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

from __future__ import annotations
import logging
import re
from typing import Any

# Configure logger for this module
logger = logging.getLogger(__name__)

DOCUMENTATION = r"""
---
short_description: Extract zSecure alert attributes from events.
description:
  - An event filter that extracts zSecure alert attributes from incoming events.
  - Extracts alert code, message, hostname, IP address, job name, group name,
    target user, and action user from alert messages.
  - If errors occur during processing, the original event is returned unchanged
    and errors are logged for debugging.
  - The filter uses defensive programming to ensure the event processing pipeline
    never crashes due to malformed or missing data.
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
    - ibm.ibm_z_solutions.security_alerts:
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
    if not userid or len(userid) > max_userid_length or len(userid) < min_userid_length:
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
    pattern_search = re.search(pattern, string)
    alert_message = None
    if pattern_search is not None:
        alert_message = pattern_search.group(1).strip()
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
    return pattern_search.group(0).strip() if pattern_search is not None else None


def _get_job_name(string: str) -> str | None:
    """Extract job name from an alert message.

    Searches for the keyword 'job' (case-insensitive) and extracts
    the following word as the job name.

    Parameters
    ----------
    string : str
        The alert message string to search

    Returns
    -------
    str or None
        The job name (word following 'job'), or None if 'job' keyword
        is not found or is the last word in the string

    """
    substring = "job"
    string_split = string.split(" ")
    job_name = None
    for idx, strings in enumerate(string_split):
        if strings.lower() == substring and idx < len(string_split) - 1:
            job_name = string_split[idx + 1]
    return job_name


def _get_group_name(string: str) -> str | None:
    """Extract group name from an alert message.

    Searches for the keyword 'in' and extracts the following word
    as the group name.

    Parameters
    ----------
    string : str
        The alert message string to search

    Returns
    -------
    str or None
        The group name (word following 'in'), or None if 'in' keyword
        is not found or is the last word in the string

    """
    substring = "in"
    string_split = string.split(" ")
    group_name = None
    for idx, strings in enumerate(string_split):
        if strings == substring and idx < len(string_split) - 1:
            group_name = string_split[idx + 1]
    return group_name


def _get_target_user_name(string: str) -> str | None:
    """Extract target user name from an alert message.

    Searches for various keywords ('from', 'user', 'User', 'superuser',
    'Superuser', 'to', 'for') and extracts the following word as the
    target user name. Validates that the extracted value is a valid
    mainframe user ID.

    Special handling for 'User' keyword: looks for target user after
    subsequent 'from' or 'for' keywords.

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
    substrings = ["from", "user", "User", "superuser", "Superuser",
                  "to", "for"]
    string_split = string.split(" ")
    target_user_name = None
    for idx, strings in enumerate(string_split):
        if strings in substrings and idx < len(string_split) - 1:
                if strings == "User":
                    # Look for target user after "from" or "for"
                    for j in range(idx + 2, len(string_split) - 1):
                        if string_split[j] in ["from", "for"] and _is_valid_userid(string_split[j + 1]):
                                return string_split[j + 1]
                    continue

                if (_is_valid_userid(string_split[idx + 1]) and
                        string_split[idx + 1] != "user"):
                    return string_split[idx + 1]
    return target_user_name


def _get_action_user_name(string: str) -> str | None:
    """Extract action user name from an alert message.

    Searches for the keyword 'by' or the pattern 'User X' and extracts
    the user who performed the action. Validates that the extracted value
    is a valid mainframe user ID and not 'unknown'.

    First checks for 'User X' pattern at the start (edge case), then
    searches for user ID following 'by' keyword.

    Parameters
    ----------
    string : str
        The alert message string to search

    Returns
    -------
    str or None
        The action user name (valid user ID following 'by' or after
        'User'), or None if no valid user ID is found

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

    for idx, strings in enumerate(string_split):
        if (strings == substring and
            idx < len(string_split) - 1 and
            string_split[idx + 1] != "unknown" and
            _is_valid_userid(string_split[idx + 1])):
                action_user_name = string_split[idx + 1]
    return action_user_name


def main(event: dict[str, Any], event_source: str | None = None) -> (
        dict[str, Any]):
    """Extract zSecure alert attributes and add them to the event.

    This filter processes events from various sources (currently supports
    Kafka) and extracts security-related attributes including alert code,
    message, hostname, IP address, job name, group name, target user, and
    action user.

    If any errors occur during processing, the original event is returned
    unchanged and errors are logged. Uses defensive programming to ensure
    the event processing pipeline never crashes.

    Parameters
    ----------
    event : dict[str, Any]
        The event dictionary to process, expected to contain 'body' with
        'message' and 'metadata' fields for Kafka events
    event_source : str or None, optional
        The source of the event (e.g., 'kafka'). Events from unsupported
        sources are passed through unchanged. Default is None.

    Returns
    -------
    dict[str, Any]
        The event dictionary with extracted attributes added to the
        'body', or the original event unchanged if processing fails or
        source is not supported

    Notes
    -----
    Extracted fields added to event body:
    - alert_message : str - The full alert message text
    - alert_code : str - The alert code identifier
    - hostname : str or None - The source hostname
    - ip_address : str or None - IPv4 address if present
    - job_name : str or None - Job name if present
    - group_name : str or None - Group name if present
    - target_user : str or None - Target user ID if present
    - action_user : str or None - Action user ID if present

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
            alert_message = _get_full_alert_message_kafka(
                given_alert_message)
            if alert_message:
                body["alert_message"] = alert_message
            else:
                logger.warning("Could not extract alert message from event")
                return event

            # Extract alert code
            body["alert_code"] = _get_alert_code_kafka(alert_message)

            # Extract hostname from metadata
            metadata_string = body.get("metadata", "")
            hostname = _get_hostname_kafka(metadata_string)
            if hostname:
                body["hostname"] = hostname
                logger.debug("Extracted hostname: %s", hostname)
            else:
                logger.warning("Could not extract hostname from metadata")

            # Extract optional fields - failures are acceptable
            body["ip_address"] = _get_ip_address(alert_message)
            body["job_name"] = _get_job_name(alert_message)
            body["group_name"] = _get_group_name(alert_message)
            body["target_user"] = _get_target_user_name(alert_message)
            body["action_user"] = _get_action_user_name(alert_message)

        except KeyError:
            logger.exception("Missing required field in event: %s")
        except Exception:
            logger.exception("Unexpected error processing event: %s")
        else:
            logger.debug("Successfully processed zSecure alert event")
        return event


    # Non-kafka events are passed through unchanged
    logger.debug("Event source '%s' not supported, returning event "
                    "unchanged", event_source)
    return event
