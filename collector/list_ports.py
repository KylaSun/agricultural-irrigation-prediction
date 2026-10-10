try:
    from serial.tools import list_ports
except ImportError:
    raise SystemExit("pyserial is not installed")

ports = list(list_ports.comports())
if not ports:
    print("No serial ports detected.")
for port in ports:
    print(f"{port.device}\t{port.description}\t{port.hwid}")
