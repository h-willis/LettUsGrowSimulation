# stores relevant information for each bed

class Bed:
    """
    Stores relevant metadata for each bed as well as some handy status funcs
    """
    def __init__(self, column, row):
        self.col = column
        self.row = row
        self.target = None
        self.target_min = -1
        self.target_max = -1
        self.water_level = -1
        self.valve_status = None
        self.capacity = -1
        # whether or not the bed is at the right level
        self.happy = False


    def __str__(self):
        """
        Prints some useful information to give a quick display of a beds status
        """
        return "{}{}: Level:{}, Targ:{}, Valve:{}, Happy:{}" \
        .format(self.col, self.row, self.water_level, self.target, self.valve_status, self.isHappy())


    def setValve(self, state, client, user):
        """
        Checks current valve state and sends MQTT message to change to requested
        state if required
        Parameters:
        state: Requested state, 'open' or 'close'
        client: MQTT client to send message through
        user: User deets for MQTT message
        """
        # if valve was asked to open and is currently closed
        if state == 'open' and self.valve_status == 'close':
            client.publish(f"{user}/bed-{self.col}{self.row}/valve/set", 'open')
            self.valve_status = 'open'
        # if valve was asked to close and is currently open
        elif state == 'close' and self.valve_status == 'open':
            client.publish(f"{user}/bed-{self.col}{self.row}/valve/set", 'close')
            self.valve_status = 'close'


    def isHappy(self):
        """
        Returns T/F depending if bed is at correct level for it's target
        """
        return (self.target == 'Fill' and (self.water_level >= self.target_min and self.water_level < self.target_max)) \
               or (self.target == 'Empty' and self.water_level == 0)


    def isOpen(self):
        """
        Returns T/F if valve is open or not
        """
        return self.valve_status == 'open'


    def needsFilling(self):
        """
        Returns T/F if more water is required in this bed
        """
        return self.target == 'Fill' and self.water_level < self.target_min


    def needsDraining(self):
        """
        Returns T/F if water needs removing from bed. Takes into account overfilling
        """
        return (self.target == 'Empty' and self.water_level > 0) or \
               (self.target == 'Fill' and self.water_level > self.target_max)
