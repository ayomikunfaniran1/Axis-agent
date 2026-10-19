import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from typing import Dict, Any


class AxisClient:
    def __init__(self, host: str, username: str = None, password: str = None, timeout: int = 10, scheme: str = "http"):
        self.host = host
        self.username = username
        self.password = password
        self.scheme = scheme
        self.base = f"{scheme}://{host}"
        self.timeout = timeout
        self.session = requests.Session()
        retries = Retry(total=3, backoff_factor=0.5, status_forcelist=(500, 502, 503, 504))
        self.session.mount("http://", HTTPAdapter(max_retries=retries))
        if username and password:
            self.session.auth = (username, password)

    def _get(self, path: str, params=None) -> Dict[str, Any]:
        url = f"{self.base}{path}"
        r = self.session.get(url, params=params, timeout=self.timeout)
        r.raise_for_status()
        return r.text

    def _post(self, path: str, data=None) -> Dict[str, Any]:
        url = f"{self.base}{path}"
        r = self.session.post(url, data=data or {}, timeout=self.timeout)
        r.raise_for_status()
        return r.text

    def get_network_config(self) -> Dict[str, Any]:
        # Try Axis parameter list CGI
        try:
            text = self._get("/axis-cgi/admin/param.cgi", params={"action": "list", "group": "Network"})
            # return as raw text for snapshot; parsing could be added
            return {"host": self.host, "raw": text}
        except Exception:
            # Fallback to a minimal snapshot
            return {"host": self.host}

    def set_vlan(self, vlan: int) -> Dict[str, Any]:
        # Axis cameras differ; many accept param.cgi for network/VLAN settings
        # We'll attempt setting through a common param endpoint.
        data = {"action": "update", "Network.VLAN.ID": str(vlan)}
        try:
            res = self._post("/axis-cgi/admin/param.cgi", data=data)
            return {"host": self.host, "applied": True, "response": res}
        except Exception as e:
            raise RuntimeError(f"failed to set vlan on {self.host}: {e}")

    def restore_network_config(self, snapshot: Dict[str, Any]) -> Dict[str, Any]:
        # Best-effort restore: if snapshot includes raw param dump, we can't reliably parse all keys.
        # If snapshot contains structured keys, apply them. Otherwise, return snapshot.
        # This is a safe best-effort operation; real implementations should parse param dump.
        if not snapshot:
            raise RuntimeError("no snapshot provided")
        # If snapshot contains raw param dump, do not attempt blind restore in this generic agent.
        # Implement a conservative reply to indicate what should be done.
        return {"host": self.host, "restored": False, "reason": "no structured snapshot to restore"}

    # --- User / permission helpers (best-effort) ---
    def get_users(self) -> Dict[str, Any]:
        """Attempt to fetch user list / permissions from the device.

        Returns a best-effort dict. Axis devices expose different endpoints depending on firmware.
        This method will try a few common endpoints and return raw responses.
        """
        candidates = [
            ("/axis-cgi/admin/param.cgi", {"action": "list", "group": "User"}),
            ("/axis-cgi/admin/userlist.cgi", None),
        ]
        out = {"host": self.host, "sources": []}
        for path, params in candidates:
            try:
                if params is not None:
                    res = self._get(path, params=params)
                else:
                    res = self._get(path)
                out["sources"].append({"path": path, "response": res})
            except Exception as e:
                out["sources"].append({"path": path, "error": str(e)})
        return out

    def set_user_admin(self, username: str, make_admin: bool = True) -> Dict[str, Any]:
        """Best-effort attempt to set a user's admin rights.

        This is conservative: many Axis models require HTTPS/form authentication or direct config file edits.
        The agent will attempt to call common param update endpoints but will not perform destructive changes.
        """
        # Try param.cgi update patterns
        param_key = "User.{}.Admin".format(username)
        data = {"action": "update", param_key: "1" if make_admin else "0"}
        try:
            res = self._post("/axis-cgi/admin/param.cgi", data=data)
            return {"host": self.host, "applied": True, "response": res}
        except Exception as e:
            raise RuntimeError(f"failed to set admin flag for {username} on {self.host}: {e}")

    def set_root_password(self, new_password: str) -> Dict[str, Any]:
        """Best-effort attempt to set the root password.

        Axis devices expose different parameter names; try common patterns via param.cgi.
        This method is conservative: it will attempt an `update` action for likely keys.
        """
        candidates = [
            {"action": "update", "root.Password": new_password},
            {"action": "update", "User.root.Password": new_password},
            {"action": "update", "User.1.Password": new_password},
        ]
        for data in candidates:
            try:
                res = self._post("/axis-cgi/admin/param.cgi", data=data)
                return {"host": self.host, "applied": True, "response": res, "used": data}
            except Exception:
                continue
        raise RuntimeError(f"failed to set root password on {self.host}: no supported endpoint succeeded")

    def set_static_ip(self, ip: str, netmask: str = "255.255.255.0", gateway: str = None) -> Dict[str, Any]:
        """Attempt to set static IP configuration.

        Tries common parameter keys. Not all models accept the same keys; this is best-effort.
        """
        # Common Axis params: Network.DHCP.Enabled, Network.IPAddress, Network.SubnetMask, Network.Gateway
        data = {
            "action": "update",
            "Network.DHCP.Enabled": "0",
            "Network.IPAddress": ip,
            "Network.SubnetMask": netmask,
        }
        if gateway:
            data["Network.Gateway"] = gateway
        try:
            res = self._post("/axis-cgi/admin/param.cgi", data=data)
            return {"host": self.host, "applied": True, "response": res}
        except Exception as e:
            raise RuntimeError(f"failed to set static IP on {self.host}: {e}")
