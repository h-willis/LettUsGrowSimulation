import time
import paho.mqtt.client as mqtt

from bed import Bed

# do not change
HOST = 'ec2-35-177-59-107.eu-west-2.compute.amazonaws.com'
PORT = 16237
USER = 'harry'
PASSWD = 'GLaCcpRG144an4YriV22'

# stores bed information
bed_dict = dict(dict())
top_row = -1

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
    log.write(f"{message.topic}, {value}\n")
    process_message(message.topic, value)

# Extract relevant data from message and place into objects
def process_message(msg, val):
    global top_row

    if 'bed' in msg:
        # test if bed already exists
        # print(f'{msg} {val}')
        bed_col, bed_row = get_bed_column_row(msg)

        # if new bed column, create dict to hold rows in that col
        if bed_col not in bed_dict.keys():
            bed_dict[bed_col] = {}
        # if new bed row inside col create new bed
        if bed_row not in bed_dict[bed_col].keys():
            bed_dict[bed_col][bed_row] = Bed(bed_col, bed_row)
            # update top_row based on highest row seen
            if bed_row > top_row:
                top_row = bed_row


        if 'water_level' in msg:
            # print('wl')
            bed_dict[bed_col][bed_row].water_level = int(val)

        elif 'target_min' in msg:
            # print('tm')
            bed_dict[bed_col][bed_row].target_min = int(val)

        elif 'target_max' in msg:
            # print('tm')
            bed_dict[bed_col][bed_row].target_max = int(val)

        elif 'target' in msg:
            # print('tg')
            bed_dict[bed_col][bed_row].target = val

        elif 'capacity' in  msg:
            # print('cy')
            bed_dict[bed_col][bed_row].capacity = int(val)

        elif 'valve' in msg:
            # print('vl')
            bed_dict[bed_col][bed_row].valve_status = val
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

# extracts bed position regardless of order
# returns converted int for row for ease later on
def get_bed_column_row(str):
    bed_location = str[str.find('-')+1:str.find('-')+3]
    # if flipped (as sometimes happens in medium)
    if(bed_location[0].isdigit()):
        bed_location = f"{bed_location[1]}{bed_location[0]}"
    return bed_location[0], int(bed_location[1])

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


log = open('MessageLog.txt', 'w')

client = init_sim('hard')

# wait one sec after setting mode to ensure restart has completed
time.sleep(2)

# open some valves and what the water flow :)
client.message_callback_add(f"{USER}/#/valve", valve_opened)
set_tank('open')


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


        # get list of colmns and rows for iteration
        columns = list(bed_dict)
        rows = list(bed_dict[columns[0]])
        # ascending order for rows so we start at bottom
        rows.sort()
        # print(rows)
        # create record of draining / filling requests per row
        rows_draining = dict()
        rows_filling = dict()
        total_filling = 0
        total_draining = 0
        for row in rows:
            rows_draining[row] = 0
            rows_filling[row] = 0

        tank_status = True
        sump_status = True


        # 1. assess system state with record of numbers of filling / draining
        # requests on each row
        # 2. decide whether the system needs the tank or sump open or netiher
        # (tank open if there's a bed that can't be filled by a draining bed above)
        # 3. open / close required valves

        # print('measure')
        # 1. Measure System
        # starting at bottom row, assess network status
        for row in rows:
            for column in columns:
                # if a bed is at the right level but valve is open the close the valve
                # if(bed_dict[column][row].isHappy() and bed_dict[column][row].isOpen()):
                # close all valves and only open the ones that need opening
                bed_dict[column][row].setValve('close', client, USER)

                if bed_dict[column][row].needsFilling():
                    rows_filling[row] += 1
                    total_filling += 1
                elif bed_dict[column][row].needsDraining():
                    rows_draining[row] += 1
                    total_draining += 1

        # print('decide')
        # 2. Decide on tank / sump status
        # tank open assessment
        # start at bottom. if bed need filling check rows above for draining
        # start at top, if bed needs draining check rows below for filling
        for row in rows:
            # if filling bed in row
            if rows_filling[row] > 0:
                # print('filling')
                # tank_status = True
                row_test = row + 1
                # check above rows for something draining
                while row_test <= top_row:
                    if rows_draining[row_test] > 0:
                        tank_status = False
                    row_test += 1

        # if draining bed in row
        # reversed rows, start at top
        for row in reversed(rows):
            if rows_draining[row] > 0:
                # print('draining')
                row_test = row - 1
                # sump_status = True
                # check below rows for something filling
                while row_test >= 1:
                    if rows_filling[row_test] > 0:
                        sump_status = False
                    row_test -= 1


        # 3. Control valves based on above decisions with priority given to filling?
        # (priority might have to be draining to prevent overflows?)
        # or even priority could be based on total filling vs draining
        # print('action')
        if tank_status and sump_status:
            # open all valves to drain
            if total_draining > total_filling:
                set_sump('open')
                for row in rows:
                    for column in columns:
                        if bed_dict[column][row].needsDraining():
                            bed_dict[column][row].setValve('open', client, USER)
                        else:
                            bed_dict[column][row].setValve('close', client, USER)
                            # CURRENTLY OPENS ALL VALVES TO DRAIN NOT JUST THE BOTTOM

            #  filling open highest valves
            else:
                set_tank('open')
                # for row in reversed(rows):
                for row in rows:
                    if rows_filling[row] > 0:
                        for column in columns:
                            if bed_dict[column][row].needsFilling():
                                bed_dict[column][row].setValve('open', client, USER)
                            else:
                                bed_dict[column][row].setValve('close', client, USER)
                        # only open top highest of valves
                        break
        
        #  if only tank requested
        elif tank_status:
            set_tank('open')
            # for row in reversed(rows):
            for row in rows:
                if rows_filling[row] > 0:
                    for column in columns:
                        if bed_dict[column][row].needsFilling():
                            bed_dict[column][row].setValve('open', client, USER)
                        else:
                            bed_dict[column][row].setValve('close', client, USER)
                    # only open highest row of valves
                    break

        elif sump_status:
            set_sump('open')
            for row in rows:
                for column in columns:
                    if bed_dict[column][row].needsDraining():
                        bed_dict[column][row].setValve('open', client, USER)
                    else:
                        bed_dict[column][row].setValve('close', client, USER)
                        # CURRENTLY OPENS ALL VALVES TO DRAIN NOT JUST THE BOTTOM

        # this is gunna be the fun part
        # start at top / bottom?
        # start with filling or emptying?
        # start at top opening emptying valves, then rows below opening filling valves.
        # stop when row found that needs filling
        else:
            set_sump('close')
            set_tank('close')
            remaining_rows = -1

            # start by opening top most beds that need emptying
            for row in reversed(rows):
                if rows_draining[row] > 0:
                    # to iterate through all rows beneath
                    remaining_rows = row - 1
                    for column in columns:
                        if bed_dict[column][row].needsDraining():
                            bed_dict[column][row].setValve('open', client, USER)
                        else:
                            bed_dict[column][row].setValve('close', client, USER)
                    break
            # then open the beds on the next closest row that needs filling
            for row in range(remaining_rows, 0, -1):
                if rows_filling[row] > 0:
                    for column in columns:
                        if bed_dict[column][row].needsFilling():
                            bed_dict[column][row].setValve('open', client, USER)
                        else:
                            bed_dict[column][row].setValve('close', client, USER)




        print(f"tank:{tank_status}{total_filling}  sump:{sump_status}{total_draining}")

        # print data out
        for row in reversed(rows):
            for column in columns:
                print(str(bed_dict[column][row]))
            print('--')

        print(i)



except KeyboardInterrupt:
    print("Exiting Sim.")
    client.loop_stop()
    log.close()
