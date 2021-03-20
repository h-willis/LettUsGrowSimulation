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
beds_draining = []
beds_filling  = []
max_row = -1

# tank and sump information
tank_open = False
tank_level = 0
sump_open = False

# score info
score = 0
score_max = 0
score_perc = 0


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

        # if new bed location
        if(bed_location not in bed_dict.keys()):
            if(int(bed_location[1]) > max_row):
                max_row = int(bed_location[1])
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

    elif 'harry/meta' in msg:
        if 'score-%' in msg:
            global score_perc
            score_perc = int(val)

        elif 'score-max' in msg:
            # pass here otherwise the below test for score will also
            # return this msg.
            global score_max
            score_max = int(val)


        elif 'score' in msg:
            global score
            score = int(val)

    elif 'harry/tank/water_level' in msg:
        global tank_level
        tank_level = int(val)

def get_bed_location(str):
    bed_location = str[str.find('-')+1:str.find('-')+3]
    # if flipped (as sometimes happens in medium)
    if(bed_location[0].isdigit()):
        bed_location = f"{bed_location[1]}{bed_location[0]}"
    return bed_location

def valve_opened(client, userdata, message):
    value = message.payload.decode()
    print(f'\nvalve {message.topic} successfully set to {value}\n')

def check_for_rows_below(bed_list, current_row):
    for bed in bed_list:
        # bed[1] is the beds row
        if (int(bed[1]) < current_row):
            return True
    return False

def check_for_rows_above(bed_list, current_row):
    for bed in bed_list:
        if (int(bed[1]) > current_row):
            return True
    return False

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

def set_tank(state):
    global tank_open
    if state == 'open':
        tank_open = True
        client.publish(f"{USER}/tank/valve/set", 'open')
        if sump_open:
            set_sump('close')
    elif state == 'close':
        tank_open = False
        client.publish(f"{USER}/tank/valve/set", 'close')

def set_sump(state):
    global sump_open
    if state == 'open':
        sump_open = True
        client.publish(f"{USER}/sump/valve/set", 'open')
        if tank_open:
            set_tank('close')
    elif state == 'close':
        sump_open = False
        client.publish(f"{USER}/sump/valve/set", 'close')


client = init_sim('easy')

# wait one sec after setting mode to ensure restart has completed
time.sleep(2)

# open some valves and what the water flow :)
client.message_callback_add(f"{USER}/#/valve", valve_opened)
# client.publish(f"{USER}/tank/valve/set", 'open')
set_tank('open')
# client.publish(f"{USER}/sump/valve/set", 'open')
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
        print('\n')
        print(i)
        print(f"{score}/{score_max}  |  {score_perc}%")
        print(f"tank: {tank_open}, sump: {sump_open}  |   Water Remaining: {tank_level}")

        # keeps track of tank / sump requests
        tank_count = 0
        sump_count = 0

        # cycle through all beds
        for key, bed in bed_dict.items():

            if bed.isHappy():                                # if bed is at right level but valve still open
                if bed.isOpen():
                    bed.setValve('close', client, USER)
                if key in beds_draining:
                    beds_draining.remove(key)
                if key in beds_filling:
                    beds_filling.remove(key)
                continue

            elif(bed.needsFilling()):
                if (key not in beds_filling):
                    bed_filling.append(key)

                if(tank_open):
                    bed.setValve('open', client, USER)
                elif(sump_open):
                    bed.setValve('close', client, USER)
                elif(check_for_rows_below(beds_filling, bed.row)):
                    bed.setValve('close', client, USER)
                elif(check_for_rows_above(beds_draining, bed.row)):
                    bed.setValve('open', client, USER)
                elif(bed.row == max_row):
                    bed.setValve('open', client, USER)
                    set_tank('open')

            elif(bed.needsEmptying()):
                if (key not in beds_draining):
                    bed_draining.append(key)

                if(tank_open):
                    bed.setValve('close', client, USER)
                elif(sump_open):
                    bed.setValve('open', client, USER)
                elif(check_for_rows_above(beds_draining, bed.row)):
                    bed.setValve('close', client, USER)
                elif(check_for_rows_below(beds_filling, bed.row)):
                    bed.setValve('open', client, USER)
                elif(bed.row == 1):
                    bed.setValve('open', client, USER)
                    set_sump('open')


            # print deets from each bed
            print(str(bed))









except KeyboardInterrupt:
    print("Exiting Sim.")
    client.loop_stop()
