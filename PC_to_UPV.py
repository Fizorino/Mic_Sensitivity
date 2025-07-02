import pyvisa

# # Connect to UPV via TCP/IP or USB/GPIB
rm = pyvisa.ResourceManager()
# upv = rm.open_resource("TCPIP0::192.168.1.100::inst0::INSTR")

resources = rm.list_resources()
print("Available instruments:", resources)
