import json
from datetime import datetime
import matplotlib.pyplot as plt
from matplotlib.ticker import MaxNLocator
import numpy as np

# === Load JSON Data ===
with open("lab/TVAC.json", "r") as file:
    data = json.load(file)

timestamps = [datetime.strptime(entry["timestamp"], "%Y:%m:%d:%H:%M:%S.%f") for entry in data]
ch1_temp = [entry["CH1"]["T_measured"] for entry in data]
ch2_temp = [entry["CH2"]["T_measured"] for entry in data]

# === Compute ramp-up time for each threshold ===
thresholds = np.linspace(134, 220, 200)
ramp_times_min = []

for th in thresholds:
    try:
        i = next(i for i, (t1, t2) in enumerate(zip(ch1_temp, ch2_temp)) if t1 >= th and t2 >= th)
        delta_t = (timestamps[i] - timestamps[0]).total_seconds()
        ramp_times_min.append(delta_t / 60)  # in minutes
    except StopIteration:
        ramp_times_min.append(np.nan)

# === Compute annotated threshold times ===
annotate_points = [200, 216, 218, 219, 220]
annotate_times = {}
for th in annotate_points:
    try:
        i = next(i for i, (t1, t2) in enumerate(zip(ch1_temp, ch2_temp)) if t1 >= th and t2 >= th)
        delta_t = (timestamps[i] - timestamps[0]).total_seconds()
        annotate_times[th] = delta_t / 60  # in minutes
    except StopIteration:
        annotate_times[th] = np.nan

# === Plot ===
burnt_orange = "#CC5500"
deep_iris = "#32174D"

fig, ax = plt.subplots(figsize=(6.5, 4))
ax.plot(thresholds, ramp_times_min, color=burnt_orange, linewidth=1.5)  # Burnt orange curve

# Labels and scale
ax.set_xlabel("Threshold Temperature [K]", fontsize=12)
ax.set_ylabel("Ramp-up Time [min]", fontsize=12)
ax.set_yscale("symlog", linthresh=5)
ax.yaxis.set_major_locator(MaxNLocator(integer=True))
ax.grid(True, linestyle='--', linewidth=0.5, color="black")
ax.set_title("Ramp-up Time vs Threshold Temperature", fontsize=13)

# Annotate selected thresholds in deep iris
for th, tmin in annotate_times.items():
    if not np.isnan(tmin):
        ax.plot(th, tmin, 'o', color=deep_iris)
        ax.text(th + 0.6, tmin, f"{tmin:.1f} min", fontsize=9, va='bottom', ha='left', color=deep_iris)


plt.tight_layout()
plt.show()
