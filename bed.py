
# create object for each bed and try to develop some logic for the beds to know
# where they can draw or dump to

class Bed:
    def __init__(self, column, row):
        self.col = column
        self.row = row
        self.target = None
        self.target_min = -1
        self.target_max = -1
        self.water_level = -1
        self.valve_status = None
        self.capacity = -1
        # self.target = 'Fill'
        # self.target_min = 20
        # self.target_max = 30
        # self.water_level = 0
        # self.valve_status = 'close'
        # self.capacity = 100
        # whether or not the bed is at the right level
        self.happy = False

    def __str__(self):
        # return(f"{self.row}{self.col}, Level:{self.current_level}, Targ:{self.target}, Valve:{self.valve_status}, Happy:{self.happy}")
        return "{}{}: Level:{}, Targ:{}, FillMin:{}, Valve:{}, Happy:{}" \
        .format(self.col, self.row, self.water_level, self.target, self.target_min, self.valve_status, self.isHappy())

    def setValve(self, state, client, user):
        # if valve was asked to open and is currently closed
        if state == 'open' and self.valve_status == 'close':
            client.publish(f"{user}/bed-{self.row}{self.col}/valve/set", 'open')
        # if valve was asked to close and is currently open
        elif state == 'close' and self.valve_status == 'open':
            client.publish(f"{user}/bed-{self.row}{self.col}/valve/set", 'close')

    # returns if bed has correct level
    def isHappy(self):
        return (self.target == 'Fill' and (self.water_level >= self.target_min and self.water_level < self.target_max)) \
               or (self.target == 'Empty' and self.water_level == 0)

    def isOpen(self):
        return self.valve_status == 'open'

    def needsFilling(self):
        return self.target == 'Fill' and self.water_level < self.target_min

    def needsEmptying(self):
        return (self.target == 'Empty' and self.water_level > 0) \
                or (self.target == 'Fill' and self.water_level > self.water_max)
