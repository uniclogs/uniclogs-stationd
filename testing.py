from stationd.py import StationD, Command

#Goal here is to create a pytest that verifies that the command_handler function works:
#If it receives a command_obj which:
#has a valid device, command_handler does not throw err
#has an invalid device (or no devices), command_handler throws err

#Mock command_obj
cmd_obj_null = Command(self, command = None)
cmd_obj_wrong = Command(self, command = 'vvhhff')
cmd_obj_correct = Command(self) #?

"""
class Command:
    def __init__(self, command, sock, addr, num_active_ptt=None):
        self.command = command
        self.sock = sock
        self.addr = addr
        self.num_active_ptt = num_active_ptt
"""

"""
    def command_handler(self, command_obj):
        with self.socket_lock:
            try:
                device = command_obj.command[0].replace('-', '_')
                command_obj.num_active_ptt = self.shared['num_active_ptt']

                if device in ['vhf', 'uhf', 'l_band', 'vu_tx_relay', 'satnogs_host', 'radio_host', 'rotator', 'sdr_b200']:
                    command_parser(getattr(self, device), command_obj)
                    self.shared['num_active_ptt'] = command_obj.num_active_ptt
                elif len(command_obj.command) == 1 and command_obj.command[0] == 'gettemp':
                    read_temp(command_obj, self.pi_cpu)
                else:
                    raise Invalid_Command(command_obj)
            except PTT_Conflict:
                ptt_conflict_response(command_obj)
            except PTT_Cooldown as e:
                ptt_cooldown_response(command_obj, e.seconds)
            except Molly_Guard:
                molly_guard_response(command_obj)
            except Max_PTT:
                molly_guard_response(command_obj)
            except Invalid_Command:
                invalid_command_response(command_obj)
"""
