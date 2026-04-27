import numpy as np
import matplotlib.pyplot as plt

# Generate x-values (0, 4π) with 1000 points
x = np.linspace(0, 4 * np.pi, 1000)

# Calculate sine function values
y_sine = np.sin(x)

# Calculate random walk via cumulative sum of normally distributed values added to the initial value
mu = 0
sigma = 1
y_rw = mu + np.cumsum(np.random.normal(mu, sigma, 1000))

# Plot both curves
plt.figure(figsize=(10,6))
plt.plot(x, y_sine, label='Sine function', color='blue')
plt.plot(x, y_rw, label='Random walk', color='red')
plt.legend()
plt.title('Smoothness comparison between sine function and random walk')
plt.savefig('output.png')

# Calculate total variation
total_variation_sine = np.sum(np.abs(np.diff(y_sine)))
total_variation_rw = np.sum(np.abs(np.diff(y_rw)))

print(f'Total Variation Sine: {total_variation_sine}')
print(f'Total Variation Random Walk: {total_variation_rw}')

plt.show()