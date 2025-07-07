import pyvisa

def find_upv_ip():
    # Create VISA resource manager
    rm = pyvisa.ResourceManager()

    # Scan all connected VISA resources (LAN, USB, GPIB, etc.)
    resources = rm.list_resources()
    print("🔍 Scanning for UPV on LAN...")

    for res in resources:
        try:
            # Attempt to open each resource
            inst = rm.open_resource(res)
            # Query *IDN? to get identification string
            idn = inst.query("*IDN?").strip()

            if "UPV" in idn:
                print(f"✅ Found UPV: {idn}")
                print(f"   VISA Address: {res}")

                # Try to extract IP address if it's a LAN resource
                if res.startswith("TCPIP"):
                    ip = res.split("::")[1]
                    print(f"🌐 UPV IP Address: {ip}")
                    return ip

        except Exception as e:
            continue  # Skip any devices that throw an error

    print("❌ No UPV found.")
    return None

if __name__ == "__main__":
    find_upv_ip()
