from typing import Tuple, Dict


def validate_vlan(vlan: int, cfg: Dict) -> Tuple[bool, str]:
    """Validate VLAN according to configuration.
    cfg may include: min, max, allowed (list), blocked (list)
    """
    if not isinstance(vlan, int):
        return False, "vlan must be integer"
    if vlan < 1 or vlan > 4094:
        return False, "vlan out of range 1-4094"
    allowed = cfg.get("allowed")
    blocked = cfg.get("blocked")
    if allowed is not None:
        if vlan not in allowed:
            return False, "vlan not in allowed list"
    if blocked is not None and vlan in blocked:
        return False, "vlan is blocked"
    vmin = cfg.get("min")
    vmax = cfg.get("max")
    if vmin is not None and vlan < int(vmin):
        return False, f"vlan < min ({vmin})"
    if vmax is not None and vlan > int(vmax):
        return False, f"vlan > max ({vmax})"
    return True, ""
