import time
import paho.mqtt.client as mqtt

from bed import Bed

# do not change
HOST = 'ec2-35-177-59-107.eu-west-2.compute.amazonaws.com'
PORT = 16237
USER = 'harry'
PASSWD = 'GLaCcpRG144an4YriV22'

# stores bed information
bed_dict = {}


# if you dont see a "connection successfull" message. email chelsee imediatly
# becuase this should definatly work
def on_connect(client, userdata, flags, rc):
    print("Connection Succesful")


def message_recieved(client, userdata, message):
    value = message.payload.decode()
    # print(f'messsage: {message.topic} {value}')
    process_message(message.topic, value)

# Extract relevant data from message and place into objects
def process_message(msg, val):
    if 'bed' in msg:
        # test if bed already exists
        # print(f'{msg} {val}')
        bed_location = get_bed_location(msg)
        if(bed_location not in bed_dict.keys()):
            bed_dict[bed_location] = Bed(bed_location[0], bed_location[1])

        if 'water_level' in msg:
            # print('wl')
            bed_dict[bed_location].water_level = int(val)

        elif 'target_min' in msg:
            # print('tm')
            bed_dict[bed_location].target_min = int(val)

        elif 'target_max' in msg:
            # print('tm')
            bed_dict[bed_location].target_max = int(val)

        elif 'target' in msg:
            # print('tg')
            bed_dict[bed_location].target = val

        elif 'capacity' in  msg:
            # print('cy')
            bed_dict[bed_location].capacity = int(val)

        elif 'valve' in msg:
            # print('vl')
            bed_dict[bed_location].valve_status = val
        else:
            pass


def get_bed_location(str):
    return str[str.find('-')+1:str.find('-')+3]

def valve_opened(client, userdata, message):
    value = message.payload.decode()
    print(f'\nvalve {message.topic} successfully set to {value}\n')


def mode_set(client, userdata, message):
    value = message.payload.decode()
    print(f'\nmode successfully set to {value}\n')

def init_sim(diff):
    client = mqtt.Client()
    client.username_pw_set(USER, PASSWD)
    client.on_connect = on_connect
    client.connect(HOST, PORT, keepalive=60)
    client.loop_start()

    client.subscribe(f'{USER}/#')
    client.message_callback_add(f"{USER}/#", message_recieved)
    client.message_callback_add(f"{USER}/meta/mode", mode_set)

    # calling set mode restarts the simulation
    client.publish(f"{USER}/meta/mode/set", diff)
    # client.publish(f"{USER}/meta/mode/set", 'easy')
    #client.publish(f"{USER}/meta/mode/set", 'medium')
    # client.publish(f"{USER}/meta/mode/set", 'hard')
    return client

client = init_sim('easy')

# wait one sec after setting mode to ensure restart has completed
time.sleep(2)

# open some valves and what the water flow :)
client.message_callback_add(f"{USER}/#/valve", valve_opened)
client.publish(f"{USER}/tank/valve/set", 'open')
client.publish(f"{USER}/sump/valve/set", 'close')
# client.publish(f"{USER}/bed-A1/valve/set", 'open')
# client.publish(f"{USER}/bed-A2/valve/set", 'open')
# client.publish(f"{USER}/bed-B1/valve/set", 'open')
client.publish(f"{USER}/bed-B2/valve/set", 'open')
#client.publish(f"{USER}/bed-A1/valve/set", 'close')

i = 0
try:
    while True:
        i+=1
        time.sleep(1)
        print(i)
        if (i == 10):
            client.publish(f"{USER}/tank/valve/set", 'close')
            # client.publish(f"{USER}/bed-A2/valve/set", 'close')
            # client.publish(f"{USER}/bed-B2/valve/set", 'open')
            client.publish(f"{USER}/bed-A1/valve/set", 'open')
            client.publish(f"{USER}/bed-B1/valve/set", 'open')

        for key, bed in bed_dict.items():
        #     if not bed.happy:
        #         if (bed.target == 'Fill' and (bed.water_level < bed.target_min)):
        #             client.publish(f"{USER}/bed-{key}/valve/set", 'open')
        #         elif (bed.target == 'Fill' and (bed.water_level > bed.target_min) and bed.valve_status == 'open'):
        #             client.publish(f"{USER}/bed-{key}/valve/set", 'close')
            print(str(bed))








except KeyboardInterrupt:
    print("Exiting Sim.")
    client.loop_stop()
