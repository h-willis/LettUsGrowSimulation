import time
import paho.mqtt.client as mqtt

from bed import Bed

# do not change
HOST = 'ec2-35-177-59-107.eu-west-2.compute.amazonaws.com'
PORT = 16237
USER = 'harry'
PASSWD = 'GLaCcpRG144an4YriV22'

# stores bed information in 2d dictionary by [col][row]
bed_dict = dict(dict())
# stores highest row seen
top_row = -1

# tank and sump information
tank_open = False
sump_open = False
tank_level = 0

# score info
score = 0
score_max = 0
score_perc = 0

# ------------------
# SIMULULATION SETUP
# ------------------

def on_connect(client, userdata, flags, rc):
    """
    Callback to confirm connection
    # if you dont see a "connection successfull" message. email chelsee imediatly
    # becuase this should definatly work
    """
    print("Connection Succesful")

def message_recieved(client, userdata, message):
    """
    Callback when a message is received. Message logged and passed to processing
    message function to extract relevant data
    """
    value = message.payload.decode()
    log.write(f"{message.topic}, {value}\n")
    process_message(message.topic, value)

def valve_opened(client, userdata, message):
    """
    Confirmation of valve changing state. Should be used to confirm changing state
    in a real system
    """
    value = message.payload.decode()
    print(f'\nvalve {message.topic} successfully set to {value}\n')

def mode_set(client, userdata, message):
    """
    Confirmation of simulation mode changing state and therefore resetting
    """
    value = message.payload.decode()
    print(f'\nmode successfully set to {value}\n')

def init_sim(diff):
    """
    Takes the requested difficulty and configures the MQTT client.
    Parameters:
    diff(str) : requested difficulty. Either easy, medium or hard
    Returns:
    client(obj) : Configured MQTT client
    """
    client = mqtt.Client()
    client.username_pw_set(USER, PASSWD)
    client.on_connect = on_connect
    client.connect(HOST, PORT, keepalive=60)
    client.loop_start()

    client.subscribe(f'{USER}/#')
    client.message_callback_add(f"{USER}/#", message_recieved)
    client.message_callback_add(f"{USER}/meta/mode", mode_set)
    # open some valves and what the water flow :)
    client.message_callback_add(f"{USER}/#/valve", valve_opened)

    # calling set mode restarts the simulation
    client.publish(f"{USER}/meta/mode/set", diff)
    return client


# ------------------
# MESSAGE PROCESSING
# -----------------------
def process_message(msg, val):
    """
    Extracts relevant bed and meta data for use by the simulation. Also updates
    the bed dictionary with all new seen beds.
    Parameters:
    msg(str) : MQTT topic
    val(str) : Value associated with MQTT topic
    """
    if 'bed' in msg:
        # get which bed is in msg
        bed_col, bed_row = get_bed_column_row_from_string(msg)

        check_bed_exists_create_if_not(bed_col, bed_row)
        update_top_row(bed_row)

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

def get_bed_column_row_from_string(str):
    """
    Extracts the beds column and row from a message containing 'bed'
    Tests if column / row is in correct order as sometimes they would be reversed
    Converts bed row to integer
    Parameters:
    str(str) : string containing the word 'bed'
    Returns:
    bed_location[0](str) : the bed column
    bed_location[1](int) : the bed row
    """
    bed_location = str[str.find('-')+1:str.find('-')+3]
    # if flipped (as sometimes happens in medium)
    if(bed_location[0].isdigit()):
        bed_location = f"{bed_location[1]}{bed_location[0]}"
    return bed_location[0], int(bed_location[1])

def check_bed_exists_create_if_not(bed_col, bed_row):
    """
    Tests the bed dictionary for if a bed exists at the col, row supplied
    Creates a bed object at that location if it doesn't already exist
    Parameters:
    bed_col(str) : column of bed to test
    bed_row(int) : row of bed to test
    """
    # if new bed column, create dict to hold rows in that col
    if bed_col not in bed_dict.keys():
        bed_dict[bed_col] = {}
    # if new bed row inside col create new bed
    if bed_row not in bed_dict[bed_col].keys():
        bed_dict[bed_col][bed_row] = Bed(bed_col, bed_row)

def update_top_row(row):
    """
    Tests and updates top_row with the highest row seen
    Parameters:
    row(int) : row to test
    """
    # not massively happy with this global
    global top_row
    # update top_row based on highest row seen
    if row > top_row:
        top_row = row

# -------------------------------
# SIMULATION CONTROL AND ANALYSIS
# -------------------------------
def reset_and_measure_system_state(columns, rows):
    """
    Closes all valves and gets a record of how many beds in each row are draining
    or filling as well as a total number of draining / filling beds
    Parameters:
    columns(list<str>) : list of all bed columns in system
    rows(list<int>)    : list of all bed rows in system
    Returns:
    rows_filling(dict<int, int>) : beds filling where key is row and val is number
    total_filling(int) : total number of beds filling across system
    rows_draining(dict<int, int>): beds draining where key is row and val is number
    total_draining(int): total number of beds draining across system
    """
    rows_draining = dict()
    rows_filling = dict()
    total_filling = 0
    total_draining = 0

    for row in rows:
        rows_filling[row] = 0
        rows_draining[row] = 0
        for column in columns:
            # close all valves and only open the ones that need opening later
            bed_dict[column][row].setValve('close', client, USER)

            if bed_dict[column][row].needsFilling():
                rows_filling[row] += 1
                total_filling += 1
            elif bed_dict[column][row].needsDraining():
                rows_draining[row] += 1
                total_draining += 1

    return rows_filling, total_filling, rows_draining, total_draining

def open_lowest_row_draining_valves(columns, rows, beds_draining):
    """
    Searches bottom up for beds that need draining and opens the lowest row
    Parameters:
    columns(list<str>) : list of all columns in system
    rows(list<int>) : list of all rows in system
    beds_draining(dict<int, int>) : stores row by row draining requests
    """
    for row in rows:
        if beds_draining[row] > 0:
            for column in columns:
                if bed_dict[column][row].needsDraining():
                    bed_dict[column][row].setValve('open', client, USER)
                else:
                    bed_dict[column][row].setValve('close', client, USER)
            break

def open_highest_row_filling_valves(columns, rows, beds_filling):
    """
    Searches top down for beds that need draining and opens the highest row
    Parameters:
    columns(list<str>) : list of all columns in system
    rows(list<int>) : list of all rows in system
    beds_filling(dict<int, int>) : stores row by row filling requests
    """
    for row in reversed(rows):
        if beds_filling[row] > 0:
            for column in columns:
                if bed_dict[column][row].needsFilling():
                    bed_dict[column][row].setValve('open', client, USER)
                else:
                    bed_dict[column][row].setValve('close', client, USER)
            # only open highest row of valves
            break

def open_fill_valves_in_row(columns, highest_fill_row):
    for column in columns:
        if bed_dict[column][highest_fill_row].needsFilling():
            bed_dict[column][highest_fill_row].setValve('open', client, USER)
        else:
            bed_dict[column][highest_fill_row].setValve('close', client, USER)

def open_drain_valves_in_row(columns, highest_drain_row):
    for column in columns:
        if bed_dict[column][highest_drain_row].needsDraining():
            bed_dict[column][highest_drain_row].setValve('open', client, USER)
        else:
            bed_dict[column][highest_drain_row].setValve('close', client, USER)

def get_cols_rows_from_dict():
    """
    Gets all current rows and columns from the bed_dict. Sorts rows in ascending
    order for easily going from top to bottom / bottom to top later on
    Returns:
    columns(list<str>) : list of all columns in system
    rows(list<int>)    : list of all rows in system
    """
    # get list of columns and rows for iteration
    columns = list(bed_dict)
    rows = list(bed_dict[columns[0]])
    # ascending order for rows so we start at bottom
    rows.sort()
    return columns, rows

def check_available_filling_beds(rows, beds_filling, threshold):
    """
    Figures out if the tank is needed to fill a bed. The tank is needed when a bed
    needs filling that doesn't have a bed that needs draining above it. The
    idea is to efficiently use water by moving it between beds when possible
    rather than using the tank.
    Parameters:
    rows(list<int>) : list of rows in the system
    beds_filling(dict<int, int>) : row by row filling beds
    threshold(int) : controls when to balance beds. Required for faster filling
                        to begin with so not constantly re balancing beds.
    Returns:
    tank_status(bool) : T if a bed exists that can't be filled by another bed
                        F other
    """
    tank_status = True
    for row in rows:
        # if beds more than threshold need filling
        if beds_filling[row] > threshold:
            row_test = row + 1
            # check above rows for something draining
            while row_test <= top_row:
                # if beds above are draining then tank isn't needed and beds can
                # be filled from other draining beds
                if beds_draining[row_test] > threshold:
                    tank_status = False
                row_test += 1
    return tank_status

def check_available_draining_beds(rows, beds_draining, threshold):
    """
    Figures out if the sump is needed to drain a bed. The sump is needed when
    a bed needs draining that doesn't have a bed that needs filling below it.
    The idea is to efficiently use water by moving it between beds when possible
    rather than using the sump.
    Parameters:
    rows(list<int>) : list of rows in the system
    beds_filling(dict<int, int>) : row by row draining beds
    threshold(int) : controls when to balance beds. Required for faster filling
                        to begin with so not constantly re balancing beds.
    Returns:
    sump_status(bool) : T if a bed exists that can't be drained into another bed
                        F other
    """
    # start at top, if bed needs draining check rows below for filling
    for row in reversed(rows):
        # if beds more than threshold need draining
        if beds_draining[row] > threshold:
            # print('draining')
            row_test = row - 1
            # sump_status = True
            # check below rows for something filling
            while row_test >= 1:
                if beds_filling[row_test] > threshold:
                    sump_status = False
                row_test -= 1

def calculate_threshold(loop_idx, difficulty):
    """
    A threshold is needed to speed up filling when more rows are involved so
    that we're not constantly balancing. decreases from 5 -> 0 as loops go on and
    network fills up. Only required in hard mode.
    Parameters:
    loop_idx(int) : a measure of how far in the simulation is
    difficulty(str) : simulation difficulty setting
    """
    if(difficulty != 'hard'):
        return 0
    threshold = 5 - int(loop_idx / 25)
    if threshold < 0:
        threshold = 0
    return threshold

def drain_from_top_to_fill_bottom(rows, beds_draining, beds_filling):
    """
    We get here when the tank and sump are not needed. Open the highest row that
    has draining beds in it and store that row. Then open the lowest row that needs
    filling.
    Parameters:
    rows(list<int>) : all rows in system
    beds_draining(dict<int, int>) : row by row draining beds
    beds_filling(dict<int, int>) : row by row filling beds
    """
    remaining_rows = 0

    # start by opening top most beds that need emptying
    for row in reversed(rows):
        if beds_draining[row] > 0:
            # to iterate through all rows up to row beneath
            remaining_rows = row - 1
            for column in columns:
                if bed_dict[column][row].needsDraining():
                    bed_dict[column][row].setValve('open', client, USER)
                else:
                    bed_dict[column][row].setValve('close', client, USER)
            break

    # then open beds from the bottom that need filling to recylce water from the
    # top
    for row in range(1, remaining_rows+1, 1):
        if beds_filling[row] > 0:
            for column in columns:
                if bed_dict[column][row].needsFilling():
                    bed_dict[column][row].setValve('open', client, USER)
                else:
                    bed_dict[column][row].setValve('close', client, USER)
            break

def set_tank(state):
    """
    Sets tank to requested state and updates tank_open to correct state.
    If requested state is open and the sump is open, close the sump.
    Prints error message if state is invalid
    Parameters:
    state(str) : requested state, either open or close
    """
    global tank_open
    if state == 'open':
        tank_open = True
        client.publish(f"{USER}/tank/valve/set", 'open')
        if sump_open:
            set_sump('close')
    elif state == 'close':
        tank_open = False
        client.publish(f"{USER}/tank/valve/set", 'close')
    else:
        print(f"Requested tank state:  {state}  is unrecognised.")

def set_sump(state):
    """
    Sets sump to requested state and updates sump_open to correct state.
    If requested state is open and the tank is open, close the tank.
    Prints error message if state is invalid
    Parameters:
    state(str) : requested state, either open or close
    """
    global sump_open
    if state == 'open':
        sump_open = True
        client.publish(f"{USER}/sump/valve/set", 'open')
        if tank_open:
            set_tank('close')
    elif state == 'close':
        sump_open = False
        client.publish(f"{USER}/sump/valve/set", 'close')
    else:
        print(f"Requested sump state:  {state}  is unrecognised.")

# --------------
# OUPUTTING DATA
# --------------
def print_bed_data(columns, rows):
    """
    Prints bed data top row first to the terminal seperated by '--'
    Parameters:
    columns(list<str>) : all columns in system
    rows(list<int>) : all rows in system
    """
    # print data out
    for row in reversed(rows):
        for column in columns:
            print(str(bed_dict[column][row]))
        print('--')

def print_score_data(score, score_max, score_perc):
    """
    Prints most recent score data to terminal
    Parameters:
    score(int) : Current score
    score_max(int) : Theoretical highest score
    score_perc(int) : Percentage of max score achieved
    """
    print(f"{score}/{score_max}  |  {score_perc}%")

def print_tank_sump_status(tank_open, sump_open, tank_level):
    """
    Outputs current tank / sump state to terminal along with total water remaining
    in tank.
    Parameters:
    tank_open(bool) : current tank open state
    sump_open(bool) : current sump open state
    tank_level(int) : water remaining in tank
    """
    print(f"Tank open: {tank_open}   |   Sump open: {sump_open}   |   Water Remaining: {tank_level}")


# ----------------------------
# ----- START SIMULATION -----
# ----------------------------

# set up logging file to store all received messages for debugging
log = open('MessageLog.txt', 'w')

# set diffuclty and initialised mqtt client
difficulty = 'hard'
client = init_sim(difficulty)

# wait two secs after setting mode to ensure restart has completed
# i found i was missing some beds with 1s sleep so increased to 2
time.sleep(2)

# start with tank open
set_tank('open')

# simulation progress, used for decreasing balancing threshold
loop_idx = 0
# try except loop to break out with keyboard interrupt and safely shut down program
try:
    while True:
        loop_idx+=1
        time.sleep(1)


        # get list of rows and cols for iteration through further down
        columns, rows = get_cols_rows_from_dict()


        # 1. assess system state with numbers of filling / draining
        # requests on each row
        # 2. decide whether the system needs the tank or sump open or netiher
        # (tank open if there's a bed that can't be filled by a draining bed above)
        # 3. open / close required valves



        # 1. Measure System
        beds_filling, total_filling, beds_draining, total_draining = reset_and_measure_system_state(columns, rows)


        # 2. Decide on tank / sump status
        # looks for whether the tank or sump is needed to fill or drain a bed
        # tank: start at bottom. if bed need filling check rows above for draining,
        # sump: then start at top. if bed needs draining check rows below for filling
        highest_fill_rows = [row for row in beds_filling.keys() if beds_filling[row] == max(beds_filling.values())]
        if len(highest_fill_rows) > 1:
            highest_fill_row = max(highest_fill_rows)
        else:
            highest_fill_row = highest_fill_rows[0]
        highest_drain_rows = [row for row in beds_draining.keys() if beds_draining[row] == max(beds_draining.values())]
        if len(highest_drain_rows) > 1:
            highest_drain_row = min(highest_drain_rows)
        else:
            highest_drain_row = highest_drain_rows[0]


        print(f"fill row : {highest_fill_row}")
        print(f"drain row : {highest_drain_row}")

        # if highest fill req row is higher than the highest drain req row then fill that row
        if(beds_filling[highest_fill_row] >= beds_draining[highest_drain_row]):
            set_tank('open')
            open_fill_valves_in_row(columns, highest_fill_row)
        else:
            set_sump('open')
            open_drain_valves_in_row(columns, highest_drain_row)



        threshold = calculate_threshold(loop_idx, difficulty)
        tank_status = check_available_filling_beds(rows, beds_filling, threshold)
        sump_status = check_available_draining_beds(rows, beds_draining, threshold)


        # 3. Control valves based on above decisions
        # if both tank and sump needed go on which has higher request number
        # if tank_status and sump_status:
        #     if total_draining > total_filling:
        #         set_sump('open')
        #         open_lowest_row_draining_valves(columns, rows, beds_draining)
        #
        #     else:
        #         set_tank('open')
        #         open_highest_row_filling_valves(columns, rows, beds_filling)
        #
        #
        # #  if only tank requested
        # elif tank_status:
        #     set_tank('open')
        #     open_highest_row_filling_valves(columns, rows, beds_filling)
        #
        # # if only sump requested
        # elif sump_status:
        #     set_sump('open')
        #     open_lowest_row_draining_valves(columns, rows, beds_draining)
        #
        #
        # # start at top opening draining valves, then rows from bottom opening filling valves.
        # # (if there's a high row to drain with a lower to fill)
        # else:
        #     set_sump('close')
        #     set_tank('close')
        #
        #     drain_from_top_to_fill_bottom(rows, beds_draining, beds_filling)




        # print information out
        print('\n')

        print_bed_data(columns, rows)
        print_score_data(score, score_max, score_perc)
        print_tank_sump_status(tank_open, sump_open, tank_level)

        print(loop_idx)



except KeyboardInterrupt:
    print("Exiting Sim.")
    client.loop_stop()
    log.close()
