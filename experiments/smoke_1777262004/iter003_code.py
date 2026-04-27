import numpy as np
import matplotlib.pyplot as plt

# Generate x values
x = np.linspace(0, 4 * np.pi, 10000)

# Generate sine values
sine_values = np.sin(x)

# Generate random walk values
random_walk_values = np.cumsum(np.random.normal(size=x.size))

# Calculate total variation
total_variation_sine = np.sum(np.abs(np.diff(sine_values)))
total_variation_random_walk = np.sum(np.abs(np.diff(random_walk_values)))

print(f"Total Variation of Sine: {total_variation_sine}")
print(f"Total Variation of Random Walk: {total_variation_random_walk}")

# Plot the curves
plt.figure(figsize=(10, 6))
plt.plot(x, sine_values, label='Sine Function')
plt.plot(x, random_walk_values, label='Random Walk', linestyle='--')
plt.legend()
plt.title('Comparison of Sine Function and Random Walk')
plt.xlabel('x')
plt.ylabel('y')
plt.savefig('output.png')

# Plot the difference between the curves
plt.figure(figsize=(10, 6))
plt.plot(x[1:], np.diff(sine_values), label='Sine Function Difference')
plt.plot(x[1:], np.diff(random_walk_values), label='Random Walk Difference', linestyle='--')
plt.legend()
plt.title('Difference Between Curves (Zoomed)')
plt.xlabel('x')
plt.ylabel('y difference')
plt.savefig('output_difference.png')

# Plot the histogram of differences
plt.figure(figsize=(10, 6))
plt.hist(np.diff(sine_values), bins=50, label='Sine Function Difference', alpha=0.5)
plt.hist(np.diff(random_walk_values), bins=50, label='Random Walk Difference', linestyle='--', alpha=0.5, color='red')
plt.legend()
plt.title('Histogram of Differences (Zoomed)')
plt.xlabel('y difference')
plt.ylabel('Frequency')
plt.savefig('output_histogram.png')

print("Plots saved as output.png, output_difference.png and output_histogram.png")