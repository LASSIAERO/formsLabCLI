from skyfield.api import load, EarthSatellite

# Load TLE data
stations_url = 'http://celestrak.com/NORAD/elements/stations.txt'
satellites = load.tle_file(stations_url)
by_name = {sat.name: sat for sat in satellites}
iss = by_name['ISS (ZARYA)']

# Get current time
ts = load.timescale()
t = ts.now()

# Compute position and velocity in ECI frame
geocentric = iss.at(t)
position = geocentric.position.km  # ECI position vector in kilometers
velocity = geocentric.velocity.km_per_s  # ECI velocity vector in km/s

print("ECI Position (km):", position)
print("ECI Velocity (km/s):", velocity)
