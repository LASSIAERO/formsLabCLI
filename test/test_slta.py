
#--------------------------sLTS TEST---------------------------------------------------------------------------
import os
import time
import subprocess
import signal
from datetime import datetime
from formslab.devices.DP832A import PSU

# --- Setup ---
os.chdir("/home/sensei/Soft/ltaDaemon")
dp2 = PSU("psu2")

def power_on():
    dp2.set_channel(1, 12.0, 1.50)
    dp2.set_ocp(1,1.75)
    time.sleep(7)
    dp2.output_on(1)
    print("✔️ PSU CH1 ON → 12V 1.50A")
    time.sleep(1)

def power_off():
    dp2.output_off(1)
    print("🔌 PSU CH1 OFF")
    time.sleep(1)

def capture_images(index):
    os.system("./slta_initialization_forms.sh")
    # os.system("./slta_initialization_script.sh")
    os.system(f"./lta.sh 8888 name images/darkness_testJUN20_{index}_")
    os.system("./lta.sh 8888 read")
    print("📷 Read 1 →", datetime.now())
    time.sleep(20)

def run_configure():
    return subprocess.Popen(
        "./configure.exe",
        shell=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )

# --- Main Loop ---
for i in range(1, 2):
    print(f"\n🔁 Loop {i}")
    print("⚡ Powering ON at", datetime.now())
    power_on()
    time.sleep(3)

    print("🚀 Launching configure.exe...")
    process = run_configure()
    time.sleep(20)

    print("⚙️ Running image capture...")
    capture_images(i)

    print("🛑 Killing configure.exe...")
    os.killpg(process.pid, signal.SIGTERM)

    print("🔌 Powering OFF")
    power_off()

print("✅ Test complete.")





