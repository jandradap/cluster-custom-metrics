import os
import json
import openshift_client as oc


def debug(msg):
    print(f"[DEBUG] {msg}")


def main():
    debug("Starting debug script")
    oc_bin = os.getenv("OPENSHIFT_CLIENT_PYTHON_DEFAULT_OC_PATH", "oc")
    debug(f"Setting oc path to {oc_bin}")
    oc.set_default_oc_path(oc_bin)

    try:
        debug("Checking oc client version")
        version = oc.get_client_version()
        debug(f"oc version: {version}")

        debug("Checking current user")
        user = oc.whoami()
        debug(f"oc user: {user}")

        debug("Retrieving namespaces")
        ns_json_str = oc.selector("ns", all_namespaces=True).object_json()
        debug(f"Raw namespace JSON length: {len(ns_json_str)}")
        ns_json = json.loads(ns_json_str)
        items = ns_json.get("items", [])
        debug(f"Found {len(items)} namespaces")
        for item in items:
            name = item.get("metadata", {}).get("name")
            print(name)
    except Exception as exc:
        debug(f"Error executing oc: {exc}")
        raise


if __name__ == "__main__":
    main()
