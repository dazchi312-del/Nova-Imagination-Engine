import datetime

def main():
    now = datetime.datetime.now()
    print(now.strftime("%Y-%m-%d %H:%M:%S"))

if __name__ == "__main__":
    main()