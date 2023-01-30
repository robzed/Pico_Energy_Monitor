from machine import Pin, I2C
import time

class RTC_PCF8563:
    def __init__(self):
        self.i2c = I2C(0, scl=Pin(5), sda=Pin(4), freq=100000)
        self.days_text = ["Sun", "Mon", "Tue", "Wed", "Thurs", "Fri", "Sat"]
        
        #print(self.i2c.scan())
    def from_bcd(self, value):
        return (value >> 4) * 10 + (value & 0x0F)
    
    def to_bcd(self, value):
        return ((value // 10) << 4) + (value % 10)
    
    def to_bcd_byte(self, value: int):
        value = self.to_bcd(value)
        return value.to_bytes(1, "big")
    
    def write_byte_to_bcd_register(self, register, value):
        self.i2c.writeto_mem(81, register, self.to_bcd_byte(value))
        
    #def get_bcd_register(register, mask):
    #    value = self.i2c.readfrom_mem(81, 2, 1)[0]
    #    value &= mask
    #    return self.from_bcd(value)
        
    def get_time(self):
        seconds = self.i2c.readfrom_mem(81, 2, 1)[0]
        valid = seconds < 128
        seconds = self.from_bcd(seconds & 0x7F)
        minutes = self.from_bcd(self.i2c.readfrom_mem(81, 3, 1)[0] & 0x7F)
        hours = self.from_bcd(self.i2c.readfrom_mem(81, 4, 1)[0] & 0x3F)
        days = self.from_bcd(self.i2c.readfrom_mem(81, 5, 1)[0] & 0x3F)
        weekdays = self.i2c.readfrom_mem(81, 6, 1)[0] & 0x07
        century_months = self.i2c.readfrom_mem(81, 7, 1)[0]
        century = century_months >> 7
        month = self.from_bcd(century_months & 0x1F)
        years = self.from_bcd(self.i2c.readfrom_mem(81, 8, 1)[0])
        years += (100*(century+19))

        #print("%d/%d/%d %d:%d:%d (%s) %d" % (years, month, days, hours, minutes, seconds, repr(valid), weekdays))
        return (years, month, days, hours, minutes, seconds, valid, weekdays)

    def print_time(self):
        (years, month, days, hours, minutes, seconds, valid, weekdays) = self.get_time()
        if valid:
            weekdays = self.days_text[weekdays]
        print("%d/%d/%d %d:%d:%d (%s) %s" % (years, month, days, hours, minutes, seconds, repr(valid), weekdays))
        
    def set_time(self, years, month, days, hours, minutes, seconds, weekdays):
        self.write_byte_to_bcd_register(2, seconds)
        self.write_byte_to_bcd_register(3, minutes)
        self.write_byte_to_bcd_register(4, hours)
        self.write_byte_to_bcd_register(5, days)
        self.write_byte_to_bcd_register(6, weekdays)
        cm = month
        # Always after 200, so set top bit
        cm += 80
        # make years two digits
        years %= 100
        self.write_byte_to_bcd_register(7, cm)
        self.write_byte_to_bcd_register(8, years)
    
    def set_if_not_valid(self):
        (years, month, days, hours, minutes, seconds, valid, days) = self.get_time()
        if not valid:
            now = time.time()
            (year, month, day, hour, minute, second, weekday, yearday) = time.localtime(now)

            print("Setting time - %d:%d:%d" % (hour, minute, second))

            # Python uses 0=Mon, PCF8563 uses 0=Sun
            weekday += 1
            if weekday >= 8:
                weekday = 0
            self.set_time(year, month, day, hour, minute, second, weekday)


# test code
if False:
    rtc = RTC_PCF8563()
    rtc.set_if_not_valid()
    rtc.print_time()

