import numpy as np
import matplotlib.pyplot as plt

# Generate x values for sine function and random walk
x_sine = np.linspace(0, 4 * np.pi, 10000)
x_walk = np.arange(1, 10001)

# Calculate sine function values
y_sine = np.sin(x_sine)

# Generate random walk values
np.random.seed(0)  # For reproducibility
random_walk_values = np.cumsum(np.random.normal(size=10000))

# Plot both curves
plt.figure(figsize=(10, 6))
plt.plot(x_sine, y_sine, label='Sine function', color='blue')
plt.plot(x_walk[:-1], random_walk_values, label='Random walk', color='red')

# Calculate total variation for both curves
total_variation_sine = np.sum(np.abs(np.diff(y_sine)))
total_variation_random = np.sum(np.abs(np.diff(random_walk_values)))

print(f'Total Variation of Sine Function: {total_variation_sine:.2f}')
print(f'Total Variation of Random Walk: {total_variation_random:.2f}')

# Save plot as output.png
plt.legend()
plt.savefig('output.png')

plt.show()