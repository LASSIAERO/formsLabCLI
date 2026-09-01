import json
import sys
from datetime import datetime
import matplotlib.pyplot as plt
from matplotlib.ticker import MaxNLocator

# === Load JSON Data ===
# The TVAC log to plot, named on the command line. This was a hardcoded
# `lab/TVAC.json` relative to the working directory, which only resolved from
# inside the old FORMS checkout.
if len(sys.argv) < 2:
    raise SystemExit(f"usage: python {sys.argv[0]} <tvac-log.json>")

with open(sys.argv[1], "r") as file:
    data = json.load(file)

timestamps = [datetime.strptime(entry["timestamp"], "%Y:%m:%d:%H:%M:%S.%f") for entry in data]
elapsed_hours = [(t - timestamps[0]).total_seconds() / 3600 for t in timestamps]

ch1_temp = [entry["CH1"]["T_measured"] for entry in data]
ch2_temp = [entry["CH2"]["T_measured"] for entry in data]
ch1_power = [entry["CH1"]["voltage"] * entry["CH1"]["current"] for entry in data]
ch2_power = [entry["CH2"]["voltage"] * entry["CH2"]["current"] for entry in data]

# === Calculate Ramp-up Time ===
threshold = 219.5
ramp_index = next(i for i, (t1, t2) in enumerate(zip(ch1_temp, ch2_temp)) if t1 >= threshold and t2 >= threshold)
ramp_time_seconds = (timestamps[ramp_index] - timestamps[0]).total_seconds()
ramp_minutes = ramp_time_seconds / 60

# === Plot Settings ===
plt.rcParams["font.family"] = "Garamond"
fig, ax1 = plt.subplots(figsize=(7, 4))

burnt_orange = "#CC5500"
deep_iris = "#32174D"

# === Temperature Trends ===
ax1.plot(elapsed_hours, ch1_temp, label="+Y Temperature", color=burnt_orange, linewidth=1.2)
ax1.plot(elapsed_hours, ch2_temp, label="-Y Temperature", linestyle='dotted', color=burnt_orange, linewidth=1.2)
ax1.set_ylabel("Temperature (K)", fontsize=12)
ax1.set_ylim(130, 230)
ax1.yaxis.set_major_locator(MaxNLocator(integer=True))

# === Grid ===
ax1.grid(True, linestyle='--', linewidth=0.5, color="black")

# === Power Trends (Secondary Y Axis) ===
ax2 = ax1.twinx()
ax2.plot(elapsed_hours, ch1_power, label="+Y Power", color=deep_iris, linewidth=1)
ax2.plot(elapsed_hours, ch2_power, label="-Y Power", linestyle='dotted', color=deep_iris, linewidth=1)
ax2.set_ylabel("Power (W)", fontsize=12)
ax2.set_ylim(0, 55)
ax2.yaxis.set_major_locator(MaxNLocator(integer=True))

# === X-axis ===
ax1.set_xlabel("Time [hr]", fontsize=12)

# === Title with Ramp-up Time ===
plt.title("Test Shroud Heater PI Controller\n220K Umbra Target", fontsize=13)

# === Legend (Bottom Right) ===
handles1, labels1 = ax1.get_legend_handles_labels()
handles2, labels2 = ax2.get_legend_handles_labels()
fig.legend(handles1 + handles2, labels1 + labels2, loc='lower right', fontsize=10)

# === Final Layout ===
plt.tight_layout()
plt.show()
