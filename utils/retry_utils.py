import re


def parse_retry_delay_seconds(error_message: str) -> int | None:
    """Extract a retry delay in seconds from a provider error message."""

    match = re.search(r"retry in ([\d.]+)s", error_message, flags=re.IGNORECASE)
    if not match:
        return None
    return max(1, int(float(match.group(1))))
