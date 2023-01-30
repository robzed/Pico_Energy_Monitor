# 
#
#

# Testing 
ENABLE_NETWORK = False
DEBUG_SCANNER_PRINTS = True
REPLACE_SENSOR_WITH_SWITCH = True

# Imports 
from wifi_settings import ssid, password

from machine import Pin, Timer
import time
from rtc import RTC_PCF8563

import collections
if ENABLE_NETWORK:
    import network
    import socket
    
#from picozero import pico_temp_sensor, pico_led
import machine
#import _thread

flashes_per_Wh = 1      # If meter reads '1000 imp/kWh'
power_counter = 0;      # this is in W/h

microseconds_for_1Wh = None        # invalid at start
last_power_time = time.ticks_us()  # invalid at start

# Idea from https://github.com/klaasnicolaas/home-assistant-glow


if ENABLE_NETWORK:

    # Web Server
    # References:
    # https://projects.raspberrypi.org/en/projects/get-started-pico-w/0
    # https://www.petecodes.co.uk/creating-a-basic-raspberry-pi-pico-web-server-using-micropython/

    #import wifi_settings
    def connect():
        #Connect to WLAN
        wlan = network.WLAN(network.STA_IF)
        wlan.active(True)
        wlan.connect(ssid, password)
        while wlan.isconnected() == False:
            print('Waiting for Wi-Fi connection...')
            time.sleep(1)

        ip = wlan.ifconfig()[0]
        print(f'Connected on {ip}')
        return ip

    def open_socket(ip):
        # Open a socket
        address = (ip, 80)
        connection = socket.socket()
        connection.bind(address)
        connection.listen(1)
        return connection

    def webpage(current_power, current_power_average, today_consumption, power_counter):
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
        <title>
            Rob's Power Usage Page
        </title>
        <script>
            function autoRefresh() {{
                window.location = window.location.href;
            }}
            setInterval('autoRefresh()', 991);
        </script>
        </head>
        <body>
        <header><h1>Today</h1></header>
        <p>Current Power is {current_power} W</p>
        <p>Current Power Average is {current_power_average} W</p>
        <p>Total Consumption is {today_consumption} kWh</p>
        <p>Count {power_counter}</p>
        </body>
        </html>
        """
        return str(html)

#
# The I/O pin interrupt
#
def power_interrupt(pin):
    global power_counter
    power_counter += 1
    # @todo: We could time the interval between interrupts here
    # @todo: what happens if the flashes are too quick? We lose interrupts? 
    #        Maybe we need to use the hard function of .irq ??
    global last_power_time
    global microseconds_for_1Wh
    now = time.ticks_us()
    microseconds_for_1Wh = time.ticks_diff(now, last_power_time)
    last_power_time = now
    # 1Wh took microseconds_for_1Wh
    
    
# ePaper display (Pico-ePaper-2.13)
# https://www.waveshare.com/product/pico-epaper-2.13.htm
# https://www.waveshare.com/product/pico-epaper-2.13-b.htm
# https://www.waveshare.com/wiki/Pico-ePaper-2.13-B
# Connections:
#   Vsys, GND
#   GP8 = DC ... 1=data, 0=command
#   GP9 = SPI CS ... chip select active low
#   GP10 = SPI SCK
#   GP11 = SPI MOSI (e-Paper_DIN)
#   GP12 = RST ... External reset (active low)
#   GP13 = ePaper BUSY ... busy status output from ePaper

W_TO_KW = 1000

ONE_SECOND = 1000 * 1000
ONE_MINUTE = 60 * ONE_SECOND
ONE_HOUR = 60 * ONE_MINUTE
ONE_DAY = 24 * ONE_HOUR

DAY_ENTRIES = 31    # every day, plus one (intervals = 30)
MINUTE_ENTRIES = 61 # the last minute, plus one (intervals = 60)

class Power_Measurement:
    
    def __init__(self):
        # the ongoing data
        self.day_logs = [] # collections.deque((), 31)    # every day, plus one (intervals = 30)
        self.minute_logs = [] # collections.deque((), 61) # the last minute, plus one (intervals = 60)
        
        # statistics
        self.current_power = 0
        self.current_power_average = 0
        self.today_consumption = 0
        self.past_7_days_daily_average = 0
        self.past_7_days_consumption = 0
        self.past_30_days_daily_average = 0
        self.past_30_days_consumption = 0
        
        # register the first entry
        current_time = time.ticks_us()
        current_power = power_counter
        
        self.log_day_entry(current_time, current_power)
        self.log_minute_entry(current_time, current_power)
        
        
    def log_day_check(self, current_time, current_power):
        entry = self.day_logs[-1]
        if time.ticks_diff(current_time, entry[0]) > ONE_DAY:
            self.log_day_entry(current_time, current_power)
            
        # update day totals
        
    
    def log_second_check(self, current_time, current_power):
        entry = self.minute_logs[-1]
        if time.ticks_diff(current_time, entry[0]) > ONE_SECOND:
            self.log_minute_entry(current_time, current_power)
            
        # update today data
        
        
        #if len(self.minute_logs) > 1:
        #    start_time, start_power = self.minute_logs[0]
        #    end_time, end_power = self.minute_logs[-1]
        #    duration = time.ticks_diff(end_time, start_time) / ONE_HOUR
        #    self.current_power = (end_power - start_power) / duration
        #    print("--->", end_power-start_power, duration*60*60)
        if microseconds_for_1Wh is not None:
            self.current_power = ONE_HOUR / microseconds_for_1Wh
            # e.g. the 1Wh flash occurs 1 hour apart
            #      -> so that will be 1Wh / 1 hour = 1W
            # e.g. the 1Wh flash occurs 0.1 hour apart (6 minutes apart)
            #      -> so that will be 1Wh / 0.1 hour = 10W
            # e.g. the 1Wh flash ocurs 0.01 hour apart (36 seconds apart)
            #      -> so that will be 1Wh / 0.01 hour = 100W
            #
            # convert microseconds to hours -> hours = microseconds / (1,000,000 * 3600)
            # so since 1 / microseconds / (1000000*3600) = (1000000 * 3600) / microseconds
            #print("1Wh time =", microseconds_for_1Wh/1000000, "seconds")
            
        start_time, start_power = self.day_logs[-1]
        end_time, end_power = self.minute_logs[-1]
        duration = time.ticks_diff(end_time, start_time) / ONE_HOUR
        self.today_consumption = (end_power - start_power) / W_TO_KW    # W/h to kW/h
        #print("====>", duration, end_power, start_power)
        
        if len(self.minute_logs) > 5:
            start_time, start_power = self.minute_logs[-5]
            end_time, end_power = self.minute_logs[-1]
            ticks = end_power - start_power
            time_diff = time.ticks_diff(end_time, start_time)
            if time_diff != 0 and ticks != 0:
                self.current_power_average = ONE_HOUR / (ticks * time_diff)
            
    def log_day_entry(self, current_time, current_power):
        power_ref = (current_time, current_power)
        self.day_logs.append(power_ref)
        
        # limit the number stored
        if len(self.day_logs) > DAY_ENTRIES:
            self.day_logs.pop(0)

        #print('Day logs', self.day_logs)


    def log_minute_entry(self, current_time, current_power):
        power_ref = (current_time, current_power)
        self.minute_logs.append(power_ref)

        # limit the number stored
        if len(self.minute_logs) > ONE_MINUTE:
            self.minute_logs.pop(0)

        #print('Minute logs', self.minute_logs)

    def print_stats(self):
        print("Today")
        print("Current Power", self.current_power, "W");
        print("Current Power Average", self.current_power_average, "W");
        print("Total Consumption", self.today_consumption, "kWh")
        print()
        #print("Past 7 Days")
        #print("Daily Average", self.past_7_days_daily_average, "kWh")
        #print("Total Consumption", self.past_7_days_consumption, "kWh")
        #print()
        #print("Past 30 Days")
        #print("Daily Average", self.past_30_days_daily_average, "kWh")
        #print("Total Consumption", self.past_30_days_consumption, "kWh")
        #print()

    # We could use the PWM, and IRQ or PIO or the other core to measure the pulses
    #
    # https://docs.micropython.org/en/latest/library/machine.Pin.html
    # http://abyz.me.uk/picod/py_picod.html#pwm_read_high_edges
    # https://github.com/raspberrypi/pico-micropython-examples/blob/master/irq/irq.py#L1-L5
    # https://docs.micropython.org/en/latest/reference/isr_rules.html#isr-rules

    def serve(self):
        if ENABLE_NETWORK:
            try:
                ip = connect()
                connection = open_socket(ip)
            except KeyboardInterrupt:
                machine.reset()

            while True:
                client = connection.accept()[0]
                request = client.recv(1024)
                request = str(request)
                #print(request)
                try:
                     request = request.split()[1]
                except IndexError:
                     pass
    #             if request == '/lighton?':
    #                 pico_led.on()
    #                 state = 'ON'
    #             elif request =='/lightoff?':
    #                 pico_led.off()
    #                 state = 'OFF'
    #             temperature = pico_temp_sensor.temp
                html = webpage(self.current_power, self.current_power_average, self.today_consumption, power_counter)
                #print("served", client)
                client.send(html)
                client.close()
                    #time.sleep_ms(10)
        else:
            while True:
                time.sleep_ms(50)
                
    def scanner(self, timer):
#        while True:
#            start_time = time.ticks_us()
            #time.sleep_ms(1000)
            end_time = time.ticks_us()
            current_counter = power_counter

            self.log_second_check(end_time, current_counter)
            self.log_day_check(end_time, current_counter)
            
            if DEBUG_SCANNER_PRINTS:
                self.print_stats()
            
#            delta = time.ticks_diff(end_time, start_time)
#            print("---")
#            print("Power Delta", power_counter, delta)
            #self.log_hour_check(current_counter)
            
    def main(self):
        if REPLACE_SENSOR_WITH_SWITCH:
            power_input = 20
        else:
            power_input = 2
        power_trigger = Pin(power_input, Pin.IN, Pin.PULL_UP)
        power_trigger.irq(power_interrupt, Pin.IRQ_RISING)

        rtc = RTC_PCF8563()
        #rtc.set_if_not_valid()
        rtc.print_time()
    
        timer = Timer()
        timer.init(period=1000, mode=Timer.PERIODIC, callback=self.scanner)

        #second_thread = _thread.start_new_thread(self.scanner, ())
        
        self.serve()
        
        
        
        
Power_Measurement().main()
