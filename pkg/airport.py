"""Airport adapter for Mozilla WebThings Gateway."""

import re
import os
from os import path
import sys
import json
import socket
import subprocess

sys.path.append(path.join(path.dirname(path.abspath(__file__)), 'lib'))

from gateway_addon import Database, Adapter, Device, Property

_TIMEOUT = 3

__location__ = os.path.realpath(
    os.path.join(os.getcwd(), os.path.dirname(__file__)))

_CONFIG_PATHS = [
    os.path.join(os.path.expanduser('~'), '.mozilla-iot', 'config'),
]

if 'MOZIOT_HOME' in os.environ:
    _CONFIG_PATHS.insert(0, os.path.join(os.environ['MOZIOT_HOME'], 'config'))



class AirportAdapter(Adapter):
    """Adapter for Airplay"""

    def __init__(self, verbose=True):
        """
        Initialize the object.

        verbose -- whether or not to enable verbose logging
        """
        print("initialising adapter from class")
        
        self.addon_name = 'airport'
        self.name = self.__class__.__name__
        Adapter.__init__(self, self.addon_name, self.addon_name, verbose=verbose)
        #print("Adapter ID = " + self.get_id())

        self.pairing = False
        self.DEBUG = True
        self.running = True
        self.audio = False
        self.video = False
        self.rpiplay_debug = ""


        self.addon_path = os.path.join(os.path.expanduser('~'), '.mozilla-iot', 'addons', self.addon_name)
        self.persistence_file_path = os.path.join(os.path.expanduser('~'), '.mozilla-iot', 'data', self.addon_name,'persistence.json')

        
        # Get audio controls
        self.audio_controls = get_audio_controls()
        print(str(self.audio_controls))


        # Get persistent data
        try:
            with open(self.persistence_file_path) as f:
                self.persistent_data = json.load(f)
                if self.DEBUG:
                    print("Persistent data was loaded succesfully.")
        except:
            print("Could not load persistent data (if you just installed the add-on then this is normal)")
            self.persistent_data = {'audio_output': str(self.audio_controls[0]['human_device_name']) ,'video_audio_output':'analog'}
        
        print("persistent data: " + str(self.persistent_data))


        # SHAIRPORT
        self.shairport_path = os.path.join(self.addon_path, 'shairport', 'shairport')
        self.shairport_library_path = os.path.join(self.addon_path, 'shairport')
        self.shairport_default_conf_path = os.path.join(self.addon_path, 'shairport', 'shairport_default.conf')
        self.shairport_conf_path = os.path.join(self.addon_path, 'shairport', 'shairport.conf')
        self.shairport_start_command = "LD_LIBRARY_PATH='" + self.shairport_library_path + "' "  + self.shairport_path + " -j -c " + self.shairport_conf_path
        print("self.shairport_path = " + self.shairport_path)
        
        
        # RPIPLAY
        self.video_audio_output_options = ['off','analog','hdmi']
        self.rpiplay_path = os.path.join(self.addon_path, 'rpiplay', 'rpiplay')
        self.rpiplay_library_path = os.path.join(self.addon_path, 'rpiplay')
        
        
        # Get hostname
        try:
            self.hostname = str(socket.gethostname())
            self.hostname = self.hostname.title()
        except:
            print("failed to get hostname")
            self.hostname = 'Candle'
                
        
        # Get configuration
        try:
            self.add_from_config()
        except Exception as ex:
            print("Error loading config: " + str(ex))


        # create list of human readable audio-only output options for Shairport-sync
        self.audio_output_options = []
        for option in self.audio_controls:
            self.audio_output_options.append( option['human_device_name'] )


        # Create Airport device
        try:
            #airport_device = AirportDevice(self, self.audio_output_options, self.video_audio_output_options)
            airport_device = AirportDevice(self, self.audio_output_options, self.video_audio_output_options)
            #print(str(airport_device));
            self.handle_device_added( airport_device )
            #if self.DEBUG:
            print("airport device created")

        except Exception as ex:
            print("Could not create airport device: " + str(ex))


        # Start streaming servers
        if self.audio:
            print("Enabling Shairport-sync airplay audio receiver")
            self.set_audio_output(self.persistent_data['audio_output'])

        if self.video:
            print("Enabling RPiPlay airplay video receiver")
            self.set_video_audio_output(str(self.persistent_data['video_audio_output']))



        print("End of Airport adapter init process")



    def unload(self):
        print("Shutting down airport")
        kill_process('shairport')
        kill_process('rpiplay')
        

            
            
    def add_from_config(self):
        """get user configuration."""
        try:
            database = Database('airport')
            if not database.open():
                return

            config = database.load_config()
            database.close()
        except:
            print("Error! Failed to open settings database.")

        if not config:
            print("Error loading config from database")
            return
        
        
        # Debugging
        try:
            if 'Debugging' in config:
                self.DEBUG = bool(config['Debugging'])
                self.rpiplay_debug = " -vv"
                if self.DEBUG:
                    print("Debugging is set to: " + str(self.DEBUG))
            else:
                self.DEBUG = False
                
        except:
            print("Error loading debugging preference")
            
        
        # Audio (for Shairport)
        try:
            if 'Audio' in config:
                self.audio = bool(config['Audio'])
            else:
                print("Audio was not in config")
        except Exception as ex:
            print("Audio config error:" + str(ex))

        
        # Video (for RpiPlay)
        try:
            if 'Video' in config:
                self.video = bool(config['Video'])
            else:
                print("Video was not in config")
        except Exception as ex:
            print("Video config error:" + str(ex))
        
        
        
    def change_shairport_config(self, original,replacement):
        f = open(self.shairport_conf_path,'r')
        filedata = f.read()
        f.close()

        newdata = filedata.replace(original,replacement)

        f = open(self.shairport_conf_path,'w')
        f.write(newdata)
        f.close()
    



    def set_audio_output(self, selection):
        if self.DEBUG:
            print("Setting shairport selection to: " + str(selection))
            
        # Get the latest audio controls
        self.audio_controls = get_audio_controls()
        if self.DEBUG:
            print(self.audio_controls)
        
        try:
            # Kill the old Shairport-sync server
            done = kill_process('shairport')
        
            for option in self.audio_controls:
                if str(option['human_device_name']) == str(selection):
                    if self.DEBUG:
                        print("Changing Shairport audio output")
                    # Set selection in persistence data
                    self.persistent_data['audio_output'] = str(selection)
                    #print("persistent_data is now: " + str(self.persistent_data))
                    self.save_persistent_data()
                    
                    try:
                        # Create a clean default config file to start with
                        os.system('rm ' + self.shairport_conf_path)
                        os.system('cp ' + self.shairport_default_conf_path + ' ' + self.shairport_conf_path)
                
                        self.change_shairport_config('//	output_device = "default";','output_device = "plughw:CARD=' + str(option["simple_card_name"]) + ',DEV=' + str(option["device_id"]) + '";')
                        self.change_shairport_config('//	mixer_control_name = "PCM";','//	mixer_control_name = "' + str(option["control_name"]) + '";')
                    except Exception as ex:
                        print("Error changing shairport settings file:" + str(ex))
        
                    if self.DEBUG:
                        print("new selection on thing: " + str(selection))
                    try:
                        #print("self.devices = " + str(self.devices))
                        if self.devices['airport'] != None:
                            self.devices['airport'].properties['audio output'].update( str(selection) )
                    except Exception as ex:
                        print("Error setting new audio output selection:" + str(ex))
        
            #print("starting shairport")
            os.system(self.shairport_start_command)
        except Exception as ex:
            print("Error in set_audio_output: " + str(ex))
                
        
        

    def set_video_audio_output(self, selection):
        if self.DEBUG:
            print("Setting rpiplay audio output selection to: " + str(selection))
            
        try:
            self.persistent_data['video_audio_output'] = str(selection)
            self.save_persistent_data()
        
            self.rpiplay_start_command = "LD_LIBRARY_PATH='" + self.rpiplay_library_path + "' "  + str(self.rpiplay_path) + str(self.rpiplay_debug) + " -l -a " + str(selection) + " -b auto -n '" + str(self.hostname) + " video' &" 
            if self.DEBUG:
                print("rpiplay_start_command = " + self.rpiplay_start_command)
            
            try:
                # Kill the old rpiplay server
                done = kill_process('rpiplay')
        
                # start the new rpiplay server
                print("starting rpiplay")
                #run_command( self.rpiplay_start_command )
                os.system(self.rpiplay_start_command)
                
            except Exception as ex:
                print("Error restarting rpiplay:" + str(ex))
            
               
            try:
                if self.devices['airport'] != None:
                    self.devices['airport'].properties['video audio output'].update( str(selection) )
            except Exception as ex:
                print("Error setting new video audio output selection:" + str(ex))
        
        except Exception as ex:
            print("Error in set_audio_output: " + str(ex))
        
        
        
        

    def save_persistent_data(self):
        if self.DEBUG:
            print("Saving to persistence data store: " + str(self.persistent_data))

        try:
            if not os.path.isfile(self.persistence_file_path):
                open(self.persistence_file_path, 'a').close()
                if self.DEBUG:
                    print("Created an empty persistence file")
            else:
                if self.DEBUG:
                    print("Persistence file existed. Will try to save to it.")

            with open(self.persistence_file_path) as f:
                #if self.DEBUG:
                #    print("saving: " + str(self.persistent_data))
                json.dump( self.persistent_data, open( self.persistence_file_path, 'w+' ) )
                print("saved")
                return True
            #self.previous_persistent_data = self.persistent_data.copy()

        except Exception as ex:
            print("Error: could not store data in persistent store: " + str(ex) )
            return False



    def remove_thing(self, device_id):
        try:
            obj = self.get_device(device_id)
            self.handle_device_removed(obj)                     # Remove from device dictionary
            if self.DEBUG:
                print("User removed Airport device")
        except:
            print("Could not remove thing from devices")





#
# DEVICE
#

class AirportDevice(Device):
    """Airport device type."""

    def __init__(self, adapter, audio_output_list, video_audio_output_list):
        """
        Initialize the object.
        adapter -- the Adapter managing this device
        """

        Device.__init__(self, adapter, 'airport')

        self._id = 'airport'
        self.id = 'airport'
        self.adapter = adapter

        self.name = 'Airport'
        self.title = 'Airport'
        self.description = 'Airport streaming'
        #self._type = ['MultiLevelSwitch']
        #self.connected = False

        self.audio_output_list = audio_output_list
        self.video_audio_output_list = video_audio_output_list

        try:
            if self.adapter.audio:
                self.properties["audio output"] = AirportProperty(
                                self,
                                "audio output",
                                {
                                    'label': "Audio-only output",
                                    'type': 'string',
                                    'enum': audio_output_list,
                                },
                                self.adapter.persistent_data['audio_output'])

            if self.adapter.video:
                self.properties["video audio output"] = AirportProperty(
                                self,
                                "video audio output",
                                {
                                    'label': "Video audio output",
                                    'type': 'string',
                                    'enum': video_audio_output_list,
                                },
                                self.adapter.persistent_data['video_audio_output'])


        except Exception as ex:
            print("error adding properties: " + str(ex))

        print("Airport thing has been created.")



#
# PROPERTY
#

class AirportProperty(Property):

    def __init__(self, device, name, description, value):
        Property.__init__(self, device, name, description)
        self.device = device
        self.name = name
        self.title = name
        self.description = description # dictionary
        self.value = value
        self.set_cached_value(value)



    def set_value(self, value):
        print("property: set_value called for " + str(self.title))
        #print("property: set value to: " + str(value))
        try:
            if self.title == 'audio output':
                self.device.adapter.set_audio_output(str(value))
                #self.device.adapter.set_radio_state(True) # If the user changes the station, we also play it.
                #self.update(value)

            if self.title == 'video audio output':
                self.device.adapter.set_video_audio_output(str(value))

            #if self.title == 'power':
            #    self.device.adapter.set_airport_state(bool(value))
                #self.update(value)

            #if self.title == 'volume':
            #    self.device.adapter.set_airport_volume(int(value))
                #self.update(value)

        except Exception as ex:
            print("set_value error: " + str(ex))



    def update(self, value):
        print("property -> update")
        #if value != self.value:
        self.value = value
        self.set_cached_value(value)
        self.device.notify_property_changed(self)







def get_audio_controls():

    audio_controls = []
    
    aplay_result = run_command('aplay -l') 
    lines = aplay_result.splitlines()
    device_id = 0
    previous_card_id = 0
    for line in lines:
        if line.startswith( 'card ' ):
            
            try:
                #print(line)
                line_parts = line.split(',')
            
                line_a = line_parts[0]
                #print(line_a)
                line_b = line_parts[1]
                #print(line_b)
            except:
                continue
            
            card_id = int(line_a[5])
            #print("card id = " + str(card_id))
            
            
            if card_id != previous_card_id:
                device_id = 0
            
            #print("device id = " + str(device_id))
            
            
            simple_card_name = re.findall(r"\:([^']+)\[", line_a)[0]
            simple_card_name = str(simple_card_name).strip()
            
            #print("simple card name = " + str(simple_card_name))
            
            full_card_name   = re.findall(r"\[([^']+)\]", line_a)[0]
            #print("full card name = " + str(full_card_name))
            
            full_device_name = re.findall(r"\[([^']+)\]", line_b)[0]
            #print("full device name = " + str(full_device_name))
            
            human_device_name = str(full_device_name)
            
            # Raspberry Pi 4
            human_device_name = human_device_name.replace("bcm2835 ALSA","Built-in headphone jack")
            human_device_name = human_device_name.replace("bcm2835 IEC958/HDMI","Built-in video")
            human_device_name = human_device_name.replace("bcm2835 IEC958/HDMI1","Built-in video two")
            
            # Raspberry Pi 3
            human_device_name = human_device_name.replace("bcm2835 Headphones","Built-in headphone jack")
            
            # ReSpeaker dual microphone pi hat
            human_device_name = human_device_name.replace("bcm2835-i2s-wm8960-hifi wm8960-hifi-0","ReSpeaker headphone jack")
            #print("human device name = " + human_device_name)
            
            
            control_name = 'none'
            amixer_result = run_command('amixer -c ' + str(card_id) + ' scontrols') 
            lines = amixer_result.splitlines()
            if len(lines) > 0:
                for line in lines:
                    if "'" in line:
                        #print("line = " + line)
                        control_name = re.findall(r"'([^']+)'", line)[0]
                        #print("control name = " + control_name)
                        if control_name is not 'mic':
                            break
                        else:
                            continue # in case the first control is 'mic', ignore it.
                    else:
                        control_name = 'none'
                
            if control_name is 'mic':
                control_name = 'none'
            
            audio_controls.append({'card_id':card_id, 'device_id':device_id, 'simple_card_name':simple_card_name, 'full_card_name':str(full_card_name), 'full_device_name':str(full_device_name), 'human_device_name':str(human_device_name), 'control_name':str(control_name)}) # ,'controls':lines


            if card_id == previous_card_id:
                device_id += 1
            
            previous_card_id = card_id

    return audio_controls



def kill_process(target):
    try:
        os.system( "sudo killall " + str(target) )
        print(str(target) + " stopped")
        return True
    except:
        print("Error stopping " + str(target))
        return False
    


def run_command(cmd, timeout_seconds=20):
    try:
        
        p = subprocess.run(cmd, timeout=timeout_seconds, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True, universal_newlines=True)

        if p.returncode == 0:
            return p.stdout  + '\n' + "Command success" #.decode('utf-8')
            #yield("Command success")
        else:
            if p.stderr:
                return "Error: " + str(p.stderr)  + '\n' + "Command failed"   #.decode('utf-8'))

    except Exception as e:
        print("Error running command: "  + str(e))
        