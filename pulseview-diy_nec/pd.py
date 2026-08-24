
import sigrokdecode as srd
from common.srdhelper import bitpack

# 时序参数默认值（单位：ms），可根据常见 NEC 变种调整
DEFAULT_IDLE_TIME = 20.0        # 帧间超时
DEFAULT_AGC_PULSE_MIN = 8.5     # 标准 NEC 为 9 ms
DEFAULT_AGC_PULSE_MAX = 9.5
DEFAULT_LONG_PAUSE_MIN = 4.0    # 标准 NEC 为 4.5 ms
DEFAULT_LONG_PAUSE_MAX = 5.0
DEFAULT_SHORT_PAUSE_MIN = 2.0   # 标准 NEC 为 2.25 ms
DEFAULT_SHORT_PAUSE_MAX = 2.5
DEFAULT_BIT_PULSE_MIN = 0.46    # 标准 NEC 为 0.56 ms
DEFAULT_BIT_PULSE_MAX = 0.66
DEFAULT_ZERO_PAUSE_MIN = 0.46   # 标准 NEC 为 0.56 ms
DEFAULT_ZERO_PAUSE_MAX = 0.66
DEFAULT_ONE_PAUSE_MIN = 1.38    # 标准 NEC 为 1.68 ms
DEFAULT_ONE_PAUSE_MAX = 1.98
DEFAULT_STOP_PULSE_MIN = 0.46   # 标准 NEC 为 0.56 ms
DEFAULT_STOP_PULSE_MAX = 0.66

class SamplerateError(Exception):
    pass

class Pin:
    IR, = range(1)

class Ann:
    AGC_PULSE, LONG_PAUSE, SHORT_PAUSE, BIT_PULSE, ZERO_PAUSE, ONE_PAUSE, \
    LEADER_CODE, REPEAT_CODE, BIT_DATA, HEX_DATA, INV_HEX_DATA, WARN = range(12)

class Decoder(srd.Decoder):
    api_version = 3
    id = 'diy_ir_nec'
    name = 'DIY IR NEC'
    longname = 'DIY IR NEC'
    desc = 'DIY IR NEC'
    license = 'gplv2+'
    inputs = ['logic']
    outputs = []
    tags = ['IR']
    channels = (
        {'id': 'ir', 'name': 'IR', 'desc': 'Data line'},
    )
    options = (
        {'id': 'polarity', 'desc': 'Polarity', 'default': 'active-low',
            'values': ('auto', 'active-low', 'active-high')},
        {'id': 'cd_freq', 'desc': 'Carrier Frequency (Hz, 0=disable)', 'default': 0},
        {'id': 'idle_time', 'desc': 'IDLE Time (20ms)', 'default': DEFAULT_IDLE_TIME},
        {'id': 'agc_pulse_min', 'desc': 'AGC Pulse Min Time (9ms)', 'default': DEFAULT_AGC_PULSE_MIN},
        {'id': 'agc_pulse_max', 'desc': 'AGC Pulse Max Time (ms)', 'default': DEFAULT_AGC_PULSE_MAX},
        {'id': 'long_pause_min', 'desc': 'Long Pause Min Time (4.5ms)', 'default': DEFAULT_LONG_PAUSE_MIN},
        {'id': 'long_pause_max', 'desc': 'Long Pause Max Time (ms)', 'default': DEFAULT_LONG_PAUSE_MAX},
        {'id': 'short_pause_min', 'desc': 'Short Pause Min Time (2.25ms)', 'default': DEFAULT_SHORT_PAUSE_MIN},
        {'id': 'short_pause_max', 'desc': 'Short Pause Max Time (ms)', 'default': DEFAULT_SHORT_PAUSE_MAX},
        {'id': 'bit_pulse_min', 'desc': 'Bit Pulse Min Time (0.56ms)', 'default': DEFAULT_BIT_PULSE_MIN},
        {'id': 'bit_pulse_max', 'desc': 'Bit Pulse Max Time (ms)', 'default': DEFAULT_BIT_PULSE_MAX},
        {'id': 'zero_pause_min', 'desc': 'Logic 0 Pause Min Time (0.56ms)', 'default': DEFAULT_ZERO_PAUSE_MIN},
        {'id': 'zero_pause_max', 'desc': 'Logic 0 Pause Max Time (ms)', 'default': DEFAULT_ZERO_PAUSE_MAX},
        {'id': 'one_pause_min', 'desc': 'Logic 1 Pause Min Time (1.68ms)', 'default': DEFAULT_ONE_PAUSE_MIN},
        {'id': 'one_pause_max', 'desc': 'Logic 1 Pause Max Time (ms)', 'default': DEFAULT_ONE_PAUSE_MAX},
    )
    annotations = (
        ('agc-pulse', 'AGC Pulse'),
        ('long-pause', 'Long Pause'),
        ('short-pause', 'Short Pause'),
        ('bit-pulse', 'Bit Pulse'),
        ('zero-pause', 'Zero Pause'),
        ('one-pause', 'One Pause'),
        ('leader-code', 'Leader code'),
        ('repeat-code', 'Repeat code'),
        ('bit-data', 'Bit Data'),
        ('hex-data', 'Hex Data'),
        ('inv-hex-data', 'Inv Hex Data'),
        ('warning', 'Warning'),
    )
    annotation_rows = (
        ('bits', 'Bits', (Ann.AGC_PULSE, Ann.LONG_PAUSE, Ann.SHORT_PAUSE, Ann.BIT_PULSE, Ann.ZERO_PAUSE, Ann.ONE_PAUSE)),
        ('fields', 'Fields', (Ann.LEADER_CODE, Ann.REPEAT_CODE, Ann.BIT_DATA)),
        ('hex_data', 'Hex_Data', (Ann.HEX_DATA,)),
        ('inv_hex_data', 'Inv_Hex_Data', (Ann.INV_HEX_DATA,)),
        ('warnings', 'Warnings', (Ann.WARN,)),
    )

    def __init__(self):
        self.reset()

    def reset(self):
        self.state = 'IDLE'
        self.start_agc = self.start_data = self.start_bit = self.start_byte = 0
        self.arr_data = []

    def start(self):
        self.out_ann = self.register(srd.OUTPUT_ANN)

    def metadata(self, key, value):
        if key == srd.SRD_CONF_SAMPLERATE:
            self.samplerate = value

    def calc_rate(self):
        def ms_to_samples(ms):
            return int(self.samplerate * float(ms) / 1000.0) - 1

        self.idle_to = ms_to_samples(self.options['idle_time'])

        self.agc_min = ms_to_samples(self.options['agc_pulse_min'])
        self.agc_max = ms_to_samples(self.options['agc_pulse_max'])

        self.long_min = ms_to_samples(self.options['long_pause_min'])
        self.long_max = ms_to_samples(self.options['long_pause_max'])

        self.short_min = ms_to_samples(self.options['short_pause_min'])
        self.short_max = ms_to_samples(self.options['short_pause_max'])

        self.bit_min = ms_to_samples(self.options['bit_pulse_min'])
        self.bit_max = ms_to_samples(self.options['bit_pulse_max'])

        self.zero_min = ms_to_samples(self.options['zero_pause_min'])
        self.zero_max = ms_to_samples(self.options['zero_pause_max'])

        self.one_min = ms_to_samples(self.options['one_pause_min'])
        self.one_max = ms_to_samples(self.options['one_pause_max'])

    def in_range(self, val, min_val, max_val):
        return (val >= min_val and val <= max_val)

    def put_warn(self, ss, data):
        self.put(ss, self.samplenum, self.out_ann, 
                [Ann.WARN, ['{:x}'.format(data)]])

    def decode(self):
        if not self.samplerate:
            raise SamplerateError('Cannot decode without samplerate.')
        self.calc_rate()

        cd_count = None
        if self.options['cd_freq']:
            cd_count = int(self.samplerate / self.options['cd_freq']) + 1
        prev_ir = None

        if self.options['polarity'] == 'auto':
            curr_level, = self.wait({'skip': 0})
            active = 1 - curr_level
        else:
            active = 0 if self.options['polarity'] == 'active-low' else 1

        prev_point = 0
        pause_width = 0
        pulse_width = 0
        while True:
            if cd_count:
                (cur_ir,) = self.wait([{Pin.IR: 'e'}, {'skip': cd_count}])
                if self.matched[0]:
                    cur_ir = active
                if cur_ir == prev_ir:
                    continue
                prev_ir = cur_ir
                self.ir = cur_ir
            else:
                (self.ir,) = self.wait({Pin.IR: 'e'})

            if self.ir != active:
                pulse_width = self.samplenum - prev_point
                # self.put(prev_point, self.samplenum, self.out_ann, 
                #     [Ann.HEX_DATA, ['{:d}'.format(pulse_width)]])
            else:
                pause_width = self.samplenum - prev_point
                # self.put(prev_point, self.samplenum, self.out_ann, 
                #     [Ann.INV_HEX_DATA, ['{:d}'.format(pause_width)]])

            if self.state == 'IDLE':
                if self.in_range(pulse_width, self.agc_min, self.agc_max):
                    self.put(prev_point, self.samplenum, self.out_ann, 
                            [Ann.AGC_PULSE, ['AGC Pulse', 'AGC', 'A']])
                    self.start_agc = prev_point
                    self.state = 'LRC'
            elif self.state == 'LRC':
                if self.in_range(pause_width, self.long_min, self.long_max):
                    self.put(prev_point, self.samplenum, self.out_ann, 
                            [Ann.LONG_PAUSE, ['Long Pause', 'LP', 'L']])
                    self.put(self.start_agc, self.samplenum, self.out_ann, 
                            [Ann.LEADER_CODE, ['Leader Code ', 'LC', 'L']])
                    self.start_data = self.samplenum
                    self.start_byte = self.samplenum
                    self.state = 'DATA'
                elif self.in_range(pause_width, self.short_min, self.short_max):
                    self.put(prev_point, self.samplenum, self.out_ann, 
                            [Ann.SHORT_PAUSE, ['Short Pause', 'SP', 'S']])
                    self.put(self.start_agc, self.samplenum, self.out_ann, 
                            [Ann.REPEAT_CODE, ['Repeat Code ', 'LC', 'L']])
                    self.start_data = self.samplenum
                    self.start_byte = self.samplenum
                    self.state = 'DATA'
            elif self.state == 'DATA':
                if self.ir != active:
                    if self.in_range(pulse_width, self.bit_min, self.bit_max):
                        self.put(prev_point, self.samplenum, self.out_ann, 
                                [Ann.BIT_PULSE, ['Bit Pulse', 'BP', 'B']])
                        self.start_bit = prev_point
                else:
                    if pause_width >= self.idle_to:
                        self.reset()

                    if self.in_range(pause_width, self.one_min, self.one_max):
                        self.put(prev_point, self.samplenum, self.out_ann, 
                                [Ann.ONE_PAUSE, ['One Pause', 'OP', '1']])
                        self.put(self.start_bit, self.samplenum, self.out_ann, 
                                [Ann.BIT_DATA, ['1']])
                        tmp_bit = 1
                        self.arr_data.append(tmp_bit)
                    elif self.in_range(pause_width, self.zero_min, self.zero_max):
                        self.put(prev_point, self.samplenum, self.out_ann, 
                                [Ann.ZERO_PAUSE, ['Zero Pause', 'ZP', '0']])
                        self.put(self.start_bit, self.samplenum, self.out_ann, 
                                [Ann.BIT_DATA, ['0']])
                        tmp_bit = 0
                        self.arr_data.append(tmp_bit)

                    if len(self.arr_data) == 8:
                        tmp_hex = bitpack(self.arr_data)
                        tmp_inv_arr = [1 - b for b in self.arr_data]
                        tmp_inv_hex = bitpack(tmp_inv_arr)
                        self.put(self.start_byte, self.samplenum, self.out_ann, 
                                [Ann.HEX_DATA, ['{:02X}'.format(tmp_hex)]])
                        self.put(self.start_byte, self.samplenum, self.out_ann, 
                                [Ann.INV_HEX_DATA, ['{:02X}'.format(tmp_inv_hex)]])
                        self.arr_data = []
                        self.start_byte = self.samplenum

            prev_point = self.samplenum
