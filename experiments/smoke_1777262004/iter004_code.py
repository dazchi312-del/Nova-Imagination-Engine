import numpy as np
from scipy import integrate
import matplotlib.pyplot as plt

# Generate sine values
x = np.linspace(0, 4*np.pi, 10000)
sine_values = np.sin(x)

# Generate random walk values
random_walk_values = np.cumsum(np.random.normal(size=10000))

# Calculate total variation using numerical integration
total_variation_sine = integrate.trapz(np.abs(sine_values[1:] - sine_values[:-1]), x[1:])

print(f"Total Variation of Sine Function: {total_variation_sine}")

# Calculate total variation of random walk using numerical integration
total_variation_random_walk = integrate.trapz(np.abs(random_walk_values[1:] - random_walk_values[:-1]), x[1:])

print(f"Total Variation of Random Walk: {total_variation_random_walk}")

# Plot both curves
plt.plot(x, sine_values, label="Sine Function")
plt.plot(x, random_walk_values, label="Random Walk")

plt.title("Smoothness Comparison")
plt.xlabel("x")
plt.ylabel("y")
plt.legend()
plt.savefig("output.png")

print(f"Plot saved as output.png")