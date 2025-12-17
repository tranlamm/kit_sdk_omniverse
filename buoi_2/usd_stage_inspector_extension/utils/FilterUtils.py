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

def find_all_multi_source_attributes(
    min_sources: int = 2,
    stop_after_first: bool = False,
):
    """
    Duyệt toàn bộ stage và tìm các prim.attribute
    có Property Stack >= min_sources.

    Args:
        min_sources (int): số source tối thiểu (default = 2)
        stop_after_first (bool): True → dừng sau kết quả đầu tiên

    Returns:
        list[dict]: danh sách kết quả
    """
    stage = omni.usd.get_context().get_stage()
    if not stage:
        print("[USD] No active stage")
        return []

    results = []

    for prim in stage.Traverse():
        if not prim.IsValid():
            continue

        for attr in prim.GetAttributes():
            if not attr.IsValid():
                continue

            try:
                prop_stack = attr.GetPropertyStack()
            except Exception:
                continue

            if not prop_stack or len(prop_stack) < min_sources:
                continue

            print(prop_stack)
            entry = {
                "prim_path": str(prim.GetPath()),
                "attr_name": attr.GetName(),
                "source_count": len(prop_stack),
                "layers": [
                    spec.layer.identifier if spec.layer else "N/A"
                    for spec in prop_stack
                ],
            }

            results.append(entry)

            if stop_after_first:
                return results

    return results