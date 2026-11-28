from pathlib import Path


def is_safe_path_segment(segment: str) -> bool:
    """Return True if segment is a single filename/ID with no path traversal chars."""
    return (
        bool(segment)
        and segment not in {".", ".."}
        and "/" not in segment
        and "\\" not in segment
        and "\x00" not in segment
    )


def resolve_user_item_dir(
    base_dir: Path,
    user_id: str,
    item_id: str,
) -> Path | None:
    """Resolve <base_dir>/<user_id>/<item_id> only if it stays strictly inside the user's directory."""
    if not is_safe_path_segment(user_id) or not is_safe_path_segment(item_id):
        return None
    user_dir = (base_dir / user_id).resolve()
    item_dir = (user_dir / item_id).resolve()
    if item_dir.parent != user_dir:
        return None
    return base_dir / user_id / item_id
