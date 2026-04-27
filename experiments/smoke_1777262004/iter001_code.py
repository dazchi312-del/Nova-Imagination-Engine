import numpy as np
import matplotlib.pyplot as plt

# Generate x values from 0 to 4π with 1000 points
x = np.linspace(0, 4 * np.pi, 1000)

# Calculate y values for sine function and random walk
y_sine = np.sin(x)
y_random_walk = np.cumsum(np.random.normal(size=len(x))) + np.sin(x[0])

# Plot both curves
plt.figure(figsize=(8,6))
plt.plot(x, y_sine, label='Sine Function')
plt.plot(x, y_random_walk, label='Random Walk', linestyle='--')

# Add title and labels
plt.title('Comparison of Sine Function and Random Walk')
plt.xlabel('x')
plt.ylabel('y')
plt.legend()

# Save plot to file
plt.savefig('output.png')

# Calculate total variation for both curves
tv_sine = np.sum(np.abs(np.diff(y_sine)))
tv_random_walk = np.sum(np.abs(np.diff(y_random_walk)))

print(f'Total Variation of Sine Function: {tv_sine}')
print(f'Total Variation of Random Walk: {tv_random_walk}')

# Print ratio of total variations to quantify smoothness
ratio = tv_random_walk / tv_sine
print(f'Smoothness Ratio (Random Walk vs. Sine Function): {ratio:.2f}')