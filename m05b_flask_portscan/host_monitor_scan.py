import subprocess
from datetime import datetime, timedelta
from time import sleep
import socket
import requests
import scapy.all as scapy
import nmap


MONITOR_INTERVAL = 60
DISCOVERY_INTERVAL = 600
PORTSCAN_INTERVAL = 3600


def get_hosts():

    print("\n\n----> Retrieving hosts ...", end="")
    response = requests.get("http://127.0.0.1:5000/hosts")
    if response.status_code != 200:
        print(f" !!!  Failed to retrieve hosts from server: {response.reason}")
        return {}

    print(" Hosts successfully retrieved")
    return response.json()


def discovery():

    # DISCOVER HOSTS ON NETWORK USING ARPING FUNCTION
    print(
        "\n\n----- Discovery hosts on network using arping() function ---------------------"
    )
    ans, unans = scapy.arping("192.168.254.0/24")
    ans.summary()

    existing_hosts = get_hosts()
    for res in ans.res:

        print(f"oooo> IP address discovered: {res[0].payload.pdst}")

        ip_addr = res[1].payload.psrc
        mac_addr = res[1].payload.hwsrc
        try:
            hostname = socket.gethostbyaddr(str(ip_addr))
        except (socket.error, socket.gaierror):
            hostname = (str(ip_addr), [], [str(ip_addr)])
        last_heard = str(datetime.now())[:-3]

        if hostname[0] in existing_hosts:
            continue

        host = {
            "ip": ip_addr,
            "mac": mac_addr,
            "hostname": hostname[0],
            "last_heard": last_heard,
            "availability": True,
            "open_tcp_ports": []
        }
        update_host(host)


def update_host(host):

    print(f"----> Updating host status via REST API: {host['hostname']}", end="")
    rsp = requests.put("http://127.0.0.1:5000/hosts", params={"hostname": host["hostname"]}, json=host)
    if rsp.status_code != 204:
        print(
            f"{str(datetime.now())[:-3]}: Error posting to /hosts, response: {rsp.status_code}, {rsp.content}"
        )
        print(f" !!!  Unsuccessful attempt to update host status via REST API: {host['hostname']}")
    else:
        print(f" Successfully updated host status via REST API: {host['hostname']}")


def ping_host(host):

    try:
        print(f"----> Pinging host: {host['hostname']}", end="")
        ping_output = subprocess.check_output(
            ["ping", "-c3", "-n", "-i0.5", "-W2", host["ip"]]
        )
        host["availability"] = True
        host["last_heard"] = str(datetime.now())[:-3]
        print(f" Host ping successful: {host['hostname']}")

    except subprocess.CalledProcessError:
        host["availability"] = False
        print(f" !!!  Host ping failed: {host['hostname']}")


def portscan_hosts(hosts):

    for _, host in hosts.items():

        if "availability" not in host or not host["availability"]:
            continue

        ip = host["ip"]

        print(f"====> Scanning host: {host['hostname']} at IP: {host['ip']}")
        nm = nmap.PortScanner()
        nm.scan(ip, '22-1024')

        try:
            nm[ip]
        except KeyError as e:
            print(f" !!!  Scan failed: {e}")
            continue

        print(f"===> Scan results: {nm[ip].all_tcp()}")
        host["open_tcp_ports"] = nm[ip].all_tcp()
        update_host(host)


def main():

    last_discovery = datetime.now()-timedelta(days=1)
    last_portscan = datetime.now()-timedelta(days=1)

    while True:

        if (datetime.now() - last_discovery).total_seconds() > DISCOVERY_INTERVAL:
            discovery()
            last_discovery = datetime.now()

        hosts = get_hosts()

        if (datetime.now() - last_portscan).total_seconds() > PORTSCAN_INTERVAL:
            portscan_hosts(hosts)
            last_portscan = datetime.now()

        for _, host in hosts.items():
            ping_host(host)
            update_host(host)

        sleep(MONITOR_INTERVAL)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nExiting host-monitor")
        exit()
