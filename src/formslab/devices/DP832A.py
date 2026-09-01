# rigoldriver.py

import time
import re
import os
import threading

from formslab.devices.psu_config import resource_for

# --- Backend selector ---
# Set FORMS_PSU_BACKEND=visa to revert to the pyvisa-based driver.
# Default is "serial" (pyserial — no NI-VISA dependency).
_BACKEND = os.environ.get("FORMS_PSU_BACKEND", "serial").strip().lower()


class RigolDriverVISA:
    """Original pyvisa-based driver. Kept for instant revert."""

    def __init__(self, resource):
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
                if self.interface == "RS232":
                    self._flush_rs232()
                else:
                    self.inst.clear()
                return self.inst.query(cmd)
            except Exception:
                if attempt == retry - 1:
                    raise
                time.sleep(0.1)

    def _flush_rs232(self):
        """Drain pending bytes from the RS232 read buffer."""
        saved = self.inst.timeout
        try:
            self.inst.timeout = 50
            while True:
                self.inst.read_bytes(256)
        except Exception:
            pass
        finally:
            self.inst.timeout = saved

    def write(self, cmd):
        self.inst.write(cmd)
        if self.interface == "RS232":
            time.sleep(0.05)

    def clear(self):
        """Flush instrument buffers."""
        try:
            if self.interface == "RS232":
                self._flush_rs232()
            else:
                self.inst.clear()
        except Exception:
            pass

    def reconnect(self):
        import pyvisa
        try:
            self.inst.close()
        except Exception:
            pass
        if self.interface == "RS232":
            try:
                self.rm.close()
            except Exception:
                pass
            self.rm = pyvisa.ResourceManager()
        self.inst = self.rm.open_resource(self.resource)
        self.inst.write_termination = '\n'
        self.inst.read_termination = '\n'
        self.inst.timeout = 5000
        self._handshake()

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

    def parse_floats_3(self, s):
        nums = re.findall(r"[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?", str(s))
        return [float(x) for x in nums[:3]] if len(nums) >= 2 else None


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
        """Extract device path from VISA resource string or use as-is.

        ASRL/dev/psu2::INSTR  ->  /dev/psu2
        /dev/psu2              ->  /dev/psu2
        /dev/ttyUSB0           ->  /dev/ttyUSB0
        """
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
                self._flush_rs232()
                self.ser.write(cmd.encode() + b'\n')
                # DP832A echoes commands over RS232 — skip echo lines
                for _ in range(3):
                    line = self.ser.readline().decode(errors='ignore').strip()
                    if not line:
                        raise TimeoutError(f"No response to {cmd!r}")
                    if line == cmd:
                        continue  # skip echo
                    return line
                raise TimeoutError(f"Only got echo for {cmd!r}")
            except Exception:
                if attempt == retry - 1:
                    raise
                time.sleep(0.1)

    def _flush_rs232(self):
        """Drain pending bytes from the serial read buffer."""
        self.ser.reset_input_buffer()

    def write(self, cmd):
        self.ser.write(cmd.encode() + b'\n')
        time.sleep(0.05)  # let DP832A finish processing before next op

    def clear(self):
        """Flush serial buffers."""
        try:
            self.ser.reset_input_buffer()
        except Exception:
            pass

    def reconnect(self):
        """Reopen the serial port. No ResourceManager to recycle."""
        try:
            self.ser.close()
        except Exception:
            pass
        self.ser = self._serial.Serial(self.device_path, baudrate=9600, timeout=5.0)
        self._handshake()

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

    def parse_floats_3(self, s):
        nums = re.findall(r"[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?", str(s))
        return [float(x) for x in nums[:3]] if len(nums) >= 2 else None


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
            resource = label
        else:
            resource = self._lookup_resource(label)

        self.label = label
        self.resource = resource
        self.driver = driver_for_resource(resource)(resource)
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
        for ch in [1, 2, 3]:
            psu.off(ch)
            psu.set(ch, 0.0, 0.0)
        return psu

    @staticmethod
    def safe_lt(a, b):
        """Return True if a < b, treating None as +inf."""
        if a is None:
            return False
        return a < b

    def idn(self):
        return self.driver.query("*IDN?")

    def _select(self, ch):
        if self._last_channel != ch:
            self.driver.write(f":INST:NSEL {ch}")
            self._last_channel = ch
            time.sleep(0.05)

    def set(self, ch, v, c):
        self._select(ch)
        self.driver.write(f":APPL CH{ch},{v},{c}")

    def setOVCP(self, ch, ovp=None, ocp=None, enable=True):
        self._select(ch)
        state = "ON" if enable else "OFF"

        ovp = ovp if ovp is not None else 0.001
        ocp = ocp if ocp is not None else 0.001

        self.driver.write(f":VOLT:PROT {ovp}")
        self.driver.write(f":VOLT:PROT:STAT CH{ch},{state}")

        self.driver.write(f":CURR:PROT {ocp}")
        self.driver.write(f":CURR:PROT:STAT CH{ch},{state}")

    def read(self, ch):
        self._select(ch)
        res = self.driver.query(":APPL?")
        parts = [t for t in res.split(",") if t.strip()]
        return (
            self.driver.parse_float(parts[0]),
            self.driver.parse_float(parts[1]),
        )

    def measure_all(self, ch: int, retries: int = 3, settle: float = 0.05):
        """
        Atomic measurement for channel ch.
        Returns (V, I, P) or (None, None, None) on failure.
        Uses ':MEAS:ALL? CHn' to avoid state drift between separate queries.
        """
        last_exc = None
        for _ in range(retries):
            try:
                self._select(ch)
                time.sleep(settle)
                resp = self.driver.query(f":MEAS:ALL? CH{ch}")
                vals = self.driver.parse_floats_3(resp)
                if not vals:
                    raise ValueError(f"PARSE: {resp!r}")
                if len(vals) == 2:
                    vals.append(vals[0] * vals[1])
                v, i, p = vals[:3]
                return v, i, p
            except Exception as e:
                last_exc = e
                self.driver.clear()
                time.sleep(0.1)
        print(f"[DP832A] MEAS:ALL failed CH{ch}: {last_exc}")
        return None, None, None

    def measure(self, ch: int, retries: int = 3, settle: float = 0.05):
        v, i, _ = self.measure_all(ch, retries=retries, settle=settle)
        return v, i

    def on(self, ch):
        self.driver.write(f":OUTP CH{ch},ON")

    def off(self, ch):
        self.driver.write(f":OUTP CH{ch},OFF")

    def alloff(self):
        for ch in [1, 2, 3]:
            self.off(ch)

    def close(self):
        self.driver.close()

    def shutdown(self):
        try:
            for ch in [1, 2, 3]:
                self.off(ch)
                self.set(ch, 0.0, 0.0)
            return True
        except Exception as e:
            print(f"[PSU] shutdown failed: {e}")
            return False

    def _reconnect(self):
        self._last_channel = None
        self.driver.reconnect()

    def _query_channel(self, ch):
        """Query a single channel's state. Returns a dict or raises on failure."""
        self._select(ch)
        out = self.driver.query(":OUTP?").strip().upper()
        is_on = out in {"1", "ON"}

        res_raw = ""
        vset = cset = None
        for attempt in range(3):
            res_raw = self.driver.query(":APPL?")
            res = [s.strip() for s in res_raw.split(",") if s.strip()]
            if res_raw.strip().upper() not in {"ON", "OFF"} and len(res) >= 2:
                vset = self.driver.parse_float(res[0], None)
                cset = self.driver.parse_float(res[1], None)
                if vset is not None and cset is not None:
                    break
            if attempt < 2:
                self.driver.clear()
                time.sleep(0.1)
            else:
                print(f"[{self.label}] malformed :APPL? response for CH{ch}: {res_raw!r}")
                raise ValueError(f"Malformed :APPL? response for CH{ch}: {res_raw!r}")

        vmeas = self.driver.parse_float(self.driver.query(":MEAS:VOLT?"), None)
        cmeas = self.driver.parse_float(self.driver.query(":MEAS:CURR?"), None)

        return {
            "on": is_on,
            "vset": vset,
            "cset": cset,
            "vmeas": vmeas,
            "cmeas": cmeas,
        }

    def update(self, channels=(1, 2, 3)):
        """Query the PSU to get the actual current state of each channel, obeying cooldown."""
        with self._lock:
            now = time.time()
            wait_time = self._time + self._cooldown - now
            if wait_time > 0:
                if self._verbose_cooldown:
                    print(f"[{self.label}] Waiting {wait_time:.2f}s for update cooldown...")
                time.sleep(wait_time)

            for ch in channels:
                try:
                    self.state[ch] = self._query_channel(ch)
                except Exception as e:
                    print(f"[{self.label}] CH{ch} query failed: {e}")
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
