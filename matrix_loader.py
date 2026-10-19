import yaml
from typing import List


def load_matrix(path: str) -> List[dict]:
    """Load camera matrix from YAML file. Expected format:
    - name: cam1
      host: 192.0.2.10
      username: root
      password: pass
      target_vlan: 20
    """
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or []
    if not isinstance(data, list):
        raise ValueError("matrix file must contain a list of cameras")
    # Basic normalization
    for cam in data:
        if "host" not in cam:
            raise ValueError("each camera needs a host entry")
    return data
