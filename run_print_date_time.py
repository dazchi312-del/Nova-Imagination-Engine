# Define a function to get current date and time
def get_current_datetime():
    # Import the required modules
    import datetime
    
    # Get the current date and time
    current_datetime = datetime.datetime.now()
    
    # Return the current date and time as a string
    return str(current_datetime)

# Call the defined function to execute it
if __name__ == "__main__":
    print(get_current_datetime())