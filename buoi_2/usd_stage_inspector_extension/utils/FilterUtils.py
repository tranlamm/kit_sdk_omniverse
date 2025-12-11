import re
import fnmatch

def _match_filter(text, pattern, use_regex=False, use_wildcard=False):
    if not pattern:
        return True

    if use_regex:
        try:
            return re.search(pattern, text) is not None
        except re.error:
            return False

    if use_wildcard:
        return fnmatch.fnmatch(text, pattern)

    return pattern.lower() == text.lower()