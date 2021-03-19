import time



sorttest = ['A2', 'B1', 'B2', 'A1', 'A63', 'B3', 'C1']
sorttest.sort()
for thing in sorttest:
    print(thing)

try:
    while True:
        time.sleep(1)
        print("awake")

except KeyboardInterrupt:
    print("done")
