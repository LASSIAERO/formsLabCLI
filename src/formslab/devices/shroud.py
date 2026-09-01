# from time import time, sleep
# import json
# from pathlib import Path
# class HeaterController:
#     def __init__(self, psu, forms, channel_map, target_vars,
#                  kp=2.0, ki=0.1, vlim=28.0, clim=2.5,
#                  integrator_clip=100.0, decay_factor=0.95,
#                  log_file="TVAC.json", log_interval=30.0):

#         self.psu = psu
#         self.forms = forms
#         self.channel_map = channel_map
#         self.target_vars = target_vars
#         self.kp = kp
#         self.ki = ki
#         self.vlim = vlim
#         self.clim = clim
#         self.integrator_clip = integrator_clip
#         self.decay_factor = decay_factor
#         self._integral = {name: 0.0 for name in channel_map}
#         self._last_time = time()

#         self.log_file = Path(__file__).parent / log_file
#         self.log_interval = log_interval
#         self._last_log_time = time()

#     def update(self):
#         now = time()
#         dt = now - self._last_time if self._last_time else 1.0
#         self._last_time = now
 
#         # Force log file to same directory as script
#         # print(f"[DEBUG] Time since last log: {now - self._last_log_time:.2f}s (Interval: {self.log_interval}s)")
#         # print(f"[DEBUG] Logging to: {self.log_file.resolve()}")

#         for var_name, ch in self.channel_map.items():
#             T_target = self.forms.dictionary_scalars[self.target_vars[var_name]].value
#             T_measured = self.forms.dictionary_scalars[var_name].value
#             error = T_target - T_measured

#             P = self.kp * error
#             I = self.ki * self._integral[var_name]
#             raw_voltage = P + I
#             voltage = min(max(raw_voltage, 0.0), self.vlim)

#             self.psu.set(ch, voltage, self.clim)
#             sleep(0.5)
#             v_meas, i_meas = self.psu.measure(ch)
#             sleep(0.1)
#             if v_meas is None or i_meas is None:
#                 self.forms.log(f"PSU read returned None on CH{ch}",level='ERROR',component="HeaterController")
#                 v_meas = 0.0
#                 i_meas = 0.0

#             in_CC_mode = abs(i_meas - self.clim) < 0.05
#             saturated = voltage >= self.vlim or (self.psu.safe_lt(v_meas, voltage - 1.0) and in_CC_mode)

#             if saturated:
#                 self._integral[var_name] *= self.decay_factor
#                 note = "CC 🧱"
#             else:
#                 self._integral[var_name] += error * dt
#                 self._integral[var_name] = max(min(self._integral[var_name], self.integrator_clip),
#                                                -self.integrator_clip)
#                 note = "CV ✅"

#         # ✅ LOGGING
#         if now - self._last_log_time >= self.log_interval:
#             self._last_log_time = now
#             log_entry = {"timestamp": self.forms.time.timestamp}

#             for var_name, ch in self.channel_map.items():
#                 T_measured = self.forms.dictionary_scalars[var_name].value
#                 log_entry[var_name] = T_measured
#                 try:
#                     v_meas, i_meas = self.psu.measure(ch)
#                 except Exception as e:
#                     self.forms.log(f"PSU read failed on CH{ch}: {e}", level="WARNING", component="shroud")
#                     v_meas = 0.0
#                     i_meas = 0.0
#                 log_entry[f"CH{ch}"] = {
#                     "T_measured": T_measured,
#                     "voltage": v_meas,
#                     "current": i_meas
#                 }

#             try:
#                 # Ensure directory exists
#                 self.log_file.parent.mkdir(parents=True, exist_ok=True)

#                 if self.log_file.exists():
#                     with self.log_file.open("r+", encoding="utf-8") as f:
#                         try:
#                             data = json.load(f)
#                         except json.JSONDecodeError:
#                             data = []
#                         data.append(log_entry)
#                         f.seek(0)
#                         json.dump(data, f, indent=2)
#                         f.truncate()
#                 else:
#                     with self.log_file.open("w", encoding="utf-8") as f:
#                         json.dump([log_entry], f, indent=2)

#                 self.forms.log(f"Logged TVAC data to {self.log_file.name}", level="INFO", component="shroud")

#             except Exception as e:
#                 self.forms.log(f"Failed to log TVAC data: {e}", level="ERROR", component="shroud")




# shroud.py

from time import time, sleep
import json
from pathlib import Path

from formslab.config import output_dir

class HeaterController:
    """Direct PSU1 heater loop used by TVAC.

    This remains the current exception to the shared PSU-owner model:
    TVAC's heater controller still commands PSU1 directly.
    """
    def __init__(self, psu, forms, channel_map, target_vars,
                 kp=2.0, ki=0.1, vlim=28.0, clim=2.5,
                 integrator_clip=100.0, decay_factor=0.95,
                 log_file="TVAC.json", log_interval=30.0):

        self.psu = psu
        self.forms = forms
        self.channel_map = channel_map
        self.target_vars = target_vars
        self.kp = kp
        self.ki = ki
        self.vlim = vlim
        self.clim = clim
        self.integrator_clip = integrator_clip
        self.decay_factor = decay_factor
        self._integral = {name: 0.0 for name in channel_map}
        self._last_time = time()

        # Run product, not code: into the output directory, never beside the
        # driver. site-packages is read-only on a shared lab machine.
        self.log_file = (Path(log_file) if Path(log_file).is_absolute()
                         else output_dir() / log_file)
        self.log_interval = log_interval
        self._last_log_time = time()

    def update(self):
        now = time()
        dt = now - self._last_time if self._last_time else 1.0
        self._last_time = now

        # --- CONTROL LOOP & SINGLE MEASUREMENT ---
        measured = {}  # cache {ch: (voltage_meas, current_meas)}
        for var_name, ch in self.channel_map.items():
            T_target   = self.forms.dictionary("scalar")[self.target_vars[var_name]].value
            T_measured = self.forms.dictionary("scalar")[var_name].value
            error      = T_target - T_measured

            # PID compute
            P = self.kp * error
            I = self.ki * self._integral[var_name]
            raw_v = P + I
            v_set = min(max(raw_v, 0.0), self.vlim)

            # apply and measure once
            self.psu.set(ch, v_set, self.clim)
            sleep(0.5)
            v_meas, i_meas = self.psu.measure(ch)
            sleep(0.1)

            # sanitize
            if v_meas is None or i_meas is None:
                self.forms.log(f"PSU read returned None on CH{ch}",
                               level='ERROR', component="HeaterController")
                v_meas, i_meas = 0.0, 0.0

            measured[ch] = (v_meas, i_meas)

            # integrator update
            in_cc   = abs(i_meas - self.clim) < 0.05
            sat     = (v_set >= self.vlim) or (self.psu.safe_lt(v_meas, v_set - 1.0) and in_cc)
            if sat:
                self._integral[var_name] *= self.decay_factor
            else:
                self._integral[var_name] += error * dt
                self._integral[var_name] = max(min(self._integral[var_name],
                                                   self.integrator_clip),
                                               -self.integrator_clip)

        # --- LOGGING & TENSOR REGISTRATION ---
        if now - self._last_log_time >= self.log_interval:
            self._last_log_time = now

            # build log entry
            log_entry = {"timestamp": self.forms.time.timestamp}
            for var_name, ch in self.channel_map.items():
                Tm = self.forms.dictionary("scalar")[var_name].value
                v_meas, i_meas = measured[ch]
                log_entry[var_name] = Tm
                log_entry[f"CH{ch}"] = {
                    "T_measured": Tm,
                    "voltage":    v_meas,
                    "current":    i_meas
                }

            # register a 2×2 tensor [[v1,i1],[v2,i2]] sorted by channel
            # assume channel_map has exactly two entries for ch=1,2
            ordered = sorted(measured.items(), key=lambda x: x[0])  # sort by ch
            tensor_value = [[v,i] for _, (v,i) in ordered]
            # Keep PSU1 telemetry resilient even if the registry was rebuilt.
            psu_var = self.forms.get_variable("PSU1") or self.forms.types.tensor(
                "PSU1", overwrite=False
            )
            psu_var.set(tensor_value)
            # write JSON log
            try:
                self.log_file.parent.mkdir(parents=True, exist_ok=True)
                if self.log_file.exists():
                    with open(self.log_file, "r+", encoding="utf-8") as f:
                        try:
                            arr = json.load(f)
                        except json.JSONDecodeError:
                            arr = []
                        arr.append(log_entry)
                        f.seek(0)
                        json.dump(arr, f, indent=2)
                        f.truncate()
                else:
                    with open(self.log_file, "w", encoding="utf-8") as f:
                        json.dump([log_entry], f, indent=2)

                # self.forms.log(f"Logged TVAC data to {self.log_file.name}",
                #                level="INFO", component="shroud")

            except Exception as e:
                self.forms.log(f"Failed to log TVAC data: {e}",
                               level="ERROR", component="shroud")
