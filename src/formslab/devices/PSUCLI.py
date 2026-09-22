
import sys
import time
import re
import os
import threading

from formslab.devices.psu_config import resource_for

# --- Backend selector (shared with DP832A.py) ---
_BACKEND = os.environ.get("FORMS_PSU_BACKEND", "serial").strip().lower()


class RigolDriverVISA:
    """Original pyvisa-based driver. Kept for instant revert."""

    def __init__(self, resource):
        if sys.platform == "win32" and resource.upper().startswith("ASRL"):
            raise RuntimeError("pyvisa RS232 backend not supported on Windows")
        import pyvisa
        self.resource = resource
        self.rm = pyvisa.ResourceManager()
        self.inst = self.rm.open_resource(resource)
        self.inst.write_termination = '\n'
        self.inst.read_termination = '\n'
        self.inst.timeout = 5000
        self.interface = self._detect_interface()
        self._handshake()

    def _detect_interface(self):
        if self.resource.startswith("ASRL"):
            return "RS232"
        elif "USB" in self.resource:
            return "USB"
        elif self.resource.startswith("TCPIP"):
            return "LAN"
        return "UNKNOWN"

    def _handshake(self):
        self.write("SYSTEM:REMOTE")
        idn = self.query("*IDN?")
        if "RIGOL" not in idn:
            raise RuntimeError(f"Invalid IDN: {idn}")

    def query(self, cmd, retry=2):
        for attempt in range(retry):
            try:
                if self.interface != "RS232":
                    self.clear()
                return self.inst.query(cmd)
            except Exception:
                if attempt == retry - 1:
                    raise
                time.sleep(0.1)

    def write(self, cmd):
        self.inst.write(cmd)

    def clear(self):
        """Flush instrument buffers."""
        try:
            self.inst.clear()
        except Exception:
            pass

    def close(self):
        try:
            if self.inst:
                self.inst.close()
            if self.rm:
                self.rm.close()
        except Exception:
            pass

    def parse_float(self, text, default=None):
        try:
            match = re.search(r"[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?", str(text))
            if match:
                return float(match.group(0))
        except Exception:
            pass
        return default


class RigolDriverSerial:
    """pyserial-based driver. No NI-VISA dependency."""

    def __init__(self, resource):
        import serial as _serial
        self._serial = _serial
        self.resource = resource
        self.device_path = self._parse_device_path(resource)
        self.ser = _serial.Serial(self.device_path, baudrate=9600, timeout=5.0)
        self.interface = "RS232"
        self._handshake()

    @staticmethod
    def _parse_device_path(resource):
        """Extract device path from VISA resource string or use as-is."""
        if resource.startswith("ASRL") and "::" in resource:
            return resource[4:resource.index("::")]
        if resource.startswith("/dev/"):
            return resource
        raise ValueError(f"Cannot parse device path from: {resource!r}")

    def _handshake(self):
        self.write("SYSTEM:REMOTE")
        idn = self.query("*IDN?")
        if "RIGOL" not in idn:
            raise RuntimeError(f"Invalid IDN: {idn}")

    def query(self, cmd, retry=2):
        for attempt in range(retry):
            try:
                self.ser.reset_input_buffer()
                self.ser.write(cmd.encode() + b'\n')
                for _ in range(3):
                    line = self.ser.readline().decode(errors='ignore').strip()
                    if not line:
                        raise TimeoutError(f"No response to {cmd!r}")
                    if line == cmd:
                        continue
                    return line
                raise TimeoutError(f"Only got echo for {cmd!r}")
            except Exception:
                if attempt == retry - 1:
                    raise
                time.sleep(0.1)

    def write(self, cmd):
        self.ser.write(cmd.encode() + b'\n')
        time.sleep(0.05)

    def clear(self):
        """Flush serial buffers."""
        try:
            self.ser.reset_input_buffer()
        except Exception:
            pass

    def close(self):
        try:
            if self.ser and self.ser.is_open:
                self.ser.close()
        except Exception:
            pass

    def parse_float(self, text, default=None):
        try:
            match = re.search(r"[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?", str(text))
            if match:
                return float(match.group(0))
        except Exception:
            pass
        return default


# --- Select active driver ---
if _BACKEND == "visa":
    RigolDriver = RigolDriverVISA
else:
    RigolDriver = RigolDriverSerial


def driver_for_resource(resource):
    """Select VISA automatically for native USB/LAN instrument resources."""
    if _BACKEND == "visa" or resource.upper().startswith(("USB", "TCPIP")):
        return RigolDriverVISA
    return RigolDriverSerial


class PSU:
    def __init__(self, label):
        if "::" in label:
            self.resource = label
        else:
            self.resource = self._lookup_resource(label)
        self.driver = None
        self.state = {}
        self._last_channel = None
        self._lock = threading.Lock()
        self._time = 0.0
        self._cooldown = 3.0  # seconds
        self._verbose_cooldown = os.environ.get("FORMS_PSU_VERBOSE_COOLDOWN", "").strip().lower() in {
            "1",
            "true",
            "yes",
            "on",
        }

    def _lookup_resource(self, name):
        return resource_for(name)

    @classmethod
    def configure(cls, label):
        psu = cls(label)
        psu.connect()
        for ch in [1, 2, 3]:
            psu.off(ch)
            psu.set(ch, 0.0, 0.0)
        psu.disconnect()
        return psu

    def connect(self):
        if self.driver:
            self.disconnect()
        self.driver = driver_for_resource(self.resource)(self.resource)

    def disconnect(self):
        """Return front panel to local and close session."""
        if self.driver:
            try:
                self.driver.write("SYSTEM:LOCAL")
            except Exception:
                pass
            self.driver.close()
            self.driver = None

    def _ensure_connected(self):
        if self.driver is None:
            self.connect()

    def idn(self):
        self._ensure_connected()
        return self.driver.query("*IDN?")

    def _select(self, ch):
        self._ensure_connected()
        if self._last_channel != ch:
            self.driver.write(f":INST:NSEL {ch}")
            self._last_channel = ch
            time.sleep(0.05)

    def set(self, ch, v, c):
        self._ensure_connected()
        self._select(ch)
        self.driver.write(f":APPL CH{ch},{v},{c}")

    def setOVCP(self, ch, ovp=None, ocp=None, enable=True):
        self._ensure_connected()
        self._select(ch)
        state = "ON" if enable else "OFF"
        ovp = ovp if ovp is not None else 0.001
        ocp = ocp if ocp is not None else 0.001
        self.driver.write(f":VOLT:PROT {ovp}")
        self.driver.write(f":VOLT:PROT:STAT CH{ch},{state}")
        self.driver.write(f":CURR:PROT {ocp}")
        self.driver.write(f":CURR:PROT:STAT CH{ch},{state}")

    def read(self, ch):
        self._ensure_connected()
        self._select(ch)
        res = self.driver.query(":APPL?")
        parts = [t for t in res.split(",") if t.strip()]
        return (
            self.driver.parse_float(parts[0]),
            self.driver.parse_float(parts[1]),
        )

    def measure(self, ch):
        self._ensure_connected()
        self._select(ch)
        v = self.driver.query(":MEAS:VOLT?")
        c = self.driver.query(":MEAS:CURR?")
        return self.driver.parse_float(v, 0), self.driver.parse_float(c, 0)

    def on(self, ch):
        self._ensure_connected()
        self.driver.write(f":OUTP CH{ch},ON")

    def off(self, ch):
        self._ensure_connected()
        self.driver.write(f":OUTP CH{ch},OFF")

    def alloff(self):
        self._ensure_connected()
        for ch in [1, 2, 3]:
            self.off(ch)

    def shutdown(self):
        self._ensure_connected()
        for ch in [1, 2, 3]:
            self.off(ch)
            self.set(ch, 0.0, 0.0)
            self.setOVCP(ch, enable=False)
        self.update()
        self.disconnect()

    def close(self):
        """Alias for disconnect."""
        self.disconnect()

    def update(self, channels=(1, 2, 3)):
        """Query the PSU to get the actual current state of each channel, obeying cooldown."""
        self._ensure_connected()
        with self._lock:
            now = time.time()
            wait_time = self._time + self._cooldown - now
            if wait_time > 0:
                if self._verbose_cooldown:
                    print(f"[PSU] Waiting {wait_time:.2f}s for update cooldown...")
                time.sleep(wait_time)

            for ch in channels:
                try:
                    self._select(ch)
                    out = self.driver.query(":OUTP?").strip().upper()
                    is_on = out in {"1", "ON"}

                    res_raw = ""
                    vset = cset = None
                    for attempt in range(3):
                        res_raw = self.driver.query(":APPL?")
                        parts = [s.strip() for s in res_raw.split(",") if s.strip()]
                        if res_raw.strip().upper() not in {"ON", "OFF"} and len(parts) >= 2:
                            vset = self.driver.parse_float(parts[0], None)
                            cset = self.driver.parse_float(parts[1], None)
                            if vset is not None and cset is not None:
                                break
                        if attempt < 2:
                            self.driver.clear()
                            time.sleep(0.1)
                        else:
                            print(f"[PSU] malformed :APPL? response for CH{ch}: {res_raw!r}")
                            raise ValueError(f"Malformed :APPL? response for CH{ch}: {res_raw!r}")

                    vmeas = self.driver.parse_float(self.driver.query(":MEAS:VOLT?"), None)
                    cmeas = self.driver.parse_float(self.driver.query(":MEAS:CURR?"), None)

                    self.state[ch] = {
                        "on": is_on,
                        "vset": vset,
                        "cset": cset,
                        "vmeas": vmeas,
                        "cmeas": cmeas,
                    }
                except Exception as e:
                    print(f"[PSU] update failed on CH{ch}: {e}")
                    self.state[ch] = {
                        "on": None,
                        "vset": None,
                        "cset": None,
                        "vmeas": None,
                        "cmeas": None,
                    }
                time.sleep(0.05)

            self._time = time.time()

    def status(self) -> dict:
        self.update()
        return self.state.copy()

    # --- Helper Functions ---
    def safe_lt(self, a, b):
        return isinstance(a, (int, float)) and a < b

    def safe_gt(self, a, b):
        return isinstance(a, (int, float)) and a > b
