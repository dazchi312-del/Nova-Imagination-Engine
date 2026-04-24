import numpy as np
import matplotlib.pyplot as plt
import colorsys

# Function to generate Fibonacci sequence up to n numbers
def fibonacci(n):
    fib_numbers = [0, 1]
    while len(fib_numbers) < n:
        fib_numbers.append(fib_numbers[-1] + fib_numbers[-2])
    return fib_numbers

# Generate first 20 Fibonacci numbers
n = 20
fib_numbers = fibonacci(n)

# Normalize Fibonacci numbers for color mapping (Hue in HSV)
norm_fib = [f / max(fib_numbers) for f in fib_numbers]

# Create a golden spiral
golden_angle = np.pi * (3 - np.sqrt(5))
theta = np.arange(len(fib_numbers)) * golden_angle
r = np.sqrt(np.arange(len(fib_numbers)))
x, y = r * np.cos(theta), r * np.sin(theta)

# Plot with dynamic marker size and color mapped to Fibonacci numbers
plt.figure(figsize=(8, 8))
for i, (fib, x_val, y_val) in enumerate(zip(fib_numbers, x, y)):
    # Map Fibonacci number to HSV color (Hue varies with Fib, Saturation=1, Value=1)
    rgb = colorsys.hsv_to_rgb(norm_fib[i], 1, 1)
    
    # Dynamic marker size based on logarithmic scale of Fibonacci numbers
    max_log = np.log(max(fib_numbers) + 1)
    marker_size = 2 + 4 * np.log(fib + 1) / max_log
    
    plt.plot(x_val, y_val, 'o', color=rgb, markersize=marker_size)

plt.title("Golden Spiral with Fibonacci Sequence")
plt.axis('equal')  # Equal aspect ratio to ensure spiral is not distorted
plt.show()

# Optionally save the figure
# plt.savefig("fibonacci_golden_spiral.png", dpi=200)