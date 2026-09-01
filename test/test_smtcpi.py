#!/usr/bin/env python3
import sm_tc

def main():
    # Initialize card (stack ID 0, I²C bus 1)
    tc = sm_tc.SMtc(stack=0, i2c=1)

    # Configure channel 1 for Type T thermocouple
    tc.set_sensor_type(1, 'T')

    # Read temperature from channel 1
    temp = tc.get_temp(1)
    print(f"Channel 1 temperature: {temp:.2f} °C")

if __name__ == "__main__":
    main()
