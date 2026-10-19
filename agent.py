#!/usr/bin/env python3
import argparse
import logging
import os
import json
from typing import List

from matrix_loader import load_matrix
from vlan_validator import validate_vlan
from axis_client import AxisClient
from rollback import ActionStore
import yaml

LOG = logging.getLogger("axis-agent")

# Common default credentials to check for. This list is configurable and conservative.
DEFAULT_CREDENTIALS = [
    ("root", "root"),
    ("root", "pass"),
    ("root", "password"),
    ("root", ""),
    ("admin", "admin"),
    ("admin", "password"),
]


def setup_logging(level=logging.INFO):
    handler = logging.StreamHandler()
    fmt = '{"time": "%(asctime)s", "level": "%(levelname)s", "name": "%(name)s", "message": %(message)s}'
    handler.setFormatter(logging.Formatter(fmt))
    root = logging.getLogger()
    root.setLevel(level)
    root.handlers[:] = []
    root.addHandler(handler)


def load_config(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def apply_changes(cameras: List[dict], cfg: dict, dry_run: bool, simulate: bool = False):
    session_opts = cfg.get("http", {})
    action_store = ActionStore(cfg.get("action_log", "actions.log"))
    for cam in cameras:
        name = cam.get("name") or cam.get("host")
        try:
            vlan = int(cam["target_vlan"])
        except Exception:
            LOG.error(json.dumps({"camera": name, "error": "missing target_vlan"}))
            continue
        ok, reason = validate_vlan(vlan, cfg.get("vlan", {}))
        if not ok:
            LOG.error(json.dumps({"camera": name, "error": "vlan validation failed", "reason": reason}))
            continue

        # Simulation mode: do not contact real devices; generate safe simulated snapshots
        if simulate:
            before = {"host": cam.get("host"), "simulated": True}
            LOG.info(json.dumps({"camera": name, "action": "snapshot_simulated", "snapshot": before}))
            if dry_run:
                LOG.info(json.dumps({"camera": name, "action": "dry-run-simulated", "target_vlan": vlan}))
                action_store.record(name, before, {"target_vlan": vlan, "applied": False, "simulated": True}, cam)
                continue
            # Simulate applying VLAN
            after = {"host": cam.get("host"), "applied": True, "simulated": True, "target_vlan": vlan}
            LOG.info(json.dumps({"camera": name, "action": "applied_simulated", "result": after}))
            action_store.record(name, before, after, cam)
            continue

        client = get_working_client(cam.get("host"), cam.get("username"), cam.get("password"), session_opts)
        try:
            before = client.get_network_config()
            LOG.info(json.dumps({"camera": name, "action": "snapshot", "snapshot": before}))
            if dry_run:
                LOG.info(json.dumps({"camera": name, "action": "dry-run", "target_vlan": vlan}))
                action_store.record(name, before, {"target_vlan": vlan, "applied": False}, cam)
                continue

            after = client.set_vlan(vlan)
            LOG.info(json.dumps({"camera": name, "action": "applied", "result": after}))
            action_store.record(name, before, after, cam)
        except Exception as e:
            LOG.error(json.dumps({"camera": name, "error": str(e)}))


def check_default_passwords(cameras: List[dict], cfg: dict, verify: bool = False, simulate: bool = False):
    """Scan the camera matrix for default or missing credentials.

    If `verify` is True, attempt to authenticate to the device to confirm.
    If `simulate` is True, skip network verification and only analyze the matrix.
    """
    session_opts = cfg.get("http", {})
    findings = []
    for cam in cameras:
        name = cam.get("name") or cam.get("host")
        user = cam.get("username") or ""
        pwd = cam.get("password") if cam.get("password") is not None else ""
        if (user, pwd) in DEFAULT_CREDENTIALS or pwd == "" or user == "":
            entry = {"camera": name, "host": cam.get("host"), "username": user, "password_present": bool(pwd), "default_credential": (user, pwd) in DEFAULT_CREDENTIALS}
            if verify and not simulate:
                client = AxisClient(host=cam["host"], username=user or None, password=pwd or None, **session_opts)
                try:
                    # attempt a simple authenticated read
                    client.get_network_config()
                    entry.update({"verified": True})
                except Exception as e:
                    entry.update({"verified": False, "verify_error": str(e)})
            findings.append(entry)
            LOG.warning(json.dumps({"camera": name, "issue": "default-or-missing-credentials", "details": entry}))
    if not findings:
        LOG.info(json.dumps({"action": "check-defaults", "result": "no-defaults-found"}))
    return findings


def rollback(cfg: dict, count: int = 1, camera_name: str = None):
    action_store = ActionStore(cfg.get("action_log", "actions.log"))
    entries = action_store.load()
    if camera_name:
        entries = [e for e in entries if e.get("camera") == camera_name]
    if not entries:
        LOG.warning(json.dumps({"action": "rollback", "reason": "no entries"}))
        return
    to_rollback = entries[-count:]
    session_opts = cfg.get("http", {})
    for entry in reversed(to_rollback):
        cam = entry["camera"]
        before = entry["before"]
        host = entry.get("host") or before.get("host")
        username = entry.get("username")
        password = entry.get("password")
        client = get_working_client(host, username, password, session_opts)
        try:
            res = client.restore_network_config(before)
            LOG.info(json.dumps({"camera": cam, "action": "rollback", "result": res}))
        except Exception as e:
            LOG.error(json.dumps({"camera": cam, "action": "rollback_failed", "error": str(e)}))


def main():
    parser = argparse.ArgumentParser(description="Axis Camera IP Automation Agent")
    parser.add_argument("--config", "-c", default="config.yaml", help="Path to config.yaml")
    parser.add_argument("--dry-run", action="store_true", help="Don't apply changes")
    parser.add_argument("--simulate", action="store_true", help="Run in offline simulation mode (no network calls)")
    parser.add_argument("--list-users", action="store_true", help="List users / permissions on target cameras")
    parser.add_argument("--grant-admin", metavar="USER", help="Grant admin rights to USER on all targets")
    parser.add_argument("--check-defaults", action="store_true", help="Scan matrix for default or missing credentials")
    parser.add_argument("--check-defaults-verify", action="store_true", help="Verify default credentials by attempting authentication")
    parser.add_argument("--apply-changes", action="store_true", help="Apply configured password/IP changes from the matrix")
    parser.add_argument("--target", help="Limit apply/listing to a single camera (name or host)")
    parser.add_argument("--rollback", type=int, nargs="?", const=1, help="Rollback last N actions")
    parser.add_argument("--rollback-camera", help="Rollback last action for camera name")
    args = parser.parse_args()

    setup_logging()

    cfg = load_config(args.config)
    if args.rollback or args.rollback_camera:
        rollback(cfg, count=args.rollback or 1, camera_name=args.rollback_camera)
        return

    cameras = load_matrix(cfg.get("matrix_file", "matrix.yaml"))

    def get_working_client(host, username, password, session_opts):
        """Try to create a working AxisClient using http then https."""
        # prefer explicit scheme from session_opts
        timeout = session_opts.get("timeout") if session_opts else None
        for scheme in ("http", "https"):
            try:
                client = AxisClient(host=host, username=username, password=password, timeout=timeout or 10, scheme=scheme)
                # quick probe
                try:
                    client.get_network_config()
                    return client
                except Exception:
                    # try next scheme
                    continue
            except Exception:
                continue
        # fallback to plain http client (will raise on use)
        return AxisClient(host=host, username=username, password=password, timeout=timeout or 10, scheme="http")

    # List users
    if args.list_users:
        session_opts = cfg.get("http", {})
        for cam in cameras:
            name = cam.get("name") or cam.get("host")
            client = AxisClient(host=cam["host"], username=cam.get("username"), password=cam.get("password"), **session_opts)
            try:
                users = client.get_users()
                LOG.info(json.dumps({"camera": name, "action": "list-users", "result": users}))
            except Exception as e:
                LOG.error(json.dumps({"camera": name, "action": "list-users-failed", "error": str(e)}))
        return

    # Check for default/missing credentials
    if args.check_defaults:
        findings = check_default_passwords(cameras, cfg, verify=args.check_defaults_verify, simulate=args.simulate)
        LOG.info(json.dumps({"action": "check-defaults-complete", "count": len(findings)}))
        return

    # Apply configured changes (passwords, static IPs)
    if args.apply_changes:
        session_opts = cfg.get("http", {})
        for cam in cameras:
            name = cam.get("name") or cam.get("host")
            if args.target and args.target not in (name, cam.get("host")):
                continue
            client = AxisClient(host=cam["host"], username=cam.get("username"), password=cam.get("password"), **session_opts)
            try:
                # Set password if requested
                newpw = cam.get("new_password")
                if newpw:
                    if args.dry_run or cfg.get("dry_run", False) or args.simulate:
                        LOG.info(json.dumps({"camera": name, "action": "set-root-password-dryrun", "new_password": "***"}))
                    else:
                        res = client.set_root_password(newpw)
                        LOG.info(json.dumps({"camera": name, "action": "set-root-password", "result": res}))

                # Set static IP if requested
                tip = cam.get("target_ip")
                if tip:
                    netmask = cam.get("netmask", "255.255.255.0")
                    gw = cam.get("gateway")
                    if args.dry_run or cfg.get("dry_run", False) or args.simulate:
                        LOG.info(json.dumps({"camera": name, "action": "set-static-ip-dryrun", "target_ip": tip, "netmask": netmask, "gateway": gw}))
                    else:
                        res = client.set_static_ip(tip, netmask=netmask, gateway=gw)
                        LOG.info(json.dumps({"camera": name, "action": "set-static-ip", "result": res}))
            except Exception as e:
                LOG.error(json.dumps({"camera": name, "action": "apply-changes-failed", "error": str(e)}))
        return

    # Grant admin rights
    if args.grant_admin:
        session_opts = cfg.get("http", {})
        for cam in cameras:
            name = cam.get("name") or cam.get("host")
            client = AxisClient(host=cam["host"], username=cam.get("username"), password=cam.get("password"), **session_opts)
            try:
                if args.dry_run or cfg.get("dry_run", False) or args.simulate:
                    LOG.info(json.dumps({"camera": name, "action": "grant-admin-dryrun", "user": args.grant_admin, "simulate": args.simulate}))
                    continue
                res = client.set_user_admin(args.grant_admin, make_admin=True)
                LOG.info(json.dumps({"camera": name, "action": "grant-admin", "user": args.grant_admin, "result": res}))
            except Exception as e:
                LOG.error(json.dumps({"camera": name, "action": "grant-admin-failed", "user": args.grant_admin, "error": str(e)}))
        return

    apply_changes(cameras, cfg, dry_run=args.dry_run or cfg.get("dry_run", False), simulate=args.simulate)


if __name__ == "__main__":
    main()
