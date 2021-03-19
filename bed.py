
# create object for each bed and try to develop some logic for the beds to know
# where they can draw or dump to

class Bed:
    def __init__(self, row, column):
        self.row = row
        self.col = column
        self.target = None
        self.target_min = -1
        self.target_max = -1
        self.water_level = -1
        self.valve_status = None
        self.capacity = -1
        # whether or not the bed is at the right level
        self.happy = False

    def __str__(self):
        # return(f"{self.row}{self.col}, Level:{self.current_level}, Targ:{self.target}, Valve:{self.valve_status}, Happy:{self.happy}")
        return "{}{}: Level:{}, Targ:{}, FillMin:{}, Valve:{}, Happy:{}" \
        .format(self.row, self.col, self.water_level, self.target, self.target_min, self.valve_status, self.isHappy())

    def setValve(self, state, client, user):
        if state == 'open':
            client.publish(f"{user}/bed-{self.row}{self.col}/valve/set", 'open')
        elif state == 'close':
            client.publish(f"{user}/bed-{self.row}{self.col}/valve/set", 'close')

    # returns if bed has correct level
    def isHappy(self):
        return ((self.target == 'Fill') and (self.water_level > self.target_min)) or \
               ((self.target == 'Empty') and (self.water_level == 0))
